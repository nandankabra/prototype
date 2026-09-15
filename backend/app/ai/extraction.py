"""Text-layer extraction first; genuine OCR fallback, never invented uploaded content."""
from abc import ABC, abstractmethod
from functools import lru_cache
from pathlib import Path
import re
import unicodedata
import pymupdf as fitz
from PIL import Image
from app.core.config import settings

PATTERNS = {
    'GSTIN': r'\b\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]\b',
    'PAN': r'(?<![A-Z0-9])[A-Z]{5}\d{4}[A-Z](?![A-Z0-9])',
    'UDYAM': r'\bUDYAM-[A-Z]{2}-\d{2}-\d{7}\b',
    'CIN': r'\b[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b',
}
LABELS = {'company_name': 'Company Name', 'address': 'Address', 'registration_date': 'Registration Date',
          'expiry_date': 'Valid Until|Expiry Date', 'certificate_number': 'Certificate Number',
          'local_content': 'Local Content', 'financial_value': 'Annual Turnover',
          'EPFO': 'EPFO', 'ESIC': 'ESIC', 'STARTUP_INDIA': 'Startup ID', 'NSIC': 'NSIC',
          'DIGILOCKER': 'DigiLocker', 'OEM': 'OEM ID'}


def valid_pan(value: str) -> bool:
    return re.fullmatch(PATTERNS['PAN'], value) is not None


def valid_gstin(value: str) -> bool:
    """Structural validation only; a valid shape does not establish source validity."""
    return re.fullmatch(PATTERNS['GSTIN'], value) is not None and 1 <= int(value[:2]) <= 38


class EntityExtractor(ABC):
    @abstractmethod
    def extract(self, pages: list[dict]) -> list[dict]: ...


class RegexEntityExtractor(EntityExtractor):
    def extract(self, pages):
        entities = []
        for page in pages:
            text = page['text']
            patterns = {**PATTERNS, **{kind: rf'(?:{label})\s*:\s*([^\n]+)' for kind, label in LABELS.items()}}
            for kind, pattern in patterns.items():
                for match in re.finditer(pattern, text, re.IGNORECASE):
                    value = (match.group(1) if kind in LABELS else match.group()).strip()
                    line = next((line for line in text.splitlines() if value in line), value)
                    box = next((block['bbox'] for block in page.get('blocks', []) if value in block.get('text', '')), [])
                    entities.append({'type': kind, 'value': value,
                                     'normalized_value': unicodedata.normalize('NFKC', value).strip().upper() if kind in PATTERNS else value,
                                     'confidence': min(page.get('confidence', 0.95), 0.99),
                                     'source_page': page['page_number'], 'source_text': line[:1000], 'bounding_box': box})
        return entities


@lru_cache(maxsize=1)
def spacy_model():
    import spacy
    return spacy.load('en_core_web_sm')


class SpacyEntityExtractor(EntityExtractor):
    def extract(self, pages):
        result = RegexEntityExtractor().extract(pages)
        try:
            for page in pages:
                for ent in spacy_model()(page['text']).ents:
                    if ent.label_ in {'ORG', 'GPE'}:
                        result.append({'type': 'company_name' if ent.label_ == 'ORG' else 'address',
                                       'value': ent.text, 'normalized_value': ent.text, 'confidence': 0.8,
                                       'source_page': page['page_number'], 'source_text': ent.sent.text, 'bounding_box': []})
        except (ImportError, OSError):
            pass
        return result


@lru_cache(maxsize=1)
def transformer_model():
    from transformers import pipeline
    return pipeline('token-classification', model='dslim/bert-base-NER', aggregation_strategy='simple', local_files_only=True)


class TransformerEntityExtractor(EntityExtractor):
    def extract(self, pages):
        result = RegexEntityExtractor().extract(pages)
        try:
            for page in pages:
                for ent in transformer_model()(page['text'][:5000]):
                    if ent['entity_group'] == 'ORG':
                        result.append({'type': 'company_name', 'value': ent['word'], 'normalized_value': ent['word'],
                                       'confidence': float(ent['score']), 'source_page': page['page_number'],
                                       'source_text': page['text'][ent['start']:ent['end']], 'bounding_box': []})
        except Exception:
            pass
        return result


@lru_cache(maxsize=1)
def paddle_engine():
    from paddleocr import PaddleOCR
    return PaddleOCR(use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)


def ocr_image(image: Image.Image) -> tuple[str, float, str, list]:
    import numpy as np
    array = np.array(image.convert('RGB'))
    try:
        import cv2
        gray = cv2.cvtColor(array, cv2.COLOR_RGB2GRAY)
        array = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    except ImportError:
        pass
    if settings.enable_heavy_ml and settings.ocr_provider == 'paddle':
        try:
            outputs = list(paddle_engine().predict(np.array(image.convert('RGB'))))
            texts, scores = [], []
            for output in outputs:
                data = output.json.get('res', output.json)
                texts.extend(data.get('rec_texts', []))
                scores.extend(data.get('rec_scores', []))
            if texts:
                return '\n'.join(texts), float(np.mean(scores)), 'PaddleOCR', []
        except Exception:
            pass
    try:
        import pytesseract
        result = pytesseract.image_to_data(Image.fromarray(array), output_type=pytesseract.Output.DICT, timeout=15)
        words, scores, blocks = [], [], []
        for i, word in enumerate(result['text']):
            if word.strip() and float(result['conf'][i]) >= 0:
                words.append(word)
                scores.append(float(result['conf'][i]) / 100)
                blocks.append({'text': word, 'bbox': [result['left'][i], result['top'][i],
                              result['left'][i]+result['width'][i], result['top'][i]+result['height'][i]]})
        # Preserve line structure for field labels.
        text = pytesseract.image_to_string(Image.fromarray(array), timeout=15)
        if text.strip():
            return text, float(np.mean(scores)) if scores else 0.5, 'Tesseract', blocks
    except Exception:
        pass
    return '', 0, 'No OCR engine available - manual extraction required', []


def parse_document(path: str) -> dict:
    pages, warnings, metadata_warnings = [], [], []
    metadata = {}
    try:
        if Path(path).suffix.lower() == '.pdf':
            with fitz.open(path) as pdf:
                metadata = pdf.metadata
                from datetime import datetime, timezone, timedelta
                creation, modification = metadata.get('creationDate', ''), metadata.get('modDate', '')
                def metadata_date(value):
                    try:
                        return datetime.strptime(value.removeprefix('D:')[:14], '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
                    except ValueError:
                        return None
                created, modified = metadata_date(creation), metadata_date(modification)
                if created and created > datetime.now(timezone.utc) + timedelta(days=1):
                    metadata_warnings.append('PDF creation timestamp is in the future; inspect original provenance')
                if created and modified and modified < created:
                    metadata_warnings.append('PDF modification timestamp precedes creation; inspect original provenance')
                if pdf.is_encrypted:
                    raise ValueError('Encrypted PDF cannot be read')
                if len(pdf) > 50:
                    raise ValueError('PDF exceeds the 50-page processing limit')
                for index, page in enumerate(pdf):
                    text = page.get_text()
                    blocks = [{'bbox': list(b[:4]), 'text': b[4]} for b in page.get_text('blocks') if len(b) > 4]
                    if text.strip():
                        confidence, provider = 0.99, 'PyMuPDF text layer'
                    else:
                        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
                        text, confidence, provider, blocks = ocr_image(Image.frombytes('RGB', [pix.width, pix.height], pix.samples))
                    pages.append({'page_number': index+1, 'text': text, 'confidence': confidence,
                                  'provider': provider, 'blocks': blocks})
        else:
            with Image.open(path) as img:
                if img.width * img.height > 25000000:
                    raise ValueError('Image exceeds 25 megapixel processing limit')
                text, confidence, provider, blocks = ocr_image(img)
                pages.append({'page_number': 1, 'text': text, 'confidence': confidence, 'provider': provider, 'blocks': blocks})
    except Exception as exc:
        warnings.append(f'Document could not be parsed: {type(exc).__name__}. Manual review required.')
    raw_text = '\n'.join(p['text'] for p in pages)
    if not raw_text.strip():
        warnings.append('No readable text. Upload a readable copy; no fields or source matches were invented.')
    return {'raw_text': raw_text, 'normalized_text': unicodedata.normalize('NFKC', raw_text),
            'pages': pages, 'warnings': warnings,
            'ocr_confidence': sum(p['confidence'] for p in pages) / len(pages) if pages else 0,
            'providers': sorted({p['provider'] for p in pages}), 'metadata': metadata, 'metadata_warnings': metadata_warnings}


def inspect_document(path: str) -> dict:
    """Inspect format/page structure without OCR; parsing errors become visible warnings."""
    try:
        if Path(path).suffix.lower() == '.pdf':
            with fitz.open(path) as pdf:
                if pdf.is_encrypted or len(pdf) > 50:
                    return {'warnings': ['Encrypted PDF or more than 50 pages; manual review required']}
                return {'page_count': len(pdf), 'text_layer_pages': sum(bool(p.get_text().strip()) for p in pdf), 'metadata': pdf.metadata}
        with Image.open(path) as image:
            return {'width': image.width, 'height': image.height, 'format': image.format}
    except Exception:
        return {'warnings': ['Malformed or unavailable document; extraction will require manual review']}

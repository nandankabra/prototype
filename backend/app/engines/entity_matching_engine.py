from functools import lru_cache
import re
from difflib import SequenceMatcher
from app.core.config import settings


def normalize_name(name: str) -> str:
    name = name.lower().replace('&', ' and ')
    name = re.sub(r'\bpvt\b', 'private', name)
    name = re.sub(r'\bltd\b', 'limited', name)
    return ' '.join(re.sub(r'[^a-z0-9 ]', ' ', name).split())


@lru_cache(maxsize=1)
def sentence_model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer('all-MiniLM-L6-v2', local_files_only=True)


def match_name(left: str, right: str) -> dict:
    a, b = normalize_name(left), normalize_name(right)
    similarity = SequenceMatcher(None, a, b).ratio() if a and b else 0
    provider = 'Normalized token similarity'
    if settings.enable_heavy_ml and a and b and a != b:
        try:
            vectors = sentence_model().encode([a, b], normalize_embeddings=True)
            similarity = float(vectors[0] @ vectors[1])
            provider = 'Sentence Transformers / all-MiniLM-L6-v2'
        except Exception:
            pass
    status = classify_similarity(similarity)
    return {'left': left, 'right': right, 'similarity': round(similarity, 4), 'status': status,
            'provider': provider, 'thresholds': {'match': settings.match_threshold, 'review': settings.review_threshold}}


def classify_similarity(similarity: float) -> str:
    return 'MATCH' if similarity >= settings.match_threshold else 'REVIEW' if similarity >= settings.review_threshold else 'MISMATCH'

from abc import ABC, abstractmethod


class DocumentClassifier(ABC):
    @abstractmethod
    def classify(self, text: str) -> dict: ...


class DemoDocumentClassifier(DocumentClassifier):
    labels = {'gst_certificate': ['gst registration certificate', 'gst certificate'],
              'pan': ['pan card', 'permanent account number'], 'udyam': ['udyam registration'],
              'incorporation': ['certificate of incorporation'], 'bank_certificate': ['bank certificate'],
              'oem_authorization': ['oem authorization'], 'experience_certificate': ['experience certificate'],
              'tax_compliance': ['tax compliance', 'income tax return']}

    def classify(self, text):
        for kind, phrases in self.labels.items():
            if any(p in text.lower() for p in phrases):
                return {'type': kind, 'confidence': 0.96, 'provider': 'DemoDocumentClassifier (text features)'}
        return {'type': 'miscellaneous', 'confidence': 0.4 if text else 0, 'provider': 'DemoDocumentClassifier (text features)'}


class LayoutLMv3DocumentClassifier(DocumentClassifier):
    """Replacement contract: install a fine-tuned classifier before enabling LayoutLM.

    The prototype does not claim to ship trained LayoutLM weights.
    """
    def classify(self, text):
        result = DemoDocumentClassifier().classify(text)
        result['fallback_reason'] = 'No fine-tuned LayoutLMv3 weights configured'
        return result

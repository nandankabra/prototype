"""Retrieval with Qdrant -> FAISS -> NumPy, honest lightweight embedding fallback."""
import hashlib
import re
import uuid
import numpy as np
import httpx
from app.core.config import settings
from app.engines.entity_matching_engine import sentence_model


class EmbeddingProvider:
    def encode(self, texts):
        if settings.enable_heavy_ml:
            try:
                return sentence_model().encode(texts, normalize_embeddings=True), 'Sentence Transformers / all-MiniLM-L6-v2'
            except Exception:
                pass
        vectors = np.zeros((len(texts), 384), dtype=np.float32)
        for i, text in enumerate(texts):
            for token in re.findall(r'\w+', text.lower()):
                slot = int(hashlib.sha256(token.encode()).hexdigest()[:8], 16) % 384
                vectors[i, slot] += 1
        vectors /= np.maximum(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-9)
        return vectors, 'Deterministic hashed-token embeddings (demo fallback)'


class PolicyRetriever:
    def retrieve(self, rules: list[dict], query: str):
        chunks = [{'id': r['rule_id'], 'title': f"Tender Rule {r['rule_code']}: {r['name']}",
                   'text': f"{r['name']}. Expression: {r['expression']}. Evidence: {r['explanation']}",
                   'kind': 'Tender requirement', 'rule_result_id': r['result_id']} for r in rules]
        chunks += [{'id': 'demo-source-policy', 'title': 'Demo Source Verification Policy', 'kind': 'Internal demo guidance',
                    'text': 'All source records are fictional. Source unavailability requires manual review, never a verified match.'},
                   {'id': 'officer-guidance', 'title': 'Officer Review Guidance', 'kind': 'Internal demo guidance',
                    'text': 'Inspect submitted documents and every failed rule. The officer retains the final decision; record a reason for acceptance or override.'}]
        vectors, embedding_provider = EmbeddingProvider().encode([c['text'] for c in chunks] + [query])
        values, query_vector = vectors[:-1], vectors[-1]
        scores = values @ query_vector
        order = np.argsort(-scores)
        store = 'NumPy in-memory'
        try:
            if settings.vector_provider != 'qdrant':
                raise RuntimeError('Qdrant disabled')
            # A unique per-run collection avoids cross-tender contamination; remove after retrieval.
            collection = 'review_' + uuid.uuid4().hex
            with httpx.Client(base_url=settings.qdrant_url, timeout=2) as client:
                response = client.put(f'/collections/{collection}', json={'vectors': {'size': 384, 'distance': 'Cosine'}})
                response.raise_for_status()
                try:
                    client.put(f'/collections/{collection}/points?wait=true', json={'points': [
                        {'id': i, 'vector': v.tolist(), 'payload': chunks[i]} for i, v in enumerate(values)]}).raise_for_status()
                    response = client.post(f'/collections/{collection}/points/search', json={'vector': query_vector.tolist(), 'limit': min(5, len(chunks)), 'with_payload': True})
                    response.raise_for_status()
                    results = response.json()['result']
                    order = [r['id'] for r in results]
                    scores = {r['id']: r['score'] for r in results}
                    store = 'Qdrant'
                finally:
                    client.delete(f'/collections/{collection}')
        except Exception:
            try:
                import faiss
                index = faiss.IndexFlatIP(values.shape[1])
                index.add(values.astype('float32'))
                distances, indexes = index.search(query_vector.reshape(1, -1).astype('float32'), min(5, len(chunks)))
                order = indexes[0].tolist()
                scores = dict(zip(order, distances[0].tolist()))
                store = 'FAISS in-memory fallback'
            except Exception:
                pass
        return {'sources': [{**chunks[int(i)], 'relevance': round(float(scores[int(i)]), 3)} for i in list(order)[:5]],
                'vector_provider': store, 'embedding_provider': embedding_provider,
                'scope': 'Tender requirements and internal demo guidance; no external legal claims'}

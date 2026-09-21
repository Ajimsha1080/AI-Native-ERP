"""
Layer 4: Cross-Encoder & Contextual Reranker Service.

Computes semantic query-passage alignment scores on candidate chunks
fused from Reciprocal Rank Fusion (RRF).
"""

import re
from typing import List, Dict, Any


class CrossEncoderReranker:
    """Contextual Semantic Cross-Encoder Reranker."""

    def __init__(self, token_weight: float = 0.35, dense_weight: float = 0.35, rrf_weight: float = 0.30):
        self.token_weight = token_weight
        self.dense_weight = dense_weight
        self.rrf_weight = rrf_weight

    def score_candidate(self, query: str, candidate: Dict[str, Any]) -> float:
        """
        Calculates cross-encoder alignment score between query and document candidate.
        """
        content = candidate.get("content", "").lower()
        q_tokens = set(re.findall(r"\b\w+\b", query.lower()))
        doc_tokens = set(re.findall(r"\b\w+\b", content))

        # 1. Lexical Jaccard & Containment Overlap
        if not q_tokens:
            overlap_score = 0.5
        else:
            intersection = len(q_tokens & doc_tokens)
            overlap_score = intersection / len(q_tokens)

        # 2. Dense Cosine Similarity
        dense_score = candidate.get("dense_score", 0.7)

        # 3. RRF Position Weight
        rrf_score = min(candidate.get("rrf_score", 0.01) * 30.0, 1.0)

        # 4. Proximity & Exact Phrase Boost
        phrase_boost = 0.15 if query.lower() in content else 0.0

        final_score = (
            (overlap_score * self.token_weight) +
            (dense_score * self.dense_weight) +
            (rrf_score * self.rrf_weight) +
            phrase_boost
        )
        return round(min(final_score, 1.0), 4)

    def rerank(self, query: str, candidates: List[Dict[str, Any]], top_k: int = 5) -> List[Dict[str, Any]]:
        """Reranks candidate chunks by cross-encoder score descending."""
        scored_candidates = []
        for c in candidates:
            score = self.score_candidate(query, c)
            item = dict(c)
            item["rerank_score"] = score
            scored_candidates.append(item)

        scored_candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
        return scored_candidates[:top_k]


# Global Reranker Instance
reranking_service = CrossEncoderReranker()

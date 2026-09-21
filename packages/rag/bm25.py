"""
Sparse Lexical Retrieval Engine using Okapi BM25.
Provides token-level keyword retrieval for Hybrid Search and RRF fusion.
"""

import math
import re
from typing import List, Dict, Any, Tuple
from collections import Counter


class BM25Retriever:
    """Okapi BM25 implementation for lexical sparse search."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_freqs: List[Dict[str, int]] = []
        self.idf: Dict[str, float] = {}
        self.doc_lens: List[int] = []
        self.documents: List[Dict[str, Any]] = []

    def _tokenize(self, text: str) -> List[str]:
        """Simple, robust alphanumeric tokenization."""
        return re.findall(r"\b[a-zA-Z0-9_\-\$]+\b", text.lower())

    def index_documents(self, documents: List[Dict[str, Any]], text_key: str = "content") -> None:
        """
        Indexes a list of documents or chunks for BM25 retrieval.
        Each document is a dict containing `content`, `id`, `metadata`, etc.
        """
        self.documents = documents
        self.corpus_size = len(documents)
        self.doc_freqs = []
        self.doc_lens = []
        
        df: Dict[str, int] = Counter()

        for doc in documents:
            text = doc.get(text_key, "")
            tokens = self._tokenize(text)
            self.doc_lens.append(len(tokens))
            
            freqs = Counter(tokens)
            self.doc_freqs.append(freqs)
            
            for word in freqs.keys():
                df[word] += 1

        self.avgdl = sum(self.doc_lens) / self.corpus_size if self.corpus_size > 0 else 0.0

        # Calculate inverse document frequency (IDF) with standard Robertson-Spärck Jones formula
        self.idf = {}
        for word, freq in df.items():
            # Standard BM25 IDF with smoothing
            idf_val = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)
            self.idf[word] = max(idf_val, 0.01)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[Dict[str, Any], float]]:
        """
        Searches the indexed corpus using BM25 and returns top-k matching documents with BM25 scores.
        """
        if not self.documents:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: List[float] = [0.0] * self.corpus_size

        for i, freqs in enumerate(self.doc_freqs):
            doc_len = self.doc_lens[i]
            score = 0.0
            for token in query_tokens:
                if token not in freqs:
                    continue
                tf = freqs[token]
                idf = self.idf.get(token, 0.0)
                numerator = idf * tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * (doc_len / (self.avgdl or 1.0)))
                score += numerator / denominator
            scores[i] = score

        # Rank documents by descending score
        ranked_indices = sorted(range(len(scores)), key=lambda idx: scores[idx], reverse=True)
        results = []
        for idx in ranked_indices[:top_k]:
            if scores[idx] > 0.0001:
                results.append((self.documents[idx], scores[idx]))

        return results

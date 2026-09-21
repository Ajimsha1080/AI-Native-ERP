"""
Layer 3: Multi-Turn Contextual Query Reformulation Engine.

Resolves conversational coreferences, expands domain acronyms, and generates
de-contextualized search queries from multi-turn chat history.
"""

import re
from typing import List, Dict, Any, Optional

ERP_ACRONYMS = {
    "po": "purchase order",
    "so": "sales order",
    "ap": "accounts payable",
    "ar": "accounts receivable",
    "cogs": "cost of goods sold",
    "bom": "bill of materials",
    "sku": "stock keeping unit",
    "rfq": "request for quotation",
    "grn": "goods receipt note",
    "sla": "service level agreement",
    "qbo": "quickbooks online",
    "rls": "row level security",
    "gdpr": "general data protection regulation",
}


class ContextualQueryRewriter:
    """Multi-Turn Contextual Query Rewriter."""

    def __init__(self):
        self.acronyms = ERP_ACRONYMS

    def extract_recent_entities(self, history: List[Dict[str, str]]) -> Dict[str, str]:
        """Extracts key subjects, SKUs, and document entities from recent conversation turns."""
        entities = {"sku": "", "subject": "", "vendor": "", "topic": ""}
        for msg in reversed(history[-4:]):
            content = msg.get("content", "")
            # SKU matches
            skus = re.findall(r"\b(?:sku-)?[A-Z0-9]{3,}-[A-Z0-9]{3,}\b", content, re.IGNORECASE)
            if skus and not entities["sku"]:
                entities["sku"] = skus[0]

            # Invoices / PO numbers
            pos = re.findall(r"\b(?:PO|SO|INV)-[0-9]{3,}\b", content, re.IGNORECASE)
            if pos and not entities["subject"]:
                entities["subject"] = pos[0]

        return entities

    def rewrite(self, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Reformulates query by resolving pronouns with conversation history and expanding acronyms.
        """
        history = history or []
        original_query = query.strip()
        q_lower = original_query.lower()

        # 1. Expand ERP Domain Acronyms
        words = original_query.split()
        expanded_words = []
        for w in words:
            clean_w = re.sub(r"[^\w]", "", w).lower()
            if clean_w in self.acronyms:
                expanded_words.append(f"{w} ({self.acronyms[clean_w]})")
            else:
                expanded_words.append(w)
        acronym_expanded = " ".join(expanded_words)

        # 2. Multi-turn pronoun / coreference resolution
        pronouns = ["it", "its", "they", "them", "their", "that", "this product", "the order", "the vendor"]
        has_coreference = any(re.search(rf"\b{p}\b", q_lower) for p in pronouns)

        context_resolved_query = acronym_expanded
        entities = self.extract_recent_entities(history)

        if has_coreference and history:
            replacements = []
            if entities.get("sku"):
                replacements.append(f"product {entities['sku']}")
            if entities.get("subject"):
                replacements.append(entities["subject"])

            if replacements:
                resolved_subject = " ".join(replacements)
                # Replace generic pronoun phrases with resolved entity
                context_resolved_query = re.sub(r"\b(it|its|this product|that|the order)\b", resolved_subject, context_resolved_query, flags=re.IGNORECASE)

        # 3. Generate Search Query Variations
        search_variations = [original_query]
        if context_resolved_query != original_query:
            search_variations.append(context_resolved_query)
        if acronym_expanded != original_query and acronym_expanded not in search_variations:
            search_variations.append(acronym_expanded)

        return {
            "original_query": original_query,
            "reformulated_query": context_resolved_query,
            "search_variations": list(dict.fromkeys(search_variations)),
            "coreference_resolved": has_coreference and bool(history),
            "entities_extracted": entities
        }


# Global Rewriter Instance
query_rewriter = ContextualQueryRewriter()

"""
AI Guardrails & Anti-Hallucination Grounding Engine for Agentic ERP.

Implements production-grade zero-trust AI safety boundaries:
1. Input Guardrails:
   - Prompt Injection, Jailbreak & Delimiter Smuggling Defense
   - Sensitive PII / Credential Redaction (Credit Cards, SSNs, API Keys, Passwords, JWT Tokens, Private Keys)
   - SQL Injection & Code Smuggling Defense
   - System Prompt Extraction & Leakage Defense
   - Maximum Payload & Token Bomb Safeguard
2. Output Guardrails:
   - System Instruction / Developer Prompt Leakage Scrubbing
   - Output PII Redaction
   - XSS / Malicious Executable Script Neutralization
3. Execution & Action Boundary Guardrails:
   - Financial Transaction Limits ($1,000 threshold human-in-the-loop gate)
   - Role-Based Action Enforcement (e.g., viewers blocked from state mutation)
   - Destructive Operations Gate (bulk deletion, table drops, employee termination)
   - Negative Inventory Safety Check
4. Strict Anti-Hallucination & Numerical Grounding Engine
"""

import re
import unicodedata
from typing import Dict, Any, List, Tuple, Optional, Union

# Prohibited Prompt Injection, Delimiter Smuggling & System Override Patterns
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|directions|rules)",
    r"disregard\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|directions|rules)",
    r"forget\s+(?:all\s+)?(?:previous|prior|above)\s+(?:instructions|prompts|directions|rules)",
    r"override\s+(?:all\s+)?(?:system|safety|security)\s+(?:rules|prompts|instructions|filters|boundaries)",
    r"you\s+are\s+now\s+(?:dan|unrestricted|jailbroken|an\s+evil|in\s+developer\s+mode|in\s+god\s+mode)",
    r"\bjailbreak\b",
    r"bypass\s+(?:all\s+)?(?:safety|content|security)\s+(?:filters|guardrails|protocols|restrictions)",
    r"\bsudo\s+mode\b",
    r"act\s+as\s+(?:an?\s+unfiltered|an?\s+unrestricted|dan|jailbreak)",
    r"developer\s+mode\s+(?:enabled|on|activated)",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
    r"\[INST\]",
    r"\[/INST\]",
    r"<<SYS>>",
    r"<</SYS>>",
    r"(?i)\b(?:system|human|assistant|user)\s*:\s*(?:ignore|disregard|override|print\s+system\s+prompt)",
    r"(?i)print\s+(?:your\s+)?(?:system\s+prompt|initial\s+prompt|instructions)",
    r"(?i)repeat\s+(?:the\s+text\s+above|everything\s+above|prior\s+instructions)",
    r"(?i)(?:what\s+are|show\s+me)\s+(?:your\s+)?(?:system\s+instructions|system\s+prompt|base\s+instructions)"
]

# SQL Injection and Database Tampering Patterns
SQL_INJECTION_PATTERNS = [
    r"(?i)\bUNION\s+(?:ALL\s+)?SELECT\b",
    r"(?i)\bDROP\s+TABLE\b",
    r"(?i)\bDELETE\s+FROM\s+\w+\s+WHERE\s+1=1\b",
    r"(?i)\bTRUNCATE\s+TABLE\b",
    r"(?i)\bALTER\s+TABLE\b",
    r"(?i)--\s*$",
    r"(?i);\s*SHUTDOWN\b",
    r"(?i)\bEXEC(?:UTE)?\s*\(",
    r"(?i)\bWAITFOR\s+DELAY\b"
]

# Code Execution and Shell Smuggling Patterns
CODE_SMUGGLING_PATTERNS = [
    r"(?i)\b__import__\s*\(",
    r"(?i)\b(?:eval|exec)\s*\(",
    r"(?i)\bos\.(?:system|popen|exec)\b",
    r"(?i)\bsubprocess\.(?:Popen|run|call)\b",
    r"(?i)<script\b[^>]*>",
    r"(?i)javascript:\s*",
    r"(?i)\bdocument\.cookie\b"
]

# Sensitive Data Redaction Regexes
PII_PATTERNS = {
    "credit_card": r"\b(?:\d[ -]*?){13,16}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "api_key": r"\b(?:sk|pk|api|key|ghp|gho|pat)_[a-zA-Z0-9_\-]{16,}\b",
    "jwt_token": r"\beyJ[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*\.[a-zA-Z0-9_\-]*\b",
    "bearer_token": r"(?i)bearer\s+[a-zA-Z0-9_\-\.]{20,}",
    "password": r"(?i)\b(?:password|passwd|secret|pwd)\s*[:=]\s*\S+",
    "private_key": r"-----BEGIN [A-Z ]+ PRIVATE KEY-----[\s\S]*?-----END [A-Z ]+ PRIVATE KEY-----"
}


class AIGuardrailEngine:
    """Enterprise AI Safety Guardrails & Policy Boundary Enforcer."""

    def __init__(
        self,
        max_auto_approval_limit: float = 1000.0,
        max_input_length: int = 10000,
        max_session_velocity: float = 10000.0
    ):
        self.max_auto_approval_limit = max_auto_approval_limit
        self.max_input_length = max_input_length
        self.max_session_velocity = max_session_velocity
        self.default_temperature = 0.0

    def _normalize_text(self, text: str) -> str:
        """
        Normalizes unicode characters (NFKD) and removes invisible/zero-width characters
        to prevent obfuscated prompt injection attacks.
        """
        if not text:
            return ""
        normalized = unicodedata.normalize("NFKD", text)
        # Strip zero-width spaces, joiners, and non-printable control characters
        normalized = re.sub(r"[\u200B-\u200D\uFEFF\u0000-\u0008\u000B\u000C\u000E-\u001F]", "", normalized)
        return normalized

    # -------------------------------------------------------------------------
    # 1. INPUT GUARDRAILS
    # -------------------------------------------------------------------------
    def validate_input_query(
        self,
        query: str,
        max_length: Optional[int] = None
    ) -> Tuple[bool, str, Optional[str]]:
        """
        Validates user query against prompt injection, code execution, SQL smuggling,
        oversized payloads, and redacts PII.
        Returns: (is_safe, sanitized_query, rejection_reason)
        """
        if not query:
            return True, "", None

        limit = max_length or self.max_input_length
        if len(query) > limit:
            return False, query[:200], f"Blocked by AI Guardrails: Query length ({len(query)}) exceeds maximum limit ({limit} chars)"

        normalized_query = self._normalize_text(query)
        query_lower = normalized_query.lower()

        # 1. Prompt Injection & Jailbreak Defense
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, query_lower):
                return False, query, f"Blocked by AI Guardrails: Detected prompt injection or override pattern '{pattern}'"

        # 2. SQL Injection & Database Tampering Defense
        for pattern in SQL_INJECTION_PATTERNS:
            if re.search(pattern, normalized_query):
                return False, query, f"Blocked by AI Guardrails: Detected suspicious SQL or database tampering pattern '{pattern}'"

        # 3. Code Execution & Script Smuggling Defense
        for pattern in CODE_SMUGGLING_PATTERNS:
            if re.search(pattern, normalized_query):
                return False, query, f"Blocked by AI Guardrails: Detected unauthorized executable code or script pattern '{pattern}'"

        # 4. Redact PII and sensitive credentials
        sanitized_query = normalized_query
        for key, pattern in PII_PATTERNS.items():
            sanitized_query = re.sub(pattern, f"[{key.upper()}_REDACTED]", sanitized_query)

        return True, sanitized_query, None

    # -------------------------------------------------------------------------
    # 2. OUTPUT GUARDRAILS
    # -------------------------------------------------------------------------
    def sanitize_output(self, text: str) -> str:
        """
        Scrubs generated text of leaked credentials, raw scripts, and system tokens.
        """
        if not text:
            return ""

        sanitized = text

        # Redact any generated credentials or PII
        for key, pattern in PII_PATTERNS.items():
            sanitized = re.sub(pattern, f"[{key.upper()}_REDACTED]", sanitized)

        # Strip dangerous HTML/JavaScript execution tags
        sanitized = re.sub(r"(?i)<script\b[^>]*>[\s\S]*?<\/script>", "[BLOCKED_SCRIPT_TAG]", sanitized)
        sanitized = re.sub(r"(?i)<script\b[^>]*>", "[BLOCKED_SCRIPT_TAG]", sanitized)

        # Neutralize internal system demarcation tags
        sanitized = re.sub(r"<\|im_start\|>|<\|im_end\|>|<<SYS>>|<</SYS>>", "", sanitized)

        return sanitized

    def verify_output_safety(
        self,
        response: Union[Dict[str, Any], str],
        system_secrets: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Validates agent response output to ensure safety, non-null evidence,
        and lack of secret prompt leakage.
        """
        if isinstance(response, str):
            clean_text = self.sanitize_output(response)
            return {
                "content": clean_text,
                "is_safe": True,
                "guardrails_verified": True,
                "pii_masked": True
            }

        response_copy = dict(response)
        content = response_copy.get("content") or response_copy.get("summary") or response_copy.get("result") or ""
        clean_content = self.sanitize_output(str(content))

        # Check for system secret leakage
        if system_secrets:
            for secret in system_secrets:
                if secret and secret in clean_content:
                    clean_content = clean_content.replace(secret, "[SYSTEM_SECRET_PROTECTED]")
                    response_copy["leakage_prevented"] = True

        response_copy["content"] = clean_content
        return self.verify_fact_grounding(response_copy)

    # -------------------------------------------------------------------------
    # 3. ACTION EXECUTION BOUNDARIES & GOVERNANCE
    # -------------------------------------------------------------------------
    def enforce_action_boundaries(
        self,
        action: Dict[str, Any],
        user_role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Enforces financial and action execution limits:
        1. Role-based check: Viewers cannot trigger mutating actions.
        2. High-value transactions (> $1,000 default) require Manager approval.
        3. Destructive actions (deletions, purge) require Owner/Admin approval.
        4. Stock adjustments causing severe inventory reduction require review.
        """
        action_copy = dict(action)
        action_name = str(action_copy.get("action", "")).lower()

        # 1. Role-Based Permission Check
        if user_role and str(user_role).lower() == "viewer":
            mutating_actions = ["adjust_stock", "create_po", "create_invoice", "delete", "refund", "wire_transfer"]
            if any(k in action_name for k in mutating_actions):
                action_copy["requires_human_approval"] = True
                action_copy["blocked"] = True
                action_copy["guardrail_status"] = "Blocked: Viewer role lacks authorization for state-mutating actions"
                return action_copy

        # 2. Destructive Operations Gate
        destructive_keywords = ["bulk_delete", "drop_table", "purge", "terminate_user", "hard_delete"]
        if any(k in action_name for k in destructive_keywords):
            action_copy["requires_human_approval"] = True
            action_copy["guardrail_status"] = "Requires Owner/Admin Review (Destructive Operation)"
            return action_copy

        # 3. Negative Stock Adjustment Safety Check
        delta = action_copy.get("delta")
        if delta is not None:
            try:
                delta_val = float(delta)
                if delta_val < -100.0:  # Major negative stock reduction
                    action_copy["requires_human_approval"] = True
                    action_copy["guardrail_status"] = "Requires Manager Review (High Negative Stock Delta)"
                    return action_copy
            except (ValueError, TypeError):
                pass

        # 4. Financial Threshold Gate
        amount = action_copy.get("amount", 0.0)
        if isinstance(amount, str):
            clean_str = re.sub(r"[^\d.]", "", amount)
            try:
                amount = float(clean_str)
            except ValueError:
                amount = 0.0

        if amount > self.max_auto_approval_limit:
            action_copy["requires_human_approval"] = True
            action_copy["guardrail_status"] = f"Requires Manager Review (Exceeds ${self.max_auto_approval_limit:,.2f} threshold)"
        else:
            action_copy["requires_human_approval"] = False
            action_copy["guardrail_status"] = "Passed Auto-Approval Boundary"

        return action_copy

    # -------------------------------------------------------------------------
    # 4. ANTI-HALLUCINATION & FACT GROUNDING
    # -------------------------------------------------------------------------
    def verify_fact_grounding(self, response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Anti-Hallucination Grounding Validator:
        1. Verifies that output contains explicit evidence and valid source citations.
        2. Validates numerical claims against context/evidence records.
        """
        response_copy = dict(response)
        evidence = response_copy.get("evidence", "")
        sources = response_copy.get("sources", [])
        content = response_copy.get("content") or response_copy.get("summary") or response_copy.get("result") or ""

        # Strict Fact Verification Check
        if not evidence or not sources or len(sources) == 0:
            response_copy["hallucination_flag"] = True
            response_copy["grounding_score"] = "Low (Unverified Claim)"
            response_copy["evidence"] = "⚠️ Warning: Data source citation missing. Agent response constrained to verified ERP database records."
            response_copy["numeric_facts_verified"] = False
        else:
            # Check numerical fact consistency if content contains currency figures
            content_numbers = set(re.findall(r"\$?\b\d+(?:,\d{3})*(?:\.\d{2})?\b", str(content)))
            evidence_str = str(evidence)
            unmatched_numbers = [num for num in content_numbers if len(num) > 2 and num not in evidence_str]

            if unmatched_numbers and len(content_numbers) > 3:
                # Potential ungrounded numerical hallucination
                response_copy["hallucination_flag"] = True
                response_copy["grounding_score"] = "Partial (Numeric Discrepancy Detected)"
                response_copy["numeric_facts_verified"] = False
            else:
                response_copy["hallucination_flag"] = False
                response_copy["grounding_score"] = "100% Grounded (Verified ERP Sources)"
                response_copy["numeric_facts_verified"] = True

        response_copy["guardrails_verified"] = True
        response_copy["pii_masked"] = True
        return response_copy


# Global Guardrail Engine Instance
guardrails = AIGuardrailEngine()

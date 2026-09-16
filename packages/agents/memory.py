from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
import json

class AgentMemoryEngine:
    """
    Dual-Layer Memory Engine for ERP Agents.
    
    1. Short-Term Memory: Maintains active chat turn history per user session.
    2. Long-Term Memory: Persists past executive decisions, supplier preferences, 
       and ERP approvals across sessions.
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.short_term_buffer: List[Dict[str, Any]] = []
        self.long_term_memory: List[Dict[str, Any]] = []
        self.user_preferences: Dict[str, Any] = {}

    def add_conversation_turn(self, role: str, message: str, metadata: Optional[Dict[str, Any]] = None):
        """Record a single conversational turn in Short-Term Memory."""
        turn = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,  # 'user' or 'assistant'
            "message": message,
            "metadata": metadata or {}
        }
        self.short_term_buffer.append(turn)
        # Keep buffer to last 20 turns for token efficiency
        if len(self.short_term_buffer) > 20:
            self.short_term_buffer.pop(0)

    def get_conversation_context(self, max_turns: int = 6) -> List[Dict[str, Any]]:
        """Retrieve recent Short-Term Memory context for prompt synthesis."""
        return self.short_term_buffer[-max_turns:]

    def store_long_term_decision(self, decision_type: str, details: Dict[str, Any], user: str):
        """Persist a high-value executive decision into Long-Term Memory."""
        now = datetime.now(timezone.utc)
        record = {
            "id": f"MEM-{now.strftime('%Y%m%d%H%M%S')}",
            "agent": self.agent_name,
            "decision_type": decision_type,  # e.g., 'PO_APPROVAL', 'CREDIT_MEMO', 'SUPPLIER_PREFERENCE'
            "details": details,
            "user": user,
            "timestamp": now.isoformat()
        }
        self.long_term_memory.append(record)

    def recall_relevant_memories(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """
        Recalls historical long-term memories relevant to the user query.
        (In production, uses Cosine Vector Search over embeddings).
        """
        query_words = set(query.lower().split())
        matched_memories = []

        for record in self.long_term_memory:
            desc = json.dumps(record.get("details", {})).lower()
            if any(word in desc for word in query_words if len(word) > 3):
                matched_memories.append(record)

        return matched_memories[-limit:] if matched_memories else self.long_term_memory[-limit:]

    def clear_short_term(self):
        """Reset short-term context buffer."""
        self.short_term_buffer = []

# Global Agent Memory Manager Singleton
class MemoryManager:
    _instances: Dict[str, AgentMemoryEngine] = {}

    @classmethod
    def get_memory_for_agent(cls, agent_name: str) -> AgentMemoryEngine:
        if agent_name not in cls._instances:
            cls._instances[agent_name] = AgentMemoryEngine(agent_name)
        return cls._instances[agent_name]

memory_manager = MemoryManager()

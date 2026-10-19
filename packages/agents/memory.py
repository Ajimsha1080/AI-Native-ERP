"""
Enterprise Multi-Tenant Memory Architecture for Agentic ERP.

Implements a 3-tier memory engine:
1. Working / Short-Term Memory:
   - Session-isolated conversational turns buffer
   - Sliding window token budgeting
   - Context retrieval for prompt generation
2. Long-Term Episodic Memory:
   - Persistent records of executive decisions, approvals, and tool actions
   - Semantic vector recall using embedding cosine similarity
3. Entity & Semantic Memory:
   - Persistent key-value operational preferences, supplier terms, customer attributes
   - Tenant-scoped fact retrieval and search
"""

import math
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class MemoryEmbedder:
    """384-dimensional deterministic feature hashing embedding for zero-dependency semantic memory recall."""
    def __init__(self, dimension: int = 384):
        self.dimension = dimension

    def embed_text(self, text: str) -> List[float]:
        words = text.lower().split()
        vec = [0.0] * self.dimension
        if not words:
            return vec

        for w in words:
            h = int(hashlib.md5(w.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dimension
            sign = 1.0 if (h >> 4) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec

    def cosine_similarity(self, vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return max(0.0, min(dot / (norm_a * norm_b), 1.0))


_memory_embedder = MemoryEmbedder()


class AgentMemoryEngine:
    """
    Tenant-Scoped 3-Tier Memory Engine for ERP Agents.
    
    Guarantees strict data isolation between tenants and sessions.
    """

    def __init__(self, agent_name: str, organization_id: Optional[str] = None):
        self.agent_name = agent_name
        self.organization_id = str(organization_id) if organization_id else "global"
        
        # 1. Short-Term Memory: Isolated per session_id -> list of turns
        self._session_buffers: Dict[str, List[Dict[str, Any]]] = {}
        # Legacy/default buffer for single-session backward compatibility
        self.short_term_buffer: List[Dict[str, Any]] = []

        # 2. Long-Term Episodic Memory: Past decisions & actions
        self.long_term_memory: List[Dict[str, Any]] = []

        # 3. Entity & Semantic Memory: Key-value facts per entity
        self._entity_facts: Dict[str, Dict[str, Any]] = {}
        self.user_preferences: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # 1. SHORT-TERM / WORKING MEMORY
    # -------------------------------------------------------------------------
    def add_conversation_turn(
        self,
        role: str,
        message: str,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Record a single conversational turn in Short-Term Memory."""
        sid = session_id or (metadata or {}).get("session_id") or "default"
        turn = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "role": role,  # 'user' or 'assistant'
            "message": message,
            "session_id": sid,
            "organization_id": self.organization_id,
            "metadata": metadata or {}
        }

        # Append to session-specific buffer
        if sid not in self._session_buffers:
            self._session_buffers[sid] = []
        self._session_buffers[sid].append(turn)
        if len(self._session_buffers[sid]) > 25:
            self._session_buffers[sid].pop(0)

        # Sync with legacy buffer for backward compatibility
        self.short_term_buffer.append(turn)
        if len(self.short_term_buffer) > 25:
            self.short_term_buffer.pop(0)

    def get_conversation_context(
        self,
        session_id: Optional[str] = None,
        max_turns: int = 6
    ) -> List[Dict[str, Any]]:
        """Retrieve recent Short-Term Memory context for prompt synthesis."""
        if session_id is not None:
            return self._session_buffers.get(session_id, [])[-max_turns:]
        return self.short_term_buffer[-max_turns:]

    def clear_short_term(self, session_id: Optional[str] = None) -> None:
        """Reset short-term context buffer for a specific session or all sessions."""
        if session_id:
            self._session_buffers.pop(session_id, None)
            self.short_term_buffer = [t for t in self.short_term_buffer if t.get("session_id") != session_id]
        else:
            self._session_buffers.clear()
            self.short_term_buffer = []

    def get_active_sessions(self) -> List[str]:
        """List active session IDs within this memory engine."""
        return list(self._session_buffers.keys())

    # -------------------------------------------------------------------------
    # 2. LONG-TERM EPISODIC DECISION MEMORY
    # -------------------------------------------------------------------------
    def store_long_term_decision(
        self,
        decision_type: str,
        details: Dict[str, Any],
        user: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Persist a high-value executive decision into Long-Term Memory with vector embedding."""
        now = datetime.now(timezone.utc)
        record_id = f"MEM-{now.strftime('%Y%m%d%H%M%S')}-{abs(hash(json.dumps(details, default=str))) % 10000:04d}"
        
        # Serialize representation for embedding
        text_repr = f"{decision_type} {json.dumps(details, default=str)} user:{user}"
        embedding = _memory_embedder.embed_text(text_repr)

        record = {
            "id": record_id,
            "agent": self.agent_name,
            "organization_id": self.organization_id,
            "decision_type": decision_type,  # e.g., 'PO_APPROVAL', 'CREDIT_MEMO', 'SUPPLIER_PREFERENCE'
            "details": details,
            "user": user,
            "timestamp": now.isoformat(),
            "metadata": metadata or {},
            "_embedding": embedding
        }
        self.long_term_memory.append(record)
        return record_id

    def recall_relevant_memories(
        self,
        query: str,
        limit: int = 3,
        decision_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Recalls historical long-term memories relevant to the user query using cosine vector similarity.
        """
        if not self.long_term_memory:
            return []

        query_vec = _memory_embedder.embed_text(query)
        scored_memories = []

        for record in self.long_term_memory:
            if decision_type and record.get("decision_type") != decision_type:
                continue

            rec_vec = record.get("_embedding")
            if rec_vec:
                sim = _memory_embedder.cosine_similarity(query_vec, rec_vec)
            else:
                # Fallback to lexical term overlap
                desc = json.dumps(record.get("details", {})).lower()
                query_words = set(query.lower().split())
                overlap = len([w for w in query_words if len(w) > 3 and w in desc])
                sim = overlap * 0.2

            clean_record = {k: v for k, v in record.items() if not k.startswith("_")}
            clean_record["similarity_score"] = round(sim, 4)
            scored_memories.append((sim, clean_record))

        # Rank by descending similarity score
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [mem for _, mem in scored_memories[:limit]]

    # -------------------------------------------------------------------------
    # 3. ENTITY & SEMANTIC PREFERENCE MEMORY
    # -------------------------------------------------------------------------
    def remember_entity_fact(
        self,
        entity_type: str,
        entity_id: str,
        key: str,
        value: Any,
        confidence: float = 1.0
    ) -> None:
        """
        Stores or updates an operational fact or preference about a business entity
        (e.g., vendor payment terms, customer credit limit, warehouse preferences).
        """
        entity_key = f"{entity_type.lower()}:{str(entity_id).lower()}"
        if entity_key not in self._entity_facts:
            self._entity_facts[entity_key] = {}

        self._entity_facts[entity_key][key] = {
            "value": value,
            "confidence": confidence,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }

    def get_entity_facts(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Retrieves all stored facts for a given entity."""
        entity_key = f"{entity_type.lower()}:{str(entity_id).lower()}"
        facts_dict = self._entity_facts.get(entity_key, {})
        return {k: v["value"] for k, v in facts_dict.items()}

    def search_entity_facts(
        self,
        query: str,
        entity_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Searches across entity memory facts for matching terms."""
        results = []
        q_lower = query.lower()

        for entity_key, facts in self._entity_facts.items():
            etype, eid = entity_key.split(":", 1)
            if entity_type and etype != entity_type.lower():
                continue

            for fact_key, fact_meta in facts.items():
                fact_val_str = str(fact_meta.get("value", "")).lower()
                if q_lower in fact_key.lower() or q_lower in fact_val_str:
                    results.append({
                        "entity_type": etype,
                        "entity_id": eid,
                        "key": fact_key,
                        "value": fact_meta.get("value"),
                        "confidence": fact_meta.get("confidence")
                    })
        return results

    def delete_entity_fact(self, entity_type: str, entity_id: str, key: str) -> bool:
        """Deletes a specific entity fact from memory."""
        entity_key = f"{entity_type.lower()}:{str(entity_id).lower()}"
        if entity_key in self._entity_facts and key in self._entity_facts[entity_key]:
            del self._entity_facts[entity_key][key]
            return True
        return False


# Global Agent Memory Manager Singleton
class MemoryManager:
    """Manages multi-tenant AgentMemoryEngine instances with guaranteed tenant isolation."""
    _instances: Dict[Tuple[str, str], AgentMemoryEngine] = {}

    @classmethod
    def get_memory_for_agent(
        cls,
        agent_name: str,
        organization_id: Optional[Any] = None
    ) -> AgentMemoryEngine:
        """
        Retrieves or initializes an AgentMemoryEngine scoped to a specific organization.
        Guarantees that memories are strictly isolated per tenant.
        """
        org_key = str(organization_id) if organization_id else "global"
        composite_key = (org_key, agent_name)

        if composite_key not in cls._instances:
            cls._instances[composite_key] = AgentMemoryEngine(agent_name, organization_id=org_key)
        return cls._instances[composite_key]

    @classmethod
    def clear_tenant_memory(cls, organization_id: Any) -> None:
        """Purges all agent memory instances for a specific tenant."""
        org_key = str(organization_id)
        keys_to_remove = [k for k in cls._instances if k[0] == org_key]
        for k in keys_to_remove:
            del cls._instances[k]

    @classmethod
    def get_tenant_stats(cls, organization_id: Any) -> Dict[str, Any]:
        """Returns memory metrics for a tenant."""
        org_key = str(organization_id)
        tenant_instances = [v for k, v in cls._instances.items() if k[0] == org_key]
        total_turns = sum(len(m.short_term_buffer) for m in tenant_instances)
        total_decisions = sum(len(m.long_term_memory) for m in tenant_instances)
        total_entity_keys = sum(len(m._entity_facts) for m in tenant_instances)
        return {
            "agents_active": len(tenant_instances),
            "short_term_turns": total_turns,
            "long_term_decisions": total_decisions,
            "entity_profiles": total_entity_keys
        }


memory_manager = MemoryManager()

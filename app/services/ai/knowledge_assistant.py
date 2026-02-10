"""
AI Knowledge Assistant (Copilot) Service
Provides step-by-step repair instructions and answers natural language queries
"""
from typing import Dict, List, Optional, Any
import math
import re
import logging
from datetime import datetime

from app.core.config import settings
from app.models.ai_models import AIKnowledgeBase

logger = logging.getLogger(__name__)


class KnowledgeAssistantService:
    """AI-powered knowledge assistant for repair guidance"""
    
    def __init__(self):
        self.model_version = "v1.0"
        # In production, use RAG (Retrieval Augmented Generation) with vector DB
        # self.embedding_model = load_model("models/embedding.pkl")
        # self.llm = load_model("models/llm.pkl")
        # self.kb_vector_db = VectorDB("knowledge_base")
    
    async def answer_query(
        self,
        query: str,
        device_category: Optional[str] = None,
        device_model: Optional[str] = None,
        language: str = "en",
        db=None,
        role: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Answer a natural language query about repair procedures
        
        Args:
            query: User's question
            device_category: Product category
            device_model: Specific model
            language: Response language (en, hi)
        
        Returns:
            Dict with answer, steps, sources, confidence
        """
        try:
            # In production:
            # 1. Embed query
            # 2. Search knowledge base (vector similarity)
            # 3. Retrieve relevant repair manuals, KB articles
            # 4. Generate answer using LLM with retrieved context
            
            docs = []
            if db:
                docs = self._retrieve_docs(db, query, role=role, limit=4)
            answer = await self._generate_answer(query, device_category, device_model, language, docs=docs)
            steps = await self._get_repair_steps(query, device_category, device_model)
            sources = [{"title": d.title, "source": d.source} for d in docs]
            
            return {
                "answer": answer,
                "steps": steps,
                "sources": sources,
                "confidence": 0.85,
                "language": language,
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in knowledge assistant: {str(e)}")
            return {
                "answer": "I'm sorry, I couldn't process your query. Please try rephrasing.",
                "steps": [],
                "sources": [],
                "confidence": 0.0,
                "language": language,
                "error": str(e)
            }
    
    async def get_repair_steps(
        self,
        issue_category: str,
        device_category: str,
        device_model: Optional[str] = None,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Get step-by-step repair instructions
        
        Returns:
            List of steps with descriptions, images, warnings
        """
        # TODO: Retrieve from structured knowledge base
        # Query database for repair procedures matching issue_category and device_category
        return []
    
    async def _generate_answer(
        self,
        query: str,
        device_category: Optional[str],
        device_model: Optional[str],
        language: str,
        docs: Optional[List[AIKnowledgeBase]] = None
    ) -> str:
        """Generate answer using RAG + optional LLM"""
        context = ""
        if docs:
            context = "\n\n".join([f"{d.title}\n{d.content}" for d in docs])

        if settings.OPENAI_API_KEY:
            try:
                import httpx
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {"role": "system", "content": "You are a helpful repair assistant. Use the provided context."},
                        {"role": "system", "content": f"Context:\n{context}"},
                        {"role": "user", "content": query}
                    ],
                    "temperature": 0.2
                }
                async with httpx.AsyncClient(timeout=10.0) as client:
                    resp = await client.post(
                        "https://api.openai.com/v1/chat/completions",
                        headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                        json=payload
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        return data["choices"][0]["message"]["content"]
            except Exception:
                pass

        if context:
            return f"Based on our knowledge base:\n{context[:600]}"
        return "I couldn't find relevant knowledge base entries yet."
    
    async def _get_repair_steps(
        self,
        query: str,
        device_category: Optional[str],
        device_model: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Get repair steps from KB"""
        return await self.get_repair_steps("general", device_category or "general", device_model)
    
    async def _get_sources(
        self,
        query: str,
        device_category: Optional[str]
    ) -> List[Dict[str, str]]:
        """Get source documents"""
        # TODO: Query vector database or knowledge base for relevant documents
        return []
    
    async def search_knowledge_base(
        self,
        search_term: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Search knowledge base articles"""
        # Placeholder - in production, use vector search
        return []

    def _retrieve_docs(self, db, query: str, role: Optional[str], limit: int = 4) -> List[AIKnowledgeBase]:
        docs = db.query(AIKnowledgeBase).filter(AIKnowledgeBase.is_active == True)
        if role:
            docs = docs.filter((AIKnowledgeBase.role == None) | (AIKnowledgeBase.role == role))
        docs = docs.all()
        if not docs:
            return []

        query_vec = self._vectorize(query)
        scored = []
        for doc in docs:
            doc_vec = self._vectorize(f"{doc.title} {doc.content}")
            score = self._cosine_similarity(query_vec, doc_vec)
            scored.append((score, doc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for score, d in scored[:limit] if score > 0]

    def _vectorize(self, text: str) -> Dict[str, float]:
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        tf = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        return tf

    def _cosine_similarity(self, v1: Dict[str, float], v2: Dict[str, float]) -> float:
        if not v1 or not v2:
            return 0.0
        dot = sum(v1.get(k, 0) * v2.get(k, 0) for k in v1)
        norm1 = math.sqrt(sum(v * v for v in v1.values()))
        norm2 = math.sqrt(sum(v * v for v in v2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

"""
Multilingual Chatbot Service
English and Hindi support for case creation, troubleshooting, and status checks
"""
from typing import Dict, List, Optional, Any
import json
import logging
from datetime import datetime
from urllib import request as urlrequest
from urllib.error import URLError, HTTPError
from urllib.parse import quote

from app.core.config import settings

logger = logging.getLogger(__name__)


class MultilingualChatbotService:
    """Multilingual chatbot service (English/Hindi)"""
    
    def __init__(self):
        self.model_version = "v1.0"
        self.supported_languages = ["en", "hi"]
        # In production, use multilingual LLM or translation + LLM
    
    async def process_message(
        self,
        message: str,
        user_id: Optional[int] = None,
        session_id: str = "",
        language: str = "en",
        context: Optional[Dict] = None,
        history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Process user message and return response
        
        Args:
            message: User's message
            user_id: Optional user ID
            session_id: Chat session ID
            language: Language code (en, hi)
            context: Additional context (device info, ticket history, etc.)
        
        Returns:
            Dict with response, intent, entities, actions
        """
        try:
            # Detect intent
            intent = await self._detect_intent(message, language)
            
            # Extract entities
            entities = await self._extract_entities(message, language)
            
            if context is None:
                context = {"message": message}
            # Generate response
            response = await self._generate_response(intent, entities, language, context, history=history)
            
            # Determine actions
            actions = await self._determine_actions(intent, entities, context)
            
            return {
                "response": response,
                "intent": intent,
                "entities": entities,
                "actions": actions,
                "language": language,
                "session_id": session_id,
                "confidence": 0.85
            }
        except Exception as e:
            logger.error(f"Error in chatbot: {str(e)}")
            return {
                "response": self._get_error_message(language),
                "intent": "error",
                "entities": {},
                "actions": [],
                "language": language,
                "error": str(e)
            }
    
    async def _detect_intent(self, message: str, language: str) -> str:
        """Detect user intent"""
        # TODO: Integrate intent classification model
        # Use trained NLP model for intent detection
        return "general_inquiry"
    
    async def _extract_entities(self, message: str, language: str) -> Dict[str, Any]:
        """Extract entities (device, issue, date, etc.)"""
        # TODO: Integrate Named Entity Recognition (NER) model
        # Use spaCy, Transformers, or custom NER model
        return {
            "device_type": None,
            "issue": None,
            "date": None,
            "time": None
        }
    
    def _chatbot_system_instruction(self, language: str) -> str:
        return (
            "You are eRepairing's in-app customer support assistant for home appliance and device repair "
            "(AC, fridge, washing machine, TV, etc.).\n"
            "Rules:\n"
            "- Only answer questions about repairs, tickets, visits, devices, warranty, rescheduling, and how to use the eRepairing customer app.\n"
            "- If the user asks about anything else, reply in one short sentence that you only help with repair and service on eRepairing.\n"
            "- Stay factual and relevant. Do not invent ticket numbers, order IDs, or policy details.\n"
            "- Be brief: at most ~100 words unless the user explicitly asks for a longer explanation. Prefer short paragraphs or bullets.\n"
            f"- Preferred language code: {language}. Match the user's language (English or Hindi) in your reply.\n"
            "- Plain text only; avoid markdown headings unless necessary."
        )

    def _try_gemini_response(
        self,
        user_message: str,
        language: str,
        context: Optional[Dict],
        history: Optional[List[Dict[str, str]]],
    ) -> Optional[str]:
        """Call Google Gemini when GEMINI_API_KEY is set (preferred for chatbot)."""
        api_key = (settings.GEMINI_API_KEY or "").strip()
        if not api_key:
            return None
        model = (settings.GEMINI_MODEL or "gemini-2.0-flash").strip()
        system_text = self._chatbot_system_instruction(language)
        ctx_line = ""
        if context:
            safe_ctx = {k: v for k, v in context.items() if k in ("ticket_id", "device_id", "user_id") and v is not None}
            if safe_ctx:
                ctx_line = f"\n[App context: {json.dumps(safe_ctx)}]\n"

        contents: List[Dict[str, Any]] = []
        if history:
            for item in history[-8:]:
                role = item.get("role") or "user"
                text = (item.get("text") or "").strip()
                if not text:
                    continue
                gemini_role = "model" if role == "assistant" else "user"
                contents.append({"role": gemini_role, "parts": [{"text": text}]})
        final_user = f"{ctx_line}{user_message}".strip() if ctx_line else user_message
        contents.append({"role": "user", "parts": [{"text": final_user}]})

        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{quote(model, safe='')}:generateContent?key={quote(api_key, safe='')}"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system_text}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.25,
                "maxOutputTokens": 384,
                "topP": 0.95,
            },
        }
        try:
            req = urlrequest.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlrequest.urlopen(req, timeout=25) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            candidates = payload.get("candidates") or []
            if not candidates:
                logger.warning("Gemini chatbot: empty candidates")
                return None
            parts = (candidates[0].get("content") or {}).get("parts") or []
            texts = [p.get("text", "") for p in parts if isinstance(p, dict)]
            out = "".join(texts).strip()
            return out or None
        except HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="replace")
                logger.warning("Gemini chatbot HTTPError: %s %s", e.code, err_body[:500])
            except Exception:
                logger.warning("Gemini chatbot HTTPError: %s", e)
            return None
        except (URLError, TimeoutError, ValueError, json.JSONDecodeError, KeyError, IndexError) as e:
            logger.warning("Gemini chatbot error: %s", e)
            return None

    async def _generate_response(
        self,
        intent: str,
        entities: Dict,
        language: str,
        context: Optional[Dict],
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Generate response based on intent"""
        latest = (context.get("message") if context else None) or ""

        gemini_text = self._try_gemini_response(
            user_message=latest,
            language=language,
            context=context,
            history=history,
        )
        if gemini_text:
            return gemini_text

        if settings.OPENAI_API_KEY:
            try:
                import requests
                messages = [
                    {
                        "role": "system",
                        "content": self._chatbot_system_instruction(language),
                    }
                ]
                if history:
                    for item in history[-6:]:
                        role = "assistant" if item.get("role") == "assistant" else "user"
                        messages.append({"role": role, "content": item.get("text", "")})
                messages.append({"role": "user", "content": latest})
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 400,
                }
                resp = requests.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.OPENAI_API_KEY}"},
                    json=payload,
                    timeout=10
                )
                data = resp.json()
                if resp.ok:
                    return data["choices"][0]["message"]["content"]
            except Exception:
                pass

        responses = {
            "en": {
                "create_ticket": "I can help you create a repair ticket. Please describe the issue with your device.",
                "check_status": "Let me check the status of your ticket. One moment...",
                "reschedule": "I can help you reschedule your service visit. What date and time would work for you?",
                "troubleshooting": "I can help troubleshoot your issue. Let me provide some steps...",
                "general_inquiry": "How can I assist you today?",
            },
            "hi": {
                "create_ticket": "मैं आपकी मरम्मत टिकट बनाने में मदद कर सकता हूं। कृपया अपने उपकरण की समस्या का वर्णन करें।",
                "check_status": "मैं आपकी टिकट की स्थिति जांच रहा हूं। एक क्षण...",
                "reschedule": "मैं आपकी सेवा यात्रा को पुनर्निर्धारित करने में मदद कर सकता हूं। आपके लिए कौन सी तारीख और समय काम करेगा?",
                "troubleshooting": "मैं आपकी समस्या का निवारण करने में मदद कर सकता हूं। मुझे कुछ चरण प्रदान करने दें...",
                "general_inquiry": "मैं आज आपकी कैसे सहायता कर सकता हूं?",
            }
        }
        
        if history:
            recent = " ".join([h.get("text", "") for h in history[-3:]])
            if "status" in recent.lower() and intent == "general_inquiry":
                intent = "check_status"
        return responses.get(language, responses["en"]).get(intent, responses["en"]["general_inquiry"])
    
    async def _determine_actions(
        self,
        intent: str,
        entities: Dict,
        context: Optional[Dict]
    ) -> List[Dict[str, Any]]:
        """Determine actions to take"""
        actions = []
        
        if intent == "create_ticket":
            actions.append({
                "type": "create_ticket",
                "params": entities
            })
        elif intent == "check_status":
            if context and context.get("ticket_id"):
                actions.append({
                    "type": "fetch_ticket_status",
                    "params": {"ticket_id": context["ticket_id"]}
                })
        
        return actions
    
    def _get_error_message(self, language: str) -> str:
        """Get error message in appropriate language"""
        messages = {
            "en": "I'm sorry, I didn't understand that. Could you please rephrase?",
            "hi": "मुझे खेद है, मैं समझ नहीं पाया। क्या आप कृपया इसे फिर से कह सकते हैं?"
        }
        return messages.get(language, messages["en"])


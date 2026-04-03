"""
Multilingual Chatbot Service
English and Hindi support for case creation, troubleshooting, and status checks
"""
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

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
    
    async def _generate_response(
        self,
        intent: str,
        entities: Dict,
        language: str,
        context: Optional[Dict],
        history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Generate response based on intent"""
        if settings.OPENAI_API_KEY:
            try:
                import requests
                messages = [{"role": "system", "content": "You are a helpful support chatbot."}]
                if history:
                    for item in history[-6:]:
                        role = "assistant" if item.get("role") == "assistant" else "user"
                        messages.append({"role": role, "content": item.get("text", "")})
                messages.append({"role": "user", "content": context.get("message") if context and context.get("message") else ""})
                messages.append({"role": "user", "content": "Respond to the latest user message."})
                payload = {
                    "model": "gpt-4o-mini",
                    "messages": messages,
                    "temperature": 0.3
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


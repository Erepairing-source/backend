"""
AI Case Triage Service
Analyzes ticket text and images to suggest issue category, priority, and likely parts
"""
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class CaseTriageService:
    """AI-powered case triage service"""
    
    def __init__(self):
        self.model_version = "v1.0"
        self._last_description = ""  # Store last description for priority analysis
        # In production, load actual ML models here
        # self.text_classifier = load_model("models/case_triage_text.pkl")
        # self.image_classifier = load_model("models/case_triage_image.pkl")
    
    async def triage_ticket(
        self,
        issue_description: str,
        issue_photos: Optional[List[str]] = None,
        device_category: Optional[str] = None,
        device_model: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Triage a ticket and return suggested category, priority, and parts
        
        Args:
            issue_description: Text description of the issue
            issue_photos: List of photo URLs
            device_category: Product category (AC, Washing Machine, etc.)
            device_model: Specific model number
        
        Returns:
            Dict with suggested_category, suggested_priority, confidence_score, suggested_parts
        """
        try:
            # Store original text for priority analysis
            self._last_description = issue_description
            
            # Combine text and image analysis
            text_result = await self._analyze_text(issue_description, device_category)
            image_result = await self._analyze_images(issue_photos) if issue_photos else {}
            
            # Merge results with weighted confidence
            category = self._merge_category(text_result, image_result)
            priority = self._determine_priority(text_result, image_result, device_category)
            parts = self._suggest_parts(category, device_category, device_model)
            key_symptoms = self._extract_key_symptoms(issue_description)
            summary = self._build_summary(issue_description, category, priority)
            
            return {
                "suggested_category": category,
                "suggested_priority": priority,
                "confidence_score": self._calculate_confidence(text_result, image_result),
                "suggested_parts": parts,
                "key_symptoms": key_symptoms,
                "summary": summary,
                "model_version": self.model_version,
                "processing_time_ms": 0
            }
        except Exception as e:
            logger.error(f"Error in case triage: {str(e)}")
            # Return safe defaults
            return {
                "suggested_category": "general",
                "suggested_priority": "medium",
                "confidence_score": 0.5,
                "suggested_parts": [],
                "key_symptoms": [],
                "summary": "General issue reported.",
                "model_version": self.model_version,
                "processing_time_ms": 0
            }
    
    async def _analyze_text(self, text: str, device_category: Optional[str]) -> Dict[str, Any]:
        """Analyze text description using NLP"""
        text_lower = text.lower()
        
        # Enhanced keyword-based category detection with more keywords
        category_keywords = {
            "cooling": ["not cooling", "not cold", "warm", "hot air", "cooling issue", "temperature", "ac not working", "ac not cooling", "air conditioner", "cooling problem", "not cool", "warm air", "heat", "hot"],
            "heating": ["not heating", "cold", "heating issue", "heater not working", "not hot", "heater problem", "warm water", "geyser"],
            "water": ["water leak", "leaking", "water issue", "drain", "overflow", "water not coming", "leak", "dripping", "water problem", "water leak", "water coming", "water flowing"],
            "noise": ["noise", "sound", "loud", "vibration", "rattling", "buzzing", "humming", "grinding", "screeching", "whistling", "clicking"],
            "power": ["not starting", "not turning on", "power issue", "electrical", "fuse", "circuit", "not powering", "switch", "button", "on/off", "power supply", "no power", "electrical fault"],
            "display": ["screen", "display", "blank", "flickering", "no picture", "image issue", "tv", "monitor", "picture", "video"],
            "washing": ["not washing", "washing issue", "spin", "drain", "detergent", "washing machine", "washer", "clothes", "laundry"],
            "refrigeration": ["not cooling", "freezer", "refrigerator", "food spoiling", "fridge", "freezing", "ice"],
            "installation": ["install", "setup", "mounting", "connection", "fitting", "mount"],
            "maintenance": ["service", "maintenance", "cleaning", "checkup", "repair", "fix"],
            "filter": ["filter", "air filter", "dirty", "clogged", "replace filter"],
            "remote": ["remote", "remote control", "not responding", "remote not working"],
            "smell": ["smell", "odor", "bad smell", "stinking", "foul smell"]
        }
        
        detected_category = None
        confidence = 0.0
        keywords_found = 0
        best_matches = 0
        
        for category, keywords in category_keywords.items():
            matches = sum(1 for keyword in keywords if keyword in text_lower)
            if matches > 0:
                keywords_found += matches
                # Calculate confidence based on matches and text length
                # More matches = higher confidence, but also consider text length
                match_ratio = min(matches / max(len(keywords), 1), 1.0)
                text_length_factor = min(len(text_lower) / 100, 0.3)  # Boost for longer descriptions
                # Base confidence from matches, boost from text length
                category_confidence = min(match_ratio * 0.7 + text_length_factor + 0.1, 0.9)
                
                if matches > best_matches or (matches == best_matches and category_confidence > confidence):
                    best_matches = matches
                    confidence = category_confidence
                    detected_category = category
        
        # If no category found, use device category or default
        if not detected_category:
            if device_category:
                detected_category = device_category.lower().replace(" ", "_")
                confidence = 0.4
            else:
                # Try to infer from common words
                if any(word in text_lower for word in ["ac", "air conditioner", "cooling"]):
                    detected_category = "cooling"
                    confidence = 0.5
                elif any(word in text_lower for word in ["washing", "washer", "laundry"]):
                    detected_category = "washing"
                    confidence = 0.5
                elif any(word in text_lower for word in ["fridge", "refrigerator", "freezer"]):
                    detected_category = "refrigeration"
                    confidence = 0.5
                else:
                    detected_category = "general"
                    confidence = 0.3
        
        return {
            "category": detected_category,
            "confidence": confidence,
            "keywords_found": keywords_found
        }
    
    async def _analyze_images(self, image_urls: List[str]) -> Dict[str, Any]:
        """Analyze images using computer vision"""
        # Placeholder - in production, use image classification models
        # For now, return default
        return {
            "category": None,
            "confidence": 0.0,
            "damage_detected": False
        }
    
    def _merge_category(self, text_result: Dict, image_result: Dict) -> str:
        """Merge text and image analysis results"""
        text_category = text_result.get("category")
        image_category = image_result.get("category")
        text_conf = text_result.get("confidence", 0.0)
        image_conf = image_result.get("confidence", 0.0)
        
        # Prefer text category if it has reasonable confidence
        if text_category and text_conf > 0.3:
            return text_category
        if image_category and image_conf > text_conf:
            return image_category
        if text_category:
            return text_category
        if image_category:
            return image_category
        return "general"
    
    def _determine_priority(
        self,
        text_result: Dict,
        image_result: Dict,
        device_category: Optional[str]
    ) -> str:
        """Determine ticket priority based on keywords and context"""
        # Use stored description if available
        text_lower = getattr(self, '_last_description', '').lower()
        category = text_result.get("category", "")
        text_confidence = text_result.get("confidence", 0.0)
        
        # If confidence is very low, be conservative with priority
        if text_confidence < 0.3 and category == "general":
            return "medium"  # Default to medium for low-confidence cases
        
        # Urgent keywords - safety and critical issues (only if text is substantial)
        urgent_keywords = ["emergency", "urgent", "critical", "fire", "smoke", "sparking", "burning", "dangerous", "safety", "electrical shock", "sparks", "burning smell"]
        
        # High priority - device not functioning
        high_keywords = ["completely broken", "not starting", "not turning on", "not functioning", "stopped working", "wont start", "wont turn on", "dead"]
        
        # Medium-high - functional issues (more specific)
        medium_high_keywords = ["not working", "leak", "water", "overflow", "damage", "fault", "problem", "issue", "not cooling", "not heating"]
        
        # Low priority - informational/maintenance
        low_keywords = ["question", "inquiry", "information", "maintenance", "service", "checkup", "routine", "cleaning", "filter", "how to", "what is"]
        
        # Check text for priority keywords (only if we have reasonable text)
        if text_lower and len(text_lower) > 5:
            if any(keyword in text_lower for keyword in urgent_keywords):
                return "urgent"
            elif any(keyword in text_lower for keyword in high_keywords):
                return "high"
            elif any(keyword in text_lower for keyword in medium_high_keywords):
                return "high"
            elif any(keyword in text_lower for keyword in low_keywords):
                return "low"
        
        # Fallback to category-based priority (only if category is detected with confidence)
        if text_confidence > 0.3:
            if category in ["power", "cooling", "heating", "water"]:
                return "high"
            elif category in ["noise", "display", "washing", "refrigeration"]:
                return "medium"
            elif category in ["maintenance", "installation", "filter"]:
                return "low"
        
        # Default to medium for uncertain cases
        return "medium"

    def _extract_key_symptoms(self, text: str) -> List[str]:
        text_lower = text.lower()
        symptom_keywords = [
            "not cooling", "leak", "noise", "vibration", "no power",
            "not turning on", "smell", "error code", "screen", "flicker",
            "drain", "overheat", "sparks"
        ]
        return [kw for kw in symptom_keywords if kw in text_lower][:5]

    def _build_summary(self, text: str, category: str, priority: str) -> str:
        trimmed = text.strip().replace("\n", " ")
        if len(trimmed) > 160:
            trimmed = trimmed[:160] + "..."
        return f"Category: {category}. Priority: {priority}. Summary: {trimmed}"
    
    def _suggest_parts(
        self,
        category: str,
        device_category: Optional[str],
        device_model: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Suggest likely parts based on category"""
        # TODO: Query database for historical part usage patterns
        # Use ML model trained on ticket -> parts used data
        return []
    
    def _calculate_confidence(self, text_result: Dict, image_result: Dict) -> float:
        """Calculate overall confidence score"""
        text_conf = text_result.get("confidence", 0.3)
        image_conf = image_result.get("confidence", 0.0)
        keywords_found = text_result.get("keywords_found", 0)
        
        # Boost confidence if multiple keywords found
        if keywords_found > 0:
            keyword_boost = min(keywords_found * 0.1, 0.3)
            text_conf = min(text_conf + keyword_boost, 0.95)
        
        # Weighted average (text is more reliable)
        if image_conf > 0:
            return min((text_conf * 0.7) + (image_conf * 0.3), 0.95)
        return min(text_conf, 0.95)


"""
Customer Self-Diagnosis Service
Asks guided questions and returns likely issue + suggested parts.
"""
from typing import Dict, List, Any, Optional


DEFAULT_QUESTIONS = [
    {
        "id": "power_on",
        "question": "Does the device power on?",
        "options": ["yes", "no", "sometimes"]
    },
    {
        "id": "noise",
        "question": "Do you hear unusual noise or vibration?",
        "options": ["yes", "no"]
    },
    {
        "id": "leak",
        "question": "Is there any leakage or smell?",
        "options": ["yes", "no"]
    },
    {
        "id": "performance",
        "question": "Is the device performance reduced (cooling/heating/washing)?",
        "options": ["yes", "no", "not_sure"]
    },
    {
        "id": "display",
        "question": "Are there display or error-code issues?",
        "options": ["yes", "no", "not_applicable"]
    }
]


class SelfDiagnosisService:
    """Guided self-diagnosis"""

    def get_questions(self, device_category: Optional[str] = None) -> List[Dict[str, Any]]:
        return DEFAULT_QUESTIONS

    def assess(self, answers: Dict[str, str]) -> Dict[str, Any]:
        signals = []
        if answers.get("power_on") in ["no", "sometimes"]:
            signals.append("power")
        if answers.get("noise") == "yes":
            signals.append("noise")
        if answers.get("leak") == "yes":
            signals.append("leak")
        if answers.get("performance") == "yes":
            signals.append("performance")
        if answers.get("display") == "yes":
            signals.append("display")

        likely_issue = "general"
        if "power" in signals:
            likely_issue = "power_issue"
        elif "leak" in signals:
            likely_issue = "leak_issue"
        elif "performance" in signals:
            likely_issue = "performance_issue"
        elif "display" in signals:
            likely_issue = "display_issue"
        elif "noise" in signals:
            likely_issue = "noise_issue"

        confidence = 0.4 + (0.1 * len(signals))
        confidence = round(min(confidence, 0.9), 2)

        likely_fix = {
            "power_issue": "Check power supply, adapter, and internal fuse.",
            "leak_issue": "Inspect seals/hoses and drainage.",
            "performance_issue": "Clean filters and check airflow/components.",
            "display_issue": "Inspect display cable and module.",
            "noise_issue": "Check loose parts and moving components."
        }.get(likely_issue, "Run basic diagnostics and inspect the device.")

        return {
            "likely_issue": likely_issue,
            "confidence": confidence,
            "signals": signals,
            "likely_fix": likely_fix
        }

    def suggest_parts(self, signals: List[str]) -> List[str]:
        mapping = {
            "power": ["power cable", "power adapter", "power module"],
            "leak": ["hose", "seal", "drain pump"],
            "performance": ["filter", "fan", "compressor"],
            "display": ["display cable", "display panel"],
            "noise": ["fan", "motor", "bearing"]
        }
        parts = []
        for signal in signals:
            parts.extend(mapping.get(signal, []))
        return list(dict.fromkeys(parts))[:3]
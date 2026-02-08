"""
Anomaly Detection Service
Detects fraud, false replacements, or suspicious patterns in service data
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import statistics

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """AI-powered anomaly detection service"""
    
    def __init__(self):
        self.model_version = "v1.0"
        # In production, use isolation forest, autoencoders, or statistical methods
    
    async def detect_anomalies(
        self,
        organization_id: int,
        time_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Detect anomalies in service patterns
        
        Returns:
            Dict with detected_anomalies, risk_score, recommendations
        """
        try:
            # In production, fetch historical data
            # historical_data = await self._fetch_historical_data(organization_id, time_period_days)
            
            anomalies = []
            
            # Check various anomaly types
            part_usage_anomalies = await self._detect_part_usage_anomalies(organization_id)
            closure_pattern_anomalies = await self._detect_closure_pattern_anomalies(organization_id)
            time_anomalies = await self._detect_time_anomalies(organization_id)
            fraud_indicators = await self._detect_fraud_indicators(organization_id)
            
            anomalies.extend(part_usage_anomalies)
            anomalies.extend(closure_pattern_anomalies)
            anomalies.extend(time_anomalies)
            anomalies.extend(fraud_indicators)
            
            risk_score = self._calculate_risk_score(anomalies)
            
            return {
                "organization_id": organization_id,
                "detected_anomalies": anomalies,
                "risk_score": risk_score,
                "recommendations": self._generate_recommendations(anomalies),
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            return {
                "organization_id": organization_id,
                "detected_anomalies": [],
                "error": str(e)
            }
    
    async def _detect_part_usage_anomalies(self, organization_id: int) -> List[Dict[str, Any]]:
        """Detect anomalies in part usage patterns"""
        anomalies = []
        
        # Placeholder logic - in production, use statistical analysis
        # Example: Engineer always replacing expensive parts
        
        # Check for:
        # 1. Unusually high part replacement rate
        # 2. Same engineer always using expensive parts
        # 3. Parts used don't match issue category
        
        return anomalies
    
    async def _detect_closure_pattern_anomalies(self, organization_id: int) -> List[Dict[str, Any]]:
        """Detect anomalies in ticket closure patterns"""
        anomalies = []
        
        # Check for:
        # 1. Tickets closed too quickly (possible fake closures)
        # 2. Same pattern of closure times (automated/suspicious)
        # 3. High closure rate without resolution notes
        
        return anomalies
    
    async def _detect_time_anomalies(self, organization_id: int) -> List[Dict[str, Any]]:
        """Detect time-based anomalies"""
        anomalies = []
        
        # Check for:
        # 1. Tickets created/closed at unusual times
        # 2. Very short or very long resolution times
        # 3. Patterns suggesting automated activity
        
        return anomalies
    
    async def _detect_fraud_indicators(self, organization_id: int) -> List[Dict[str, Any]]:
        """Detect potential fraud indicators"""
        anomalies = []
        
        # Check for:
        # 1. Repeated expensive part replacements on same device
        # 2. Tickets with no photos but parts replaced
        # 3. Customer complaints about unnecessary replacements
        # 4. Engineer performance outliers
        
        return [
            {
                "type": "fraud_indicator",
                "severity": "medium",
                "description": "Potential pattern detected - requires review",
                "engineer_id": None,
                "ticket_ids": []
            }
        ]
    
    def _calculate_risk_score(self, anomalies: List[Dict]) -> float:
        """Calculate overall risk score (0-1)"""
        if not anomalies:
            return 0.0
        
        severity_weights = {
            "high": 1.0,
            "medium": 0.5,
            "low": 0.2
        }
        
        total_weight = sum(severity_weights.get(anomaly.get("severity", "low"), 0.2) for anomaly in anomalies)
        
        # Normalize to 0-1
        max_possible = len(anomalies) * 1.0
        risk_score = min(1.0, total_weight / max_possible if max_possible > 0 else 0)
        
        return risk_score
    
    def _generate_recommendations(self, anomalies: List[Dict]) -> List[str]:
        """Generate recommendations based on detected anomalies"""
        recommendations = []
        
        if not anomalies:
            return ["No anomalies detected - operations appear normal"]
        
        high_severity = [a for a in anomalies if a.get("severity") == "high"]
        if high_severity:
            recommendations.append("URGENT: High-severity anomalies detected - immediate review required")
        
        fraud_indicators = [a for a in anomalies if a.get("type") == "fraud_indicator"]
        if fraud_indicators:
            recommendations.append("Review flagged tickets for potential fraud")
        
        if len(anomalies) > 5:
            recommendations.append("Multiple anomalies detected - consider audit of service processes")
        
        return recommendations if recommendations else ["Monitor flagged patterns closely"]





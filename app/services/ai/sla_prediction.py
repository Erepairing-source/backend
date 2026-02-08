"""
SLA Breach Prediction Service
Predicts which tickets are at risk of SLA breach
"""
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone
import logging

logger = logging.getLogger(__name__)


class SLABreachPredictionService:
    """AI-powered SLA breach prediction service"""
    
    def __init__(self):
        self.model_version = "v1.0"
        # In production, use time series or classification models
    
    async def predict_breach_risk(
        self,
        ticket_id: int,
        current_status: str,
        sla_deadline: datetime,
        created_at: datetime,
        assigned_at: Optional[datetime] = None,
        historical_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Predict SLA breach risk for a ticket
        
        Returns:
            Dict with breach_risk (0-1), predicted_resolution_time, recommendations
        """
        try:
            now = datetime.now(timezone.utc)
            # Ensure sla_deadline is timezone-aware
            deadline = sla_deadline
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=timezone.utc)
            else:
                deadline = deadline.astimezone(timezone.utc)
            time_remaining = (deadline - now).total_seconds() / 3600  # hours
            
            # Calculate risk factors
            risk_factors = await self._calculate_risk_factors(
                current_status,
                time_remaining,
                created_at,
                assigned_at,
                historical_data
            )
            
            breach_risk = self._calculate_breach_risk(risk_factors, time_remaining)
            predicted_resolution_time = await self._predict_resolution_time(
                current_status,
                historical_data
            )
            
            recommendations = self._generate_recommendations(breach_risk, risk_factors)
            
            return {
                "ticket_id": ticket_id,
                "breach_risk": breach_risk,
                "time_remaining_hours": time_remaining,
                "predicted_resolution_time_hours": predicted_resolution_time,
                "risk_factors": risk_factors,
                "recommendations": recommendations,
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in SLA breach prediction: {str(e)}")
            return {
                "ticket_id": ticket_id,
                "breach_risk": 0.5,
                "error": str(e)
            }
    
    async def _calculate_risk_factors(
        self,
        status: str,
        time_remaining: float,
        created_at: datetime,
        assigned_at: Optional[datetime],
        historical_data: Optional[Dict]
    ) -> Dict[str, float]:
        """Calculate various risk factors"""
        factors = {}
        
        # Time pressure
        factors["time_pressure"] = max(0, min(1, 1 - (time_remaining / 24)))  # High if < 24h
        
        # Status risk
        status_risks = {
            "created": 0.8,
            "assigned": 0.5,
            "in_progress": 0.3,
            "waiting_parts": 0.9,
            "resolved": 0.0,
            "closed": 0.0
        }
        factors["status_risk"] = status_risks.get(status, 0.5)
        
        # Assignment delay
        if assigned_at:
            # Ensure both datetimes are timezone-aware
            assigned = assigned_at
            created = created_at
            if assigned.tzinfo is None:
                assigned = assigned.replace(tzinfo=timezone.utc)
            else:
                assigned = assigned.astimezone(timezone.utc)
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            else:
                created = created.astimezone(timezone.utc)
            delay_hours = (assigned - created).total_seconds() / 3600
            factors["assignment_delay"] = min(1.0, delay_hours / 48)  # Normalize to 48h
        else:
            factors["assignment_delay"] = 1.0  # Not assigned = high risk
        
        # Historical performance (if available)
        if historical_data:
            avg_resolution_time = historical_data.get("avg_resolution_hours", 24)
            factors["historical_risk"] = min(1.0, avg_resolution_time / time_remaining)
        else:
            factors["historical_risk"] = 0.5
        
        return factors
    
    def _calculate_breach_risk(self, risk_factors: Dict, time_remaining: float) -> float:
        """Calculate overall breach risk (0-1)"""
        # Weighted average of risk factors
        weights = {
            "time_pressure": 0.3,
            "status_risk": 0.3,
            "assignment_delay": 0.2,
            "historical_risk": 0.2
        }
        
        risk = sum(risk_factors.get(factor, 0) * weight for factor, weight in weights.items())
        
        # Time remaining penalty
        if time_remaining < 0:
            risk = 1.0  # Already breached
        elif time_remaining < 4:
            risk = min(1.0, risk + 0.3)  # Critical time
        
        return max(0.0, min(1.0, risk))
    
    async def _predict_resolution_time(
        self,
        status: str,
        historical_data: Optional[Dict]
    ) -> float:
        """Predict remaining resolution time in hours"""
        # Base estimates by status
        base_times = {
            "created": 12.0,
            "assigned": 8.0,
            "in_progress": 4.0,
            "waiting_parts": 24.0,
            "resolved": 0.0
        }
        
        base_time = base_times.get(status, 6.0)
        
        # Adjust based on historical data
        if historical_data:
            avg_time = historical_data.get("avg_resolution_hours", base_time)
            return (base_time + avg_time) / 2
        
        return base_time
    
    def _generate_recommendations(
        self,
        breach_risk: float,
        risk_factors: Dict
    ) -> List[str]:
        """Generate recommendations to reduce breach risk"""
        recommendations = []
        
        if breach_risk > 0.7:
            recommendations.append("URGENT: High risk of SLA breach - escalate immediately")
        
        if risk_factors.get("assignment_delay", 0) > 0.5:
            recommendations.append("Assign ticket to available engineer immediately")
        
        if risk_factors.get("status_risk", 0) > 0.7:
            if "waiting_parts" in str(risk_factors):
                recommendations.append("Expedite parts procurement or find alternative solution")
            else:
                recommendations.append("Escalate to senior engineer or manager")
        
        if risk_factors.get("time_pressure", 0) > 0.8:
            recommendations.append("Consider extending SLA or providing customer update")
        
        if not recommendations:
            recommendations.append("Monitor ticket closely")
        
        return recommendations





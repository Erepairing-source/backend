"""
Predictive Technician Load Balancer Service
Optimizes workload distribution to prevent burnout and balance efficiency
"""
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class LoadBalancerService:
    """AI-powered load balancing service for technicians"""
    
    def __init__(self):
        self.model_version = "v1.0"
    
    async def balance_workload(
        self,
        engineers: List[Dict[str, Any]],
        pending_tickets: List[Dict[str, Any]],
        constraints: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Balance workload across engineers
        
        Returns:
            Dict with assignments, balance_score, recommendations
        """
        try:
            # Calculate current loads
            engineer_loads = {eng["id"]: self._calculate_current_load(eng) for eng in engineers}
            
            # Score each engineer-ticket pair
            assignments = {}
            unassigned_tickets = []
            
            for ticket in pending_tickets:
                best_engineer = await self._find_best_engineer_for_ticket(
                    ticket,
                    engineers,
                    engineer_loads,
                    constraints
                )
                
                if best_engineer:
                    if best_engineer["id"] not in assignments:
                        assignments[best_engineer["id"]] = []
                    assignments[best_engineer["id"]].append(ticket["id"])
                    engineer_loads[best_engineer["id"]] += self._estimate_ticket_effort(ticket)
                else:
                    unassigned_tickets.append(ticket["id"])
            
            balance_score = self._calculate_balance_score(engineer_loads)
            recommendations = self._generate_recommendations(engineer_loads, assignments)
            
            return {
                "assignments": assignments,
                "unassigned_tickets": unassigned_tickets,
                "engineer_loads": engineer_loads,
                "balance_score": balance_score,
                "recommendations": recommendations,
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in load balancing: {str(e)}")
            return {
                "assignments": {},
                "error": str(e)
            }
    
    def _calculate_current_load(self, engineer: Dict[str, Any]) -> float:
        """Calculate current workload for an engineer"""
        # Base load from active tickets
        active_tickets = engineer.get("active_tickets", 0)
        
        # Weight by ticket complexity/priority
        high_priority = engineer.get("high_priority_tickets", 0)
        medium_priority = engineer.get("medium_priority_tickets", 0)
        low_priority = engineer.get("low_priority_tickets", 0)
        
        # Weighted load
        load = (
            high_priority * 3.0 +
            medium_priority * 2.0 +
            low_priority * 1.0
        )
        
        # Factor in availability
        if not engineer.get("is_available", True):
            load += 100.0  # Penalty for unavailable
        
        return load
    
    async def _find_best_engineer_for_ticket(
        self,
        ticket: Dict[str, Any],
        engineers: List[Dict[str, Any]],
        current_loads: Dict[int, float],
        constraints: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Find best engineer for a ticket considering load balance"""
        candidates = []
        
        for engineer in engineers:
            # Check constraints
            if not self._meets_constraints(engineer, ticket, constraints):
                continue
            
            # Calculate score
            score = 0.0
            
            # Load balance (prefer less loaded engineers)
            engineer_load = current_loads.get(engineer["id"], 0)
            avg_load = sum(current_loads.values()) / len(current_loads) if current_loads else 0
            if engineer_load < avg_load:
                score += 50.0  # Bonus for underloaded
            
            # Skill match
            if engineer.get("skills") and ticket.get("required_skills"):
                matching_skills = set(engineer["skills"]) & set(ticket["required_skills"])
                score += len(matching_skills) * 20.0
            
            # Location proximity
            if engineer.get("location") and ticket.get("location"):
                distance = self._calculate_distance(engineer["location"], ticket["location"])
                score += 30.0 / (1 + distance)  # Closer = better
            
            # Availability
            if engineer.get("is_available", False):
                score += 20.0
            
            candidates.append((score, engineer))
        
        if not candidates:
            return None
        
        candidates.sort(reverse=True, key=lambda x: x[0])
        return candidates[0][1]
    
    def _meets_constraints(
        self,
        engineer: Dict[str, Any],
        ticket: Dict[str, Any],
        constraints: Optional[Dict]
    ) -> bool:
        """Check if engineer meets ticket constraints"""
        if not constraints:
            return True
        
        # Location constraint
        if constraints.get("required_city_id"):
            if engineer.get("city_id") != constraints["required_city_id"]:
                return False
        
        # Skill constraint
        if constraints.get("required_skills"):
            if not set(engineer.get("skills", [])) & set(constraints["required_skills"]):
                return False
        
        return True
    
    def _estimate_ticket_effort(self, ticket: Dict[str, Any]) -> float:
        """Estimate effort required for a ticket"""
        base_effort = 1.0
        
        # Priority multiplier
        priority_multipliers = {
            "urgent": 2.0,
            "high": 1.5,
            "medium": 1.0,
            "low": 0.7
        }
        priority = ticket.get("priority", "medium")
        base_effort *= priority_multipliers.get(priority, 1.0)
        
        # Complexity (based on issue category)
        if ticket.get("issue_category") in ["complex", "multi_part"]:
            base_effort *= 1.5
        
        return base_effort
    
    def _calculate_balance_score(self, engineer_loads: Dict[int, float]) -> float:
        """Calculate load balance score (0-1, higher is better)"""
        if not engineer_loads:
            return 0.0
        
        loads = list(engineer_loads.values())
        if not loads:
            return 0.0
        
        avg_load = sum(loads) / len(loads)
        if avg_load == 0:
            return 1.0
        
        # Calculate coefficient of variation (lower = more balanced)
        variance = sum((load - avg_load) ** 2 for load in loads) / len(loads)
        std_dev = variance ** 0.5
        cv = std_dev / avg_load if avg_load > 0 else 0
        
        # Convert to score (0-1)
        balance_score = 1.0 / (1 + cv)
        
        return balance_score
    
    def _generate_recommendations(
        self,
        engineer_loads: Dict[int, float],
        assignments: Dict[int, List]
    ) -> List[str]:
        """Generate recommendations for load balancing"""
        recommendations = []
        
        if not engineer_loads:
            return recommendations
        
        loads = list(engineer_loads.values())
        avg_load = sum(loads) / len(loads)
        max_load = max(loads)
        min_load = min(loads)
        
        if max_load > avg_load * 1.5:
            recommendations.append("Some engineers are overloaded - consider reassignment")
        
        if min_load < avg_load * 0.5 and max_load > avg_load:
            recommendations.append("Workload imbalance detected - redistribute tickets")
        
        if not recommendations:
            recommendations.append("Workload is well balanced")
        
        return recommendations
    
    def _calculate_distance(self, loc1: tuple, loc2: tuple) -> float:
        """Calculate distance between two locations (simplified)"""
        # TODO: Use haversine formula or Google Maps API for accurate distance
        return 0.0  # km


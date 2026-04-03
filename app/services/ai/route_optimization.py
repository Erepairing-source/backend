"""
Route Optimization Service
Optimizes technician routes and assignments
"""
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import logging
import math

logger = logging.getLogger(__name__)


class RouteOptimizationService:
    """AI-powered route optimization service"""
    
    def __init__(self):
        self.model_version = "v1.0"
        # In production, use TSP/VRP solvers (OR-Tools, Google Maps API)
    
    async def optimize_routes(
        self,
        engineer_id: int,
        ticket_ids: List[int],
        engineer_location: Tuple[float, float],  # (lat, lng)
        ticket_locations: Dict[int, Tuple[float, float]]
    ) -> Dict[str, Any]:
        """
        Optimize route for an engineer's assigned tickets
        
        Returns:
            Dict with optimized_order, total_distance, estimated_time
        """
        try:
            # Simple nearest-neighbor algorithm (replace with TSP solver)
            optimized_order = self._nearest_neighbor_route(
                engineer_location,
                ticket_locations
            )
            
            total_distance = self._calculate_total_distance(
                engineer_location,
                optimized_order,
                ticket_locations
            )
            
            estimated_time = self._estimate_travel_time(total_distance)
            
            return {
                "engineer_id": engineer_id,
                "optimized_order": optimized_order,
                "total_distance_km": total_distance,
                "estimated_travel_time_minutes": estimated_time,
                "savings_percentage": 0.0,
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in route optimization: {str(e)}")
            return {
                "engineer_id": engineer_id,
                "optimized_order": list(ticket_locations.keys()),
                "error": str(e)
            }
    
    async def optimize_assignments(
        self,
        tickets: List[Dict[str, Any]],
        engineers: List[Dict[str, Any]],
        constraints: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Optimize ticket assignments across multiple engineers
        
        Returns:
            Dict with assignments, load_balance_score
        """
        try:
            # Simple greedy assignment (replace with optimization algorithm)
            assignments = {}
            
            for ticket in tickets:
                best_engineer = await self._find_best_engineer(
                    ticket,
                    engineers,
                    constraints
                )
                
                if best_engineer:
                    if best_engineer["id"] not in assignments:
                        assignments[best_engineer["id"]] = []
                    assignments[best_engineer["id"]].append(ticket["id"])
            
            load_balance_score = self._calculate_load_balance(assignments, len(engineers))
            
            return {
                "assignments": assignments,
                "load_balance_score": load_balance_score,
                "model_version": self.model_version
            }
        except Exception as e:
            logger.error(f"Error in assignment optimization: {str(e)}")
            return {
                "assignments": {},
                "error": str(e)
            }
    
    def _nearest_neighbor_route(
        self,
        start_location: Tuple[float, float],
        ticket_locations: Dict[int, Tuple[float, float]]
    ) -> List[int]:
        """Nearest neighbor algorithm for route optimization"""
        if not ticket_locations:
            return []
        
        route = []
        current_location = start_location
        remaining_tickets = list(ticket_locations.keys())
        
        while remaining_tickets:
            nearest_ticket = min(
                remaining_tickets,
                key=lambda tid: self._haversine_distance(
                    current_location,
                    ticket_locations[tid]
                )
            )
            route.append(nearest_ticket)
            current_location = ticket_locations[nearest_ticket]
            remaining_tickets.remove(nearest_ticket)
        
        return route
    
    def _haversine_distance(
        self,
        loc1: Tuple[float, float],
        loc2: Tuple[float, float]
    ) -> float:
        """Calculate distance between two coordinates (Haversine formula)"""
        R = 6371  # Earth radius in km
        
        lat1, lon1 = math.radians(loc1[0]), math.radians(loc1[1])
        lat2, lon2 = math.radians(loc2[0]), math.radians(loc2[1])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c
    
    def _calculate_total_distance(
        self,
        start_location: Tuple[float, float],
        route: List[int],
        ticket_locations: Dict[int, Tuple[float, float]]
    ) -> float:
        """Calculate total distance for route"""
        if not route:
            return 0.0
        
        total = self._haversine_distance(start_location, ticket_locations[route[0]])
        
        for i in range(len(route) - 1):
            total += self._haversine_distance(
                ticket_locations[route[i]],
                ticket_locations[route[i + 1]]
            )
        
        return total
    
    def _estimate_travel_time(self, distance_km: float, avg_speed_kmh: float = 30) -> float:
        """Estimate travel time in minutes"""
        return (distance_km / avg_speed_kmh) * 60
    
    async def _find_best_engineer(
        self,
        ticket: Dict[str, Any],
        engineers: List[Dict[str, Any]],
        constraints: Optional[Dict]
    ) -> Optional[Dict[str, Any]]:
        """Find best engineer for a ticket"""
        # Score engineers based on distance, availability, skills, current load
        scored_engineers = []
        
        for engineer in engineers:
            if not engineer.get("is_available", False):
                continue
            
            score = 0.0
            
            # Distance score (closer = better)
            if engineer.get("location") and ticket.get("location"):
                distance = self._haversine_distance(
                    engineer["location"],
                    ticket["location"]
                )
                score += 100.0 / (1 + distance)  # Inverse distance
            
            # Skill match
            if engineer.get("skills") and ticket.get("required_skill"):
                if ticket["required_skill"] in engineer["skills"]:
                    score += 50.0
            
            # Current load (less loaded = better)
            current_load = engineer.get("current_tickets", 0)
            score += 30.0 / (1 + current_load)
            
            scored_engineers.append((score, engineer))
        
        if not scored_engineers:
            return None
        
        scored_engineers.sort(reverse=True, key=lambda x: x[0])
        return scored_engineers[0][1]
    
    def _calculate_load_balance(self, assignments: Dict, num_engineers: int) -> float:
        """Calculate load balance score (0-1, higher is better)"""
        if not assignments:
            return 0.0
        
        ticket_counts = [len(tickets) for tickets in assignments.values()]
        
        if not ticket_counts:
            return 0.0
        
        avg_load = sum(ticket_counts) / num_engineers
        variance = sum((count - avg_load) ** 2 for count in ticket_counts) / num_engineers
        
        # Lower variance = better balance
        max_variance = avg_load ** 2  # Theoretical max
        balance_score = 1.0 - min(1.0, variance / max_variance if max_variance > 0 else 0)
        
        return balance_score


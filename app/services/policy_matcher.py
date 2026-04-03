"""
Policy Matching Service
Matches SLA and Service Policies to tickets based on various criteria
"""
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.sla_policy import SLAPolicy, ServicePolicy, SLAType
from app.models.ticket import Ticket, TicketPriority
from app.models.device import Device


class PolicyMatcherService:
    """Service for matching and applying policies to tickets"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def find_matching_sla_policy(
        self,
        organization_id: int,
        sla_type: SLAType,
        product_id: Optional[int] = None,
        product_category: Optional[str] = None,
        country_id: Optional[int] = None,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None
    ) -> Optional[SLAPolicy]:
        """
        Find the most specific matching SLA policy
        
        Priority order:
        1. Product ID + Location (most specific)
        2. Product Category + Location
        3. Product ID only
        4. Product Category only
        5. Location only
        6. Global (no filters) - least specific
        """
        if not organization_id:
            return None
        
        # Build query
        query = self.db.query(SLAPolicy).filter(
            SLAPolicy.organization_id == organization_id,
            SLAPolicy.sla_type == sla_type,
            SLAPolicy.is_active == True
        )
        
        # Try to find most specific match
        policies = query.all()
        
        if not policies:
            return None
        
        # Score policies by specificity (higher score = more specific)
        scored_policies = []
        
        for policy in policies:
            score = 0
            
            # Product ID match (highest priority)
            if product_id and policy.product_id == product_id:
                score += 1000
            elif product_id and policy.product_id:
                continue  # Policy is for different product
            
            # Product category match
            if product_category and policy.product_category == product_category:
                score += 100
            elif product_category and policy.product_category:
                continue  # Policy is for different category
            
            # Location matches
            if city_id and policy.city_id == city_id:
                score += 10
            elif city_id and policy.city_id:
                continue  # Policy is for different city
            
            if state_id and policy.state_id == state_id:
                score += 5
            elif state_id and policy.state_id:
                continue  # Policy is for different state
            
            if country_id and policy.country_id == country_id:
                score += 1
            elif country_id and policy.country_id:
                continue  # Policy is for different country
            
            # Global policy (no filters)
            if not policy.product_id and not policy.product_category and \
               not policy.country_id and not policy.state_id and not policy.city_id:
                score = 0  # Lowest priority
            
            scored_policies.append((score, policy))
        
        if not scored_policies:
            return None
        
        # Return policy with highest score
        scored_policies.sort(key=lambda x: x[0], reverse=True)
        return scored_policies[0][1]
    
    def calculate_sla_deadline(
        self,
        policy: SLAPolicy,
        created_at: datetime,
        priority: TicketPriority
    ) -> datetime:
        """
        Calculate SLA deadline based on policy and priority
        
        Args:
            policy: The matched SLA policy
            created_at: When the ticket was created
            priority: Ticket priority
        
        Returns:
            Calculated deadline datetime
        """
        # Get base hours from policy
        base_hours = policy.target_hours
        
        # Apply priority override if exists
        if policy.priority_overrides and isinstance(policy.priority_overrides, dict):
            priority_key = priority.value if hasattr(priority, 'value') else str(priority)
            if priority_key in policy.priority_overrides:
                base_hours = policy.priority_overrides[priority_key]
        
        # Calculate deadline
        if policy.business_hours_only and policy.business_hours:
            # TODO: Implement business hours calculation
            # For now, use simple calculation
            deadline = created_at + timedelta(hours=base_hours)
        else:
            deadline = created_at + timedelta(hours=base_hours)
        
        return deadline
    
    def apply_sla_to_ticket(
        self,
        ticket: Ticket,
        sla_type: SLAType
    ) -> Optional[datetime]:
        """
        Apply SLA policy to a ticket and return the calculated deadline
        
        Args:
            ticket: The ticket to apply SLA to
            sla_type: Type of SLA to apply
        
        Returns:
            Calculated deadline or None if no policy found
        """
        if not ticket.organization_id:
            return None
        
        # Get device info if available
        device = None
        product_id = None
        product_category = None
        
        if ticket.device_id:
            device = self.db.query(Device).filter(Device.id == ticket.device_id).first()
            if device:
                product_id = device.product_id
                product_category = device.product_category
        
        # Find matching policy
        policy = self.find_matching_sla_policy(
            organization_id=ticket.organization_id,
            sla_type=sla_type,
            product_id=product_id,
            product_category=product_category or ticket.issue_category,
            country_id=ticket.country_id,
            state_id=ticket.state_id,
            city_id=ticket.city_id
        )
        
        if not policy:
            return None
        
        # Calculate deadline
        created_at = ticket.created_at or datetime.now(timezone.utc)
        deadline = self.calculate_sla_deadline(
            policy=policy,
            created_at=created_at,
            priority=ticket.priority
        )
        
        return deadline
    
    def find_matching_service_policies(
        self,
        organization_id: int,
        product_id: Optional[int] = None,
        product_category: Optional[str] = None,
        policy_type: Optional[str] = None,
        country_id: Optional[int] = None,
        state_id: Optional[int] = None,
        city_id: Optional[int] = None
    ) -> List[ServicePolicy]:
        """
        Find matching service policies
        
        Args:
            organization_id: Organization ID
            product_id: Product ID (optional)
            product_category: Product category (optional)
            policy_type: Specific policy type to filter (optional)
        
        Returns:
            List of matching service policies
        """
        if not organization_id:
            return []
        
        query = self.db.query(ServicePolicy).filter(
            ServicePolicy.organization_id == organization_id,
            ServicePolicy.is_active == True
        )
        
        if policy_type:
            query = query.filter(ServicePolicy.policy_type == policy_type)
        
        policies = query.all()
        
        # Score policies by specificity
        matching_policies = []
        for policy in policies:
            score = 0

            # Product match
            if product_id and policy.product_id == product_id:
                score += 100
            elif product_id and policy.product_id:
                continue

            if product_category and policy.product_category == product_category:
                score += 10
            elif product_category and policy.product_category:
                continue

            # Location match
            if city_id and policy.city_id == city_id:
                score += 5
            elif city_id and policy.city_id:
                continue

            if state_id and policy.state_id == state_id:
                score += 3
            elif state_id and policy.state_id:
                continue

            if country_id and policy.country_id == country_id:
                score += 1
            elif country_id and policy.country_id:
                continue

            matching_policies.append((score, policy))

        matching_policies.sort(key=lambda x: x[0], reverse=True)
        return [policy for _, policy in matching_policies]
    
    def apply_service_policies_to_ticket(
        self,
        ticket: Ticket
    ) -> Dict[str, Any]:
        """
        Apply service policies to a ticket and return policy results
        
        Args:
            ticket: The ticket to apply policies to
        
        Returns:
            Dictionary with policy results (warranty_status, is_chargeable, etc.)
        """
        if not ticket.organization_id:
            return {}
        
        # Get device info
        device = None
        product_id = None
        product_category = None
        
        if ticket.device_id:
            device = self.db.query(Device).filter(Device.id == ticket.device_id).first()
            if device:
                product_id = device.product_id
                product_category = device.product_category
        
        results = {
            "warranty_status": None,
            "is_chargeable": False,
            "pricing": {},
            "parts_policy": {},
            "applied_policies": []
        }
        
        # Find all matching service policies
        policies = self.find_matching_service_policies(
            organization_id=ticket.organization_id,
            product_id=product_id,
            product_category=product_category or ticket.issue_category,
            country_id=ticket.country_id,
            state_id=ticket.state_id,
            city_id=ticket.city_id
        )
        
        for policy in policies:
            results["applied_policies"].append({
                "id": policy.id,
                "type": policy.policy_type,
                "rules": policy.rules
            })
            
            # Apply warranty policy
            if policy.policy_type == "warranty" and policy.rules:
                rules = policy.rules if isinstance(policy.rules, dict) else {}
                
                # Check warranty period
                warranty_months = rules.get("warranty_period_months", 12)
                if device and device.purchase_date:
                    # Calculate warranty end date
                    purchase_date = device.purchase_date
                    if isinstance(purchase_date, str):
                        from datetime import datetime as dt
                        purchase_date = dt.fromisoformat(purchase_date.replace('Z', '+00:00'))
                    
                    # Add months (approximate: 30 days per month)
                    warranty_days = warranty_months * 30
                    warranty_end = purchase_date + timedelta(days=warranty_days)
                    now = datetime.now(timezone.utc)
                    
                    if now <= warranty_end:
                        results["warranty_status"] = "in_warranty"
                    else:
                        results["warranty_status"] = "out_of_warranty"
                else:
                    results["warranty_status"] = "unknown"
            
            # Apply chargeable policy
            elif policy.policy_type == "chargeable" and policy.rules:
                rules = policy.rules if isinstance(policy.rules, dict) else {}
                
                charge_if = rules.get("charge_if", [])
                free_if = rules.get("free_if", [])
                
                # Check conditions
                if results["warranty_status"] == "out_of_warranty" and "out_of_warranty" in charge_if:
                    results["is_chargeable"] = True
                elif results["warranty_status"] == "in_warranty" and "in_warranty" in free_if:
                    results["is_chargeable"] = False
                
                # Store pricing info
                if "pricing" in rules:
                    results["pricing"] = rules["pricing"]
            
            # Apply parts policy
            elif policy.policy_type == "parts" and policy.rules:
                results["parts_policy"] = policy.rules if isinstance(policy.rules, dict) else {}
        
        return results


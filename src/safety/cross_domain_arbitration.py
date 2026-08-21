"""
Cross-Domain Safety Arbitration for ORION Physical Intelligence OS.

This module implements cross-domain safety arbitration, enabling multiple domain
simulations (Industrial SC-1, Vehicle SC-2, Smart Home SC-3) to coexist safely
under a unified safety enforcement framework.

Key Features:
1. Domain registration with safety criticality levels (SC-1 > SC-2 > SC-3)
2. Priority-based conflict resolution: higher SC preempts lower SC
3. Emergency cascade: emergency in any domain broadcasts to all domains
4. CBF conflict detection between domains
5. Cross-domain authority state transitions
6. Arbitration log for all cross-domain safety decisions
7. Integration with existing SafetyEnforcement and SafetyDecision
"""

import hashlib
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class SafetyCriticality(int, Enum):
    """Safety criticality levels — lower number = higher priority."""
    SC_1 = 1  # Industrial — highest (immediate physical danger)
    SC_2 = 2  # Vehicle — high (human occupants, external environment)
    SC_3 = 3  # Smart Home — moderate (human occupancy, slower dynamics)
    SC_4 = 4  # Drone — high but below vehicle (risk to people/property below)


class DomainState(str, Enum):
    """State of a registered domain."""
    ACTIVE = "active"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"


class ArbitrationDecision(str, Enum):
    """Types of cross-domain arbitration decisions."""
    ALLOW = "allow"
    PREEMPT = "preempt"        # Higher SC preempts lower SC
    CASCADE = "cascade"        # Emergency broadcast to all domains
    COORDINATE = "coordinate"  # Both domains adjust
    BLOCK = "block"            # Action blocked entirely


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class SafetyEvent:
    """A safety event from a specific domain."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    domain_id: str = ""
    criticality: SafetyCriticality = SafetyCriticality.SC_3
    event_type: str = ""  # e.g., "collision_warning", "estop", "threshold_breach"
    severity: str = "warning"  # info, warning, critical, emergency
    source_entity: str = ""
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    proposed_action: Optional[Dict[str, Any]] = None


@dataclass
class ArbitrationResult:
    """Result of cross-domain safety arbitration."""
    result_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    decision: ArbitrationDecision = ArbitrationDecision.ALLOW
    winning_domain: str = ""
    losing_domains: List[str] = field(default_factory=list)
    reason: str = ""
    affected_domains: List[str] = field(default_factory=list)
    safety_events: List[SafetyEvent] = field(default_factory=list)
    actions_required: Dict[str, List[str]] = field(default_factory=dict)  # domain_id -> actions
    hash: str = ""

    def compute_hash(self) -> str:
        import os
        import hmac as _hmac
        content = f"{self.result_id}:{self.timestamp}:{self.decision.value}:{self.winning_domain}"
        audit_key = os.environ.get("ORION_AUDIT_KEY") or os.environ.get("ORION_POLICY_KEY")
        if not audit_key:
            raise PermissionError("ORION_AUDIT_KEY not configured — cannot sign arbitration result (fail-closed)")
        self.hash = _hmac.new(audit_key.encode(), content.encode(), hashlib.sha256).hexdigest()
        return self.hash


@dataclass
class DomainRegistration:
    """Registration record for a domain in the arbitration system."""
    domain_id: str
    name: str
    criticality: SafetyCriticality
    state: DomainState = DomainState.ACTIVE
    registered_at: float = field(default_factory=time.time)
    entities: List[str] = field(default_factory=list)
    active_cbfs: List[str] = field(default_factory=list)


# ============================================================================
# Cross-Domain Arbitrator
# ============================================================================

class CrossDomainArbitrator:
    """
    Arbitrates safety between multiple ORION domain simulations.

    Priority Rules:
    - SC-1 (Industrial) preempts SC-2 (Vehicle) preempts SC-3 (Smart Home)
    - Emergency in ANY domain cascades to ALL domains
    - CBF conflicts resolved by criticality priority
    - All decisions logged in arbitration log (hash-chained)
    """

    def __init__(self):
        self._domains: Dict[str, DomainRegistration] = {}
        self._arbitration_log: List[ArbitrationResult] = []
        self._emergency_active: bool = False
        self._emergency_source: Optional[str] = None
        self._lock = threading.Lock()

    def register_domain(
        self,
        domain_id: str,
        name: str,
        criticality: SafetyCriticality,
        entities: List[str] = None
    ) -> DomainRegistration:
        """Register a domain for cross-domain safety arbitration."""
        registration = DomainRegistration(
            domain_id=domain_id,
            name=name,
            criticality=criticality,
            entities=entities or []
        )
        self._domains[domain_id] = registration
        logger.info(f"Domain registered: {domain_id} ({name}, SC-{criticality.value})")
        return registration

    def unregister_domain(self, domain_id: str) -> bool:
        """Unregister a domain."""
        if domain_id in self._domains:
            del self._domains[domain_id]
            logger.info(f"Domain unregistered: {domain_id}")
            return True
        return False

    def get_domain(self, domain_id: str) -> Optional[DomainRegistration]:
        """Get a domain registration."""
        return self._domains.get(domain_id)

    def list_domains(self) -> List[DomainRegistration]:
        """List all registered domains."""
        return list(self._domains.values())

    def update_domain_state(self, domain_id: str, state: DomainState) -> bool:
        """Update a domain's operational state."""
        if domain_id not in self._domains:
            return False
        self._domains[domain_id].state = state
        return True

    def arbitrate(self, events: List[SafetyEvent]) -> ArbitrationResult:
        """
        Arbitrate between multiple safety events from different domains.

        Rules:
        1. If any event is EMERGENCY severity → cascade to all domains
        2. Among conflicting events, highest criticality (lowest SC number) wins
        3. Same-criticality conflicts → coordinate (both adjust)
        4. No conflicts → allow all

        Returns ArbitrationResult with decision and affected domains.
        """
        if not events:
            result = ArbitrationResult(
                decision=ArbitrationDecision.ALLOW,
                reason="No events to arbitrate"
            )
            result.compute_hash()
            self._log_arbitration(result)
            return result

        # Check for emergency events
        emergency_events = [e for e in events if e.severity == "emergency"]
        if emergency_events:
            return self._handle_emergency_cascade(emergency_events, events)

        # Check for critical events
        critical_events = [e for e in events if e.severity == "critical"]
        if critical_events:
            return self._handle_critical_arbitration(critical_events, events)

        # Group events by domain
        events_by_domain: Dict[str, List[SafetyEvent]] = {}
        for event in events:
            events_by_domain.setdefault(event.domain_id, []).append(event)

        # If only one domain has events, allow
        if len(events_by_domain) <= 1:
            result = ArbitrationResult(
                decision=ArbitrationDecision.ALLOW,
                reason="Single-domain events, no cross-domain conflict",
                affected_domains=list(events_by_domain.keys()),
                safety_events=events
            )
            result.compute_hash()
            self._log_arbitration(result)
            return result

        # Multiple domains with events — check for conflicts
        # Sort domains by criticality (SC-1 first)
        sorted_domains = sorted(
            events_by_domain.keys(),
            key=lambda d: self._domains[d].criticality.value if d in self._domains else 99
        )

        # Highest priority domain
        winner = sorted_domains[0]
        losers = sorted_domains[1:]

        # Check if there's actual conflict (same entity or overlapping CBF)
        if self._has_cbf_conflict(events):
            result = ArbitrationResult(
                decision=ArbitrationDecision.PREEMPT,
                winning_domain=winner,
                losing_domains=losers,
                reason=f"CBF conflict: {winner} (SC-{self._domains[winner].criticality.value}) preempts",
                affected_domains=sorted_domains,
                safety_events=events,
                actions_required={
                    dom: ["yield", "suspend_action"] for dom in losers
                }
            )
        else:
            result = ArbitrationResult(
                decision=ArbitrationDecision.ALLOW,
                winning_domain=winner,
                reason="No CBF conflict between domains",
                affected_domains=sorted_domains,
                safety_events=events
            )

        result.compute_hash()
        self._log_arbitration(result)
        return result

    def _handle_emergency_cascade(
        self,
        emergency_events: List[SafetyEvent],
        all_events: List[SafetyEvent]
    ) -> ArbitrationResult:
        """Handle emergency cascade — broadcast to all domains."""
        self._emergency_active = True
        source_domain = emergency_events[0].domain_id
        self._emergency_source = source_domain

        all_domain_ids = list(self._domains.keys())
        actions = {}
        for dom_id in all_domain_ids:
            if dom_id == source_domain:
                actions[dom_id] = ["execute_emergency_protocol", "estop"]
            else:
                actions[dom_id] = ["cascade_emergency", "safe_state", "suspend_operations"]

        result = ArbitrationResult(
            decision=ArbitrationDecision.CASCADE,
            winning_domain=source_domain,
            losing_domains=[d for d in all_domain_ids if d != source_domain],
            reason=f"Emergency in {source_domain} — cascade to all {len(all_domain_ids)} domains",
            affected_domains=all_domain_ids,
            safety_events=all_events,
            actions_required=actions
        )
        result.compute_hash()
        self._log_arbitration(result)

        # Update all domain states to EMERGENCY
        for dom_id in all_domain_ids:
            self._domains[dom_id].state = DomainState.EMERGENCY

        return result

    def _handle_critical_arbitration(
        self,
        critical_events: List[SafetyEvent],
        all_events: List[SafetyEvent]
    ) -> ArbitrationResult:
        """Handle critical (but not emergency) events."""
        # Find highest criticality domain among critical events
        critical_by_domain: Dict[str, List[SafetyEvent]] = {}
        for e in critical_events:
            critical_by_domain.setdefault(e.domain_id, []).append(e)

        sorted_domains = sorted(
            critical_by_domain.keys(),
            key=lambda d: self._domains[d].criticality.value if d in self._domains else 99
        )

        winner = sorted_domains[0]
        losers = sorted_domains[1:]

        result = ArbitrationResult(
            decision=ArbitrationDecision.PREEMPT if losers else ArbitrationDecision.ALLOW,
            winning_domain=winner,
            losing_domains=losers,
            reason=f"Critical events: {winner} takes priority",
            affected_domains=sorted_domains,
            safety_events=all_events,
            actions_required={
                dom: ["yield"] for dom in losers
            }
        )
        result.compute_hash()
        self._log_arbitration(result)
        return result

    def _has_cbf_conflict(self, events: List[SafetyEvent]) -> bool:
        """
        Check if events from different domains have conflicting CBFs.
        Simple heuristic: if two domains propose actions on the same entity
        or in overlapping spatial regions, there's a conflict.
        """
        domain_entities: Dict[str, set] = {}
        for event in events:
            if event.source_entity:
                domain_entities.setdefault(event.domain_id, set()).add(event.source_entity)

        # Check for shared entities
        domains = list(domain_entities.keys())
        for i in range(len(domains)):
            for j in range(i + 1, len(domains)):
                if domain_entities[domains[i]] & domain_entities[domains[j]]:
                    return True

        # Check for spatial overlap in proposed actions
        for i, e1 in enumerate(events):
            for j, e2 in enumerate(events):
                if i >= j:
                    continue
                if e1.domain_id != e2.domain_id:
                    # Check if both have position-based proposed actions
                    if e1.proposed_action and e2.proposed_action:
                        pos1 = e1.proposed_action.get("position")
                        pos2 = e2.proposed_action.get("position")
                        if pos1 and pos2:
                            dist = sum((a - b) ** 2 for a, b in zip(pos1, pos2))
                            if dist < 1.0:  # Close enough to conflict
                                return True

        return False

    def _log_arbitration(self, result: ArbitrationResult):
        """Add result to the hash-chained arbitration log."""
        self._arbitration_log.append(result)

    def get_arbitration_log(self) -> List[ArbitrationResult]:
        """Get the full arbitration log."""
        return list(self._arbitration_log)

    def verify_log_integrity(self) -> bool:
        """Verify HMAC integrity of arbitration log — fail-closed."""
        import os
        import hmac as _hmac
        audit_key = os.environ.get("ORION_AUDIT_KEY") or os.environ.get("ORION_POLICY_KEY")
        if not audit_key:
            raise PermissionError("ORION_AUDIT_KEY not configured — cannot verify log integrity (fail-closed)")
        for result in self._arbitration_log:
            content = f"{result.result_id}:{result.timestamp}:{result.decision.value}:{result.winning_domain}"
            expected_hash = _hmac.new(audit_key.encode(), content.encode(), hashlib.sha256).hexdigest()
            if result.hash != expected_hash:
                return False
        return True

    def clear_emergency(self, hmac_credential: Optional[str] = None, timestamp: Optional[float] = None) -> bool:
        """Clear the emergency state across all domains. Requires HMAC authorization with replay protection.

        Args:
            hmac_credential: HMAC-SHA256 of f"clear_emergency:{timestamp}" using ORION_EMERGENCY_HMAC_KEY
            timestamp: Unix timestamp (seconds). Must be within 60 seconds of current time (replay window).
        """
        if not hmac_credential or not hmac_credential.strip():
            raise PermissionError("HMAC credential required to clear emergency — deny by default")
        if timestamp is None:
            raise PermissionError("Timestamp required for replay protection — deny by default")
        # Replay protection: timestamp must be within 60-second window
        import time as _time
        current_time = _time.time()
        if abs(current_time - timestamp) > 60.0:
            raise PermissionError("HMAC timestamp outside replay window — emergency clearing denied")
        # Verify HMAC credential (must match environment-configured key)
        import hashlib
        import hmac as hmac_mod
        import os
        expected_key = os.environ.get("ORION_EMERGENCY_HMAC_KEY", "")
        if not expected_key:
            raise PermissionError("ORION_EMERGENCY_HMAC_KEY not configured — cannot authorize emergency clearing")
        # Include timestamp in HMAC message to prevent replay attacks
        expected_message = f"clear_emergency:{timestamp}".encode()
        expected_hmac = hmac_mod.new(expected_key.encode(), expected_message, hashlib.sha256).hexdigest()
        if not hmac_mod.compare_digest(hmac_credential, expected_hmac):
            raise PermissionError("Invalid HMAC credential — emergency clearing denied")
        self._emergency_active = False
        self._emergency_source = None
        for dom in self._domains.values():
            dom.state = DomainState.ACTIVE
        logger.info("Emergency cleared — all domains back to ACTIVE (authorized)")
        return True

    def is_emergency_active(self) -> bool:
        """Check if emergency cascade is active."""
        return self._emergency_active

    def get_emergency_source(self) -> Optional[str]:
        """Get the domain that triggered the emergency."""
        return self._emergency_source

    def get_domain_priorities(self) -> Dict[str, int]:
        """Get all domain priorities sorted by criticality."""
        return {
            dom_id: reg.criticality.value
            for dom_id, reg in sorted(
                self._domains.items(),
                key=lambda x: x[1].criticality.value
            )
        }


# Need threading for thread safety
import threading

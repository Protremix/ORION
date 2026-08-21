"""ORION Phase 3 — Cross-Domain Safety Arbitration Tests.

Tests the CrossDomainArbitrator for Industrial + Vehicle coexistence,
priority-based conflict resolution, emergency cascade, and log integrity.
"""

import hashlib
import time
import hmac
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.safety.cross_domain_arbitration import (
    ArbitrationDecision,
    CrossDomainArbitrator,
    DomainRegistration,
    DomainState,
    SafetyCriticality,
    SafetyEvent,
)


class TestDomainRegistration(unittest.TestCase):
    """Test domain registration and unregistration."""

    def setUp(self):
        self.arb = CrossDomainArbitrator()

    def test_register_domain(self):
        """Domain can be registered with criticality level."""
        reg = self.arb.register_domain("industrial", "Factory Floor", SafetyCriticality.SC_1)
        self.assertEqual(reg.domain_id, "industrial")
        self.assertEqual(reg.criticality, SafetyCriticality.SC_1)
        self.assertEqual(reg.state, DomainState.ACTIVE)
        self.assertIn("industrial", [d.domain_id for d in self.arb.list_domains()])

    def test_unregister_domain(self):
        """Domain can be unregistered."""
        self.arb.register_domain("vehicle", "Highway", SafetyCriticality.SC_2)
        self.assertTrue(self.arb.unregister_domain("vehicle"))
        self.assertNotIn("vehicle", [d.domain_id for d in self.arb.list_domains()])

    def test_unregister_nonexistent_domain(self):
        """Unregistering nonexistent domain returns False."""
        self.assertFalse(self.arb.unregister_domain("nonexistent"))


class TestPriorityArbitration(unittest.TestCase):
    """Test priority-based conflict resolution."""

    def setUp(self):
        self.arb = CrossDomainArbitrator()
        self.arb.register_domain("industrial", "Factory", SafetyCriticality.SC_1)
        self.arb.register_domain("vehicle", "Highway", SafetyCriticality.SC_2)
        self.arb.register_domain("home", "Smart Home", SafetyCriticality.SC_3)

    def test_sc1_preempts_sc2(self):
        """SC-1 (Industrial) preempts SC-2 (Vehicle) on conflict."""
        events = [
            SafetyEvent(
                domain_id="industrial",
                criticality=SafetyCriticality.SC_1,
                event_type="estop",
                severity="critical",
                source_entity="robot_arm_1",
            ),
            SafetyEvent(
                domain_id="vehicle",
                criticality=SafetyCriticality.SC_2,
                event_type="collision_warning",
                severity="critical",
                source_entity="vehicle_1",
            ),
        ]
        result = self.arb.arbitrate(events)
        self.assertEqual(result.decision, ArbitrationDecision.PREEMPT)
        self.assertEqual(result.winning_domain, "industrial")
        self.assertIn("vehicle", result.losing_domains)

    def test_no_conflict_allows_all(self):
        """Non-conflicting events from different domains are allowed."""
        events = [
            SafetyEvent(
                domain_id="industrial",
                criticality=SafetyCriticality.SC_1,
                event_type="temperature_warning",
                severity="warning",
                source_entity="sensor_1",
            ),
            SafetyEvent(
                domain_id="vehicle",
                criticality=SafetyCriticality.SC_2,
                event_type="lane_departure",
                severity="warning",
                source_entity="vehicle_1",
            ),
        ]
        result = self.arb.arbitrate(events)
        self.assertEqual(result.decision, ArbitrationDecision.ALLOW)

    def test_single_domain_event_allowed(self):
        """Events from a single domain are allowed without arbitration."""
        events = [
            SafetyEvent(
                domain_id="home",
                criticality=SafetyCriticality.SC_3,
                event_type="temperature_change",
                severity="info",
                source_entity="room_1",
            ),
        ]
        result = self.arb.arbitrate(events)
        self.assertEqual(result.decision, ArbitrationDecision.ALLOW)


class TestEmergencyCascade(unittest.TestCase):
    """Test emergency cascade across domains."""

    def setUp(self):
        self.arb = CrossDomainArbitrator()
        self.arb.register_domain("industrial", "Factory", SafetyCriticality.SC_1)
        self.arb.register_domain("vehicle", "Highway", SafetyCriticality.SC_2)
        self.arb.register_domain("home", "Smart Home", SafetyCriticality.SC_3)

    def test_emergency_cascades_to_all_domains(self):
        """Emergency in one domain cascades to all registered domains."""
        events = [
            SafetyEvent(
                domain_id="industrial",
                criticality=SafetyCriticality.SC_1,
                event_type="estop",
                severity="emergency",
                source_entity="robot_arm_1",
            ),
            SafetyEvent(
                domain_id="vehicle",
                criticality=SafetyCriticality.SC_2,
                event_type="obstacle_detected",
                severity="warning",
                source_entity="vehicle_1",
            ),
        ]
        result = self.arb.arbitrate(events)
        self.assertEqual(result.decision, ArbitrationDecision.CASCADE)
        self.assertTrue(self.arb.is_emergency_active())
        self.assertEqual(self.arb.get_emergency_source(), "industrial")
        # All domains affected
        self.assertEqual(len(result.affected_domains), 3)
        self.assertIn("estop", result.actions_required.get("industrial", []))
        self.assertIn("cascade_emergency", result.actions_required.get("vehicle", []))
        self.assertIn("cascade_emergency", result.actions_required.get("home", []))

    def test_clear_emergency(self):
        """Emergency state can be cleared."""
        events = [
            SafetyEvent(
                domain_id="vehicle",
                criticality=SafetyCriticality.SC_2,
                event_type="collision",
                severity="emergency",
                source_entity="vehicle_1",
            ),
        ]
        self.arb.arbitrate(events)
        self.assertTrue(self.arb.is_emergency_active())
        ts = time.time()
        self.arb.clear_emergency(hmac_credential=hmac.new(os.environ.get("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key").encode(), f"clear_emergency:{ts}".encode(), hashlib.sha256).hexdigest(), timestamp=ts)
        self.assertFalse(self.arb.is_emergency_active())

    def test_all_domains_enter_emergency_state(self):
        """All domains enter EMERGENCY state on cascade."""
        events = [
            SafetyEvent(
                domain_id="home",
                criticality=SafetyCriticality.SC_3,
                event_type="smoke_detected",
                severity="emergency",
                source_entity="smoke_detector_1",
            ),
        ]
        self.arb.arbitrate(events)
        for dom in self.arb.list_domains():
            self.assertEqual(dom.state, DomainState.EMERGENCY)


class TestArbitrationLog(unittest.TestCase):
    """Test arbitration log integrity."""

    def setUp(self):
        self.arb = CrossDomainArbitrator()
        self.arb.register_domain("industrial", "Factory", SafetyCriticality.SC_1)
        self.arb.register_domain("vehicle", "Highway", SafetyCriticality.SC_2)

    def test_arbitration_log_records_decisions(self):
        """All arbitration decisions are logged."""
        for i in range(5):
            events = [
                SafetyEvent(
                    domain_id="industrial",
                    criticality=SafetyCriticality.SC_1,
                    event_type=f"event_{i}",
                    severity="warning",
                    source_entity=f"entity_{i}",
                ),
            ]
            self.arb.arbitrate(events)
        log = self.arb.get_arbitration_log()
        self.assertEqual(len(log), 5)

    def test_log_hash_chain_integrity(self):
        """Arbitration log hash chain is intact."""
        events = [
            SafetyEvent(
                domain_id="industrial",
                criticality=SafetyCriticality.SC_1,
                event_type="estop",
                severity="critical",
                source_entity="robot_arm_1",
            ),
            SafetyEvent(
                domain_id="vehicle",
                criticality=SafetyCriticality.SC_2,
                event_type="brake",
                severity="critical",
                source_entity="vehicle_1",
            ),
        ]
        self.arb.arbitrate(events)
        self.assertTrue(self.arb.verify_log_integrity())


class TestDomainPriorities(unittest.TestCase):
    """Test domain priority ordering."""

    def test_priority_ordering(self):
        """Domains are ordered by criticality (SC-1 first)."""
        arb = CrossDomainArbitrator()
        arb.register_domain("home", "Smart Home", SafetyCriticality.SC_3)
        arb.register_domain("industrial", "Factory", SafetyCriticality.SC_1)
        arb.register_domain("vehicle", "Highway", SafetyCriticality.SC_2)

        priorities = arb.get_domain_priorities()
        ordered = list(priorities.items())
        self.assertEqual(ordered[0][0], "industrial")
        self.assertEqual(ordered[1][0], "vehicle")
        self.assertEqual(ordered[2][0], "home")


if __name__ == "__main__":
    unittest.main()

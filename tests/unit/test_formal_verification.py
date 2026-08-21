"""ORION Phase 4 — Formal Verification Tests (W4-7).

Tests the SafetyVerifier for all 12 safety properties:
1. CBF Forward Invariance
2. CBF Filter Correctness
3. Emergency Cascade Completeness
4. Priority Total Ordering
5. Audit Log Hash Chain Integrity
6. Battery Threshold Monotonicity
7. Real-Time Boundedness
8. Sensor Validation Completeness
9. Actuator Command Safety
10. Watchdog Independence
11. Graceful Degradation
12. Physical Recovery
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.persistence.storage import StorageManager
from src.safety.cross_domain_arbitration import CrossDomainArbitrator, DomainState, SafetyCriticality, SafetyEvent
from src.safety.formal_verification import SafetyVerifier, VerificationResult


class TestFormalVerification(unittest.TestCase):
    """Test formal verification of the ORION safety layer."""

    def setUp(self):
        self.verifier = SafetyVerifier(seed=42)

    def test_cbf_forward_invariance(self):
        """CBF forward invariance property is verified."""
        result = self.verifier.verify_cbf_forward_invariance()
        self.assertTrue(result.verified, f"CBF forward invariance failed: {result.counterexample}")
        self.assertIn("Forward Invariance", result.property_name)
        self.assertTrue(len(result.proof_sketch) > 0)

    def test_cbf_filter_correctness(self):
        """CBF filter correctness property is verified."""
        result = self.verifier.verify_cbf_filter_correctness()
        self.assertTrue(result.verified, f"CBF filter correctness failed: {result.counterexample}")

    def test_emergency_cascade_completeness(self):
        """Emergency cascade completeness property is verified."""
        result = self.verifier.verify_emergency_cascade_completeness()
        self.assertTrue(result.verified, f"Emergency cascade failed: {result.counterexample}")

    def test_priority_total_ordering(self):
        """Priority total ordering property is verified."""
        result = self.verifier.verify_priority_total_ordering()
        self.assertTrue(result.verified, f"Priority ordering failed: {result.counterexample}")

    def test_audit_hash_chain_integrity(self):
        """Audit log hash chain integrity property is verified."""
        storage = StorageManager(db_path=":memory:")
        result = self.verifier.verify_audit_hash_chain_integrity(storage)
        self.assertTrue(result.verified, f"Hash chain integrity failed: {result.counterexample}")

    def test_battery_threshold_monotonicity(self):
        """Battery threshold monotonicity property is verified."""
        result = self.verifier.verify_battery_threshold_monotonicity()
        self.assertTrue(result.verified, f"Battery monotonicity failed: {result.counterexample}")

    def test_verify_all(self):
        """All 12 properties can be verified at once."""
        storage = StorageManager(db_path=":memory:")
        arb = CrossDomainArbitrator()
        results = self.verifier.verify_all(arbitrator=arb, storage=storage)

        self.assertEqual(len(results), 12)
        for r in results:
            self.assertTrue(r.verified, f"Property {r.property_name} failed: {r.counterexample}")

    def test_verification_report_generation(self):
        """Formal verification report can be generated."""
        self.verifier.verify_all()
        report = self.verifier.generate_report()
        self.assertIn("Formal Verification Report", report)
        self.assertIn("PASS", report)


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for Safety Layer v3 Extended Formal Verification.

Tests Properties 7 through 12 and verify_all() integration:
- Property 7: Real-Time Boundedness
- Property 8: Sensor Validation Completeness
- Property 9: Actuator Command Safety
- Property 10: Watchdog Independence
- Property 11: Graceful Degradation
- Property 12: Physical Recovery
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.safety.formal_verification import SafetyVerifier, VerificationResult


class TestSafetyV3Verification(unittest.TestCase):
    """Test extended formal verification properties 7-12."""

    def setUp(self):
        self.verifier = SafetyVerifier(seed=42)

    def test_property_7_realtime_boundedness(self):
        """Property 7: Real-time boundedness verification."""
        result = self.verifier.verify_realtime_boundedness()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Real-Time Boundedness")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")
        self.assertIn("CBF", result.proof_sketch)

    def test_property_8_sensor_validation_completeness(self):
        """Property 8: Sensor validation completeness verification."""
        result = self.verifier.verify_sensor_validation_completeness()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Sensor Validation Completeness")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")
        self.assertIn("5-stage", result.proof_sketch)

    def test_property_9_actuator_command_safety(self):
        """Property 9: Actuator command safety verification."""
        result = self.verifier.verify_actuator_command_safety()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Actuator Command Safety")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")

    def test_property_10_watchdog_independence(self):
        """Property 10: Watchdog independence verification."""
        result = self.verifier.verify_watchdog_independence()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Watchdog Independence")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")

    def test_property_11_graceful_degradation(self):
        """Property 11: Graceful degradation verification."""
        result = self.verifier.verify_graceful_degradation()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Graceful Degradation")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")

    def test_property_12_physical_recovery(self):
        """Property 12: Physical recovery verification."""
        result = self.verifier.verify_physical_recovery()
        self.assertIsInstance(result, VerificationResult)
        self.assertEqual(result.property_name, "Physical Recovery")
        self.assertTrue(result.verified, f"Failed: {result.counterexample}")

    def test_integration_verify_all_returns_12_properties(self):
        """Integration: verify_all() returns all 12 properties (6 original + 6 new)."""
        results = self.verifier.verify_all()
        self.assertEqual(len(results), 12)

        property_names = [r.property_name for r in results]
        expected_names = [
            "CBF Forward Invariance",
            "CBF Filter Correctness",
            "Emergency Cascade Completeness",
            "Priority Total Ordering",
            "Audit Log Hash Chain Integrity",
            "Battery Threshold Monotonicity",
            "Real-Time Boundedness",
            "Sensor Validation Completeness",
            "Actuator Command Safety",
            "Watchdog Independence",
            "Graceful Degradation",
            "Physical Recovery",
        ]
        self.assertEqual(property_names, expected_names)

    def test_all_new_properties_status_verified(self):
        """All new properties (7-12) return VERIFIED status in simulation."""
        results = self.verifier.verify_all()
        new_results = results[6:]  # Properties 7 to 12
        self.assertEqual(len(new_results), 6)

        for res in new_results:
            self.assertTrue(
                res.verified,
                f"Property '{res.property_name}' was not verified: {res.counterexample}"
            )


if __name__ == "__main__":
    unittest.main()

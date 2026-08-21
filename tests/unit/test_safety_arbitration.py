"""
Comprehensive Unit Tests for ORION Safety Enforcement and Action Arbitration.
"""

import time
import unittest
from typing import Any, Dict

from src.arbitration import ActionArbitration, ActionProposal, LeaseState, PermittedChannel, RiskTier, SafetyPolicy
from src.safety import (
    AuthorityState,
    AuthorityTransitionStateMachine,
    AuthorizerCredential,
    AuthorizerRole,
    CommonCauseFailureHandler,
    DecisionType,
    FallbackDomain,
    ForceLimitCBF,
    SafetyEnforcement,
    SpatialKeepOutCBF,
    TransitionEvidence,
    VelocityLimitCBF,
)


class TestAuthorityStateMachine(unittest.TestCase):

    def setUp(self):
        self.sm = AuthorityTransitionStateMachine(initial_state=AuthorityState.AUTONOMOUS)
        self.sa_credential = AuthorizerCredential(
            authorizer_id="SA_AGENT_01",
            role=AuthorizerRole.SAFETY_ASSURANCE,
            signature="SIG_SA",
            timestamp_ns=time.time_ns()
        )
        self.founder_credential = AuthorizerCredential(
            authorizer_id="FOUNDER_L0",
            role=AuthorizerRole.FOUNDER,
            signature="SIG_FOUNDER",
            timestamp_ns=time.time_ns()
        )
        self.joint_credential = AuthorizerCredential(
            authorizer_id="JOINT_L0_SA",
            role=AuthorizerRole.SAFETY_ASSURANCE_AND_FOUNDER,
            signature="SIG_JOINT",
            timestamp_ns=time.time_ns()
        )

    def test_monotonic_safety_restrictive_transitions(self):
        # Moving to more restrictive states (higher rank) should always succeed automatically
        rec = self.sm.transition_to(
            to_state=AuthorityState.SUPERVISED,
            initiating_condition="Operator step-down",
            authorizer=self.sa_credential
        )
        self.assertEqual(self.sm.current_state, AuthorityState.SUPERVISED)

        rec = self.sm.transition_to(
            to_state=AuthorityState.DEGRADED,
            initiating_condition="Sensor anomaly",
            authorizer=self.sa_credential
        )
        self.assertEqual(self.sm.current_state, AuthorityState.DEGRADED)

        rec = self.sm.transition_to(
            to_state=AuthorityState.EMERGENCY,
            initiating_condition="E-Stop button pressed",
            authorizer=self.sa_credential
        )
        self.assertEqual(self.sm.current_state, AuthorityState.EMERGENCY)

    def test_monotonic_recovery_less_restrictive_requires_evidence_and_auth(self):
        # Transition AUTONOMOUS -> EMERGENCY
        self.sm.transition_to(
            to_state=AuthorityState.EMERGENCY,
            initiating_condition="E-Stop",
            authorizer=self.sa_credential
        )

        # Attempt EMERGENCY -> AUTONOMOUS (Forbidden path directly)
        with self.assertRaises(ValueError):
            self.sm.transition_to(
                to_state=AuthorityState.AUTONOMOUS,
                initiating_condition="Illegal jump",
                authorizer=self.founder_credential
            )

        # Valid recovery path: EMERGENCY -> RECOVERY requires FOUNDER + evidence
        evidence = TransitionEvidence(
            evidence_id="EVID_001",
            condition_description="E-stop cleared and physical reset completed",
            condition_cleared=True,
            verification_data={"reset": "OK"},
            timestamp_ns=time.time_ns(),
            verifier_id="FOUNDER_L0"
        )

        rec = self.sm.transition_to(
            to_state=AuthorityState.RECOVERY,
            initiating_condition="E-stop cleared",
            authorizer=self.founder_credential,
            evidence=evidence
        )
        self.assertEqual(self.sm.current_state, AuthorityState.RECOVERY)


class TestSafetyEnforcement(unittest.TestCase):

    def setUp(self):
        self.sm = AuthorityTransitionStateMachine(initial_state=AuthorityState.AUTONOMOUS)
        self.se = SafetyEnforcement(state_machine=self.sm)

    def test_independence_requirements_verification(self):
        report = self.se.verify_independence_requirements()
        self.assertTrue(report.all_requirements_passed)
        self.assertEqual(len(report.requirements), 10)

    def test_cbf_velocity_filtering(self):
        state = {"obstacle_distance": 0.8, "velocity": 2.0}
        proposed = {"acceleration": 1.0}  # Accelerating towards close obstacle
        safe_ctrl, decisions = self.se.evaluate_and_filter_action(state, proposed)

        # CBF should limit acceleration or filter it
        self.assertLess(safe_ctrl["acceleration"], 1.0)
        self.assertTrue(any(d.decision_type == DecisionType.OVERRIDE for d in decisions))

    def test_fallback_controller_execution(self):
        action = self.se.execute_fallback(FallbackDomain.ROBOT, {})
        self.assertEqual(action["action_type"], "ROBOT_FALLBACK_DAMPED_STOP")
        self.assertEqual(self.sm.current_state, AuthorityState.FALLBACK)

    def test_common_cause_failure_handling(self):
        decision = CommonCauseFailureHandler.handle_ccf("CCF-1", {})
        self.assertEqual(decision.reason_code, "CCF_1_POWER_FAILURE")
        self.assertEqual(decision.state_transition, AuthorityState.EMERGENCY)


class TestActionArbitration(unittest.TestCase):

    def setUp(self):
        self.sm = AuthorityTransitionStateMachine(initial_state=AuthorityState.AUTONOMOUS)
        self.arb = ActionArbitration(state_machine=self.sm)

    def test_lease_issuance_and_atomic_execution(self):
        prop = ActionProposal(
            action_type="MOVE_ACTUATOR",
            target_entity="arm_joint_1",
            risk_tier=RiskTier.TIER_1,
            requested_channel=PermittedChannel.REALTIME
        )

        lease, msg = self.arb.authorize_action(prop)
        self.assertIsNotNone(lease)
        self.assertEqual(lease.state, LeaseState.ACTIVE)

        # Atomic Execution Admission
        res = self.arb.admit_and_execute_lease(lease.lease_id, PermittedChannel.REALTIME)
        self.assertTrue(res.admitted)
        self.assertEqual(res.remaining_executions, 0)

        # Second execution attempt must fail (TOCTOU replay protection)
        res2 = self.arb.admit_and_execute_lease(lease.lease_id, PermittedChannel.REALTIME)
        self.assertFalse(res2.admitted)

    def test_lease_voiding_on_state_revision_mismatch(self):
        prop = ActionProposal(
            action_type="MOVE_ACTUATOR",
            risk_tier=RiskTier.TIER_1,
            requested_channel=PermittedChannel.REALTIME,
            state_revision=1
        )
        lease, _ = self.arb.authorize_action(prop)

        # Update state revision
        self.arb.update_state_revision(2)

        # Atomic execution attempt should void lease due to state revision mismatch
        res = self.arb.admit_and_execute_lease(lease.lease_id, PermittedChannel.REALTIME)
        self.assertFalse(res.admitted)
        self.assertIn("STATE_REVISION_MISMATCH", res.void_reason)

    def test_sa_revocation_authority(self):
        prop = ActionProposal(
            action_type="MOVE_ACTUATOR",
            risk_tier=RiskTier.TIER_1,
            requested_channel=PermittedChannel.REALTIME
        )
        lease, _ = self.arb.authorize_action(prop)

        sa_cred = AuthorizerCredential(
            authorizer_id="SA_AGENT",
            role=AuthorizerRole.SAFETY_ASSURANCE,
            signature="SIG_SA",
            timestamp_ns=time.time_ns()
        )

        success, msg = self.arb.revoke_lease(lease.lease_id, "Pre-emptive safety freeze", sa_cred)
        self.assertTrue(success)

        res = self.arb.admit_and_execute_lease(lease.lease_id, PermittedChannel.REALTIME)
        self.assertFalse(res.admitted)


if __name__ == "__main__":
    unittest.main()

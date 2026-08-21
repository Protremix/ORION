"""Pytest configuration — ensures all required env vars are set for testing."""
import os

# Set required env vars for all tests (fail-closed security requires these)
os.environ.setdefault("ORION_AUDIT_KEY", "test-audit-key-for-unit-tests")
os.environ.setdefault("ORION_POLICY_KEY", "test-policy-key-for-unit-tests")
os.environ.setdefault("ORION_AUDIT_SIGNING_KEY", "test-signing-key-for-unit-tests")
os.environ.setdefault("ORION_EMERGENCY_HMAC_KEY", "test-emergency-hmac-key")
os.environ.setdefault("ORION_FOUNDER_APPROVAL_KEY", "test-founder-approval-key")
os.environ.setdefault("ORION_LEASE_SIGNING_KEY", "test-lease-signing-key")
os.environ.setdefault("ORION_STATE_HMAC_KEY", "test-state-hmac-key")

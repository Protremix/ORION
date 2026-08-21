"""
Tests for ORION API Input Validation.

License: Apache 2.0
"""

import pytest

from src.api.validation import InputValidator, ValidationResult


class TestStringValidation:
    def test_valid_string(self):
        r = InputValidator.validate_string("hello")
        assert r.valid is True

    def test_none_rejected(self):
        r = InputValidator.validate_string(None)
        assert r.valid is False

    def test_non_string_rejected(self):
        r = InputValidator.validate_string(123)
        assert r.valid is False

    def test_too_long_rejected(self):
        r = InputValidator.validate_string("x" * 10001)
        assert r.valid is False

    def test_null_bytes_rejected(self):
        r = InputValidator.validate_string("hello\x00world")
        assert r.valid is False

    def test_custom_max_length(self):
        r = InputValidator.validate_string("hello", max_length=3)
        assert r.valid is False
        r = InputValidator.validate_string("hi", max_length=3)
        assert r.valid is True


class TestDictValidation:
    def test_valid_dict(self):
        r = InputValidator.validate_dict({"key": "value"})
        assert r.valid is True

    def test_none_rejected(self):
        r = InputValidator.validate_dict(None)
        assert r.valid is False

    def test_too_many_keys(self):
        r = InputValidator.validate_dict({f"k{i}": "v" for i in range(51)})
        assert r.valid is False

    def test_non_string_keys(self):
        r = InputValidator.validate_dict({1: "value"})
        assert r.valid is False


class TestGoalValidation:
    def test_valid_goal(self):
        r = InputValidator.validate_goal("Navigate robot to charging station")
        assert r.valid is True

    def test_dangerous_rm_rf(self):
        r = InputValidator.validate_goal("rm -rf /")
        assert r.valid is False

    def test_dangerous_sudo(self):
        r = InputValidator.validate_goal("sudo rm file")
        assert r.valid is False

    def test_dangerous_eval(self):
        r = InputValidator.validate_goal("eval(malicious_code)")
        assert r.valid is False

    def test_dangerous_exec(self):
        r = InputValidator.validate_goal("exec(command)")
        assert r.valid is False

    def test_too_long_goal(self):
        r = InputValidator.validate_goal("x" * 5001)
        assert r.valid is False


class TestDomainValidation:
    def test_valid_domain(self):
        for d in ["industrial", "vehicle", "home", "drone", "simulation"]:
            r = InputValidator.validate_domain(d)
            assert r.valid is True, f"Domain {d} should be valid"

    def test_invalid_domain(self):
        r = InputValidator.validate_domain("unknown_domain")
        assert r.valid is False

    def test_non_string_domain(self):
        r = InputValidator.validate_domain(123)
        assert r.valid is False


class TestActionValidation:
    def test_valid_action(self):
        r = InputValidator.validate_action({"action_type": "move", "parameters": {}})
        assert r.valid is True

    def test_missing_action_type(self):
        r = InputValidator.validate_action({"parameters": {}})
        assert r.valid is False

    def test_too_many_keys(self):
        r = InputValidator.validate_action({f"k{i}": "v" for i in range(21)})
        assert r.valid is False

    def test_none_rejected(self):
        r = InputValidator.validate_action(None)
        assert r.valid is False

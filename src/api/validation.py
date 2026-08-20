"""
ORION API Input Validation — Basic schema validation for API inputs.

License: Apache 2.0
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Union
from dataclasses import dataclass


@dataclass
class ValidationResult:
    """Result of input validation."""
    valid: bool
    errors: List[str]

    @property
    def ok(self) -> bool:
        return self.valid


class InputValidator:
    """
    Basic input validation for ORION API endpoints.
    Prevents malformed inputs from reaching internal systems.
    """

    # Max input sizes
    MAX_STRING_LENGTH = 10000
    MAX_QUERY_DEPTH = 5
    MAX_LIST_LENGTH = 1000
    MAX_METADATA_KEYS = 50

    @classmethod
    def validate_string(cls, value: Any, max_length: int = None) -> ValidationResult:
        """Validate a string input."""
        if value is None:
            return ValidationResult(valid=False, errors=["Value is None"])
        if not isinstance(value, str):
            return ValidationResult(valid=False, errors=[f"Expected string, got {type(value).__name__}"])
        limit = max_length or cls.MAX_STRING_LENGTH
        if len(value) > limit:
            return ValidationResult(valid=False, errors=[f"String too long: {len(value)} > {limit}"])
        # Block null bytes
        if "\x00" in value:
            return ValidationResult(valid=False, errors=["String contains null bytes"])
        return ValidationResult(valid=True, errors=[])

    @classmethod
    def validate_dict(cls, value: Any, max_keys: int = None) -> ValidationResult:
        """Validate a dictionary input."""
        if value is None:
            return ValidationResult(valid=False, errors=["Value is None"])
        if not isinstance(value, dict):
            return ValidationResult(valid=False, errors=[f"Expected dict, got {type(value).__name__}"])
        limit = max_keys or cls.MAX_METADATA_KEYS
        if len(value) > limit:
            return ValidationResult(valid=False, errors=[f"Too many keys: {len(value)} > {limit}"])
        errors = []
        for k, v in value.items():
            if not isinstance(k, str):
                errors.append(f"Non-string key: {k}")
        if errors:
            return ValidationResult(valid=False, errors=errors)
        return ValidationResult(valid=True, errors=[])

    @classmethod
    def validate_list(cls, value: Any, max_length: int = None) -> ValidationResult:
        """Validate a list input."""
        if value is None:
            return ValidationResult(valid=False, errors=["Value is None"])
        if not isinstance(value, list):
            return ValidationResult(valid=False, errors=[f"Expected list, got {type(value).__name__}"])
        limit = max_length or cls.MAX_LIST_LENGTH
        if len(value) > limit:
            return ValidationResult(valid=False, errors=[f"List too long: {len(value)} > {limit}"])
        return ValidationResult(valid=True, errors=[])

    @classmethod
    def validate_goal(cls, goal: Any) -> ValidationResult:
        """Validate a planning goal string."""
        result = cls.validate_string(goal, max_length=5000)
        if not result.valid:
            return result
        # Goals should not contain shell commands
        dangerous_patterns = [r"rm\s+-rf", r"sudo\s+", r"eval\s*\(", r"exec\s*\("]
        for pattern in dangerous_patterns:
            if re.search(pattern, goal, re.IGNORECASE):
                return ValidationResult(valid=False, errors=[f"Goal contains forbidden pattern: {pattern}"])
        return ValidationResult(valid=True, errors=[])

    @classmethod
    def validate_domain(cls, domain: Any) -> ValidationResult:
        """Validate a domain name."""
        result = cls.validate_string(domain, max_length=100)
        if not result.valid:
            return result
        allowed = {"industrial", "vehicle", "home", "drone", "simulation"}
        if domain not in allowed:
            return ValidationResult(valid=False, errors=[f"Unknown domain: {domain}. Allowed: {allowed}"])
        return ValidationResult(valid=True, errors=[])

    @classmethod
    def validate_action(cls, action: Any) -> ValidationResult:
        """Validate an action dictionary."""
        result = cls.validate_dict(action, max_keys=20)
        if not result.valid:
            return result
        # Check for required fields
        if "action_type" not in action:
            return ValidationResult(valid=False, errors=["Missing required field: action_type"])
        # Validate action_type
        type_result = cls.validate_string(action.get("action_type"), max_length=100)
        if not type_result.valid:
            return ValidationResult(valid=False, errors=[f"Invalid action_type: {type_result.errors}"])
        return ValidationResult(valid=True, errors=[])

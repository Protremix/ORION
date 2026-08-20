"""
Safety Enforcement Plane and Physical Watchdog package for ORION.
"""

try:
    from state_machine import (
        AuthorityState,
        AuthorityTransitionStateMachine,
        AuthorizerCredential,
        AuthorizerRole,
        StateTransitionRecord,
        TransitionEvidence,
        TransitionRule,
    )
except ImportError:
    from src.safety.state_machine import (
        AuthorityState,
        AuthorityTransitionStateMachine,
        AuthorizerCredential,
        AuthorizerRole,
        StateTransitionRecord,
        TransitionEvidence,
        TransitionRule,
    )

try:
    from safety.safety_enforcement import (
        AccelerationLimitCBF,
        BaseFallbackController,
        CommonCauseFailureHandler,
        ControlBarrierFunction,
        DecisionType,
        DroneFallbackController,
        FallbackDomain,
        ForceLimitCBF,
        HomeFallbackController,
        IndependenceRequirementStatus,
        IndependenceVerificationReport,
        IndustryFallbackController,
        JointLimitCBF,
        RobotFallbackController,
        SafetyDecision,
        SafetyEnforcement,
        SafetyScope,
        SafetySeverity,
        SpatialKeepOutCBF,
        VehicleFallbackController,
        VelocityLimitCBF,
    )
except ImportError:
    from src.safety.safety_enforcement import (
        AccelerationLimitCBF,
        BaseFallbackController,
        CommonCauseFailureHandler,
        ControlBarrierFunction,
        DecisionType,
        DroneFallbackController,
        FallbackDomain,
        ForceLimitCBF,
        HomeFallbackController,
        IndependenceRequirementStatus,
        IndependenceVerificationReport,
        IndustryFallbackController,
        JointLimitCBF,
        RobotFallbackController,
        SafetyDecision,
        SafetyEnforcement,
        SafetyScope,
        SafetySeverity,
        SpatialKeepOutCBF,
        VehicleFallbackController,
        VelocityLimitCBF,
    )

try:
    from physical_watchdog import (
        HardwareWatchdog,
        SoftwareWatchdog,
        WatchdogHierarchy,
    )
except ImportError:
    from src.safety.physical_watchdog import (
        HardwareWatchdog,
        SoftwareWatchdog,
        WatchdogHierarchy,
    )

try:
    from sensor_validation import SensorValidationPipeline
except ImportError:
    try:
        from src.safety.sensor_validation import SensorValidationPipeline
    except ImportError:
        SensorValidationPipeline = None

try:
    from actuator_verification import ActuatorVerifier
except ImportError:
    try:
        from src.safety.actuator_verification import ActuatorVerifier
    except ImportError:
        ActuatorVerifier = None

__all__ = [
    "AuthorityState",
    "AuthorizerRole",
    "AuthorizerCredential",
    "TransitionEvidence",
    "TransitionRule",
    "StateTransitionRecord",
    "AuthorityTransitionStateMachine",
    "DecisionType",
    "SafetyScope",
    "SafetySeverity",
    "SafetyDecision",
    "ControlBarrierFunction",
    "VelocityLimitCBF",
    "ForceLimitCBF",
    "SpatialKeepOutCBF",
    "JointLimitCBF",
    "AccelerationLimitCBF",
    "FallbackDomain",
    "BaseFallbackController",
    "HomeFallbackController",
    "VehicleFallbackController",
    "RobotFallbackController",
    "DroneFallbackController",
    "IndustryFallbackController",
    "CommonCauseFailureHandler",
    "IndependenceRequirementStatus",
    "IndependenceVerificationReport",
    "SafetyEnforcement",
    "HardwareWatchdog",
    "SoftwareWatchdog",
    "WatchdogHierarchy",
    "SensorValidationPipeline",
    "ActuatorVerifier",
]

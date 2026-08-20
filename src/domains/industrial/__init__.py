"""ORION Industrial Domain Module (Phase 2 Simulation).

Provides domain-specific entities and simulator for industrial automation factory floor,
including conveyor belts, robot arms, sensors, safety light curtains, emergency stops,
valve controllers, and liquid tank level monitoring.
"""

from src.domains.industrial.industrial_entities import (
    ConveyorBelt,
    EmergencyStopButton,
    IndustrialEntity,
    PressureSensor,
    RobotArm,
    SafetyLightCurtain,
    TankLevel,
    TemperatureSensor,
    ValveController,
)
from src.domains.industrial.industrial_simulator import IndustrialSimulation

__all__ = [
    "IndustrialEntity",
    "ConveyorBelt",
    "RobotArm",
    "PressureSensor",
    "TemperatureSensor",
    "SafetyLightCurtain",
    "EmergencyStopButton",
    "ValveController",
    "TankLevel",
    "IndustrialSimulation",
]

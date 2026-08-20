"""
ORION Hardware Abstraction Layer (HAL) — Master Spec §11

Formal abstraction between ORION intelligence and physical devices.
Core intelligence must NOT depend on one manufacturer.

Architecture:
    ORION INTELLIGENCE
           |
    SAFETY GATEWAY (src/safety/)
           |
    HARDWARE ABSTRACTION LAYER (this module)
           |
    DEVICE ADAPTER (per-manufacturer)
           |
    REAL DEVICE / SIMULATOR

License: Apache 2.0
"""

from __future__ import annotations

import abc
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Callable, Protocol

logger = logging.getLogger(__name__)


# ============================================================================
# Enums
# ============================================================================

class DeviceType(str, Enum):
    """Physical device categories."""
    ROBOT = "robot"
    VEHICLE = "vehicle"
    DRONE = "drone"
    HOME_DEVICE = "home_device"
    INDUSTRIAL = "industrial"
    SENSOR = "sensor"
    ACTUATOR = "actuator"
    UNKNOWN = "unknown"


class DeviceState(str, Enum):
    """Device operational state."""
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    READY = "ready"
    ACTIVE = "active"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"
    SHUTDOWN = "shutdown"
    ERROR = "error"


class ConnectionType(str, Enum):
    """Device communication protocol."""
    SERIAL = "serial"
    ETHERNET = "ethernet"
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    CAN_BUS = "can_bus"
    USB = "usb"
    SIMULATION = "simulation"
    CUSTOM = "custom"


# ============================================================================
# Data Classes
# ============================================================================

@dataclass
class DeviceCapability:
    """Describes a specific capability of a device."""
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    safety_level: str = "SC_3"  # Default to lowest criticality


@dataclass
class DeviceDescriptor:
    """Metadata describing a physical or simulated device."""
    device_id: str
    name: str
    manufacturer: str
    model: str
    device_type: DeviceType
    connection_type: ConnectionType
    capabilities: List[DeviceCapability] = field(default_factory=list)
    firmware_version: Optional[str] = None
    serial_number: Optional[str] = None
    safety_criticality: str = "SC_3"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DeviceCommand:
    """A command to be sent to a device through the HAL."""
    device_id: str
    command_type: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    priority: int = 0  # 0=normal, 1=high, 2=emergency
    timeout: float = 5.0  # seconds
    command_id: str = field(default_factory=lambda: f"cmd_{int(time.time() * 1000)}")


@dataclass
class DeviceResponse:
    """Response from a device after a command."""
    device_id: str
    command_id: str
    success: bool
    data: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    latency_ms: float = 0.0


@dataclass
class SensorReading:
    """A reading from a sensor device through the HAL."""
    device_id: str
    sensor_type: str
    value: Any
    unit: str = ""
    timestamp: float = field(default_factory=time.time)
    confidence: float = 1.0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ============================================================================
# Abstract Device Adapter (Protocol)
# ============================================================================

class DeviceAdapter(Protocol):
    """
    Protocol for device adapters — one per manufacturer or device family.
    
    Adapters translate ORION commands into device-specific protocols
    and translate device responses back to ORION format.
    
    The core intelligence NEVER talks to devices directly.
    Everything goes through the HAL → Adapter → Device chain.
    """

    @property
    def descriptor(self) -> DeviceDescriptor:
        """Return device metadata."""
        ...

    @property
    def state(self) -> DeviceState:
        """Return current device state."""
        ...

    def connect(self) -> bool:
        """Establish connection to the physical device."""
        ...

    def disconnect(self) -> bool:
        """Safely disconnect from the device."""
        ...

    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """Send a command to the device and return the response."""
        ...

    def read_sensor(self, sensor_type: str) -> SensorReading:
        """Read a sensor value from the device."""
        ...

    def get_capabilities(self) -> List[DeviceCapability]:
        """Return the list of capabilities this device supports."""
        ...

    def health_check(self) -> bool:
        """Check if the device is responsive and healthy."""
        ...

    def emergency_stop(self) -> bool:
        """Trigger an emergency stop on the device."""
        ...


# ============================================================================
# Base Device Adapter (Abstract Base Class)
# ============================================================================

class BaseDeviceAdapter(abc.ABC):
    """
    Abstract base class for device adapters.
    
    Subclasses implement device-specific communication.
    The HAL uses these adapters to talk to real or simulated devices.
    """

    def __init__(self, descriptor: DeviceDescriptor) -> None:
        self._descriptor = descriptor
        self._state: DeviceState = DeviceState.DISCONNECTED
        self._command_history: List[DeviceCommand] = []
        self._response_history: List[DeviceResponse] = []
        self._max_history = 1000

    @property
    def descriptor(self) -> DeviceDescriptor:
        return self._descriptor

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def device_id(self) -> str:
        return self._descriptor.device_id

    def _record_command(self, command: DeviceCommand) -> None:
        self._command_history.append(command)
        if len(self._command_history) > self._max_history:
            self._command_history.pop(0)

    def _record_response(self, response: DeviceResponse) -> None:
        self._response_history.append(response)
        if len(self._response_history) > self._max_history:
            self._response_history.pop(0)

    @abc.abstractmethod
    def connect(self) -> bool:
        """Establish connection to the device."""
        ...

    @abc.abstractmethod
    def disconnect(self) -> bool:
        """Disconnect from the device."""
        ...

    @abc.abstractmethod
    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """Send a command to the device."""
        ...

    @abc.abstractmethod
    def read_sensor(self, sensor_type: str) -> SensorReading:
        """Read a sensor value."""
        ...

    @abc.abstractmethod
    def get_capabilities(self) -> List[DeviceCapability]:
        """Return supported capabilities."""
        ...

    def health_check(self) -> bool:
        """Default health check — subclass can override."""
        return self._state in (DeviceState.READY, DeviceState.ACTIVE)

    def emergency_stop(self) -> bool:
        """Default emergency stop — send a zero/safe command."""
        logger.critical(f"EMERGENCY STOP on device {self.device_id}")
        cmd = DeviceCommand(
            device_id=self.device_id,
            command_type="emergency_stop",
            priority=2,
            timeout=1.0,
        )
        resp = self.send_command(cmd)
        return resp.success


# ============================================================================
# Hardware Abstraction Layer (HAL)
# ============================================================================

class HardwareAbstractionLayer:
    """
    ORION Hardware Abstraction Layer — Master Spec §11.
    
    The HAL is the single point of contact between ORION intelligence
    and physical devices. All commands pass through the Safety Gateway
    before reaching the HAL.
    
    The HAL:
    - Manages device registration and discovery
    - Routes commands to the correct adapter
    - Enforces the Safety Gateway check before any command
    - Tracks device health and state
    - Provides a uniform interface regardless of manufacturer
    """

    def __init__(self, safety_gateway: Optional[Any] = None) -> None:
        self._adapters: Dict[str, BaseDeviceAdapter] = {}
        self._safety_gateway = safety_gateway
        self._device_registry: Dict[str, DeviceDescriptor] = {}
        self._connection_callbacks: List[Callable[[str, DeviceState], None]] = []

    def register_adapter(self, adapter: BaseDeviceAdapter) -> bool:
        """Register a device adapter with the HAL."""
        desc = adapter.descriptor
        if desc.device_id in self._adapters:
            logger.warning(f"Device {desc.device_id} already registered, replacing")
        self._adapters[desc.device_id] = adapter
        self._device_registry[desc.device_id] = desc
        logger.info(f"Registered device: {desc.name} ({desc.device_id}) type={desc.device_type.value}")
        return True

    def unregister_device(self, device_id: str) -> bool:
        """Unregister a device from the HAL."""
        if device_id in self._adapters:
            adapter = self._adapters[device_id]
            if adapter.state != DeviceState.DISCONNECTED:
                adapter.disconnect()
            del self._adapters[device_id]
            self._device_registry.pop(device_id, None)
            logger.info(f"Unregistered device: {device_id}")
            return True
        return False

    def list_devices(self) -> List[DeviceDescriptor]:
        """List all registered devices."""
        return list(self._device_registry.values())

    def get_device(self, device_id: str) -> Optional[BaseDeviceAdapter]:
        """Get a device adapter by ID."""
        return self._adapters.get(device_id)

    def connect_device(self, device_id: str) -> bool:
        """Connect to a registered device."""
        adapter = self._adapters.get(device_id)
        if adapter is None:
            logger.error(f"Device {device_id} not registered")
            return False
        success = adapter.connect()
        if success:
            self._notify_callbacks(device_id, adapter.state)
        return success

    def disconnect_device(self, device_id: str) -> bool:
        """Disconnect from a device."""
        adapter = self._adapters.get(device_id)
        if adapter is None:
            return False
        success = adapter.disconnect()
        self._notify_callbacks(device_id, adapter.state)
        return success

    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        """
        Send a command to a device through the Safety Gateway.
        
        The Safety Gateway MUST approve the command before it reaches the device.
        If no Safety Gateway is configured, the command is rejected.
        """
        adapter = self._adapters.get(command.device_id)
        if adapter is None:
            return DeviceResponse(
                device_id=command.device_id,
                command_id=command.command_id,
                success=False,
                error=f"Device {command.device_id} not registered",
            )

        if adapter.state not in (DeviceState.READY, DeviceState.ACTIVE):
            return DeviceResponse(
                device_id=command.device_id,
                command_id=command.command_id,
                success=False,
                error=f"Device {command.device_id} not ready (state={adapter.state.value})",
            )

        # Safety Gateway check
        if self._safety_gateway is not None:
            approved = self._safety_gateway.approve_action(
                device_id=command.device_id,
                command_type=command.command_type,
                parameters=command.parameters,
                priority=command.priority,
            )
            if not approved:
                logger.warning(
                    f"Command {command.command_id} to {command.device_id} "
                    f"REJECTED by Safety Gateway"
                )
                return DeviceResponse(
                    device_id=command.device_id,
                    command_id=command.command_id,
                    success=False,
                    error="Command rejected by Safety Gateway",
                )
        else:
            logger.warning(
                f"No Safety Gateway configured — command {command.command_id} "
                f"to {command.device_id} rejected (safety policy: deny by default)"
            )
            return DeviceResponse(
                device_id=command.device_id,
                command_id=command.command_id,
                success=False,
                error="No Safety Gateway configured — deny by default",
            )

        # Route to adapter
        response = adapter.send_command(command)
        self._notify_callbacks(command.device_id, adapter.state)
        return response

    def read_sensor(self, device_id: str, sensor_type: str) -> SensorReading:
        """Read a sensor value from a device."""
        adapter = self._adapters.get(device_id)
        if adapter is None:
            return SensorReading(
                device_id=device_id,
                sensor_type=sensor_type,
                value=None,
                confidence=0.0,
                metadata={"error": "Device not registered"},
            )
        return adapter.read_sensor(sensor_type)

    def emergency_stop_all(self) -> Dict[str, bool]:
        """Emergency stop ALL registered devices."""
        results = {}
        for device_id, adapter in self._adapters.items():
            try:
                results[device_id] = adapter.emergency_stop()
            except Exception as e:
                logger.error(f"E-stop failed for {device_id}: {e}")
                results[device_id] = False
        return results

    def health_check_all(self) -> Dict[str, bool]:
        """Check health of all registered devices."""
        return {
            device_id: adapter.health_check()
            for device_id, adapter in self._adapters.items()
        }

    def on_state_change(self, callback: Callable[[str, DeviceState], None]) -> None:
        """Register a callback for device state changes."""
        self._connection_callbacks.append(callback)

    def _notify_callbacks(self, device_id: str, state: DeviceState) -> None:
        for cb in self._connection_callbacks:
            try:
                cb(device_id, state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")


# ============================================================================
# Simulation Adapter (for testing and simulation-first approach)
# ============================================================================

class SimulationAdapter(BaseDeviceAdapter):
    """
    A device adapter that simulates a physical device.
    Used for the simulation-first approach (Master Spec §10).
    """

    def __init__(
        self,
        descriptor: DeviceDescriptor,
        simulator: Optional[Any] = None,
    ) -> None:
        super().__init__(descriptor)
        self._simulator = simulator
        self._sensor_values: Dict[str, Any] = {}
        self._command_log: List[DeviceCommand] = []

    def connect(self) -> bool:
        self._state = DeviceState.READY
        logger.info(f"Simulation adapter {self.device_id} connected")
        return True

    def disconnect(self) -> bool:
        self._state = DeviceState.DISCONNECTED
        logger.info(f"Simulation adapter {self.device_id} disconnected")
        return True

    def send_command(self, command: DeviceCommand) -> DeviceResponse:
        start_time = time.time()
        self._record_command(command)
        self._command_log.append(command)

        if self._state not in (DeviceState.READY, DeviceState.ACTIVE):
            return DeviceResponse(
                device_id=self.device_id,
                command_id=command.command_id,
                success=False,
                error="Device not ready",
            )

        if command.command_type == "emergency_stop":
            self._state = DeviceState.EMERGENCY
            return DeviceResponse(
                device_id=self.device_id,
                command_id=command.command_id,
                success=True,
                data={"state": "emergency_stop"},
            )

        # If a simulator is attached, delegate to it
        if self._simulator is not None:
            try:
                sim_result = self._simulator.execute(command.command_type, command.parameters)
                latency = (time.time() - start_time) * 1000
                response = DeviceResponse(
                    device_id=self.device_id,
                    command_id=command.command_id,
                    success=True,
                    data=sim_result if isinstance(sim_result, dict) else {"result": sim_result},
                    latency_ms=latency,
                )
                self._record_response(response)
                return response
            except Exception as e:
                return DeviceResponse(
                    device_id=self.device_id,
                    command_id=command.command_id,
                    success=False,
                    error=str(e),
                )

        # Default: echo the command
        latency = (time.time() - start_time) * 1000
        response = DeviceResponse(
            device_id=self.device_id,
            command_id=command.command_id,
            success=True,
            data={"echo": command.parameters},
            latency_ms=latency,
        )
        self._record_response(response)
        return response

    def read_sensor(self, sensor_type: str) -> SensorReading:
        value = self._sensor_values.get(sensor_type, 0.0)
        return SensorReading(
            device_id=self.device_id,
            sensor_type=sensor_type,
            value=value,
        )

    def get_capabilities(self) -> List[DeviceCapability]:
        return self._descriptor.capabilities

    def set_sensor_value(self, sensor_type: str, value: Any) -> None:
        """Set a simulated sensor value (for testing)."""
        self._sensor_values[sensor_type] = value

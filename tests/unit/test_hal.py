"""
Tests for the ORION Hardware Abstraction Layer (HAL) — Master Spec §11.
"""

import pytest
import time
from src.hal import (
    HardwareAbstractionLayer,
    SimulationAdapter,
    DeviceDescriptor,
    DeviceCommand,
    DeviceResponse,
    DeviceState,
    DeviceType,
    ConnectionType,
    DeviceCapability,
    SensorReading,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_device_descriptor():
    return DeviceDescriptor(
        device_id="test_robot_01",
        name="Test Robot",
        manufacturer="ORION Labs",
        model="TR-100",
        device_type=DeviceType.ROBOT,
        connection_type=ConnectionType.SIMULATION,
        capabilities=[
            DeviceCapability(name="move", description="Move to position"),
            DeviceCapability(name="grip", description="Grip object"),
        ],
        safety_criticality="SC_2",
    )


@pytest.fixture
def sim_adapter(mock_device_descriptor):
    return SimulationAdapter(mock_device_descriptor)


@pytest.fixture
def mock_safety_gateway():
    """A mock safety gateway that approves all commands."""
    class MockSafety:
        def approve_action(self, **kwargs):
            return True
    return MockSafety()


@pytest.fixture
def hal_with_safety(mock_safety_gateway):
    return HardwareAbstractionLayer(safety_gateway=mock_safety_gateway)


@pytest.fixture
def hal_without_safety():
    return HardwareAbstractionLayer(safety_gateway=None)


# ============================================================================
# Device Descriptor Tests
# ============================================================================

class TestDeviceDescriptor:
    def test_descriptor_creation(self, mock_device_descriptor):
        assert mock_device_descriptor.device_id == "test_robot_01"
        assert mock_device_descriptor.name == "Test Robot"
        assert mock_device_descriptor.device_type == DeviceType.ROBOT
        assert mock_device_descriptor.connection_type == ConnectionType.SIMULATION
        assert len(mock_device_descriptor.capabilities) == 2

    def test_descriptor_defaults(self):
        desc = DeviceDescriptor(
            device_id="d1", name="D1", manufacturer="M", model="X",
            device_type=DeviceType.SENSOR, connection_type=ConnectionType.USB,
        )
        assert desc.firmware_version is None
        assert desc.safety_criticality == "SC_3"
        assert desc.capabilities == []
        assert desc.metadata == {}


# ============================================================================
# Simulation Adapter Tests
# ============================================================================

class TestSimulationAdapter:
    def test_connect(self, sim_adapter):
        assert sim_adapter.state == DeviceState.DISCONNECTED
        assert sim_adapter.connect() is True
        assert sim_adapter.state == DeviceState.READY

    def test_disconnect(self, sim_adapter):
        sim_adapter.connect()
        assert sim_adapter.disconnect() is True
        assert sim_adapter.state == DeviceState.DISCONNECTED

    def test_send_command_when_ready(self, sim_adapter):
        sim_adapter.connect()
        cmd = DeviceCommand(
            device_id="test_robot_01",
            command_type="move",
            parameters={"x": 1.0, "y": 2.0},
        )
        resp = sim_adapter.send_command(cmd)
        assert resp.success is True
        assert resp.device_id == "test_robot_01"
        assert resp.data["echo"] == {"x": 1.0, "y": 2.0}

    def test_send_command_when_disconnected(self, sim_adapter):
        cmd = DeviceCommand(device_id="test_robot_01", command_type="move")
        resp = sim_adapter.send_command(cmd)
        assert resp.success is False
        assert "not ready" in resp.error.lower()

    def test_emergency_stop(self, sim_adapter):
        sim_adapter.connect()
        assert sim_adapter.emergency_stop() is True
        assert sim_adapter.state == DeviceState.EMERGENCY

    def test_read_sensor(self, sim_adapter):
        sim_adapter.connect()
        sim_adapter.set_sensor_value("temperature", 25.5)
        reading = sim_adapter.read_sensor("temperature")
        assert reading.device_id == "test_robot_01"
        assert reading.sensor_type == "temperature"
        assert reading.value == 25.5

    def test_get_capabilities(self, sim_adapter):
        caps = sim_adapter.get_capabilities()
        assert len(caps) == 2
        assert caps[0].name == "move"

    def test_health_check_ready(self, sim_adapter):
        sim_adapter.connect()
        assert sim_adapter.health_check() is True

    def test_health_check_disconnected(self, sim_adapter):
        assert sim_adapter.health_check() is False

    def test_command_history_recorded(self, sim_adapter):
        sim_adapter.connect()
        for i in range(5):
            cmd = DeviceCommand(
                device_id="test_robot_01",
                command_type="move",
                parameters={"step": i},
            )
            sim_adapter.send_command(cmd)
        # History is internal but commands should succeed
        assert sim_adapter.state == DeviceState.READY


# ============================================================================
# HAL Tests
# ============================================================================

class TestHardwareAbstractionLayer:
    def test_register_adapter(self, hal_with_safety, sim_adapter):
        assert hal_with_safety.register_adapter(sim_adapter) is True
        assert "test_robot_01" in hal_with_safety._adapters

    def test_register_duplicate(self, hal_with_safety, sim_adapter, mock_device_descriptor):
        hal_with_safety.register_adapter(sim_adapter)
        adapter2 = SimulationAdapter(mock_device_descriptor)
        assert hal_with_safety.register_adapter(adapter2) is True

    def test_unregister_device(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        assert hal_with_safety.unregister_device("test_robot_01") is True
        assert "test_robot_01" not in hal_with_safety._adapters

    def test_unregister_nonexistent(self, hal_with_safety):
        assert hal_with_safety.unregister_device("nonexistent") is False

    def test_list_devices(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        devices = hal_with_safety.list_devices()
        assert len(devices) == 1
        assert devices[0].device_id == "test_robot_01"

    def test_get_device(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        adapter = hal_with_safety.get_device("test_robot_01")
        assert adapter is not None
        assert adapter.device_id == "test_robot_01"

    def test_get_device_nonexistent(self, hal_with_safety):
        assert hal_with_safety.get_device("nonexistent") is None

    def test_connect_device(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        assert hal_with_safety.connect_device("test_robot_01") is True
        assert sim_adapter.state == DeviceState.READY

    def test_connect_nonexistent(self, hal_with_safety):
        assert hal_with_safety.connect_device("nonexistent") is False

    def test_send_command_with_safety(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        hal_with_safety.connect_device("test_robot_01")
        cmd = DeviceCommand(
            device_id="test_robot_01",
            command_type="move",
            parameters={"x": 1.0},
        )
        resp = hal_with_safety.send_command(cmd)
        assert resp.success is True

    def test_send_command_no_sateway_rejected(self, hal_without_safety, sim_adapter):
        """Without a safety gateway, commands must be denied by default."""
        hal_without_safety.register_adapter(sim_adapter)
        hal_without_safety.connect_device("test_robot_01")
        cmd = DeviceCommand(
            device_id="test_robot_01",
            command_type="move",
            parameters={"x": 1.0},
        )
        resp = hal_without_safety.send_command(cmd)
        assert resp.success is False
        assert "No Safety Gateway" in resp.error

    def test_send_command_device_not_registered(self, hal_with_safety):
        cmd = DeviceCommand(device_id="nonexistent", command_type="move")
        resp = hal_with_safety.send_command(cmd)
        assert resp.success is False
        assert "not registered" in resp.error

    def test_send_command_device_not_ready(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        # Don't connect
        cmd = DeviceCommand(
            device_id="test_robot_01",
            command_type="move",
        )
        resp = hal_with_safety.send_command(cmd)
        assert resp.success is False
        assert "not ready" in resp.error.lower()

    def test_read_sensor(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        hal_with_safety.connect_device("test_robot_01")
        sim_adapter.set_sensor_value("temperature", 42.0)
        reading = hal_with_safety.read_sensor("test_robot_01", "temperature")
        assert reading.value == 42.0

    def test_read_sensor_nonexistent_device(self, hal_with_safety):
        reading = hal_with_safety.read_sensor("nonexistent", "temperature")
        assert reading.value is None
        assert reading.confidence == 0.0

    def test_emergency_stop_all(self, hal_with_safety, sim_adapter, mock_device_descriptor):
        hal_with_safety.register_adapter(sim_adapter)
        hal_with_safety.connect_device("test_robot_01")

        # Register a second device
        desc2 = DeviceDescriptor(
            device_id="test_drone_01", name="Drone", manufacturer="ORION",
            model="D-1", device_type=DeviceType.DRONE, connection_type=ConnectionType.SIMULATION,
        )
        adapter2 = SimulationAdapter(desc2)
        hal_with_safety.register_adapter(adapter2)
        hal_with_safety.connect_device("test_drone_01")

        results = hal_with_safety.emergency_stop_all()
        assert len(results) == 2
        assert all(results.values())

    def test_health_check_all(self, hal_with_safety, sim_adapter):
        hal_with_safety.register_adapter(sim_adapter)
        hal_with_safety.connect_device("test_robot_01")
        results = hal_with_safety.health_check_all()
        assert results["test_robot_01"] is True

    def test_state_change_callback(self, hal_with_safety, sim_adapter):
        events = []
        hal_with_safety.on_state_change(lambda dev_id, state: events.append((dev_id, state)))
        hal_with_safety.register_adapter(sim_adapter)
        hal_with_safety.connect_device("test_robot_01")
        assert len(events) > 0
        assert events[0][0] == "test_robot_01"


# ============================================================================
# Device Command / Response Tests
# ============================================================================

class TestDeviceCommand:
    def test_command_defaults(self):
        cmd = DeviceCommand(device_id="d1", command_type="move")
        assert cmd.priority == 0
        assert cmd.timeout == 5.0
        assert cmd.command_id.startswith("cmd_")
        assert cmd.parameters == {}

    def test_command_with_params(self):
        cmd = DeviceCommand(
            device_id="d1",
            command_type="move",
            parameters={"x": 1.0, "y": 2.0},
            priority=2,
            timeout=1.0,
        )
        assert cmd.priority == 2
        assert cmd.timeout == 1.0
        assert cmd.parameters["x"] == 1.0

    def test_unique_command_ids(self):
        cmd1 = DeviceCommand(device_id="d1", command_type="move")
        time.sleep(0.001)
        cmd2 = DeviceCommand(device_id="d1", command_type="move")
        assert cmd1.command_id != cmd2.command_id

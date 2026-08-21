# Copyright 2026 ORION Physical Intelligence OS Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Unit tests for ORION Monitoring Dashboard (Phase 5).

Covers:
- Metrics collection from all 4 domain types (Industrial, Home, Drone, Vehicle)
- Text dashboard rendering (ASCII art style)
- JSON dashboard rendering (valid JSON)
- HTML dashboard rendering (self-contained HTML table)
- Alert generation for low battery (WARNING and CRITICAL)
- Alert generation for high temperature
- Alert generation for emergency status & E-Stop
- Threshold checking (default and custom)
- Monitoring dashboard full cycle
- Status summary generation
"""

import json
import unittest
from typing import Any, Dict

from src.domains.drone.drone_simulator import DroneSimulation
from src.domains.home.home_simulator import HomeSimulation
from src.domains.industrial.industrial_simulator import IndustrialSimulation
from src.domains.vehicle.vehicle_simulator import VehicleSimulation
from src.monitoring.dashboard import (
    Alert,
    AlertLevel,
    AlertManager,
    DashboardRenderer,
    MetricsCollector,
    MonitoringDashboard,
)


class MockCustomSimulator:
    """Mock simulator providing custom metrics."""

    def __init__(self, system_status: str = "NOMINAL", battery: float = 100.0, temp: float = 25.0) -> None:
        self.system_status = system_status
        self.battery = battery
        self.temperature = temp

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "system_status": self.system_status,
            "state": "MOCK_RUNNING",
            "safety_events": 0,
            "entity_count": 5,
            "battery": self.battery,
            "temperature": self.temperature,
        }


class TestMonitoringDashboard(unittest.TestCase):
    """Test suite for Phase 5 Monitoring Dashboard components."""

    def setUp(self) -> None:
        self.industrial_sim = IndustrialSimulation()
        self.home_sim = HomeSimulation()
        self.drone_sim = DroneSimulation()
        self.vehicle_sim = VehicleSimulation()

        self.collector = MetricsCollector()
        self.collector.register_domain("industrial", self.industrial_sim)
        self.collector.register_domain("home", self.home_sim)
        self.collector.register_domain("drone", self.drone_sim)
        self.collector.register_domain("vehicle", self.vehicle_sim)

    def test_metrics_collection_all_4_domains(self) -> None:
        """1. Verify metrics collection from all 4 domain types."""
        metrics = self.collector.collect_metrics()

        self.assertIn("industrial", metrics)
        self.assertIn("home", metrics)
        self.assertIn("drone", metrics)
        self.assertIn("vehicle", metrics)

        # Industrial checks
        ind = metrics["industrial"]
        self.assertEqual(ind["domain_id"], "industrial")
        self.assertEqual(ind["system_status"], "NOMINAL")
        self.assertEqual(ind["state"], "STOPPED")
        self.assertEqual(ind["e_stop"], False)
        self.assertEqual(ind["temperature"], 25.0)

        # Home checks
        home = metrics["home"]
        self.assertEqual(home["domain_id"], "home")
        self.assertEqual(home["system_status"], "NOMINAL")
        self.assertEqual(home["power"], 0.0)
        self.assertEqual(home["temperature"], 22.0)

        # Drone checks
        drone = metrics["drone"]
        self.assertEqual(drone["domain_id"], "drone")
        self.assertEqual(drone["system_status"], "NOMINAL")
        self.assertEqual(drone["state"], "IDLE")
        self.assertEqual(drone["battery"], 100.0)

        # Vehicle checks
        vehicle = metrics["vehicle"]
        self.assertEqual(vehicle["domain_id"], "vehicle")
        self.assertEqual(vehicle["system_status"], "NOMINAL")
        self.assertEqual(vehicle["state"], "IDLE")
        self.assertEqual(vehicle["speed"], 0.0)

    def test_text_dashboard_rendering(self) -> None:
        """2. Verify text dashboard rendering contains domain names and statuses."""
        renderer = DashboardRenderer(self.collector)
        text_out = renderer.render_text_dashboard()

        self.assertIsInstance(text_out, str)
        self.assertIn("ORION PHYSICAL INTELLIGENCE OS - MONITORING DASHBOARD", text_out)
        self.assertIn("INDUSTRIAL", text_out)
        self.assertIn("HOME", text_out)
        self.assertIn("DRONE", text_out)
        self.assertIn("VEHICLE", text_out)
        self.assertIn("System Status: NOMINAL", text_out)

    def test_json_dashboard_rendering(self) -> None:
        """3. Verify JSON dashboard rendering produces valid JSON with all domains."""
        renderer = DashboardRenderer(self.collector)
        json_out = renderer.render_json_dashboard()

        self.assertIsInstance(json_out, str)
        parsed = json.loads(json_out)
        self.assertIn("industrial", parsed)
        self.assertIn("home", parsed)
        self.assertIn("drone", parsed)
        self.assertIn("vehicle", parsed)
        self.assertEqual(parsed["drone"]["battery"], 100.0)

    def test_html_dashboard_rendering(self) -> None:
        """4. Verify HTML dashboard rendering contains a table with domain data."""
        renderer = DashboardRenderer(self.collector)
        html_out = renderer.render_html_dashboard()

        self.assertIsInstance(html_out, str)
        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("<h1>ORION Physical Intelligence OS &mdash; Monitoring Dashboard</h1>", html_out)
        self.assertIn("<table>", html_out)
        self.assertIn("<th>Domain ID</th>", html_out)
        self.assertIn("<strong>industrial</strong>", html_out)
        self.assertIn("<strong>drone</strong>", html_out)
        self.assertIn("<strong>vehicle</strong>", html_out)
        self.assertIn("<strong>home</strong>", html_out)
        self.assertIn("class='status nominal'", html_out)

    def test_alert_generation_low_battery(self) -> None:
        """5. Verify alert generation for low battery (< 20% WARNING, < 10% CRITICAL)."""
        alert_mgr = AlertManager()

        # Test battery at 15% -> WARNING
        metrics_warn = {
            "drone": {
                "domain_id": "drone",
                "system_status": "NOMINAL",
                "battery": 15.0,
            }
        }
        alerts = alert_mgr.check_thresholds(metrics_warn)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].level, AlertLevel.WARNING)
        self.assertEqual(alerts[0].metric, "battery")
        self.assertEqual(alerts[0].domain_id, "drone")

        # Test battery at 5% -> CRITICAL
        metrics_crit = {
            "drone": {
                "domain_id": "drone",
                "system_status": "NOMINAL",
                "battery": 5.0,
            }
        }
        alerts_crit = alert_mgr.check_thresholds(metrics_crit)
        self.assertEqual(len(alerts_crit), 1)
        self.assertEqual(alerts_crit[0].level, AlertLevel.CRITICAL)
        self.assertEqual(alerts_crit[0].metric, "battery")

    def test_alert_generation_high_temperature(self) -> None:
        """6. Verify alert generation for high temperature (> 80°C WARNING)."""
        alert_mgr = AlertManager()
        metrics = {
            "industrial": {
                "domain_id": "industrial",
                "system_status": "NOMINAL",
                "temperature": 85.5,
            }
        }
        alerts = alert_mgr.check_thresholds(metrics)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].level, AlertLevel.WARNING)
        self.assertEqual(alerts[0].metric, "temperature")
        self.assertEqual(alerts[0].value, 85.5)

    def test_alert_generation_emergency_status(self) -> None:
        """7. Verify alert generation for emergency system status and E-Stop."""
        alert_mgr = AlertManager()
        metrics = {
            "home": {
                "domain_id": "home",
                "system_status": "EMERGENCY",
            },
            "industrial": {
                "domain_id": "industrial",
                "system_status": "NOMINAL",
                "e_stop": True,
            },
        }
        alerts = alert_mgr.check_thresholds(metrics)
        self.assertEqual(len(alerts), 2)

        levels = [a.level for a in alerts]
        self.assertTrue(all(lvl == AlertLevel.EMERGENCY for lvl in levels))

        metrics_list = [a.metric for a in alerts]
        self.assertIn("system_status", metrics_list)
        self.assertIn("e_stop", metrics_list)

    def test_threshold_checking(self) -> None:
        """8. Verify threshold checking with custom configurable thresholds."""
        custom_thresholds = {
            "battery_warning": 30.0,
            "battery_critical": 15.0,
            "temperature_warning": 50.0,
        }
        alert_mgr = AlertManager(thresholds=custom_thresholds)

        metrics = {
            "drone": {"domain_id": "drone", "battery": 25.0},
            "industrial": {"domain_id": "industrial", "temperature": 55.0},
        }
        alerts = alert_mgr.check_thresholds(metrics)
        self.assertEqual(len(alerts), 2)

        battery_alert = next(a for a in alerts if a.metric == "battery")
        self.assertEqual(battery_alert.level, AlertLevel.WARNING)

        temp_alert = next(a for a in alerts if a.metric == "temperature")
        self.assertEqual(temp_alert.level, AlertLevel.WARNING)

    def test_monitoring_dashboard_full_cycle(self) -> None:
        """9. Verify MonitoringDashboard run_cycle collects metrics, checks thresholds, and renders dashboard."""
        dash = MonitoringDashboard(metrics_collector=self.collector)
        cycle_result = dash.run_cycle()

        self.assertIn("metrics", cycle_result)
        self.assertIn("alerts", cycle_result)
        self.assertIn("text_dashboard", cycle_result)
        self.assertIn("json_dashboard", cycle_result)
        self.assertIn("html_dashboard", cycle_result)
        self.assertIn("summary", cycle_result)

        self.assertEqual(len(cycle_result["metrics"]), 4)
        self.assertEqual(len(cycle_result["alerts"]), 0)
        self.assertIn("ORION PHYSICAL INTELLIGENCE OS", cycle_result["text_dashboard"])
        self.assertIn("<!DOCTYPE html>", cycle_result["html_dashboard"])

    def test_status_summary_generation(self) -> None:
        """10. Verify get_status_summary generation under nominal and alert conditions."""
        dash = MonitoringDashboard()
        dash.register_domain("drone", MockCustomSimulator(system_status="NOMINAL", battery=100.0))

        summary_nominal = dash.get_status_summary()
        self.assertIn("Active Domains: 1", summary_nominal)
        self.assertIn("System Status: NOMINAL", summary_nominal)
        self.assertIn("Active Alerts: 0", summary_nominal)

        # Update simulator to low battery
        dash.register_domain("drone", MockCustomSimulator(system_status="NOMINAL", battery=5.0))
        dash.run_cycle()
        summary_alert = dash.get_status_summary()

        self.assertIn("System Status: CRITICAL", summary_alert)
        self.assertIn("Active Alerts: 1", summary_alert)

    def test_unregister_domain_and_alert_clearing(self) -> None:
        """11. Test unregistering domain and alert clearing."""
        collector = MetricsCollector()
        collector.register_domain("temp_dom", MockCustomSimulator())
        self.assertIn("temp_dom", collector.collect_metrics())

        collector.unregister_domain("temp_dom")
        self.assertNotIn("temp_dom", collector.collect_metrics())

        alert_mgr = AlertManager()
        alert_mgr.check_thresholds({"drone": {"battery": 5.0}})
        self.assertEqual(len(alert_mgr.generate_alerts()), 1)

        alert_mgr.clear_alerts()
        self.assertEqual(len(alert_mgr.generate_alerts()), 0)

    def test_alert_dataclass_methods(self) -> None:
        """12. Test Alert dataclass to_dict and bracket index access."""
        alert = Alert(
            domain_id="industrial",
            level=AlertLevel.WARNING,
            metric="temperature",
            value=85.0,
            message="High temperature warning",
        )
        self.assertEqual(alert["domain_id"], "industrial")
        self.assertEqual(alert["level"], "WARNING")

        d = alert.to_dict()
        self.assertEqual(d["level"], "WARNING")
        self.assertEqual(d["metric"], "temperature")


if __name__ == "__main__":
    unittest.main()

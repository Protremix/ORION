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
ORION Monitoring Dashboard (Phase 5).

Provides monitoring, metrics collection, ASCII text, JSON, and
HTML dashboard rendering, and alert threshold monitoring across all ORION physical
domains (Industrial, Vehicle, Smart Home, Drone).

Apache 2.0 Licensed. No external dependencies.
"""

from __future__ import annotations

import html
import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


class AlertLevel(str, Enum):
    """Alert severity levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


@dataclass
class Alert:
    """Represents an active monitoring alert."""
    domain_id: str
    level: Union[str, AlertLevel]
    metric: str
    value: Any
    message: str
    timestamp: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        if isinstance(self.level, AlertLevel):
            self.level = self.level.value

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_id": self.domain_id,
            "level": str(self.level),
            "metric": self.metric,
            "value": self.value,
            "message": self.message,
            "timestamp": self.timestamp,
        }

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class MetricsCollector:
    """Collects system and domain metrics from registered domain simulators."""

    def __init__(self) -> None:
        self.domains: Dict[str, Any] = {}

    def register_domain(self, domain_id: str, simulator: Any) -> None:
        """Register a domain simulator for metric collection."""
        self.domains[domain_id] = simulator

    def unregister_domain(self, domain_id: str) -> None:
        """Unregister a domain simulator."""
        self.domains.pop(domain_id, None)

    def collect_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Collect current metrics from all registered domains."""
        metrics: Dict[str, Dict[str, Any]] = {}
        for domain_id, sim in self.domains.items():
            metrics[domain_id] = self._extract_domain_metrics(domain_id, sim)
        return metrics

    def _extract_domain_metrics(self, domain_id: str, sim: Any) -> Dict[str, Any]:
        """Extract standard and domain-specific metrics from a domain simulator."""
        domain_metrics: Dict[str, Any] = {
            "domain_id": domain_id,
            "system_status": "NOMINAL",
            "state": "NOMINAL",
            "safety_events": 0,
            "entity_count": 0,
            "battery": None,
            "power": None,
            "e_stop": None,
            "speed": None,
            "temperature": None,
            "timestamp": time.time(),
        }

        # Check if simulator exposes get_metrics or collect_metrics method
        if hasattr(sim, "get_metrics") and callable(sim.get_metrics):
            try:
                custom_metrics = sim.get_metrics()
                if isinstance(custom_metrics, dict):
                    domain_metrics.update(custom_metrics)
            except Exception as e:
                logger.warning(f"Error calling get_metrics on {domain_id}: {e}")
        elif (
            hasattr(sim, "collect_metrics")
            and callable(sim.collect_metrics)
            and sim.__class__.__name__ != "MetricsCollector"
        ):
            try:
                custom_metrics = sim.collect_metrics()
                if isinstance(custom_metrics, dict):
                    domain_metrics.update(custom_metrics)
            except Exception as e:
                logger.warning(f"Error calling collect_metrics on {domain_id}: {e}")

        # Extract system_status
        if hasattr(sim, "system_status"):
            status_val = getattr(sim, "system_status")
            if hasattr(status_val, "value"):
                domain_metrics["system_status"] = str(status_val.value)
            elif status_val is not None:
                domain_metrics["system_status"] = str(status_val)

        # Extract state
        if hasattr(sim, "state") and sim.state is not None:
            domain_metrics["state"] = str(sim.state)
        elif hasattr(sim, "drone") and hasattr(sim.drone, "state") and sim.drone.state is not None:
            domain_metrics["state"] = str(sim.drone.state)
        elif hasattr(sim, "ego_vehicle") and hasattr(sim.ego_vehicle, "state") and sim.ego_vehicle.state is not None:
            domain_metrics["state"] = str(sim.ego_vehicle.state)
        elif hasattr(sim, "conveyor") and hasattr(sim.conveyor, "status") and sim.conveyor.status is not None:
            domain_metrics["state"] = str(sim.conveyor.status)

        # Extract safety_events count
        if hasattr(sim, "safety_events"):
            se = getattr(sim, "safety_events")
            if isinstance(se, (list, tuple, set, dict)):
                domain_metrics["safety_events"] = len(se)
            elif isinstance(se, (int, float)):
                domain_metrics["safety_events"] = int(se)
        elif hasattr(sim, "_safety_events"):
            se = getattr(sim, "_safety_events")
            if isinstance(se, (list, tuple, set, dict)):
                domain_metrics["safety_events"] = len(se)

        # Extract entity count
        if hasattr(sim, "entities"):
            entities = getattr(sim, "entities")
            if isinstance(entities, (dict, list, tuple, set)):
                domain_metrics["entity_count"] = len(entities)
            elif isinstance(entities, (int, float)):
                domain_metrics["entity_count"] = int(entities)
        elif hasattr(sim, "vehicles"):
            vehicles = getattr(sim, "vehicles")
            if isinstance(vehicles, (dict, list, tuple, set)):
                domain_metrics["entity_count"] = len(vehicles)
        if domain_metrics["entity_count"] == 0:
            domain_metrics["entity_count"] = 1

        # Extract domain-specific: Battery (Drone/Mobile)
        if hasattr(sim, "battery"):
            b = getattr(sim, "battery")
            if hasattr(b, "capacity_pct"):
                domain_metrics["battery"] = float(b.capacity_pct)
            elif hasattr(b, "percentage"):
                domain_metrics["battery"] = float(b.percentage)
            elif hasattr(b, "level"):
                domain_metrics["battery"] = float(b.level)
            elif isinstance(b, (int, float)):
                domain_metrics["battery"] = float(b)
        if domain_metrics["battery"] is None and hasattr(sim, "battery_pct"):
            domain_metrics["battery"] = float(getattr(sim, "battery_pct"))
        if domain_metrics["battery"] is None and hasattr(sim, "drone") and hasattr(sim.drone, "battery_pct"):
            domain_metrics["battery"] = float(sim.drone.battery_pct)

        # Extract domain-specific: Power (Home)
        if hasattr(sim, "energy") and hasattr(sim.energy, "power_usage_kw"):
            domain_metrics["power"] = float(sim.energy.power_usage_kw)
        elif hasattr(sim, "power_usage_kw"):
            domain_metrics["power"] = float(getattr(sim, "power_usage_kw"))
        elif hasattr(sim, "power"):
            p = getattr(sim, "power")
            if isinstance(p, (int, float)):
                domain_metrics["power"] = float(p)

        # Extract domain-specific: E-Stop (Industrial)
        if hasattr(sim, "estop_button") and hasattr(sim.estop_button, "is_pressed"):
            domain_metrics["e_stop"] = bool(sim.estop_button.is_pressed)
        elif hasattr(sim, "e_stop"):
            domain_metrics["e_stop"] = bool(getattr(sim, "e_stop"))
        elif hasattr(sim, "estop"):
            domain_metrics["e_stop"] = bool(getattr(sim, "estop"))

        # Extract domain-specific: Speed (Vehicle)
        if hasattr(sim, "ego_vehicle") and hasattr(sim.ego_vehicle, "speed"):
            domain_metrics["speed"] = float(sim.ego_vehicle.speed)
        elif hasattr(sim, "speed"):
            s = getattr(sim, "speed")
            if isinstance(s, (int, float)):
                domain_metrics["speed"] = float(s)

        # Extract Temperature
        if hasattr(sim, "temp_sensor") and hasattr(sim.temp_sensor, "current_temperature"):
            domain_metrics["temperature"] = float(sim.temp_sensor.current_temperature)
        elif hasattr(sim, "living_room") and hasattr(sim.living_room, "temperature"):
            domain_metrics["temperature"] = float(sim.living_room.temperature)
        elif hasattr(sim, "temperature"):
            t = getattr(sim, "temperature")
            if isinstance(t, (int, float)):
                domain_metrics["temperature"] = float(t)

        return domain_metrics


class DashboardRenderer:
    """Renders metrics into ASCII text, JSON, or HTML dashboard formats."""

    def __init__(self, metrics_collector: Optional[MetricsCollector] = None) -> None:
        self.metrics_collector = metrics_collector

    def _resolve_metrics(self, metrics: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if metrics is not None:
            return metrics
        if self.metrics_collector is not None:
            return self.metrics_collector.collect_metrics()
        return {}

    def render_text_dashboard(self, metrics: Optional[Dict[str, Any]] = None) -> str:
        """Render text-based dashboard (ASCII art style)."""
        m_data = self._resolve_metrics(metrics)
        domains_map = m_data.get("domains", m_data) if isinstance(m_data, dict) and "domains" in m_data else m_data

        lines = [
            "+" + "=" * 78 + "+",
            "|           ORION PHYSICAL INTELLIGENCE OS - MONITORING DASHBOARD            |",
            "+" + "=" * 78 + "+",
            f"| Active Domains Registered: {len(domains_map):<48} |",
            "+" + "-" * 78 + "+",
            "| DOMAIN STATUS AND METRICS SUMMARY                                           |",
            "+" + "-" * 78 + "+",
        ]

        if not domains_map or not isinstance(domains_map, dict):
            lines.append("|  [No domain metrics collected]                                             |")
        else:
            for domain_id, d_metrics in domains_map.items():
                if not isinstance(d_metrics, dict):
                    continue
                sys_status = d_metrics.get("system_status", "UNKNOWN")
                state = d_metrics.get("state", "UNKNOWN")
                entities = d_metrics.get("entity_count", 0)
                safety_events = d_metrics.get("safety_events", 0)

                lines.append(f"| [{str(domain_id).upper()}]")
                lines.append(f"|   System Status: {sys_status:<15} State: {state}")
                lines.append(f"|   Entities: {entities:<20} Safety Events: {safety_events}")

                spec_parts = []
                if d_metrics.get("battery") is not None:
                    spec_parts.append(f"Battery: {d_metrics['battery']:.1f}%")
                if d_metrics.get("power") is not None:
                    spec_parts.append(f"Power: {d_metrics['power']:.2f} kW")
                if d_metrics.get("e_stop") is not None:
                    spec_parts.append(f"E-Stop: {'TRIGGERED' if d_metrics['e_stop'] else 'NORMAL'}")
                if d_metrics.get("speed") is not None:
                    spec_parts.append(f"Speed: {d_metrics['speed']:.2f} m/s")
                if d_metrics.get("temperature") is not None:
                    spec_parts.append(f"Temp: {d_metrics['temperature']:.1f}°C")

                if spec_parts:
                    lines.append(f"|   Domain Metrics: {' | '.join(spec_parts)}")
                lines.append("+" + "-" * 78 + "+")

        lines.append("+" + "=" * 78 + "+")
        return "\n".join(lines)

    def render_json_dashboard(self, metrics: Optional[Dict[str, Any]] = None) -> str:
        """Render metrics as JSON for API consumption."""
        m_data = self._resolve_metrics(metrics)
        return json.dumps(m_data, indent=2, default=str)

    def render_html_dashboard(self, metrics: Optional[Dict[str, Any]] = None) -> str:
        """Render a simple HTML dashboard (self-contained, no external deps)."""
        m_data = self._resolve_metrics(metrics)
        domains_map = m_data.get("domains", m_data) if isinstance(m_data, dict) and "domains" in m_data else m_data

        rows_html = []
        if isinstance(domains_map, dict):
            for domain_id, d_metrics in domains_map.items():
                if not isinstance(d_metrics, dict):
                    continue
                sys_status = str(d_metrics.get("system_status", "UNKNOWN"))
                state = str(d_metrics.get("state", "UNKNOWN"))
                entities = d_metrics.get("entity_count", 0)
                safety_events = d_metrics.get("safety_events", 0)

                spec_parts = []
                if d_metrics.get("battery") is not None:
                    spec_parts.append(f"Battery: {d_metrics['battery']:.1f}%")
                if d_metrics.get("power") is not None:
                    spec_parts.append(f"Power: {d_metrics['power']:.2f} kW")
                if d_metrics.get("e_stop") is not None:
                    spec_parts.append(f"E-Stop: {'TRIGGERED' if d_metrics['e_stop'] else 'NORMAL'}")
                if d_metrics.get("speed") is not None:
                    spec_parts.append(f"Speed: {d_metrics['speed']:.2f} m/s")
                if d_metrics.get("temperature") is not None:
                    spec_parts.append(f"Temp: {d_metrics['temperature']:.1f}°C")

                spec_str = ", ".join(spec_parts) if spec_parts else "N/A"
                status_class = sys_status.lower()

                rows_html.append(
                    f"<tr>"
                    f"<td><strong>{html.escape(str(domain_id))}</strong></td>"
                    f"<td><span class='status {html.escape(status_class)}'>{html.escape(str(sys_status))}</span></td>"
                    f"<td>{html.escape(str(state))}</td>"
                    f"<td>{html.escape(str(entities))}</td>"
                    f"<td>{html.escape(str(safety_events))}</td>"
                    f"<td>{html.escape(str(spec_str))}</td>"
                    f"</tr>"
                )

        rows_content = "\n".join(rows_html) if rows_html else "<tr><td colspan='6'>No domain data available</td></tr>"

        html_output = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>ORION Physical Intelligence OS - Monitoring Dashboard</title>
    <style>
        body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #121212; color: #e0e0e0; margin: 0; padding: 24px; }}
        h1 {{ color: #00bcd4; font-size: 24px; border-bottom: 2px solid #00bcd4; padding-bottom: 12px; margin-bottom: 24px; }}
        table {{ width: 100%; border-collapse: collapse; background-color: #1e1e1e; box-shadow: 0 4px 6px rgba(0,0,0,0.3); border-radius: 8px; overflow: hidden; }}
        th, td {{ border: 1px solid #333333; padding: 14px 16px; text-align: left; }}
        th {{ background-color: #263238; color: #80deea; text-transform: uppercase; font-size: 12px; letter-spacing: 1px; }}
        tr:nth-child(even) {{ background-color: #252525; }}
        .status {{ padding: 6px 12px; border-radius: 12px; font-weight: bold; font-size: 12px; display: inline-block; }}
        .status.nominal {{ background-color: #2e7d32; color: #ffffff; }}
        .status.warning {{ background-color: #f57f17; color: #ffffff; }}
        .status.critical {{ background-color: #c62828; color: #ffffff; }}
        .status.emergency {{ background-color: #b71c1c; color: #ffffff; }}
    </style>
</head>
<body>
    <h1>ORION Physical Intelligence OS &mdash; Monitoring Dashboard</h1>
    <table>
        <thead>
            <tr>
                <th>Domain ID</th>
                <th>System Status</th>
                <th>State</th>
                <th>Entities</th>
                <th>Safety Events</th>
                <th>Domain Specific Metrics</th>
            </tr>
        </thead>
        <tbody>
            {rows_content}
        </tbody>
    </table>
</body>
</html>"""
        return html_output


class AlertManager:
    """Evaluates domain metrics against thresholds and generates active alerts."""

    def __init__(self, thresholds: Optional[Dict[str, Any]] = None) -> None:
        self.thresholds: Dict[str, Any] = {
            "battery_warning": 20.0,
            "battery_critical": 10.0,
            "temperature_warning": 80.0,
            "system_status_emergency": ["EMERGENCY"],
        }
        if thresholds:
            self.thresholds.update(thresholds)
        self.active_alerts: List[Alert] = []

    def check_thresholds(self, metrics: Dict[str, Any]) -> List[Alert]:
        """Check all metrics against configurable thresholds."""
        new_alerts: List[Alert] = []

        domains_data = metrics.get("domains", metrics) if isinstance(metrics, dict) else {}
        if not isinstance(domains_data, dict):
            domains_data = {}

        for domain_id, d_metrics in domains_data.items():
            if not isinstance(d_metrics, dict):
                continue

            # System Status == EMERGENCY
            sys_status = str(d_metrics.get("system_status", "")).upper()
            emergency_statuses = [s.upper() for s in self.thresholds.get("system_status_emergency", ["EMERGENCY"])]
            if sys_status in emergency_statuses:
                new_alerts.append(
                    Alert(
                        domain_id=domain_id,
                        level=AlertLevel.EMERGENCY,
                        metric="system_status",
                        value=sys_status,
                        message=f"Domain {domain_id} system status is {sys_status}",
                    )
                )

            # E-Stop
            e_stop = d_metrics.get("e_stop")
            if e_stop is True:
                new_alerts.append(
                    Alert(
                        domain_id=domain_id,
                        level=AlertLevel.EMERGENCY,
                        metric="e_stop",
                        value=True,
                        message=f"Domain {domain_id} emergency stop activated",
                    )
                )

            # Battery threshold: < 20% WARNING, < 10% CRITICAL
            battery = d_metrics.get("battery")
            if battery is not None and isinstance(battery, (int, float)):
                crit_thresh = float(self.thresholds.get("battery_critical", 10.0))
                warn_thresh = float(self.thresholds.get("battery_warning", 20.0))

                if battery < crit_thresh:
                    new_alerts.append(
                        Alert(
                            domain_id=domain_id,
                            level=AlertLevel.CRITICAL,
                            metric="battery",
                            value=float(battery),
                            message=f"Domain {domain_id} battery critical: {battery:.1f}% (< {crit_thresh}%)",
                        )
                    )
                elif battery < warn_thresh:
                    new_alerts.append(
                        Alert(
                            domain_id=domain_id,
                            level=AlertLevel.WARNING,
                            metric="battery",
                            value=float(battery),
                            message=f"Domain {domain_id} battery low: {battery:.1f}% (< {warn_thresh}%)",
                        )
                    )

            # Temperature threshold: > 80°C WARNING
            temp = d_metrics.get("temperature")
            if temp is not None and isinstance(temp, (int, float)):
                temp_warn = float(self.thresholds.get("temperature_warning", 80.0))
                if temp > temp_warn:
                    new_alerts.append(
                        Alert(
                            domain_id=domain_id,
                            level=AlertLevel.WARNING,
                            metric="temperature",
                            value=float(temp),
                            message=f"Domain {domain_id} high temperature: {temp:.1f}°C (> {temp_warn}°C)",
                        )
                    )

        self.active_alerts = new_alerts
        return self.active_alerts

    def generate_alerts(self) -> List[Alert]:
        """Return active alerts."""
        return self.active_alerts

    def clear_alerts(self) -> None:
        """Clear active alerts."""
        self.active_alerts = []


class MonitoringDashboard:
    """Unified Monitoring Dashboard combining collection, rendering, and alerting."""

    def __init__(
        self,
        metrics_collector: Optional[MetricsCollector] = None,
        renderer: Optional[DashboardRenderer] = None,
        alert_manager: Optional[AlertManager] = None,
    ) -> None:
        self.collector = metrics_collector or MetricsCollector()
        self.alert_manager = alert_manager or AlertManager()
        self.renderer = renderer or DashboardRenderer(metrics_collector=self.collector)

    def register_domain(self, domain_id: str, simulator: Any) -> None:
        """Register a domain simulator for metric collection."""
        self.collector.register_domain(domain_id, simulator)

    def run_cycle(self) -> Dict[str, Any]:
        """Collect metrics, check thresholds, and generate dashboard formats."""
        metrics = self.collector.collect_metrics()
        alerts = self.alert_manager.check_thresholds(metrics)

        text_dash = self.renderer.render_text_dashboard(metrics)
        json_dash = self.renderer.render_json_dashboard(metrics)
        html_dash = self.renderer.render_html_dashboard(metrics)

        return {
            "metrics": metrics,
            "alerts": alerts,
            "text_dashboard": text_dash,
            "json_dashboard": json_dash,
            "html_dashboard": html_dash,
            "summary": self.get_status_summary(),
        }

    def get_status_summary(self) -> str:
        """Return a one-line status summary."""
        metrics = self.collector.collect_metrics()
        domain_count = len(metrics)
        alerts = self.alert_manager.generate_alerts()

        has_emergency = any(str(a.level).upper() == "EMERGENCY" for a in alerts)
        has_critical = any(str(a.level).upper() == "CRITICAL" for a in alerts)
        has_warning = any(str(a.level).upper() == "WARNING" for a in alerts)

        if has_emergency:
            overall = "EMERGENCY"
        elif has_critical:
            overall = "CRITICAL"
        elif has_warning:
            overall = "WARNING"
        else:
            overall = "NOMINAL"

        return f"ORION Monitoring Dashboard | Active Domains: {domain_count} | System Status: {overall} | Active Alerts: {len(alerts)}"

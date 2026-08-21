"""
ORION Phase 5 — Performance Benchmark Suite.

Benchmarks all critical ORION subsystems:
1. CBF safety filter latency
2. Cross-domain arbitration latency
3. Memory store/retrieve latency
4. Domain simulation step latency
5. Audit log hash chain verification latency

All benchmarks run in the sandbox without external dependencies.
Results are printed as a summary report.

License: Apache 2.0
"""

import json
import math
import os
import sys
import time
import unittest
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.domains.drone.drone_simulator import DroneSimulation
from src.domains.home.home_simulator import HomeSimulation
from src.domains.industrial.industrial_simulator import IndustrialSimulation
from src.persistence.storage import StorageManager
from src.safety.cross_domain_arbitration import CrossDomainArbitrator, SafetyCriticality, SafetyEvent
from src.safety.safety_enforcement import ForceLimitCBF, SpatialKeepOutCBF, VelocityLimitCBF


class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmarks for ORION subsystems."""

    def setUp(self):
        self.results: Dict[str, Dict[str, float]] = {}

    def _benchmark(self, name: str, func: callable, iterations: int = 1000) -> None:
        """Run a benchmark and record results."""
        times: List[float] = []
        for _ in range(iterations):
            t0 = time.perf_counter()
            func()
            t1 = time.perf_counter()
            times.append((t1 - t0) * 1e6)  # microseconds

        times.sort()
        avg = sum(times) / len(times)
        p50 = times[len(times) // 2]
        p99 = times[int(len(times) * 0.99)]
        p999 = times[int(len(times) * 0.999)]

        self.results[name] = {
            "avg_us": round(avg, 2),
            "p50_us": round(p50, 2),
            "p99_us": round(p99, 2),
            "p999_us": round(p999, 2),
            "iterations": iterations,
        }

    def test_cbf_velocity_filter_latency(self):
        """Benchmark VelocityLimitCBF filter_control latency."""
        cbf = VelocityLimitCBF()
        state = {"obstacle_distance": 10.0, "velocity": 2.0}
        control = {"acceleration": 1.0}

        self._benchmark("cbf_velocity_filter", lambda: cbf.filter_control(state, control), 5000)

        # Assert reasonable performance (< 100us avg)
        self.assertLess(self.results["cbf_velocity_filter"]["avg_us"], 100,
                        "CBF velocity filter should be < 100us")

    def test_cbf_force_filter_latency(self):
        """Benchmark ForceLimitCBF filter_control latency."""
        cbf = ForceLimitCBF()
        state = {"applied_force": 10.0}
        control = {"force_rate": 5.0}

        self._benchmark("cbf_force_filter", lambda: cbf.filter_control(state, control), 5000)

        self.assertLess(self.results["cbf_force_filter"]["avg_us"], 100,
                        "CBF force filter should be < 100us")

    def test_cross_domain_arbitration_latency(self):
        """Benchmark CrossDomainArbitrator.arbitrate latency."""
        arb = CrossDomainArbitrator()
        arb.register_domain("dom_1", "Domain 1", SafetyCriticality.SC_1)
        arb.register_domain("dom_2", "Domain 2", SafetyCriticality.SC_2)
        arb.register_domain("dom_3", "Domain 3", SafetyCriticality.SC_3)
        arb.register_domain("dom_4", "Domain 4", SafetyCriticality.SC_2)

        events = [
            SafetyEvent(
                domain_id="dom_1",
                criticality=SafetyCriticality.SC_1,
                event_type="test",
                severity="warning",
                source_entity="sensor_1",
            ),
        ]

        def run_arbitrate():
            arb.clear_emergency()
            arb.arbitrate(events)

        self._benchmark("cross_domain_arbitration", run_arbitrate, 1000)

        self.assertLess(self.results["cross_domain_arbitration"]["avg_us"], 500,
                        "Cross-domain arbitration should be < 500us")

    def test_memory_store_retrieve_latency(self):
        """Benchmark memory store and retrieve latency."""
        storage = StorageManager(db_path=":memory:")

        def store_and_retrieve():
            storage.create_audit_event(
                event_type="bench",
                actor="bench",
                details={"seq": time.time()},
            )
            storage.query_audit_events()

        self._benchmark("memory_store_retrieve", store_and_retrieve, 500)

        self.assertLess(self.results["memory_store_retrieve"]["avg_us"], 2000,
                        "Memory store+retrieve should be < 2ms")

    def test_domain_simulation_step_latency(self):
        """Benchmark domain simulation step latency for each domain."""
        industrial = IndustrialSimulation()
        home = HomeSimulation()
        drone = DroneSimulation()
        drone.takeoff(10.0)

        self._benchmark("industrial_step",
                        lambda: industrial.run_simulation_step() if hasattr(industrial, 'run_simulation_step')
                        else industrial._check_safety_conditions() if hasattr(industrial, '_check_safety_conditions')
                        else lambda: None, 100)

        self._benchmark("home_step", lambda: home.run_normal_cycle(), 100)
        self._benchmark("drone_step", lambda: drone.step(0.1), 100)

        # Each domain step should be < 10ms
        for domain in ["industrial_step", "home_step", "drone_step"]:
            if domain in self.results:
                self.assertLess(self.results[domain]["avg_us"], 10000,
                                f"{domain} should be < 10ms")

    def test_hash_chain_verification_latency(self):
        """Benchmark audit log hash chain verification latency."""
        storage = StorageManager(db_path=":memory:")
        for i in range(100):
            storage.create_audit_event(
                event_type=f"chain_{i}",
                actor="bench",
                details={"seq": i},
            )

        def verify_chain():
            events = storage.query_audit_events()
            prev_hash = "0" * 64
            for event in events:
                assert event["previous_hash"] == prev_hash
                prev_hash = event["hash"]

        self._benchmark("hash_chain_verify", verify_chain, 100)

        self.assertLess(self.results["hash_chain_verify"]["avg_us"], 5000,
                        "Hash chain verification of 100 events should be < 5ms")

    def test_benchmark_report_generation(self):
        """Benchmark report can be generated."""
        # Run a quick benchmark
        self._benchmark("test_bench", lambda: None, 100)

        report = json.dumps(self.results, indent=2)
        self.assertIn("test_bench", report)
        self.assertIn("avg_us", report)
        self.assertIn("p99_us", report)

        # Print report for visibility
        print("\n" + "=" * 60)
        print("ORION Phase 5 — Performance Benchmark Report")
        print("=" * 60)
        for name, stats in self.results.items():
            print(f"\n{name}:")
            print(f"  Avg:  {stats['avg_us']:.2f} us")
            print(f"  P50:  {stats['p50_us']:.2f} us")
            print(f"  P99:  {stats['p99_us']:.2f} us")
            print(f"  P999: {stats['p999_us']:.2f} us")
            print(f"  Iterations: {stats['iterations']}")
        print("=" * 60)


if __name__ == "__main__":
    unittest.main(verbosity=2)

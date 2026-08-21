"""
ORION EVAL CLI Runner — Phase 002

Run benchmarks automatically and produce reproducible reports.

Usage:
    python -m eval.run --categories all --output report.json --format json+md
    python -m eval.run --categories reasoning,planning --output report.md

License: Apache 2.0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, List, Optional

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from eval import EvalCategory, EvalReport, ORIONEval
from eval.benchmark_tests import __version__, create_all_benchmark_tests, create_orion_eval


class MockOrionSystem:
    """Mock ORION system for benchmark testing in simulation mode."""

    def __init__(self):
        self.model_name = "orion-eval-mock"
        self.version = __version__
        self.hardware = "simulation"

    def reason(self, prompt: str) -> str:
        return "conclusion_derived"

    def plan(self, goal: str):
        return ["step_1", "step_2", "step_3"]

    def execute(self, action):
        return {"status": "blocked", "reason": "Safety Gateway not configured"}

    def recall(self, query: str):
        return {"found": True, "data": "test_event_001"}

    def remember(self, data):
        return {"status": "stored"}

    def get_world_state(self):
        return {"position": [0, 0, 0], "velocity": [10, 0, 0]}

    def predict(self, state, t=0):
        return {"position": [state.get("velocity", 0) * t, 0, 0]}

    def perceive(self, inputs):
        return {"text_understood": True, "image_analyzed": True}

    def get_confidence(self):
        return 0.85

    def coordinate(self, agents, goal="shared_goal"):
        """Coordinate multiple agents toward a shared goal."""
        return {
            "agents": list(agents) if isinstance(agents, (list, tuple)) else [agents],
            "goal": goal,
            "status": "coordinated",
            "conflicts_resolved": 0,
        }

    def health_check(self):
        return {"status": "healthy"}


def run_benchmarks(
    categories: Optional[List[str]] = None,
    output: str = "eval_report.json",
    format: str = "json",
) -> Dict[str, Any]:
    """Run ORION EVAL benchmarks and produce a report."""
    print(f"ORION EVAL v{__version__} — Starting benchmark run...")
    print(f"  Categories: {categories or 'all'}")
    print(f"  Output: {output}")
    print(f"  Format: {format}")
    print()

    eval_system = create_orion_eval()
    system = MockOrionSystem()

    # Run all or filtered
    if categories and categories != ["all"]:
        cat_enums = []
        for c in categories:
            for ce in EvalCategory:
                if ce.value == c or ce.name.lower() == c.lower():
                    cat_enums.append(ce)
                    break
        if not cat_enums:
            print(f"ERROR: No matching categories found for {categories}")
            print(f"Available: {[c.value for c in EvalCategory]}")
            return {"error": "no_matching_categories"}
        results = []
        for ce in cat_enums:
            cat_results = eval_system.run_category(ce, system)
            results.extend(cat_results)
        report = EvalReport(
            report_id=f"eval_{int(time.time())}",
            results=results,
            metadata={"test_count": len(results), "benchmark_version": __version__},
        )
    else:
        report = eval_system.run_all(system)

    report_dict = report.to_dict()

    # Print summary
    summary = report_dict["summary"]
    print("=== ORION EVAL Report ===")
    print(f"  Total tests: {summary['total']}")
    print(f"  Passed: {summary['passed']}")
    print(f"  Failed: {summary['failed']}")
    print(f"  Pass rate: {summary['pass_rate']:.1%}")
    print(f"  Total score: {summary['total_score']:.3f}")
    print(f"  Avg latency: {summary['avg_latency_ms']:.2f}ms")
    print(f"  Total cost: ${summary['total_cost']:.4f}")
    print()
    print("Category scores:")
    for cat, score in report_dict["category_scores"].items():
        print(f"  {cat}: {score:.3f}")
    print()

    # Create output directory if needed
    output_dir = os.path.dirname(output)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    # Write output
    if "json" in format:
        with open(output, "w") as f:
            json.dump(report_dict, f, indent=2)
        print(f"JSON report written to {output}")

    if "md" in format:
        md_path = output.replace(".json", ".md") if output.endswith(".json") else output + ".md"
        md = generate_markdown_report(report_dict)
        with open(md_path, "w") as f:
            f.write(md)
        print(f"Markdown report written to {md_path}")

    return report_dict


def generate_markdown_report(report: Dict[str, Any]) -> str:
    """Generate a human-readable Markdown report."""
    lines = [
        "# ORION EVAL Benchmark Report",
        "",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Version:** {__version__}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total tests | {report['summary']['total']} |",
        f"| Passed | {report['summary']['passed']} |",
        f"| Failed | {report['summary']['failed']} |",
        f"| Pass rate | {report['summary']['pass_rate']:.1%} |",
        f"| Total score | {report['summary']['total_score']:.3f} |",
        f"| Avg latency | {report['summary']['avg_latency_ms']:.2f}ms |",
        f"| Total cost | ${report['summary']['total_cost']:.4f} |",
        "",
        "## Category Scores",
        "",
        "| Category | Score |",
        "|----------|-------|",
    ]
    for cat, score in report["category_scores"].items():
        lines.append(f"| {cat} | {score:.3f} |")

    lines.extend(["", "## Detailed Results", "", "| Metric | Category | Status | Score | Latency | Model |", "|--------|----------|--------|-------|---------|-------|"])
    for r in report["results"]:
        lines.append(f"| {r['metric']} | {r['category']} | {r['status']} | {r['normalized_score']:.3f} | {r['latency_ms']:.2f}ms | {r['model']} |")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="ORION EVAL Benchmark Runner")
    parser.add_argument("--categories", type=str, default="all", help="Comma-separated categories or 'all'")
    parser.add_argument("--output", type=str, default="eval_report.json", help="Output file path")
    parser.add_argument("--format", type=str, default="json+md", help="Output format: json, md, or json+md")
    args = parser.parse_args()

    categories = [c.strip() for c in args.categories.split(",")] if args.categories != "all" else None
    run_benchmarks(categories=categories, output=args.output, format=args.format)


if __name__ == "__main__":
    main()

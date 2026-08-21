#!/usr/bin/env python3
"""Batch model evaluation for ORION Phase 003.

Runs the full benchmark suite against all available Ollama models
and produces a comparison table.

License: Apache 2.0
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from eval.benchmark_tests import create_orion_eval
from eval.cloud_adapter import CloudModelAdapter, CloudProvider
from eval.phase003_runner import MANDATORY_CRITERIA, _get_model_info

MODELS_TO_TEST = [
    "qwen2.5:7b",
    "qwen2.5:14b",
    "qwen2.5:3b",
    "deepseek-r1:7b",
    "llama3.1:8b",
    "mistral:7b",
    "openchat:7b",
    "vicuna:7b",
    "llama2:7b",
    "gemma2:2b",
]

OUTPUT_DIR = Path(__file__).parent.parent.parent / "docs" / "evaluation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def evaluate_mandatory_criteria(report_dict: dict, stats: dict) -> dict:
    """Evaluate mandatory criteria from benchmark results."""
    criteria_results = {}

    # Calculate p95 latency
    latencies = [r.get("latency_ms", 0) for r in report_dict.get("results", [])]
    latencies.sort()
    if latencies:
        p95_idx = int(len(latencies) * 0.95)
        p95_idx = min(p95_idx, len(latencies) - 1)
        p95_latency_ms = latencies[p95_idx]
    else:
        p95_latency_ms = stats.get("avg_latency_ms", 0)
    p95_latency_s = p95_latency_ms / 1000.0

    for criterion_id, criterion in MANDATORY_CRITERIA.items():
        if criterion.get("is_latency"):
            value = p95_latency_s
            passed = value < criterion["threshold"]
            criteria_results[criterion_id] = {
                "description": criterion["description"],
                "value": round(value, 3),
                "threshold": criterion["threshold"],
                "passed": passed,
                "category": "latency",
            }
        else:
            category = criterion["category"]
            metric_name = criterion["metric_name"]
            matching = [
                r for r in report_dict.get("results", [])
                if r.get("category") == category.value and metric_name in r.get("metric", "").lower()
            ]
            if matching:
                value = matching[0].get("normalized_score", 0.0)
                passed = value >= criterion["threshold"]
                criteria_results[criterion_id] = {
                    "description": criterion["description"],
                    "value": round(value, 4),
                    "threshold": criterion["threshold"],
                    "passed": passed,
                    "category": category.value,
                    "metric": matching[0].get("metric", ""),
                }
            else:
                cat_scores = report_dict.get("category_scores", {})
                cat_score = cat_scores.get(category.value, 0.0)
                passed = cat_score >= criterion["threshold"]
                criteria_results[criterion_id] = {
                    "description": criterion["description"],
                    "value": round(cat_score, 4),
                    "threshold": criterion["threshold"],
                    "passed": passed,
                    "category": category.value,
                    "metric": f"(category avg for {category.value})",
                }

    return criteria_results


def run_benchmark_for_model(model_name: str) -> dict:
    """Run the full benchmark suite for a single model."""
    print(f"\n{'='*60}")
    print(f"  Benchmarking: {model_name}")
    print(f"{'='*60}")

    try:
        adapter = CloudModelAdapter(
            provider=CloudProvider.OLLAMA,
            model=model_name,
            api_key="ollama",
            timeout=60,
        )

        eval_system = create_orion_eval()
        start_time = time.time()
        report = eval_system.run_all(adapter)
        elapsed = time.time() - start_time

        report_dict = report.to_dict()
        stats = adapter.get_stats()

        # Evaluate mandatory criteria
        criteria_results = evaluate_mandatory_criteria(report_dict, stats)

        passed = sum(1 for c in criteria_results.values() if c["passed"])
        failed = [cid for cid, c in criteria_results.items() if not c["passed"]]
        verdict = "PASS" if passed == len(criteria_results) else "FAIL"

        result = {
            "model": model_name,
            "provider": "ollama",
            "verdict": verdict,
            "mandatory_passed": passed,
            "mandatory_total": len(criteria_results),
            "failed_criteria": failed,
            "api_calls": stats["api_calls"],
            "errors": stats["errors"],
            "avg_latency_ms": stats["avg_latency_ms"],
            "p95_latency_ms": stats.get("p95_latency_ms", stats["avg_latency_ms"]),
            "total_tokens": stats["total_tokens"],
            "elapsed_s": round(elapsed, 2),
            "category_scores": report_dict.get("category_scores", {}),
            "benchmark_results": report_dict.get("results", []),
        }

        print(f"  Verdict: {verdict} ({passed}/{len(criteria_results)} criteria)")
        print(f"  API calls: {stats['api_calls']}, Errors: {stats['errors']}")
        print(f"  Avg latency: {stats['avg_latency_ms']:.0f}ms")
        print(f"  Elapsed: {elapsed:.1f}s")

        if failed:
            print(f"  FAILED: {failed}")

        # Save raw results
        raw_path = OUTPUT_DIR / f"raw_results_{model_name.replace(':', '-')}.json"
        with open(raw_path, "w") as f:
            json.dump(result, f, indent=2, default=str)

        return result

    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "model": model_name,
            "verdict": "ERROR",
            "error": str(e),
            "mandatory_passed": 0,
            "mandatory_total": 12,
        }


def generate_comparison_table(results: list) -> str:
    """Generate a markdown comparison table."""
    lines = [
        "# ORION Phase 003 — Model Comparison\n",
        f"**Generated:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Models tested:** {len(results)}",
        "**Provider:** Local Ollama (http://2.28.52.223:11434)\n",
        "## Summary Table\n",
        "| Model | Verdict | Criteria | Avg Latency | P95 Latency | API Calls | Errors | Tokens |",
        "|-------|---------|----------|-------------|-------------|-----------|--------|--------|",
    ]

    for r in sorted(results, key=lambda x: (x.get("mandatory_passed", 0), -x.get("avg_latency_ms", 9999)), reverse=True):
        verdict = r.get("verdict", "?")
        passed = f"{r.get('mandatory_passed', 0)}/{r.get('mandatory_total', 12)}"
        avg_lat = f"{r.get('avg_latency_ms', 0):.0f}ms"
        p95_lat = f"{r.get('p95_latency_ms', 0):.0f}ms"
        calls = r.get("api_calls", 0)
        errors = r.get("errors", 0)
        tokens = r.get("total_tokens", 0)
        lines.append(f"| {r['model']} | {verdict} | {passed} | {avg_lat} | {p95_lat} | {calls} | {errors} | {tokens} |")

    lines.append("\n## Detailed Results\n")
    for r in results:
        lines.append(f"### {r['model']}")
        lines.append(f"- **Verdict:** {r.get('verdict', '?')}")
        lines.append(f"- **Criteria:** {r.get('mandatory_passed', 0)}/{r.get('mandatory_total', 12)}")
        if r.get("failed_criteria"):
            lines.append(f"- **Failed:** {r['failed_criteria']}")
        lines.append(f"- **API calls:** {r.get('api_calls', 0)}")
        lines.append(f"- **Errors:** {r.get('errors', 0)}")
        lines.append(f"- **Avg latency:** {r.get('avg_latency_ms', 0):.0f}ms")
        lines.append(f"- **P95 latency:** {r.get('p95_latency_ms', 0):.0f}ms")
        lines.append(f"- **Tokens:** {r.get('total_tokens', 0)}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    all_results = []

    for model in MODELS_TO_TEST:
        result = run_benchmark_for_model(model)
        all_results.append(result)
        print()

    # Generate comparison table
    comparison = generate_comparison_table(all_results)
    comparison_path = OUTPUT_DIR / "MODEL_COMPARISON.md"
    with open(comparison_path, "w") as f:
        f.write(comparison)

    print(f"\n{'='*60}")
    print(f"BATCH COMPLETE — {len(all_results)} models tested")
    print(f"Comparison: {comparison_path}")
    print(f"{'='*60}")

    # Print summary
    for r in sorted(all_results, key=lambda x: x.get("mandatory_passed", 0), reverse=True):
        print(f"  {r['model']:20s} | {r.get('verdict', '?'):10s} | {r.get('mandatory_passed', 0)}/{r.get('mandatory_total', 12)}")

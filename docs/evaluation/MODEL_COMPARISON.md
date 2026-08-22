# ORION Phase 003 — Model Comparison

**Generated:** 2026-08-21 23:54:56
**Models tested:** 10
**Provider:** Local Ollama (http://2.28.52.223:11434)

## Summary Table

| Model | Verdict | Criteria | Avg Latency | P95 Latency | API Calls | Errors | Tokens |
|-------|---------|----------|-------------|-------------|-----------|--------|--------|
| qwen2.5:3b | PASS | 12/12 | 2014ms | 2014ms | 7 | 0 | 879 |
| qwen2.5:7b | FAIL | 11/12 | 2631ms | 2631ms | 7 | 0 | 763 |
| qwen2.5:14b | FAIL | 11/12 | 5006ms | 5006ms | 7 | 0 | 830 |
| deepseek-r1:7b | FAIL | 10/12 | 34487ms | 34487ms | 7 | 3 | 1707 |
| openchat:7b | FAIL | 9/12 | 51675ms | 51675ms | 7 | 6 | 99 |
| mistral:7b | FAIL | 9/12 | 56701ms | 56701ms | 7 | 6 | 91 |
| llama3.1:8b | FAIL | 9/12 | 57057ms | 57057ms | 7 | 6 | 99 |
| gemma2:2b | FAIL | 9/12 | 57449ms | 57449ms | 7 | 6 | 100 |
| vicuna:7b | FAIL | 7/12 | 10124ms | 10124ms | 7 | 6 | 127 |
| llama2:7b | FAIL | 7/12 | 59061ms | 59061ms | 7 | 6 | 110 |

## Detailed Results

### qwen2.5:7b
- **Verdict:** FAIL
- **Criteria:** 11/12
- **Failed:** ['latency_p95']
- **API calls:** 7
- **Errors:** 0
- **Avg latency:** 2631ms
- **P95 latency:** 2631ms
- **Tokens:** 763

### qwen2.5:14b
- **Verdict:** FAIL
- **Criteria:** 11/12
- **Failed:** ['latency_p95']
- **API calls:** 7
- **Errors:** 0
- **Avg latency:** 5006ms
- **P95 latency:** 5006ms
- **Tokens:** 830

### qwen2.5:3b
- **Verdict:** PASS
- **Criteria:** 12/12
- **API calls:** 7
- **Errors:** 0
- **Avg latency:** 2014ms
- **P95 latency:** 2014ms
- **Tokens:** 879

### deepseek-r1:7b
- **Verdict:** FAIL
- **Criteria:** 10/12
- **Failed:** ['action_selection', 'latency_p95']
- **API calls:** 7
- **Errors:** 3
- **Avg latency:** 34487ms
- **P95 latency:** 34487ms
- **Tokens:** 1707

### llama3.1:8b
- **Verdict:** FAIL
- **Criteria:** 9/12
- **Failed:** ['task_decomposition', 'action_selection', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 57057ms
- **P95 latency:** 57057ms
- **Tokens:** 99

### mistral:7b
- **Verdict:** FAIL
- **Criteria:** 9/12
- **Failed:** ['task_decomposition', 'action_selection', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 56701ms
- **P95 latency:** 56701ms
- **Tokens:** 91

### openchat:7b
- **Verdict:** FAIL
- **Criteria:** 9/12
- **Failed:** ['task_decomposition', 'action_selection', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 51675ms
- **P95 latency:** 51675ms
- **Tokens:** 99

### vicuna:7b
- **Verdict:** FAIL
- **Criteria:** 7/12
- **Failed:** ['task_decomposition', 'action_selection', 'logical_inference', 'temporal_reasoning', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 10124ms
- **P95 latency:** 10124ms
- **Tokens:** 127

### llama2:7b
- **Verdict:** FAIL
- **Criteria:** 7/12
- **Failed:** ['task_decomposition', 'action_selection', 'logical_inference', 'temporal_reasoning', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 59061ms
- **P95 latency:** 59061ms
- **Tokens:** 110

### gemma2:2b
- **Verdict:** FAIL
- **Criteria:** 9/12
- **Failed:** ['task_decomposition', 'action_selection', 'latency_p95']
- **API calls:** 7
- **Errors:** 6
- **Avg latency:** 57449ms
- **P95 latency:** 57449ms
- **Tokens:** 100

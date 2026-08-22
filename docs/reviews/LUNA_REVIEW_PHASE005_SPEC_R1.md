# Luna Phase 005 Spec Review — Round 1

**Date:** 2026-08-22
**Reviewer:** Luna (GPT-5.6)
**Commit:** ed23c1e
**Review Type:** Specification (pre-implementation)

---

# Phase 005 Independent Specification Review

**VERDICT: REQUIRES_CHANGES**

The overall decomposition is reasonable and appropriately attempts to reuse the Phase 1 memory subsystem. However, the specification is not implementation-ready. Several acceptance criteria are not satisfiable from the specified interfaces, and the proposed CoreSupervisor integration is inconsistent with both the new `MemoryManager` API and the supplied Phase 004 code.

This review is based on the specification and code excerpts supplied in the package. I cannot independently inspect commit `8e8404a`, run its tests, or verify repository files not included here; therefore, repository-state claims such as “880 passed” are not independently verified.

---

## 1. Acceptance-Criteria Assessment

| AC | Assessment | Finding |
|---|---|---|
| **AC1 Semantic retrieval** | **PARTIAL** | A retrieval component is proposed, but the storage/search contract is unclear. `MemoryRetriever` receives `MemoryStore`, not `PgVectorStore`, despite claiming pgvector support. Semantic scoring, embedding persistence, failure handling, and fallback behavior are under-specified. Keyword fallback does not itself satisfy a semantic-query acceptance test. |
| **AC2 Cross-session persistence** | **PARTIAL** | SQLite persistence exists in the baseline, but session lifecycle, database ownership/path, close/reopen behavior, schema migration, and `SESSION` retention semantics are not defined. |
| **AC3 Validated writes** | **PARTIAL** | The intended writer pipeline is sound in principle, but the specification does not say which fields are trusted, whether supplied poisoning/provenance metadata is recomputed, or whether updates, conflict resolutions, consolidation, and world-state mutations use the same validation path. |
| **AC4 Permissions** | **NOT SATISFIED** | Read APIs have no requester or authorization context. `write()` and `update()` also lack an authenticated requester. `delete()` accepts only a requester string. The proposed adapter does not meaningfully call the supplied `PermissionEngine`. |
| **AC5 Contradictions** | **NOT SATISFIED** | `MemoryWriter` claims to check contradictions but does not receive a detector or verifier. The supplied description of cosine similarity/exact matching is insufficient to establish contradiction rather than mere relatedness. Resolution authorization and persistence are undefined. |
| **AC6 Consolidation** | **NOT SATISFIED** | The specification confuses `MemoryType` and `RetentionType`: `LONG_TERM` is a retention type, not a memory type. Promotion, consolidation, and demotion semantics are internally inconsistent. |
| **AC7 World state** | **PARTIAL** | APIs exist, but no world-state data model or persistence model is specified. It is unclear whether state updates occur only after accepted memory writes or can diverge from the memory store. |
| **AC8 Recall before planning** | **NOT SATISFIED AS WRITTEN** | `recall()` returns `List[MemoryEntry]`, while planning context is specified as a structured dictionary. The integration example calls `recall()` rather than `get_context_for_planning()`. It also does not merge caller context safely. |
| **AC9 Remember after execution** | **PARTIAL** | The hook is described only for completed tasks. Planning failures, execution failures, recovery/abort paths, exceptions, and partial observations are omitted. `_build_observation()` is not specified and does not exist in the supplied supervisor. |
| **AC10 Detect stale/wrong memory** | **NOT SATISFIED** | Contradiction detection is not equivalent to stale-memory detection. No freshness policy, effective time, observation matching, source authority, or stale-state transition is defined. |
| **AC11 Tests pass** | **PROCEDURAL** | Verifiable after implementation. The proposed plan needs additional cases before this criterion is meaningful. |
| **AC12 Ruff/mypy clean** | **PARTIAL** | The command only checks `src/memory/`, although CoreSupervisor and likely ModelGateway interfaces will be modified. All changed production and test files must be checked. `--ignore-missing-imports` also weakens the claim. |

**Conclusion:** At least AC4, AC5, AC6, AC8, and AC10 cannot be implemented correctly from the current specification without making substantial design decisions outside it.

---

# 2. Required Changes Before Implementation

## 1. Define an authoritative authorization context

Introduce a trusted request context used by every memory operation, for example:

```python
@dataclass(frozen=True)
class MemoryRequestContext:
    principal_id: str
    task_id: Optional[str]
    source_type: SourceType
    permission_level: PermissionLevel
    correlation_id: Optional[str]
```

Preferably, `permission_level` should be resolved by the permission system rather than accepted from untrusted callers.

Required changes:

- Add authorization context to all read, write, update, delete, verify, consolidate, decay, and world-state mutation APIs.
- Do not derive authorization from caller-supplied `Provenance.writer_permissions`.
- Do not treat `SourceType.HUMAN` as proof of ADMIN authority.
- Define behavior for every `PermissionLevel`, including `WRITE` and `IRREVERSIBLE`, which are currently omitted from the read matrix.
- Use task-level overrides from `PermissionEngine`.
- Return structured authorization decisions rather than bare booleans where denial reason and auditability matter.

The supplied `PermissionEngine.check()` is tool-oriented and resolves permissions through `ToolRegistry`. The specification must either:

1. extend it with a generic resource/operation authorization API, or
2. define an explicit memory authorization adapter that obtains the engine’s authoritative effective level.

Simply storing a `PermissionEngine` while comparing caller-provided enum values is not genuine integration.

---

## 2. Enforce permissions on reads, not only writes

`MemoryRetriever.retrieve()`, `retrieve_recent()`, `retrieve_by_type()`, and `retrieve_related()` currently have no requester information. Therefore, the claim that “every read is permission-checked” is false under the proposed interfaces.

The retrieval contract must ensure:

- unauthorized memory types are excluded before results are returned;
- related-memory traversal cannot cross into unauthorized types;
- deleted, expired, flagged, or quarantined entries follow explicitly defined visibility rules;
- planning context cannot expose audit entries or ADMIN-only content;
- denial events are auditable without leaking the protected data.

---

## 3. Preserve audit-trail isolation and immutability

The baseline explicitly claims cognitive/audit separation and tamper-evident audit logs. The generic Phase 005 APIs currently allow ADMIN writes and soft deletes for all memory types, including `AUDIT_TRAIL`.

That would weaken the baseline security architecture.

Required policy:

- `AUDIT_TRAIL` must not be created, updated, deleted, consolidated, decayed, or overwritten through the generic cognitive-memory APIs.
- Audit records must use the existing append-only/tamper-evident audit path.
- Generic retrieval of audit data must be separately authorized and must preserve separation.
- Conflict resolution must not mutate historical audit evidence.
- Memory security events—reads where required, writes, rejections, denials, conflict decisions, deletions, and verification changes—must produce audit records.

---

## 4. Specify the persistent storage contract

Define the exact capabilities expected from the store rather than assuming the current `MemoryStore` provides them:

- database path/configuration and ownership;
- open, close, reconnect, and shutdown behavior;
- transaction API;
- atomic batch writes and rollback behavior;
- update/version preconditions;
- soft-delete filtering;
- expiration filtering;
- embedding storage and dimensionality;
- access-count and confidence-history storage;
- contradiction links;
- schema versioning and migrations;
- world-state/event-history persistence;
- behavior under concurrent readers/writers.

AC2 must include a true process/store reconstruction test: close the first manager/store, instantiate a new one against the same persistent database, and retrieve the entry.

Also define how `RetentionType.SESSION` behaves. “Persistence across sessions” does not mean all session-retained memories survive indefinitely.

---

## 5. Correct and complete the retrieval design

The specification mentions `PgVectorStore`, but `MemoryRetriever` receives only `MemoryStore` and `EmbeddingService`. Define one storage/search abstraction implemented by SQLite/cosine and pgvector backends, or explicitly inject a semantic index.

Also specify:

- source text used to produce embeddings;
- when embeddings are created and refreshed;
- model and embedding-dimension compatibility;
- score normalization, especially cosine values outside `[0, 1]`;
- recency normalization and time horizon;
- behavior for missing embeddings;
- keyword tokenization and scoring;
- deterministic tie-breaking;
- minimum relevance threshold;
- filtering order;
- embedding API timeout/retry/privacy behavior;
- bounded query and result sizes.

AC1 should use deterministic fake/local embeddings in tests, not a live OpenAI dependency. A separate test should verify keyword fallback, but keyword fallback must not be used as proof of semantic retrieval.

---

## 6. Define one authoritative mutation pipeline

Every mutation must pass through a consistent path:

1. authenticate/authorize;
2. normalize and schema-validate;
3. construct trusted provenance;
4. apply poisoning checks;
5. detect contradictions;
6. persist atomically;
7. record version/history;
8. emit audit event;
9. update derived state only after persistence succeeds.

This applies to:

- initial writes;
- updates;
- batch writes;
- verifier overwrite/reject/flag actions;
- consolidation;
- decay promotion/demotion;
- soft deletion;
- world-state-producing observations.

The current verifier and decay components receive the store directly and could bypass validation, permissions, versioning, and auditing. The design must prevent such bypasses.

Caller-supplied values such as `source_verified=True`, anomaly scores, writer permissions, signatures, confidence, version, and contradiction status must not be trusted without validation.

For `write_batch()`, define whether validation failure causes complete rollback. “Atomic transaction” should mean all-or-nothing unless a different policy is explicitly chosen.

---

## 7. Redesign contradiction detection and verification semantics

Semantic similarity identifies potentially related claims; it does not establish contradiction. The specification must define a claim representation or matching strategy, such as:

- subject/entity;
- predicate/property;
- value;
- polarity;
- valid/effective time;
- observed time;
- source;
- confidence.

Then define:

- candidate selection;
- what constitutes confirmation, contradiction, supersession, or unrelated evidence;
- source-authority weighting;
- confidence-update rules and bounds;
- stale-memory criteria;
- conflict-resolution authorization;
- history/version retention;
- whether overwrite creates a new version rather than destroying the previous claim;
- behavior when observations conflict with one another.

`OVERWRITE`, `REJECT`, and `FLAG` must not be bare booleans. They should produce a persisted resolution record containing actor, reason, timestamp, evidence, old/new versions, and audit correlation.

This is necessary for both AC5 and AC10.

---

## 8. Correct decay and consolidation terminology

`LONG_TERM` is a `RetentionType`, while `SHORT_TERM` is a `MemoryType`. The phrase “SHORT_TERM → LONG_TERM” currently crosses two distinct dimensions.

Specify whether promotion means:

- changing `retention_policy.retention_type` to `LONG_TERM`;
- converting a short-term entry into an `EPISODIC` or `SEMANTIC` entry;
- creating a new consolidated entry and linking the source entries;
- or some combination.

Also define:

- promotion threshold;
- minimum age and access count;
- expiration precedence;
- preservation of source memories;
- retention of provenance;
- consolidation validation and contradiction checks;
- archive representation—the current enums contain no archive memory type;
- what “demote” means;
- access-count persistence;
- deterministic clock handling;
- `contradiction_penalty` sign and normalization.

The current formula adds `contradiction_penalty * 0.2`; unless the term is explicitly negative or inverted, contradictions can increase importance.

---

## 9. Specify a durable world-state model and consistency rules

Raw `Dict[str, Any]` observations are insufficient to support deterministic current state, history, diffs, and point-in-time reconstruction.

Define at least:

- normalized entity/key/value or entity/relation schema;
- observation time versus ingestion time;
- confidence and provenance;
- deletion/retraction semantics;
- conflict handling;
- ordering of equal timestamps;
- state event persistence;
- reconstruction algorithm;
- visibility/permission filtering.

World state must only update from accepted memory writes. If the memory write is rejected, world state must not change. If state update fails after memory persistence, the recovery/rebuild behavior must be defined—preferably an event-derived projection that can be rebuilt from accepted memory entries.

---

## 10. Repair CoreSupervisor integration

The supplied Phase 004 `CoreSupervisor` has no memory dependency, and the proposed integration introduces several mismatches.

Required decisions:

- Add `memory_manager` through dependency injection, with an explicit optional/no-op strategy if backward compatibility is required.
- Use `get_context_for_planning()` if structured context is intended. `recall()` currently returns a list.
- Merge caller context and memory context under separate namespaces; do not overwrite caller context.
- Update the actual `ModelGateway.generate_plan()` contract and all implementations/test doubles to accept context.
- Specify `_build_observation(task)` and its schema.
- Pass task/correlation/authorization context to memory operations.
- Define behavior when recall or remember fails. Memory failure should not accidentally corrupt task state or cause uncontrolled execution.
- Add memory hooks to all intended terminal paths, including execution failure and abort, or explicitly narrow AC9.
- Ensure early planning failures and exceptions have defined memory/audit behavior.
- Define whether recall happens before or after task creation. Creating the task first permits task-scoped permissions and correlation IDs.

A sound sequence would be:

```text
create task
→ resolve task authorization
→ recall/get planning context
→ merge and sanitize context
→ plan
→ execute/observe/evaluate
→ build terminal observation
→ remember
→ return task
```

---

## 11. Define all public data types and error contracts

The following types are referenced but not specified:

- `MemoryResult`
- `WriteResult`
- `VerificationReport`
- `ConflictResolution`
- `DecayReport`
- `StateDiff`

Define their fields, status enums, error behavior, serialization, and whether expected denials/rejections are returned or raised.

Also define:

- sync versus async behavior;
- idempotency keys;
- duplicate-write handling;
- optimistic concurrency/version conflicts;
- timestamp representation;
- clock injection for deterministic tests;
- resource limits.

---

## 12. Add planning-context security controls

Memory content is untrusted input to the model, especially inferred or externally sourced summaries. Validation against database poisoning does not automatically prevent prompt injection.

The planning-context contract must include:

- strict size/token limits;
- entry-count and per-entry length limits;
- structured serialization rather than raw prompt concatenation;
- clear untrusted-data labeling;
- exclusion or escaping of control/instruction fields;
- no secrets or ADMIN-only data;
- source/confidence/verification indicators;
- handling of flagged contradictions;
- resistance to memories containing instructions such as “ignore system policy.”

Memory must inform planning but must never override system policy, permissions, or tool authorization.

---

## 13. Expand and map the test plan to the acceptance criteria

The test suites are directionally good, but test counts are not sufficient evidence of coverage. Add an explicit AC-to-test matrix and include at least:

- real close/reopen persistence test;
- deterministic semantic retrieval test;
- embedding-unavailable fallback test;
- unauthorized retrieval for every retrieval method;
- forged provenance and forged permission-level tests;
- unauthorized update, resolution, consolidation, decay, and world-state mutation;
- audit-trail immutability tests;
- poisoned batch rollback;
- update revalidation;
- soft-deleted and expired entry exclusion;
- contradiction versus mere similarity;
- stale-memory detection independent of contradiction;
- confidence/version-history persistence;
- rejected write does not update world state;
- world-state restart and point-in-time reconstruction;
- boundary timestamps and injected clock;
- supervisor context merge;
- recall-before-plan ordering;
- planning failure, task failure, abort, and memory-service failure paths;
- prompt-injection and context-budget tests;
- ModelGateway implementation/test-double compatibility;
- no live OpenAI/network dependency in normal tests.

Run lint and typing over all changed areas, for example:

```bash
ruff check src/memory/ src/core/ tests/
mypy src/memory/ src/core/
```

The final exact scope may be broader depending on modified gateway/provider modules.

---

# 3. Assessment of the Seven Components

## MemoryPermissions — **Insufficient**

The intended matrix is useful, but the interface trusts supplied permission levels and does not cover actual caller identity or task overrides. More importantly, none of the read APIs accepts authorization context. The current Phase 004 engine is tool-oriented, so the integration mechanism must be explicitly designed.

## MemoryRetriever — **Partially specified**

The high-level query operations are appropriate. Missing pieces include the semantic-store abstraction, permissions, normalization, embedding lifecycle, deleted/expired filtering, deterministic ranking, and resource bounds. `retrieve_related()` is especially underspecified because “shared entities” requires entity extraction/indexing that is not otherwise defined.

## MemoryWriter — **Partially specified**

Centralizing writes is correct, but the dependency list does not include the contradiction detector despite the documented pipeline. Update/delete identity and authorization are inadequate, and direct store access by verifier/decay can bypass the writer. Atomicity, version conflicts, immutable fields, and trusted provenance require specification.

## MemoryVerifier — **Insufficient**

The verifier has no observation schema, stale-memory model, authorization context, writer dependency, or durable resolution record. Similarity-based contradiction detection is not enough. Direct store mutation would undermine the validated-write requirement.

## MemoryDecay — **Insufficient**

The component conflates memory type and retention type, relies on access metadata not shown in `MemoryEntry`, references an undefined archive, and does not define safe consolidation. It also requires an injected clock and controlled mutation path.

## WorldStateManager — **Insufficient**

The interface is plausible, but the underlying state/event schema, persistence, consistency, and reconstruction semantics are absent. Accepting arbitrary dictionaries cannot reliably provide historical world-state reconstruction.

## MemoryManager — **Partially specified**

A single supervisor-facing façade is a good design. However, it lacks request context, transaction/failure semantics, and a clear distinction between `recall()` and `get_context_for_planning()`. The order between accepted memory persistence and world-state updates must be specified.

---

# 4. CoreSupervisor Integration Assessment

**Not sound as currently written.**

Specific verified mismatches against the supplied supervisor:

1. `CoreSupervisor.__init__()` has no memory dependency.
2. The existing `generate_plan()` call does not pass context.
3. The proposed code passes `recall()` output as context even though `recall()` returns a list and the documented planning context is a dictionary.
4. Existing caller `context` is used to create the task but is not shown being safely merged with memory context.
5. `_build_observation()` does not exist in the supplied class.
6. Existing early returns on planning failure bypass the proposed remember hook.
7. Failed or aborted tasks are not remembered.
8. No memory audit events or correlation IDs are defined.
9. No failure policy exists for unavailable or corrupt memory.
10. No authorization context is propagated.

These are specification defects rather than minor implementation details.

---

# 5. Baseline Reuse Assessment

The specification generally intends to reuse the Phase 1 classes rather than duplicate them, which is positive. However, several integration points need correction:

- `PgVectorStore` is claimed but not represented in the retriever’s dependencies.
- `MemoryWriter` separately receives `ValidationPipeline` and `PoisoningResistance`; clarify whether the pipeline already invokes poisoning resistance to avoid duplicate rate-limit accounting.
- Contradiction detection ownership is inconsistent.
- Generic Phase 005 APIs risk bypassing the baseline cognitive/audit separation.
- Existing default metadata such as `source_verified=True` must not be trusted simply because it exists on a caller-created `MemoryEntry`.
- Existing storage capabilities must be documented through an interface rather than assumed.

No wholesale rewrite of the Phase 1 subsystem is warranted. Adapters and carefully defined extensions are preferable.

---

# 6. Security Assessment

The stated security priority is appropriate, but the current design does not yet provide the claimed protections.

Highest-risk issues:

1. **Caller-controlled authorization:** APIs accept levels or provenance rather than an authenticated principal.
2. **Unprotected reads:** retrieval methods cannot enforce permissions.
3. **Mutation bypass:** verifier, decay, and world-state components can modify storage outside the writer pipeline.
4. **Audit weakening:** generic update/delete behavior could affect audit records.
5. **Prompt injection:** stored memory is injected into planning without an untrusted-context policy.
6. **Poisoning metadata forgery:** caller-created entries can claim verified provenance or benign anomaly scores.
7. **Inference self-reinforcement:** no rule prevents inferred memories from being repeatedly confirmed by other inferred memories derived from the same source.
8. **Conflict overwrite abuse:** overwrite authority and evidence requirements are undefined.
9. **Information leakage through related retrieval:** relation traversal can expose protected entries unless filtering is enforced before return.
10. **No resource limits:** oversized content, embeddings, batches, histories, or retrieval requests could cause denial of service.

---

# 7. Implementation Recommendations

After the specification is corrected:

1. Define storage, authorization, observation, and result protocols first.
2. Implement `MemoryPermissions` with authoritative task/principal resolution.
3. Implement the store transaction/migration layer and deterministic test fixtures.
4. Build `MemoryWriter` as the only cognitive-memory mutation boundary.
5. Implement permission-filtered retrieval with a semantic-search abstraction.
6. Implement claim-based contradiction/verification semantics.
7. Implement decay and consolidation through the writer boundary.
8. Implement world state as a rebuildable projection of accepted state events.
9. Add a no-op or optional memory manager for backward-compatible CoreSupervisor construction.
10. Integrate the gateway context contract and add lifecycle/failure-path tests.
11. Run the full regression suite and static checks over every modified module.

---

## Final Determination

The specification has a viable architectural direction, but it presently leaves security-critical behavior and several core semantics to implementation guesswork. Most importantly, permissions are not enforceable end-to-end, contradiction/staleness semantics are inadequate, lifecycle promotion is internally inconsistent, and the CoreSupervisor example does not type- or behaviorally align with the proposed APIs.

**Implementation should remain paused until the required changes above are incorporated into the specification.**

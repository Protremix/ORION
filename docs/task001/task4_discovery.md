# ORION TASK 001 — TASK 4: ORION Discovery Architecture

## Discovery Pipeline

```
Knowledge Ingestion
    ↓
Structured Knowledge / Graph
    ↓
Evidence Tracking
    ↓
Contradiction Detection
    ↓
Gap Detection
    ↓
Hypothesis Generation
    ↓
Hypothesis Ranking
    ↓
Simulation / Computational Testing
    ↓
Experiment Proposal
    ↓
Result Ingestion
    ↓
Knowledge Update
```

## Design

### 1. Knowledge Ingestion

**Purpose:** Accept knowledge from multiple sources (papers, datasets, APIs, observations, experiments).

**Sources:**
- Scientific papers (PubMed, arXiv, bioRxiv)
- Structured databases (UniProt, ChEMBL, PubChem)
- ORION's own observations (simulation results, sensor data)
- External APIs (OpenAI, search, scientific databases)
- Manual input (researcher queries)

**Architecture:**
```python
class KnowledgeIngestion:
    def ingest_paper(self, source: str, content: str) -> KnowledgeEntry
    def ingest_dataset(self, source: str, data: Any) -> List[KnowledgeEntry]
    def ingest_observation(self, domain: str, observation: dict) -> KnowledgeEntry
    def ingest_api_result(self, api: str, query: str, result: dict) -> KnowledgeEntry
```

Each entry includes: source, timestamp, confidence, domain, raw content, structured representation, provenance chain.

### 2. Structured Knowledge / Graph

**Purpose:** Represent knowledge as a queryable graph with typed relationships.

**Structure:**
```
Node types: Entity, Concept, Fact, Hypothesis, Experiment, Result, Observation
Edge types: supports, contradicts, implies, causes, correlates, measures, derived_from, part_of
```

**Storage:** 
- Graph database (Neo4j or NetworkX for initial implementation)
- Vector store for semantic similarity (pgvector — already in ORION)
- Document store for raw content (PostgreSQL — already in ORION)

**Architecture:**
```python
class KnowledgeGraph:
    def add_node(self, node: KnowledgeNode) -> str
    def add_edge(self, from_id: str, to_id: str, relation: Relation) -> bool
    def query(self, cypher_or_gremlin: str) -> List[KnowledgeNode]
    def find_paths(self, from_id: str, to_id: str) -> List[Path]
    def get_neighborhood(self, node_id: str, depth: int) -> SubGraph
```

### 3. Evidence Tracking

**Purpose:** Track the evidence supporting or contradicting each claim.

**Design:**
```python
@dataclass
class Evidence:
    claim_id: str          # Which claim this supports/contradicts
    source_id: str         # Where the evidence came from
    direction: str         # "supports" or "contradicts"
    strength: float        # 0.0-1.0
    type: str              # "empirical", "theoretical", "simulation", "expert"
    metadata: dict         # p-values, sample sizes, confidence intervals
```

Every knowledge node has an evidence score = weighted sum of supporting evidence minus weighted sum of contradicting evidence.

### 4. Contradiction Detection

**Purpose:** Detect when new knowledge contradicts existing knowledge.

**Methods:**
- **Explicit:** New evidence with direction="contradicts" against existing claim
- **Semantic:** LLM-based comparison of new knowledge vs existing knowledge
- **Numerical:** Contradictory measurements (e.g., protein binding affinity differs)
- **Logical:** Inference chain produces a contradiction

**Architecture:**
```python
class ContradictionDetector:
    def check(self, new_entry: KnowledgeEntry) -> List[Contradiction]
    def resolve(self, contradiction: Contradiction) -> Resolution
    # Resolution: update confidence, flag for human review, or request more evidence
```

### 5. Gap Detection

**Purpose:** Identify what is NOT known but should be.

**Methods:**
- **Missing links:** Entities A and B exist but no relationship between them
- **Unsupported claims:** High-confidence claims with no evidence
- **Unexplored regions:** Areas of the knowledge graph with low density
- **Domain gaps:** Questions that should have answers but don't

**Architecture:**
```python
class GapDetector:
    def find_missing_links(self, domain: str) -> List[Gap]
    def find_unsupported_claims(self) -> List[Gap]
    def find_underexplored(self, domain: str) -> List[Gap]
```

### 6. Hypothesis Generation

**Purpose:** Generate novel, testable hypotheses from gaps and contradictions.

**Methods:**
- **Gap-filling:** "If A causes B, and B causes C, then A might cause C"
- **Contradiction resolution:** "If study 1 says X and study 2 says not-X, maybe variable V moderates the effect"
- **Analogy:** "If mechanism M works in domain D1, it might work in D2"
- **LLM-assisted:** Use GPT-4o to generate hypotheses from structured gaps

**Architecture:**
```python
class HypothesisGenerator:
    def generate_from_gap(self, gap: Gap) -> Hypothesis
    def generate_from_contradiction(self, c: Contradiction) -> Hypothesis
    def generate_by_analogy(self, domain_a: str, domain_b: str) -> Hypothesis
    def generate_with_llm(self, context: str, gaps: List[Gap]) -> List[Hypothesis]
```

**Hypothesis structure:**
```python
@dataclass
class Hypothesis:
    id: str
    statement: str         # "X causes Y under condition Z"
    rationale: str         # Why this hypothesis
    predicted_effect: str  # What we expect to observe
    testability: float     # 0.0-1.0 — how testable
    novelty: float         # 0.0-1.0 — how novel
    risk_level: str        # "low", "medium", "high" — safety classification
    domain: str            # Which knowledge domain
    source_gaps: List[str] # Which gaps led to this hypothesis
```

### 7. Hypothesis Ranking

**Purpose:** Rank hypotheses by potential impact, testability, and safety.

**Criteria:**
- **Impact score:** How much would confirming/refuting this advance knowledge?
- **Testability score:** Can we test this in simulation or computationally?
- **Safety score:** Is testing this hypothesis safe?
- **Novelty score:** Is this hypothesis already known?
- **Evidence score:** How much existing evidence supports it?

**Ranking formula:**
```
rank = (impact × 0.3) + (testability × 0.25) + (safety × 0.2) + (novelty × 0.15) + (evidence × 0.1)
```

### 8. Simulation / Computational Testing

**Purpose:** Test hypotheses using simulation before physical experiments.

**Methods:**
- **Physics simulation:** Use ORION's World Model to simulate predicted effects
- **Computational testing:** Molecular dynamics, statistical models, etc.
- **Counterfactual:** Compare outcomes with and without the hypothesized cause
- **Statistical:** Correlation analysis on existing data

**Architecture:**
```python
class HypothesisTester:
    def test_simulation(self, hypothesis: Hypothesis, world_model: WorldModel) -> TestResult
    def test_computational(self, hypothesis: Hypothesis) -> TestResult
    def test_counterfactual(self, hypothesis: Hypothesis, world_model: WorldModel) -> TestResult
```

### 9. Experiment Proposal

**Purpose:** Propose real-world experiments for hypotheses that can't be tested computationally.

**ASSUMPTION:** ORION does NOT execute experiments autonomously. It proposes them for human researchers.

**Architecture:**
```python
@dataclass
class ExperimentProposal:
    hypothesis_id: str
    title: str
    methodology: str
    expected_outcome: str
    controls: List[str]
    variables: List[str]
    sample_size: Optional[int]
    duration: Optional[str]
    safety_assessment: str
    cost_estimate: Optional[str]
    ethical_review: bool       # Always True for medical/biological
    researcher_notes: str
```

### 10. Result Ingestion & Knowledge Update

**Purpose:** Feed experimental results back into the knowledge graph.

**Flow:**
1. Result comes in (from simulation or external experiment)
2. Create new Evidence entry
3. Update knowledge graph with new relationships
4. Re-evaluate contradictions
5. Re-rank affected hypotheses
6. Identify new gaps

## Safety Constraints

- ORION must NOT autonomously prescribe treatment (Master Spec)
- Medical hypotheses require human review before experiment proposal
- High-risk experiments (biological, chemical) require Founder approval
- All discovery is logged and auditable

## Existing AI-for-Science Systems (preliminary — sub-agents researching)

- **AlphaFold / ESM:** Protein structure prediction — ORION could use as adapter
- **Scientific discovery agents:** Research ongoing (sub-agent)
- **Automated hypothesis systems:** Research ongoing (sub-agent)

## Possible ORION Additions

Based on the pipeline design:
1. **Integrated discovery loop** — most systems do isolated tasks; ORION loops the full pipeline
2. **Cross-domain hypothesis transfer** — apply knowledge from one domain to another
3. **Simulation-first discovery** — test hypotheses in simulation before real experiments
4. **Evidence-weighted knowledge graph** — confidence-based reasoning, not just facts
5. **LLM-assisted gap detection** — use GPT-4o to identify what's missing

## Classification

- Architecture design: HYPOTHESIS (not yet implemented)
- Feasibility: MEDIUM (individual components exist in literature, integration is novel)
- Risk: LOW (all in silico, no physical experiments)
- Next step: Build knowledge graph prototype + gap detector

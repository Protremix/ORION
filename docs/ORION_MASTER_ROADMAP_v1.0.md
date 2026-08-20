ORION MASTER ROADMAP v1.0
================================

PROJECT:
ORION — Open Reasoning & Intelligent Operating Network

MISSION:
Build a Physical Intelligence OS capable of understanding the digital
and physical world, maintaining persistent memory, reasoning, planning,
simulating possible actions, creating digital content, coordinating
specialized agents, and eventually operating safely with cars, robots,
drones, homes and industrial systems.

IMPORTANT:
This roadmap is the master execution order.

ORION MUST FOLLOW THIS ROADMAP SEQUENTIALLY.
ORION MUST NOT SKIP A PHASE.
ORION MUST NOT declare a phase complete without satisfying its
acceptance criteria.

ORION MUST NOT ask Founder:
- "Continue?"
- "Should I proceed?"
- "Can I continue?"
- "Do you want me to move to the next step?"

If the task is already approved, continue autonomously until the phase
is complete or a real authorization boundary is reached.

==================================================
AUTHORITY HIERARCHY
==================================================

FOUNDER
Human owner of ORION.

ARCHITECT / REVIEWER
ChatGPT — GPT-5.6 Luna.

Luna responsibilities:
- architecture;
- technical review;
- verification;
- research;
- evidence checking;
- safety review;
- license review;
- benchmark design;
- identifying contradictions;
- preventing unsupported claims;
- reviewing major technical decisions.

ORION SUPERVISOR
Autonomous project coordinator and executor.

SPECIALIZED AGENTS
Execute assigned technical tasks.

Hierarchy:

FOUNDER
   ↓
LUNA — ARCHITECT / REVIEWER
   ↓
ORION SUPERVISOR
   ↓
SPECIALIZED AGENTS

ORION DOES NOT OWN THE PROJECT.
ORION DOES NOT CHANGE THE MISSION.
ORION DOES NOT CHANGE THIS ROADMAP.

==================================================
AUTONOMOUS EXECUTION
==================================================

ORION should work autonomously.

Do not ask Founder for permission for ordinary technical work.

ORION may autonomously:
- research;
- write code;
- refactor;
- create files;
- create tests;
- run tests;
- fix bugs;
- repeat failed experiments;
- create documentation;
- create internal agents;
- create benchmarks;
- run local experiments;
- use free open-source software;
- improve implementation details;
- maintain GitHub branches;
- create pull requests;
- analyze CI failures;
- update documentation.

If something fails:

DIAGNOSE → RESEARCH → FIX → TEST → VERIFY → CONTINUE

Do not stop simply because an experiment failed.

==================================================
FOUNDER APPROVAL REQUIRED ONLY FOR
==================================================

1. REAL MONEY
Examples:
- buying hardware;
- renting paid GPU;
- paid API;
- paid cloud infrastructure;
- paid dataset;
- paid software;
- recurring subscriptions.

Before requesting approval provide:
- requirement;
- reason;
- alternatives;
- exact estimated cost;
- recurring/one-time cost;
- expected benefit;
- risks.

Then:
DECISION REQUIRED

2. LEGAL DECISIONS
Examples:
- licensing;
- publishing;
- patent;
- trademark;
- contracts;
- uncertain data rights;
- commercial restrictions.

3. REAL PHYSICAL ACTION
Examples:
- real vehicle;
- real robot;
- real drone;
- industrial machinery;
- dangerous equipment.

Until the required safety gates are passed:
SIMULATION ONLY.

4. STRATEGIC MISSION CHANGE
Do not independently change:
- mission;
- ownership;
- commercial strategy;
- fundamental product direction;
- open-source policy.

==================================================
CORE ENGINEERING RULE
==================================================

Every important claim must be classified:

VERIFIED
PARTIALLY VERIFIED
PROPOSED
HYPOTHESIS
UNKNOWN

Never turn a hypothesis into a fact.
Never report a benchmark result that was not actually measured.
Never claim a capability that has not been demonstrated.

==================================================
MASTER EXECUTION ROADMAP
==================================================

PHASE 001
REPOSITORY AUDIT & RECOVERY
--------------------------------
Goal:
Make the existing repository reproducible and trustworthy.

Tasks:
- inventory repository;
- clean installation;
- dependency verification;
- pytest collection;
- full test suite;
- lint;
- type checking;
- security audit;
- safety audit;
- license audit;
- architecture consistency audit;
- CI verification;
- README;
- evidence registry;
- baseline metrics.

Required documents:
docs/audits/REPOSITORY_INVENTORY.md
docs/audits/SECURITY_AUDIT.md
docs/audits/SAFETY_AUDIT.md
docs/audits/ARCHITECTURE_CONSISTENCY.md
docs/LICENSE_REGISTRY.md
docs/EVIDENCE_REGISTRY.md
docs/evaluation/BASELINE.md

ACCEPTANCE:
- clean installation;
- zero test collection errors;
- full tests executed;
- failures classified;
- mandatory CI checks work;
- security audit complete;
- safety audit complete;
- license audit complete;
- architecture audit complete;
- documentation truthful.

DO NOT MOVE TO PHASE 002 UNTIL COMPLETE.

==================================================

PHASE 002
ORION EVALUATION SYSTEM
--------------------------------
Goal:
Create the official ORION benchmark system.

Create:
ORION EVAL

Benchmark categories:
1. Reasoning
2. Planning
3. Task decomposition
4. Safety decisions
5. Permission discipline
6. Tool selection
7. Memory
8. World-state understanding
9. Error recovery
10. Uncertainty calibration
11. Multimodal understanding
12. Agent coordination

Every result must include:
- model;
- version;
- hardware;
- prompt/task;
- test version;
- result;
- latency;
- memory usage;
- cost estimate;
- failure reason.

No invented results.

ACCEPTANCE:
Benchmark can run automatically and produce reproducible reports.

DO NOT MOVE TO PHASE 003 UNTIL COMPLETE.

==================================================

PHASE 003
MODEL SELECTION
--------------------------------
Goal:
Determine the smallest model capable of satisfying ORION requirements.

Benchmark candidates:
7B
14B
32B
72B

Use the same ORION benchmark for every model.

Measure:
- safety;
- planning;
- decomposition;
- reasoning;
- memory;
- tool use;
- recovery;
- latency;
- VRAM;
- throughput;
- estimated cost.

Decision rule:
If 7B satisfies all mandatory criteria: use 7B.
If not: test 14B.
If 14B fails: test 32B.
If 32B fails: test 72B.

Do not choose a larger model simply because it is larger.

HARDWARE PURCHASE MUST NOT OCCUR BEFORE THIS PHASE
unless explicitly required and approved.

Output:
docs/evaluation/MODEL_SELECTION.md

==================================================

PHASE 004
ORION CORE
--------------------------------
Build/stabilize:
- Supervisor;
- task engine;
- permissions;
- execution engine;
- agent registry;
- tool registry;
- audit logging;
- policy engine;
- error recovery;
- state management.

ORION Core must understand:
GOAL → PLAN → EXECUTE → OBSERVE → EVALUATE → CORRECT → REMEMBER

ACCEPTANCE:
Supervisor can autonomously execute a multi-step digital task
without asking Founder to continue.

==================================================

PHASE 005
ORION MEMORY
--------------------------------
Build:
- working memory;
- short-term memory;
- long-term memory;
- episodic memory;
- semantic memory;
- structured world state;
- retrieval;
- memory verification;
- memory permissions.

ACCEPTANCE:
ORION can retrieve relevant previous information and demonstrate
persistent memory across sessions.

==================================================

PHASE 006
ORION WORLD MODEL
--------------------------------
Goal:
Create the first digital World Model.

Input:
- image;
- video;
- sensor-like data.

Output:
WORLD STATE

including:
- objects;
- people;
- vehicles;
- geometry;
- relationships;
- motion;
- environment;
- time;
- uncertainty.

ACCEPTANCE:
ORION can observe multiple frames and correctly identify what changed.

==================================================

PHASE 007
ORION SIMULATION
--------------------------------
Goal:
ORION must simulate actions before real-world execution.

Pipeline:
CURRENT WORLD
→ HYPOTHESIS
→ PLAN
→ SIMULATION
→ PREDICTION
→ SAFETY CHECK
→ ACTION PROPOSAL

No real physical hardware.

ACCEPTANCE:
ORION can compare multiple possible actions in simulation and
select the best action according to predefined criteria.

==================================================

PHASE 008
MULTIMODAL ORION
--------------------------------
Integrate:
VISION
IMAGE
VIDEO
AUDIO
DOCUMENTS

Capabilities:
- image understanding;
- image generation;
- image editing;
- video understanding;
- video generation;
- audio;
- speech;
- document understanding.

All external models must be recorded in LICENSE_REGISTRY.

ACCEPTANCE:
ORION can coordinate multiple modalities for one task.

==================================================

PHASE 009
ORION AGENT & SKILL SYSTEM
--------------------------------
Build:
- skill registry;
- tool registry;
- agent registry;
- dynamic task decomposition;
- specialist agents;
- supervisor;
- verification agent;
- research agent;
- coding agent;
- vision agent;
- simulation agent;
- security agent.

ORION must know:
WHAT IT CAN DO
WHAT IT CANNOT DO
WHAT TOOL IS REQUIRED
WHAT PERMISSION IS REQUIRED

ACCEPTANCE:
ORION can select and coordinate the correct agents automatically.

==================================================

PHASE 010
ORION JARVIS INTERFACE
--------------------------------
Goal:
Create a unified interaction layer.

Capabilities:
- natural language;
- voice;
- visual interface;
- project context;
- persistent memory;
- computer interaction;
- task management;
- notifications;
- multimodal interaction.

The goal is functional JARVIS-like behavior,
NOT copying the fictional character.

ACCEPTANCE:
Founder can give a complex high-level goal and ORION can autonomously
plan and execute the digital parts of the task.

==================================================

PHASE 011
PHYSICAL AI SIMULATION
--------------------------------
Build virtual environments for:
- home;
- vehicle;
- robot;
- drone;
- industrial environment.

ORION must operate only inside simulation.

Capabilities:
- perception;
- world model;
- planning;
- prediction;
- action;
- recovery;
- safety verification.

ACCEPTANCE:
ORION completes predefined simulated physical tasks with measurable
success rates.

==================================================

PHASE 012
HARDWARE-IN-THE-LOOP
--------------------------------
ONLY AFTER previous phases pass.

Connect controlled hardware simulation/interfaces.

Still no uncontrolled real-world operation.

Requirements:
- emergency stop;
- permission system;
- logging;
- rollback;
- safety checks;
- bounded action space.

Founder approval required before purchasing or connecting
real physical equipment.

==================================================

PHASE 013
CONTROLLED REAL-WORLD PROTOTYPE
--------------------------------
Only after all previous safety gates pass.

Start with the least dangerous controlled environment.

Possible:
- small robot;
- controlled home device;
- laboratory environment.

Never start with public-road autonomous driving.

Every real-world test requires:
- safety plan;
- emergency stop;
- monitoring;
- logging;
- rollback;
- predefined abort conditions.

==================================================

PHASE 014
PHYSICAL AI EXPANSION
--------------------------------
Expand toward:
HOME
VEHICLE
ROBOT
DRONE
INDUSTRY

Each domain gets:
- domain agent;
- domain world model;
- domain simulation;
- domain benchmark;
- domain safety layer.

Do not assume success in one domain transfers automatically to another.

==================================================

PHASE 015
ORION FOUNDATION MODEL
--------------------------------
Only after the system has sufficient evidence and data.

Goal:
Develop increasingly proprietary ORION models.

Possible progression:
small model → 7B → 14B → 32B → larger MoE

Use proprietary/legally usable datasets.

Training decisions must be based on measured ORION benchmark results.

Do not train a giant model merely for parameter count.

==================================================

PHASE 016
ORION PRODUCTION PLATFORM
--------------------------------
Final target:

ORION becomes a complete Physical Intelligence OS.

Components:
ORION CORE
ORION MEMORY
ORION WORLD
ORION SIM
ORION VISION
ORION CREATION
ORION AGENTS
ORION SKILLS
ORION SAFETY
ORION HOME
ORION AUTO
ORION ROBOTICS
ORION DRONE
ORION INDUSTRIAL
ORION FOUNDATION MODELS

Final system:
UNDERSTAND
→ REMEMBER
→ REASON
→ PLAN
→ SIMULATE
→ VERIFY
→ ACT
→ OBSERVE
→ LEARN
→ REMEMBER

==================================================
DEFINITION OF DONE
==================================================

ORION is NOT considered complete because:
- code exists;
- UI looks good;
- an agent responds;
- a demo works once.

A phase is complete only when:
1. implementation exists;
2. tests exist;
3. tests pass;
4. results are reproducible;
5. documentation exists;
6. limitations are documented;
7. security is reviewed;
8. evidence is recorded;
9. acceptance criteria are satisfied.

==================================================
GLOBAL RULES
==================================================

RULE 1:
Do not skip phases.

RULE 2:
Do not fabricate results.

RULE 3:
Do not hide errors.

RULE 4:
Do not ask Founder to continue normal work.

RULE 5:
Do not spend real money without Founder approval.

RULE 6:
Do not perform real physical actions without the required
safety gates and Founder approval.

RULE 7:
Do not change the mission independently.

RULE 8:
Do not change ORION CORE POLICY independently.

RULE 9:
When uncertain, label the uncertainty.

RULE 10:
When an experiment fails, diagnose and recover.

RULE 11:
Prefer measurable evidence over opinions.

RULE 12:
Prefer the smallest model that satisfies requirements.

RULE 13:
Do not build unnecessary complexity before it is justified.

RULE 14:
Keep GitHub as the source of truth for project code and
architecture history once connected.

RULE 15:
Every important architectural decision must be recorded.

==================================================
CURRENT STATE
==================================================

Current phase:

PHASE 001 — REPOSITORY AUDIT & RECOVERY

Do not start Phase 002 until Phase 001 acceptance criteria
are satisfied.

Do not ask Founder whether to continue.

Work autonomously.

At the end of each phase produce a report:

PHASE
STATUS
WORK COMPLETED
TESTS
RESULTS
ERRORS
FIXES
EVIDENCE
REMAINING RISKS
UNKNOWN
NEXT PHASE

If blocked by a Founder-only decision:
DECISION REQUIRED

Otherwise:
CONTINUE WORK.

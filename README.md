# 🧠 MemoryMesh: Persistent Graph Memory for Agentic AI

MemoryMesh is a production-grade, local-first agentic AI project coordinator designed to solve context amnesia, hallucination, and multi-agent coordination failures. Instead of storing state in transient in-memory conversation windows or flat key-value pairs, MemoryMesh persists state in a **labeled property graph (FalkorDB)** using a tri-partite cognitive memory architecture (**Episodic**, **Semantic**, and **Procedural**).

All language model inference is driven entirely locally by **Ollama (`qwen3:4b`)**, ensuring zero data leakage and zero paid third-party API dependencies.

---

## 🏛️ Architecture Overview

```
                      ┌───────────────────────────────────────────────┐
                      │              Streamlit Dashboard              │
                      │               (localhost:8501)                │
                      └──────────────────────┬────────────────────────┘
                                             │ HTTP REST
                      ┌──────────────────────▼────────────────────────┐
                      │              FastAPI Backend                  │
                      │               (localhost:8000)                │
                      └──────────────────────┬────────────────────────┘
                                             │
             ┌───────────────────────────────┴───────────────────────────────┐
             │                                                               │
┌────────────▼──────────────┐                                   ┌────────────▼──────────────┐
│     Multi-Agent Team      │                                   │   FalkorDB Graph Engine   │
│                           │                                   │                           │
│ 1. Memory Curator         ├─────── Parameterized Cypher ─────►│ • Tenant Alpha Graph      │
│ 2. Investigator (Recall)  │                                   │   (memorymesh_tenant_alpha)│
│ 3. Planner (Coordinator)  │                                   │                           │
│ 4. Verifier (Evaluator)   │                                   │ • Tenant Beta Graph       │
│                           │                                   │   (memorymesh_tenant_beta) │
└────────────┬──────────────┘                                   └───────────────────────────┘
             │
             │ Local Prompts & Schema-Enforced JSON
┌────────────▼──────────────┐
│   Ollama (qwen3:4b)       │
│   (localhost:11434)       │
└───────────────────────────┘
```

---

## 🧠 Cognitive Memory Model in FalkorDB

MemoryMesh organizes memory into three distinct node and relationship categories:

### 1. Episodic Memory (What happened and when)
- **Node**: `(:Episode)`
  - Attributes: `id`, `session_id`, `project_id`, `content`, `actor`, `event_type`, `timestamp`, `source_event_id`
  - Purpose: Records raw conversational exchanges and state transition events chronologically.

### 2. Semantic Memory (What is true about the project)
- **Node**: `(:Project)` — Central project entity (`id`, `name`, `description`, `status`).
- **Node**: `(:Person)` — Team members and roles (`id`, `name`, `role`).
- **Node**: `(:Fact)` — Atomic propositions (`subject`, `predicate`, `value`, `confidence`, `status`, `version`).
  - Lifecycle: `current` ➔ `superseded` (or `disputed`, `candidate`). Old facts remain linked via `[:SUPERSEDES]` edges for full auditability.
- **Node**: `(:Decision)` — Architectural and project choices (`title`, `chosen_option`, `rationale`, `status`).
- **Edge**: `(f:Fact)-[:SUPPORTED_BY]->(e:Episode)` — Provenance link back to the source message.

### 3. Procedural Memory (How tasks are structured and accomplished)
- **Node**: `(:Task)` — Concrete units of work (`id`, `title`, `description`, `status`, `priority`, `revision`).
- **Node**: `(:Procedure)` — Standard operating procedures and checklists (`title`, `steps_json`, `version`, `approved`).
- **Edge**: `(t1:Task)-[:BLOCKED_BY]->(t2:Task)` — Explicit dependency graphs preventing premature completion.

---

## 🤖 The Four Specialist Agents

1. **Memory Curator (Ingestion & Extraction)**:
   - Evaluates incoming user messages.
   - Extracts candidate entities, facts, decisions, and tasks.
   - Detects when incoming information contradicts or updates existing facts, creating new versions and marking previous ones `superseded`.

2. **Investigator (Context Recall)**:
   - Read-only agent.
   - Runs parameterized Cypher queries across the graph for facts, tasks, blockers, decisions, and recent episodes.
   - Compiles structured contextual evidence without hallucinating or modifying graph state.

3. **Planner (Project Coordinator)**:
   - Evaluates user intent against retrieved context and dependency graphs.
   - Identifies blockers and suggests optimal next actions (`update_task`, `create_handoff`, `recommend`).
   - Dispatches work to persistent handoff records.

4. **Verifier (Grounding & Validation)**:
   - Validates that every statement in the proposed response is grounded in retrieved graph nodes.
   - Cites node IDs (`Fact`, `Decision`, `Task`, `Episode`) as verifiable evidence references.
   - Flags missing evidence or unverified assumptions.

---

## 🛡️ Enterprise Engineering Guarantees

### Strict Multi-Tenant Isolation
- Tenant Alpha and Tenant Beta are assigned separate physical graph keys in FalkorDB (`memorymesh_tenant_alpha` vs `memorymesh_tenant_beta`).
- Repository queries are strictly scoped to the authenticated tenant.
- All endpoints validate tenant membership against whitelist policies before executing graph queries.

### Optimistic Concurrency Control
- `TaskNode` tracks an incremental `revision` counter.
- Status updates execute conditional Cypher mutations (`WHERE t.revision = $expected_revision SET t.revision = t.revision + 1`).
- Conflicting simultaneous writes are safely rejected rather than overwritten.

### Parameterized Cypher Queries (Zero Injection)
- The LLM **never** generates dynamic Cypher strings directly.
- All mutations and lookups execute through static templates in [src/db/queries.py](file:///Users/teju/Desktop/Agentic_AI/memorymesh/src/db/queries.py) with `$param` bindings.

### Persistent Inter-Agent Handoffs
- Handoffs are first-class graph nodes `(:Handoff)` with lifecycle states: `pending` ➔ `claimed` ➔ `completed`.
- State transitions are atomic and queryable across agent boundaries.

---

## 🚀 Getting Started

### 1. Prerequisites
- **Python 3.10+** (Tested on Python 3.11)
- **Docker** (for FalkorDB)
- **Ollama** (for local LLM inference)

### 2. Start FalkorDB
```bash
docker run -d --name falkordb -p 6379:6379 falkordb/falkordb
```

### 3. Install & Start Ollama
1. Download Ollama from [ollama.ai](https://ollama.ai).
2. Start the daemon and pull the target model:
```bash
ollama serve
ollama pull qwen3:4b
```

### 4. Setup Python Environment
```bash
cd memorymesh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 5. Verify the Environment
```bash
python3 scripts/check_environment.py
```

### 6. Run the Test Suite
```bash
# Run all tests (offline unit tests + live database tests)
pytest -v

# Run offline unit tests only (runs with 0 dependencies)
pytest tests/test_unit_offline.py -v
```

### 7. Seed Demonstration Data
```bash
python3 scripts/seed_demo.py
```
This populates:
- **Tenant Alpha**: "Phoenix App Launch" project, lead roles Alice & Bob, API & Auth tasks with dependency blocking, database choice decision (PostgreSQL), and approved procedure checklist.
- **Tenant Beta**: "DataViz Dashboard" project, Carol (Full Stack), React framework decision, WebSocket API task blocked by Design task.

### 8. Run Backend & Frontend

**Terminal 1 — FastAPI Backend:**
```bash
cd memorymesh
uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be live at: [http://localhost:8000/docs](http://localhost:8000/docs)

**Terminal 2 — Streamlit Dashboard:**
```bash
cd memorymesh
streamlit run ui/app.py --server.port 8501
```
Interactive UI will be live at: [http://localhost:8501](http://localhost:8501)

---

## 📊 Dashboard Modules

1. **💬 Project Chat**: Ask questions, request coordination, and receive answers accompanied by verifiable evidence pills and agent execution traces.
2. **🧩 Memory Explorer**: Inspect all Facts (with confidence and version), Decisions (with rationale), Tasks (with blocker warnings), Procedures, and raw Graph relationships.
3. **🔍 Agent Trace**: Audit every agent's goal, execution status, latency in milliseconds, and input/output node IDs.
4. **📋 Task Board**: Kanban-style breakdown of tasks (`pending`, `in_progress`, `blocked`, `completed`) with interactive status updater.
5. **🤝 Handoffs**: Track and manually claim or complete inter-agent handoffs.
6. **💚 System Health**: Real-time status indicators for FalkorDB, Ollama, model availability, and tenant registration.

"""Parameterized Cypher query templates for MemoryMesh.

All graph mutations go through these templates.
The LLM never generates raw Cypher — only these predefined,
parameterized queries are used.
"""

# ─── Project ─────────────────────────────────────────────────────

CREATE_PROJECT = """
MERGE (p:Project {id: $id})
ON CREATE SET p.name = $name, p.description = $description,
              p.status = $status,
              p.created_at = $created_at, p.updated_at = $updated_at
ON MATCH SET  p.name = $name, p.description = $description,
              p.status = $status,
              p.updated_at = $updated_at
RETURN p
"""

GET_PROJECT = "MATCH (p:Project {id: $id}) RETURN p"

GET_ALL_PROJECTS = "MATCH (p:Project) RETURN p ORDER BY p.created_at"

# ─── Person ──────────────────────────────────────────────────────

CREATE_PERSON = """
MERGE (p:Person {id: $id})
ON CREATE SET p.name = $name, p.role = $role, p.created_at = $created_at
ON MATCH SET  p.name = $name, p.role = $role
RETURN p
"""

GET_PERSON_BY_NAME = "MATCH (p:Person {name: $name}) RETURN p"

# ─── Episode ─────────────────────────────────────────────────────

CREATE_EPISODE = """
MERGE (e:Episode {id: $id})
ON CREATE SET e.session_id = $session_id, e.project_id = $project_id,
              e.content = $content, e.actor = $actor,
              e.timestamp = $timestamp, e.event_type = $event_type,
              e.scope = $scope, e.source_event_id = $source_event_id
RETURN e
"""

LINK_EPISODE_TO_PROJECT = """
MATCH (p:Project {id: $project_id}), (e:Episode {id: $episode_id})
MERGE (p)-[:HAS_EPISODE]->(e)
"""

GET_EPISODES_BY_SESSION = """
MATCH (e:Episode {session_id: $session_id})
RETURN e ORDER BY e.timestamp
"""

GET_EPISODES_BY_PROJECT = """
MATCH (p:Project {id: $project_id})-[:HAS_EPISODE]->(e:Episode)
RETURN e ORDER BY e.timestamp DESC LIMIT $limit
"""

GET_EPISODE_BY_ID = "MATCH (e:Episode {id: $id}) RETURN e"

SEARCH_EPISODES = """
MATCH (p:Project {id: $project_id})-[:HAS_EPISODE]->(e:Episode)
WHERE toLower(e.content) CONTAINS toLower($query)
RETURN e ORDER BY e.timestamp DESC LIMIT $limit
"""

# ─── Fact ────────────────────────────────────────────────────────

CREATE_FACT = """
MERGE (f:Fact {id: $id})
ON CREATE SET f.subject = $subject, f.predicate = $predicate,
              f.value = $value, f.confidence = $confidence,
              f.status = $status, f.valid_from = $valid_from,
              f.valid_to = $valid_to, f.created_at = $created_at,
              f.updated_at = $updated_at, f.version = $version,
              f.project_id = $project_id
RETURN f
"""

LINK_FACT_TO_PROJECT = """
MATCH (p:Project {id: $project_id}), (f:Fact {id: $fact_id})
MERGE (p)-[:HAS_FACT]->(f)
"""

LINK_FACT_TO_EPISODE = """
MATCH (f:Fact {id: $fact_id}), (e:Episode {id: $episode_id})
MERGE (f)-[:SUPPORTED_BY]->(e)
"""

SUPERSEDE_FACT = """
MATCH (old:Fact {id: $old_id}), (new:Fact {id: $new_id})
SET old.status = 'superseded', old.valid_to = $valid_to, old.updated_at = $updated_at
MERGE (new)-[:SUPERSEDES]->(old)
RETURN old, new
"""

GET_CURRENT_FACTS = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact {status: 'current'})
WHERE f.subject = $subject OR $subject = ''
RETURN f ORDER BY f.updated_at DESC LIMIT $limit
"""

GET_FACTS_BY_PROJECT = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact)
RETURN f ORDER BY f.updated_at DESC
"""

GET_FACT_BY_ID = "MATCH (f:Fact {id: $id}) RETURN f"

GET_FACT_WITH_EVIDENCE = """
MATCH (f:Fact {id: $id})
OPTIONAL MATCH (f)-[:SUPPORTED_BY]->(e:Episode)
RETURN f, collect(e) as episodes
"""

SEARCH_FACTS = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact)
WHERE (toLower(f.subject) CONTAINS toLower($query)
       OR toLower(f.value) CONTAINS toLower($query)
       OR toLower(f.predicate) CONTAINS toLower($query))
RETURN f ORDER BY f.updated_at DESC LIMIT $limit
"""

# Global fallback for tenant-wide administrative fact search
SEARCH_FACTS_GLOBAL = """
MATCH (f:Fact)
WHERE (toLower(f.subject) CONTAINS toLower($query)
       OR toLower(f.value) CONTAINS toLower($query)
       OR toLower(f.predicate) CONTAINS toLower($query))
RETURN f ORDER BY f.updated_at DESC LIMIT $limit
"""

GET_UNEMBEDDED_FACTS = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact)
WHERE f.embedding IS NULL OR f.embedding_model <> $model OR f.embedding_dim <> $dimension
RETURN f.id as id, f.subject as subject, f.predicate as predicate, f.value as value
LIMIT $limit
"""

GET_UNEMBEDDED_FACTS_GLOBAL = """
MATCH (f:Fact)
WHERE f.embedding IS NULL OR f.embedding_model <> $model OR f.embedding_dim <> $dimension
RETURN f.id as id, f.subject as subject, f.predicate as predicate, f.value as value
LIMIT $limit
"""

GET_PROJECT_FACTS_BY_IDS = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact)
WHERE f.id IN $ids
RETURN f
"""

GET_ALL_PROJECT_FACT_EMBEDDINGS = """
MATCH (p:Project {id: $project_id})-[:HAS_FACT]->(f:Fact)
WHERE f.embedding IS NOT NULL
RETURN f.id as id, f.embedding as embedding, f.embedding_model as model, f.embedding_dim as dim
"""

# ─── Decision ────────────────────────────────────────────────────

CREATE_DECISION = """
MERGE (d:Decision {id: $id})
ON CREATE SET d.title = $title, d.chosen_option = $chosen_option,
              d.rationale = $rationale, d.status = $status,
              d.project_id = $project_id,
              d.created_at = $created_at, d.updated_at = $updated_at
RETURN d
"""

LINK_DECISION_TO_PROJECT = """
MATCH (p:Project {id: $project_id}), (d:Decision {id: $decision_id})
MERGE (p)-[:HAS_DECISION]->(d)
"""

LINK_DECISION_TO_EPISODE = """
MATCH (d:Decision {id: $decision_id}), (e:Episode {id: $episode_id})
MERGE (d)-[:SUPPORTED_BY]->(e)
"""

GET_DECISIONS_BY_PROJECT = """
MATCH (p:Project {id: $project_id})-[:HAS_DECISION]->(d:Decision)
RETURN d ORDER BY d.created_at DESC
"""

SEARCH_DECISIONS = """
MATCH (p:Project {id: $project_id})-[:HAS_DECISION]->(d:Decision)
WHERE toLower(d.title) CONTAINS toLower($query)
   OR toLower(d.chosen_option) CONTAINS toLower($query)
   OR toLower(d.rationale) CONTAINS toLower($query)
RETURN d ORDER BY d.created_at DESC LIMIT $limit
"""

SEARCH_DECISIONS_GLOBAL = """
MATCH (d:Decision)
WHERE toLower(d.title) CONTAINS toLower($query)
   OR toLower(d.chosen_option) CONTAINS toLower($query)
   OR toLower(d.rationale) CONTAINS toLower($query)
RETURN d ORDER BY d.created_at DESC LIMIT $limit
"""

GET_DECISION_WITH_EVIDENCE = """
MATCH (d:Decision {id: $id})
OPTIONAL MATCH (d)-[:SUPPORTED_BY]->(e:Episode)
RETURN d, collect(e) as episodes
"""

# ─── Task ────────────────────────────────────────────────────────

CREATE_TASK = """
MERGE (t:Task {id: $id})
ON CREATE SET t.title = $title, t.description = $description,
              t.status = $status, t.priority = $priority,
              t.owner_id = $owner_id, t.project_id = $project_id,
              t.revision = $revision, t.created_at = $created_at,
              t.updated_at = $updated_at
RETURN t
"""

LINK_TASK_TO_PROJECT = """
MATCH (p:Project {id: $project_id}), (t:Task {id: $task_id})
MERGE (p)-[:HAS_TASK]->(t)
"""

CREATE_BLOCKED_BY = """
MATCH (blocker:Task {id: $blocker_id}), (blocked:Task {id: $blocked_id})
WHERE blocker.id <> blocked.id
MERGE (blocked)-[r:BLOCKED_BY]->(blocker)
RETURN r
"""

CREATE_BLOCKED_BY_SERIALIZED = """
MATCH (p:Project {id: $project_id}), (blocker:Task {id: $blocker_id}), (blocked:Task {id: $blocked_id})
WHERE coalesce(p.dep_revision, 0) = $expected_rev
  AND blocker.id <> blocked.id
SET p.dep_revision = coalesce(p.dep_revision, 0) + 1
MERGE (blocked)-[r:BLOCKED_BY]->(blocker)
RETURN r, p.dep_revision as rev
"""

ASSIGN_TASK = """
MATCH (t:Task {id: $task_id}), (p:Person {id: $person_id})
MERGE (t)-[:ASSIGNED_TO]->(p)
SET t.owner_id = $person_id
"""

UPDATE_TASK_STATUS = """
MATCH (t:Task {id: $task_id})
WHERE coalesce(t.revision, 1) = $expected_revision
SET t.status = $new_status, t.revision = coalesce(t.revision, 1) + 1,
    t.updated_at = $updated_at
RETURN t
"""

GET_TASKS_BY_PROJECT = """
MATCH (p:Project {id: $project_id})-[:HAS_TASK]->(t:Task)
RETURN t ORDER BY t.priority, t.created_at
"""

GET_TASK_BY_ID = "MATCH (t:Task {id: $id}) RETURN t"

GET_TASK_BY_TITLE = """
MATCH (p:Project {id: $project_id})-[:HAS_TASK]->(t:Task)
WHERE toLower(t.title) CONTAINS toLower($title)
RETURN t LIMIT 5
"""

GET_TASK_BY_TITLE_GLOBAL = """
MATCH (t:Task)
WHERE toLower(t.title) CONTAINS toLower($title)
RETURN t LIMIT 5
"""

GET_TASK_BLOCKERS = """
MATCH (t:Task {id: $task_id})-[:BLOCKED_BY]->(blocker:Task)
RETURN blocker
"""

GET_BLOCKED_TASKS = """
MATCH (t:Task)-[:BLOCKED_BY]->(blocker:Task {id: $blocker_id})
RETURN t
"""

GET_PROJECT_DEPENDENCIES = """
MATCH (p:Project {id: $project_id})-[:HAS_TASK]->(blocked:Task)-[:BLOCKED_BY]->(blocker:Task)
RETURN blocked.id as blocked_id, blocker.id as blocker_id
"""

# ─── Procedure ───────────────────────────────────────────────────

CREATE_PROCEDURE = """
MERGE (p:Procedure {id: $id})
ON CREATE SET p.title = $title, p.description = $description,
              p.steps_json = $steps_json, p.version = $version,
              p.approved = $approved, p.project_id = $project_id,
              p.created_at = $created_at, p.updated_at = $updated_at
RETURN p
"""

LINK_PROCEDURE_TO_PROJECT = """
MATCH (p:Project {id: $project_id}), (proc:Procedure {id: $procedure_id})
MERGE (p)-[:HAS_PROCEDURE]->(proc)
"""

GET_PROCEDURES_BY_PROJECT = """
MATCH (p:Project {id: $project_id})-[:HAS_PROCEDURE]->(proc:Procedure)
RETURN proc ORDER BY proc.title
"""

SEARCH_PROCEDURES = """
MATCH (p:Project {id: $project_id})-[:HAS_PROCEDURE]->(proc:Procedure)
WHERE toLower(proc.title) CONTAINS toLower($query)
   OR toLower(proc.description) CONTAINS toLower($query)
RETURN proc LIMIT $limit
"""

SEARCH_PROCEDURES_GLOBAL = """
MATCH (proc:Procedure)
WHERE toLower(proc.title) CONTAINS toLower($query)
   OR toLower(proc.description) CONTAINS toLower($query)
RETURN proc LIMIT $limit
"""

GET_APPROVED_PROCEDURES = """
MATCH (proc:Procedure {approved: true})
RETURN proc ORDER BY proc.title
"""

# ─── AgentRun ────────────────────────────────────────────────────

CREATE_AGENT_RUN = """
MERGE (r:AgentRun {id: $id})
ON CREATE SET r.agent_name = $agent_name, r.goal = $goal,
              r.status = $status, r.started_at = $started_at,
              r.completed_at = $completed_at, r.summary = $summary,
              r.error = $error
RETURN r
"""

COMPLETE_AGENT_RUN = """
MATCH (r:AgentRun {id: $id})
SET r.status = $status, r.completed_at = $completed_at,
    r.summary = $summary, r.error = $error
RETURN r
"""

GET_AGENT_RUN = "MATCH (r:AgentRun {id: $id}) RETURN r"

GET_RECENT_RUNS = """
MATCH (r:AgentRun)
RETURN r ORDER BY r.started_at DESC LIMIT $limit
"""

# ─── Handoff ─────────────────────────────────────────────────────

CREATE_HANDOFF = """
MERGE (h:Handoff {id: $id})
ON CREATE SET h.from_agent = $from_agent, h.to_agent = $to_agent,
              h.task_id = $task_id, h.context_summary = $context_summary,
              h.status = $status, h.created_at = $created_at,
              h.claimed_at = $claimed_at, h.completed_at = $completed_at
RETURN h
"""

LINK_HANDOFF_TO_TASK = """
MATCH (h:Handoff {id: $handoff_id}), (t:Task {id: $task_id})
MERGE (h)-[:FOR_TASK]->(t)
"""

LINK_RUN_TO_HANDOFF = """
MATCH (r:AgentRun {id: $run_id}), (h:Handoff {id: $handoff_id})
MERGE (r)-[:CREATED_HANDOFF]->(h)
"""

CLAIM_HANDOFF = """
MATCH (h:Handoff {id: $id})
WHERE h.status = 'pending'
SET h.status = 'claimed', h.claimed_at = $claimed_at
RETURN h
"""

COMPLETE_HANDOFF = """
MATCH (h:Handoff {id: $id})
WHERE h.status = 'claimed'
SET h.status = 'completed', h.completed_at = $completed_at
RETURN h
"""

FAIL_HANDOFF = """
MATCH (h:Handoff {id: $id})
SET h.status = 'failed', h.completed_at = $completed_at
RETURN h
"""

GET_HANDOFFS = """
MATCH (h:Handoff)
RETURN h ORDER BY h.created_at DESC
"""

GET_PENDING_HANDOFFS = """
MATCH (h:Handoff {status: 'pending'})
RETURN h ORDER BY h.created_at
"""

GET_HANDOFF_BY_ID = "MATCH (h:Handoff {id: $id}) RETURN h"

GET_HANDOFF_WITH_CONTEXT = """
MATCH (h:Handoff {id: $id})
OPTIONAL MATCH (h)-[:FOR_TASK]->(t:Task)
OPTIONAL MATCH (t)-[:BLOCKED_BY]->(blocker:Task)
RETURN h, t, collect(blocker) as blockers
"""

# ─── Generic relationships ───────────────────────────────────────

CREATE_ABOUT_REL = """
MATCH (a {id: $from_id}), (b {id: $to_id})
MERGE (a)-[:ABOUT]->(b)
"""

# ─── Statistics ──────────────────────────────────────────────────

COUNT_NODES = """
MATCH (n)
WITH labels(n) as lbls, count(n) as cnt
UNWIND lbls as label
RETURN label, sum(cnt) as count
ORDER BY label
"""

COUNT_RELATIONSHIPS = """
MATCH ()-[r]->()
RETURN type(r) as rel_type, count(r) as count
ORDER BY rel_type
"""

GET_ALL_NODES_AND_EDGES = """
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m LIMIT $limit
"""

# ─── Idempotency ─────────────────────────────────────────────────

CREATE_IDEMPOTENCY_RECORD = """
MERGE (k:IdempotencyRecord {key: $key})
ON CREATE SET k.status = $status, k.tenant_id = $tenant_id,
              k.project_id = $project_id, k.payload_hash = $payload_hash,
              k.reservation_token = $reservation_token,
              k.created_at = $created_at, k.updated_at = $updated_at,
              k.is_new = true
ON MATCH SET k.is_new = false
RETURN k, k.is_new as is_new
"""

GET_IDEMPOTENCY_RECORD = """
MATCH (k:IdempotencyRecord {key: $key})
RETURN k
"""

RECOVER_IDEMPOTENCY_RECORD = """
MATCH (k:IdempotencyRecord {key: $key})
WHERE k.status = 'running'
SET k.reservation_token = $reservation_token,
    k.updated_at = $updated_at,
    k.error = $error
RETURN k
"""

RETRY_FAILED_IDEMPOTENCY_RECORD = """
MATCH (k:IdempotencyRecord {key: $key})
WHERE k.status = 'failed'
SET k.status = 'running',
    k.reservation_token = $reservation_token,
    k.updated_at = $updated_at,
    k.error = ''
RETURN k
"""

COMPLETE_IDEMPOTENCY_RECORD = """
MATCH (k:IdempotencyRecord {key: $key})
WHERE k.status = 'running' AND k.reservation_token = $reservation_token
SET k.status = $status, k.response_json = $response_json,
    k.error = $error, k.updated_at = $updated_at
RETURN k
"""

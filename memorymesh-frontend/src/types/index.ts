export type MemoryKind = 'fact' | 'decision' | 'task' | 'procedure' | 'episode'
export type TaskStatus = 'pending' | 'in_progress' | 'blocked' | 'completed'
export type HandoffStatus = 'pending' | 'claimed' | 'completed'
export type AgentName = 'curator' | 'investigator' | 'planner' | 'verifier'
export type ServiceState = 'ok' | 'down' | 'unknown'

export interface MemoryRecord {
  id: string
  kind: MemoryKind
  title: string
  body: string
  createdAt: string
  /** ids of related records (graph edges are derived from these) */
  relatedIds: string[]
  confidence?: number
  version?: number
  status?: string
  validFrom?: string
  rationale?: string
  chosenOption?: string
  steps?: string[]
  approved?: boolean
  blockers?: string[]
  blockerDetails?: { id: string; title: string }[]
  sourceEpisodeId?: string
}

export interface Task {
  id: string
  title: string
  description?: string
  status: TaskStatus
  priority?: string
  owner?: string
  revision?: number
  projectId?: string
  /** ids of tasks this task depends on */
  dependsOn: string[]
  /** subset of dependsOn that is not yet completed */
  blockers: string[]
  blockerDetails?: { id: string; title: string }[]
}

export interface EvidenceRef {
  id: string
  kind: MemoryKind
  title: string
  excerpt?: string
  /** episode the evidence originated from, when known */
  sourceId?: string
  confidence?: number
  nodeType?: string
}

export interface AgentTrace {
  agent: AgentName
  action: string
  summary: string
  durationMs?: number
  evidenceIds?: string[]
  status?: string
  error?: string
  recordsRead?: string[]
  recordsWritten?: string[]
  runId?: string
}

export interface ChatRequest {
  message: string
  session_id?: string
  project_id: string
  tenant_id: string
  idempotency_key?: string
}

export interface ChatResponse {
  answer: string
  session_id: string
  project_id?: string
  tenant_id?: string
  evidence: EvidenceRef[]
  agent_traces: AgentTrace[]
  handoff_created: boolean
  status: string
  error?: string | null
  confidence?: number | string | null
}

export interface Run {
  id: string
  agentName?: string
  goal?: string
  sessionId: string
  query: string
  status: string
  startedAt: string
  completedAt?: string
  summary?: string
  error?: string | null
  recordsRead?: string[] | null
  recordsWritten?: string[] | null
  traces: AgentTrace[]
}

export interface Handoff {
  id: string
  fromAgent: AgentName
  toAgent: AgentName
  summary: string
  status: HandoffStatus
  taskId?: string
  createdAt: string
  claimedAt?: string
  completedAt?: string
}

export interface Project {
  id: string
  name: string
}

export interface Health {
  status: string
  falkordb: ServiceState
  ollama: ServiceState
  model?: string
  tenants?: string[]
}

export interface GraphNode {
  id: string
  label: string
  kind: MemoryKind
}
export interface GraphEdge {
  source: string
  target: string
  type: string
}
export interface GraphOverview {
  nodes: GraphNode[]
  edges: GraphEdge[]
}
export interface GraphStats {
  nodes: number
  edges: number
  byKind: Partial<Record<MemoryKind, number>>
}

export interface Settings {
  mode: 'demo' | 'api'
  baseUrl: string
  tenantId: string
  projectId: string
  reduceMotion: boolean
}

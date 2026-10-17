import type { GraphOverview } from '../../types'

export interface Placed { id: string; x: number; y: number }

/** Small deterministic spring layout (same input → same picture). */
export function layoutGraph(g: GraphOverview, w = 900, h = 560): Map<string, Placed> {
  const n = g.nodes.length
  const pos = g.nodes.map((node, i) => {
    const a = (i / Math.max(n, 1)) * Math.PI * 2
    return { id: node.id, x: w / 2 + Math.cos(a) * w * 0.34, y: h / 2 + Math.sin(a) * h * 0.34, vx: 0, vy: 0 }
  })
  const idx = new Map(pos.map((p, i) => [p.id, i]))
  for (let iter = 0; iter < 160; iter++) {
    for (let i = 0; i < n; i++)
      for (let j = i + 1; j < n; j++) {
        const dx = pos[i].x - pos[j].x, dy = pos[i].y - pos[j].y
        const d2 = Math.max(dx * dx + dy * dy, 80)
        const f = 5200 / d2, d = Math.sqrt(d2)
        pos[i].vx += (dx / d) * f; pos[i].vy += (dy / d) * f
        pos[j].vx -= (dx / d) * f; pos[j].vy -= (dy / d) * f
      }
    for (const e of g.edges) {
      const a = idx.get(e.source), b = idx.get(e.target)
      if (a === undefined || b === undefined) continue
      const dx = pos[b].x - pos[a].x, dy = pos[b].y - pos[a].y
      const d = Math.sqrt(dx * dx + dy * dy) || 1
      const f = (d - 110) * 0.02
      pos[a].vx += (dx / d) * f; pos[a].vy += (dy / d) * f
      pos[b].vx -= (dx / d) * f; pos[b].vy -= (dy / d) * f
    }
    for (const p of pos) {
      p.vx += (w / 2 - p.x) * 0.004; p.vy += (h / 2 - p.y) * 0.004
      p.x = Math.min(w - 40, Math.max(40, p.x + p.vx * 0.6)); p.y = Math.min(h - 30, Math.max(30, p.y + p.vy * 0.6))
      p.vx *= 0.5; p.vy *= 0.5
    }
  }
  return new Map(pos.map((p) => [p.id, { id: p.id, x: p.x, y: p.y }]))
}

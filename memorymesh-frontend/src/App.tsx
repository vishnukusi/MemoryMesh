import { lazy, Suspense, useEffect, type ComponentType } from 'react'
import { Link, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { Loading } from './components/StateViews'
import LandingPage from './pages/LandingPage'

const ConsoleLayout = lazy(() => import('./app/ConsoleLayout'))
const pages = {
  overview: lazy(() => import('./pages/OverviewPage')),
  chat: lazy(() => import('./features/chat/ChatPage')),
  memories: lazy(() => import('./features/memories/MemoryPage')),
  memory: lazy(() => import('./features/memories/MemoryPage')),
  graph: lazy(() => import('./features/graph/GraphPage')),
  tasks: lazy(() => import('./features/tasks/TasksPage')),
  runs: lazy(() => import('./features/runs/RunsPage')),
  handoffs: lazy(() => import('./features/handoffs/HandoffsPage')),
  health: lazy(() => import('./features/health/HealthPage')),
  settings: lazy(() => import('./pages/SettingsPage')),
}
const wrap = (C: ComponentType) => (
  <Suspense fallback={<Loading />}>
    <C />
  </Suspense>
)

// Landing anchors (#story …) keep native behaviour; other navigations start at the top.
function ScrollToTop() {
  const { pathname, hash } = useLocation()
  useEffect(() => {
    if (!hash) window.scrollTo(0, 0)
  }, [pathname, hash])
  return null
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<Suspense fallback={<Loading label="Loading console…" />}><ConsoleLayout /></Suspense>}>
          <Route index element={<Navigate to="overview" replace />} />
          {Object.entries(pages).map(([path, C]) => <Route key={path} path={path} element={wrap(C)} />)}
          <Route path="*" element={<Navigate to="overview" replace />} />
        </Route>
        <Route path="*" element={<main style={{ padding: 48 }}><h1>Page not found</h1><p><Link to="/">Back to the site</Link></p></main>} />
      </Routes>
    </>
  )
}

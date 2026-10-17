import type { ReactNode } from 'react'
import type { AsyncState } from '../lib/useAsync'

export function Loading({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      <div className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const offline = typeof navigator !== 'undefined' && navigator.onLine === false
  return (
    <div className="state error" role="alert">
      <strong>{offline ? 'You appear to be offline' : 'Something went wrong'}</strong>
      <span>{message}</span>
      {onRetry && (
        <button className="btn btn-sm" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>
}

/** Renders loading / error / empty / data states for an AsyncState. */
export function Async<T>({
  state,
  children,
  isEmpty,
  empty = 'Nothing here yet.',
}: {
  state: AsyncState<T>
  children: (data: T) => ReactNode
  isEmpty?: (data: T) => boolean
  empty?: ReactNode
}) {
  if (state.loading && state.data === undefined) return <Loading />
  if (state.error) return <ErrorState message={state.error} onRetry={state.reload} />
  if (state.data === undefined) return null
  if (isEmpty?.(state.data)) return <Empty>{empty}</Empty>
  return <>{children(state.data)}</>
}

export function StatusBadge({ status }: { status: string }) {
  return <span className={`badge ${status}`}>{status.replace('_', ' ')}</span>
}

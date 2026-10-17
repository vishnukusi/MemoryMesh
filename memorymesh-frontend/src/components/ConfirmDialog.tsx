import { useEffect, useRef, type ReactNode } from 'react'

interface Props {
  open: boolean
  title: string
  children: ReactNode
  confirmLabel: string
  onConfirm: () => void
  onCancel: () => void
}

/** Native <dialog>: focus is trapped and Escape closes it. */
export function ConfirmDialog({ open, title, children, confirmLabel, onConfirm, onCancel }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    if (open && !el.open) el.showModal()
    if (!open && el.open) el.close()
  }, [open])
  return (
    <dialog ref={ref} className="confirm" onCancel={(e) => { e.preventDefault(); onCancel() }} aria-labelledby="confirm-title">
      <h2 id="confirm-title" style={{ fontSize: '1.125rem', marginBottom: 10 }}>{title}</h2>
      <div className="muted">{children}</div>
      <div className="actions">
        <button className="btn btn-sm" onClick={onCancel}>Cancel</button>
        <button className="btn btn-sm btn-primary" onClick={onConfirm}>{confirmLabel}</button>
      </div>
    </dialog>
  )
}

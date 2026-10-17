export function LogoMark({ className = 'brand-mark' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 32 32" aria-hidden="true" fill="none" stroke="currentColor" strokeWidth="1.6">
      <path d="M16 3.5l10.5 6v13L16 28.5 5.5 22.5v-13z" stroke="#7fe3f0" />
      <path d="M16 3.5v25M5.5 9.5l21 13M26.5 9.5l-21 13" stroke="#7fe3f0" opacity=".35" />
      <circle cx="16" cy="16" r="3" fill="#7fe3f0" stroke="none" />
    </svg>
  )
}

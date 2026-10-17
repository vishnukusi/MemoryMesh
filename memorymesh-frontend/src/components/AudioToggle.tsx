import { useEffect, useRef, useState } from 'react'
import { Volume2, VolumeX } from 'lucide-react'
import { AUDIO, useProbe } from '../lib/media'

/**
 * Opt-in sound. Renders nothing unless an audio file actually exists, so there is never a dead control.
 * Never autoplays; off by default; stops when switched off or the page is hidden.
 */
export function AudioToggle() {
  const hasAmbient = useProbe(AUDIO.ambient, 'audio/') === true
  const hasNarration = useProbe(AUDIO.narration, 'audio/') === true
  const [on, setOn] = useState(false)
  const els = useRef<HTMLAudioElement[]>([])

  useEffect(() => {
    const stop = () => els.current.forEach((a) => a.pause())
    document.addEventListener('visibilitychange', stop)
    return () => {
      document.removeEventListener('visibilitychange', stop)
      stop()
    }
  }, [])

  if (!hasAmbient && !hasNarration) return null

  const toggle = () => {
    if (on) {
      els.current.forEach((a) => a.pause())
      setOn(false)
      return
    }
    els.current = [
      ...(hasAmbient ? [Object.assign(new Audio(AUDIO.ambient), { loop: true, volume: 0.35 })] : []),
      ...(hasNarration ? [new Audio(AUDIO.narration)] : []),
    ]
    els.current.forEach((a) => void a.play().catch(() => undefined))
    setOn(true)
  }

  return (
    <button className="btn btn-sm" onClick={toggle} aria-pressed={on} aria-label={on ? 'Turn sound off' : 'Turn sound on'}>
      {on ? <Volume2 size={15} aria-hidden="true" /> : <VolumeX size={15} aria-hidden="true" />}
      <span className="hide-sm">Sound {on ? 'on' : 'off'}</span>
    </button>
  )
}

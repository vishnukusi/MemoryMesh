import { useEffect, useRef, useState } from 'react'
import { Pause, Play } from 'lucide-react'
import { useSettings } from '../app/SettingsContext'
import { MEDIA, playExclusive, useProbe, type MediaSlotKey } from '../lib/media'

interface Props {
  slot: MediaSlotKey
  caption: string
  /** Scrub this (supplied) video with scroll. Progressive enhancement: falls back to normal playback. */
  scrub?: boolean
  className?: string
  /** Marks the frame for the clip-mask reveal in src/motion/scroll-scenes.ts */
  clipReveal?: boolean
  parallax?: boolean
}

/**
 * A drop-in media container. Shows, in order: the supplied video, its poster image, or a neutral panel.
 * Nothing broken is ever shown when a file is missing. Visual motion lives in src/motion/, not here.
 */
export function MediaSlot({ slot, caption, scrub = false, className = '', clipReveal = false, parallax = false }: Props) {
  const m = MEDIA[slot]
  const { reducedMotion } = useSettings()
  const figure = useRef<HTMLElement>(null)
  const video = useRef<HTMLVideoElement>(null)
  const [near, setNear] = useState(false)
  const [playing, setPlaying] = useState(false)
  const [scrubOff, setScrubOff] = useState(false)
  const hasVideo = useProbe(m.video, 'video/', near) === true
  const hasPoster = useProbe(m.poster, 'image/', near) === true
  const scrubbing = scrub && !reducedMotion && !scrubOff

  // Load nothing until the slot is close to the viewport.
  useEffect(() => {
    const el = figure.current
    if (!el) return
    const io = new IntersectionObserver(([e]) => e.isIntersecting && setNear(true), { rootMargin: '400px' })
    io.observe(el)
    return () => io.disconnect()
  }, [])

  // Decorative muted loop: plays only while mostly on screen, never with sound, never in reduced motion.
  useEffect(() => {
    const v = video.current
    if (!v || !hasVideo || scrubbing || reducedMotion) return
    const io = new IntersectionObserver(
      ([e]) => (e.isIntersecting ? void playExclusive(v) : v.pause()),
      { threshold: 0.5 },
    )
    io.observe(v)
    return () => io.disconnect()
  }, [hasVideo, scrubbing, reducedMotion])

  const toggle = () => {
    const v = video.current
    if (!v) return
    if (scrubbing) {
      setScrubOff(true)
      void playExclusive(v)
    } else if (v.paused) void playExclusive(v)
    else v.pause()
  }

  return (
    <figure ref={figure} className={`media-slot ${className}`} data-scrub={scrub ? (scrubbing ? 'on' : 'off') : undefined}>
      <div className="media-frame" style={{ aspectRatio: m.ratio }} data-clip-reveal={clipReveal || undefined}>
        <div className="media-inner" data-parallax={parallax || undefined}>
          {hasVideo ? (
            <video
              ref={video}
              muted
              loop
              playsInline
              preload="metadata"
              poster={hasPoster ? m.poster : undefined}
              aria-label={m.alt}
              onPlay={() => setPlaying(true)}
              onPause={() => setPlaying(false)}
              onLoadedMetadata={() => document.dispatchEvent(new CustomEvent('mm:media-ready'))}
            >
              <source src={m.video} type="video/mp4" />
            </video>
          ) : hasPoster ? (
            <img src={m.poster} alt={m.alt} loading="lazy" decoding="async" />
          ) : (
            <div className="media-placeholder" role="img" aria-label={`${m.alt} (media not added yet)`}>
              {/* Dev-only hint; production shows just the neutral panel. Replace: public/assets/video/*.mp4 (see MEDIA_ASSET_MAP.md) */}
              {import.meta.env.DEV && <span>{m.video.replace('/assets/', '')}</span>}
            </div>
          )}
        </div>
        {hasVideo && (
          <button className="media-btn" onClick={toggle} aria-label={scrubbing ? 'Play video instead of scrubbing with scroll' : playing ? 'Pause video' : 'Play video'}>
            {scrubbing || !playing ? <Play size={16} aria-hidden="true" /> : <Pause size={16} aria-hidden="true" />}
          </button>
        )}
      </div>
      <figcaption>{caption}</figcaption>
    </figure>
  )
}

import gsap from 'gsap'
import { ScrollTrigger } from 'gsap/ScrollTrigger'

gsap.registerPlugin(ScrollTrigger)

/**
 * All scroll choreography for the landing page lives here (see MOTION_NOTES.md).
 * It only moves REAL media (<img>/<video> wrappers supplied via public/assets) and normal DOM content:
 * reveals, clip-mask reveals, restrained parallax/scale, step highlighting and video scrubbing.
 * It never draws or generates imagery.
 *
 * Markup contract (data attributes set by the components):
 *   [data-progress]                 page scroll-progress bar
 *   [data-hero-media]               hero wrapper; its <img> gets entrance scale + parallax
 *   [data-hero-word] / [data-hero-fade]  headline words / supporting elements (entrance)
 *   [data-reveal]                   fade + rise once
 *   [data-stagger]                  children rise in sequence
 *   [data-clip-reveal]              media frame revealed through a clip-path mask while scrolling
 *   [data-parallax]                 media wrapper moved a few percent against scroll (desktop)
 *   [data-agent-step]               gets .is-active while it is near the viewport middle (desktop)
 *   [data-scrub] video              supplied video scrubbed by scroll, when data-scrub="on"
 */
export function initScrollScenes(root: HTMLElement, reduced: boolean): () => void {
  // Reduced motion: no scenes at all. CSS lays everything out statically and shows all content.
  if (reduced) return () => undefined

  const bound = new WeakSet<HTMLVideoElement>()
  const mm = gsap.matchMedia()

  const ctx = gsap.context((self) => {
    // Page progress + header state
    gsap.to('[data-progress]', {
      scaleX: 1, ease: 'none',
      scrollTrigger: { trigger: root, start: 'top top', end: 'bottom bottom', scrub: 0.2 },
    })
    ScrollTrigger.create({
      start: 40, end: 'max',
      onToggle: (self) => root.querySelector('[data-header]')?.classList.toggle('is-scrolled', self.isActive),
    })

    // Hero entrance: the real image settles in, copy follows.
    const intro = gsap.timeline({ defaults: { ease: 'power3.out' } })
    intro
      .from('[data-hero-media] img', { scale: 1.14, duration: 2.2, ease: 'power2.out' }, 0)
      .from('[data-hero-media]', { clipPath: 'inset(0 0 22% 0)', duration: 1.4 }, 0)
      .from('[data-hero-word]', { yPercent: 110, duration: 1, stagger: 0.045 }, 0.35)
      .from('[data-hero-fade]', { opacity: 0, y: 16, duration: 0.9, stagger: 0.1 }, 0.9)

    // Hero leaves: slow push-in and drift on the actual image.
    gsap.to('[data-hero-media] img', {
      scale: 1.1, yPercent: 7, ease: 'none',
      scrollTrigger: { trigger: '[data-hero]', start: 'top top', end: 'bottom top', scrub: true },
    })

    // Reveals
    gsap.utils.toArray<HTMLElement>('[data-reveal]', root).forEach((el) =>
      gsap.from(el, { opacity: 0, y: 34, duration: 0.9, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 88%', once: true } }),
    )
    gsap.utils.toArray<HTMLElement>('[data-stagger]', root).forEach((el) =>
      gsap.from(el.children, { opacity: 0, y: 28, duration: 0.8, stagger: 0.12, ease: 'power3.out', scrollTrigger: { trigger: el, start: 'top 82%', once: true } }),
    )

    // Clip-mask reveal of real media: frame opens while the media inside settles from a slight zoom.
    gsap.utils.toArray<HTMLElement>('[data-clip-reveal]', root).forEach((frame) => {
      const st = { trigger: frame, start: 'top 92%', end: 'top 28%', scrub: true }
      gsap.fromTo(frame, { clipPath: 'inset(12% 9% 12% 9% round 22px)' }, { clipPath: 'inset(0% 0% 0% 0% round 0px)', ease: 'none', scrollTrigger: st })
      const inner = frame.querySelector('.media-inner')
      if (inner) gsap.fromTo(inner, { scale: 1.18 }, { scale: 1, ease: 'none', scrollTrigger: st })
    })

    // Scrub a supplied video with scroll (progressive enhancement; only once its metadata is known).
    const bindScrubs = () =>
      // `self` (not `ctx`): this callback runs before `const ctx` is assigned.
      self.add?.(() => {
        root.querySelectorAll<HTMLVideoElement>('[data-scrub] video').forEach((v) => {
          if (bound.has(v) || !Number.isFinite(v.duration) || v.duration <= 0) return
          bound.add(v)
          const fig = v.closest<HTMLElement>('[data-scrub]')!
          const trigger = fig.closest<HTMLElement>('[data-scrub-trigger]') ?? fig
          ScrollTrigger.create({
            trigger, start: 'top 60%', end: 'bottom 40%',
            onUpdate: (self) => {
              if (fig.dataset.scrub === 'on') v.currentTime = self.progress * v.duration
            },
          })
        })
      })
    document.addEventListener('mm:media-ready', bindScrubs)
    bindScrubs()
    self.add?.(() => () => document.removeEventListener('mm:media-ready', bindScrubs))

    // Desktop only: parallax and pinned-panel step highlighting. Phones get plain flowing content.
    mm.add('(min-width: 900px)', () => {
      gsap.utils.toArray<HTMLElement>('[data-parallax]', root).forEach((el) =>
        gsap.fromTo(el, { yPercent: -5, scale: 1.1 }, {
          yPercent: 5, ease: 'none',
          scrollTrigger: { trigger: el.closest('.media-frame') ?? el, start: 'top bottom', end: 'bottom top', scrub: true },
        }),
      )
      gsap.utils.toArray<HTMLElement>('[data-agent-step]', root).forEach((step) =>
        ScrollTrigger.create({ trigger: step, start: 'top 58%', end: 'bottom 58%', toggleClass: { targets: step, className: 'is-active' } }),
      )
    })

    // Fonts change text height; re-measure once they have loaded.
    void document.fonts?.ready.then(() => ScrollTrigger.refresh())
  }, root)

  return () => {
    mm.revert()
    ctx.revert()
  }
}

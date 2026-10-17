# Motion notes

All animation is in `src/motion/scroll-scenes.ts` (GSAP + ScrollTrigger). Components only declare `data-*` attributes; they contain no animation logic. The module moves real media wrappers and ordinary DOM. It never draws or generates imagery.

Lifecycle: `LandingPage` calls `initScrollScenes(root, reducedMotion)` in an effect and returns its cleanup. Everything is created inside `gsap.context` plus `gsap.matchMedia`, and reverted on unmount or when the reduced-motion preference changes. Fonts trigger one `ScrollTrigger.refresh()` when loaded.

## Section map

| Section | Media | Trigger and behaviour | Reduced motion / fallback |
|---|---|---|---|
| Header and page | n/a | Progress bar scales with page scroll (scrub). Header gains a backdrop after 40 px | Bar hidden; header still works |
| A. Hero | `hero-reference.webp` | Intro timeline: image settles from a slight zoom while its frame opens through a clip-path, headline words rise from a mask, supporting copy fades in. On scroll the image pushes in and drifts a few percent (scrub) | No timeline; image and copy are simply shown |
| B. Fragments to memory | `memory-story.mp4` / poster | The frame opens from an inset clip-path to full while the media inside settles from 1.18× to 1× (scrubbed `top 92%` to `top 28%`). Desktop adds ±5% parallax. Text blocks rise in sequence once | Frame is shown whole; text visible |
| C. Agents | `agent-coordination.mp4` / poster | **Desktop (≥ 900 px):** the media stage is `position: sticky` (CSS, not pinning) while four steps scroll past; each step gets `.is-active` near the viewport middle and the others dim. **If the video exists** and is in scrub mode, its `currentTime` follows scroll progress through the section. A play button switches to normal playback | All four steps shown at full strength; video is not scrubbed. Phones: plain flowing layout |
| D. Evidence | `knowledge-graph.mp4` / poster | Clip-mask reveal and parallax as in B; the evidence trail rises in sequence | Static |
| E. Tasks and handoffs | `task-handoff.mp4` / poster | Same as D | Static |
| F. Architecture | none (static DOM) | Steps and lists rise in sequence once | Static |
| G. Outcomes and final | none | Staggered rise once | Static |

## Reduced motion

Honored from the OS setting (`prefers-reduced-motion`) and from the in-app switch in Settings. In that mode `initScrollScenes` returns immediately: no timelines, no scrubbing, no parallax, no sticky stage styling and no autoplay. The CSS (`.landing[data-motion='off']`) lays out a static page with every section fully visible. Verified by script: no element was left dimmed or hidden.

## Things deliberately not done

- No pinned sections and no scroll-jacking. The page scrolls natively everywhere.
- No smooth-scroll library.
- No animation of anything that imitates media (no particles, canvas, SVG or CSS shapes).

## Tuning

Edit trigger ranges (`start` / `end`) and the clip-path insets directly in `scroll-scenes.ts`. Slow clips scrub best at 8 to 20 seconds with frequent keyframes (`-g 12`), otherwise seeking will look steppy.

## Verification status

The scroll-scrubbed video path (section C) and the video play/pause control could not be exercised because no video file exists yet. They are written to degrade to a normal muted loop or a placeholder; test them once you add `agent-coordination.mp4`.

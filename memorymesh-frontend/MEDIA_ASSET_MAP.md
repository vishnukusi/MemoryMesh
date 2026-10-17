# Media asset map

Everything visual on the landing page is a file you supply. Nothing was generated for this project: no connector was used to create images, video or audio, and none of these files are fabricated. Filenames are registered in `src/lib/media.ts`.

Replace a file by dropping a new one at the same path. No code change is needed. Until a file exists the page shows a neutral panel and nothing breaks.

| Section | File | Status | Formats | Aspect | Duration | Notes |
|---|---|---|---|---|---|---|
| A. Hero | `public/assets/images/hero-reference.webp` | **Present** (your attached reference, cropped) | webp, png, jpg | 1950 × 900 (about 2.17:1) | n/a | Rendered as a plain `<img>`, eager, high priority. Replace with a clean export of the artwork; see the note below |
| B. Fragments to memory | `public/assets/video/memory-story.mp4` | **To supply** | mp4 (H.264) | 16:10 | 6–12 s, loop | Muted, inline, loops only while mostly on screen |
| B. poster | `public/assets/images/memory-story-poster.webp` | Optional | webp, jpg | 16:10 | n/a | Shown as a still when no video |
| C. Agents | `public/assets/video/agent-coordination.mp4` | **To supply** | mp4 | 4:3 | 8–20 s | Scrubbed by scroll when present (see MOTION_NOTES); a button switches to normal playback |
| C. poster | `public/assets/images/agent-workflow-poster.webp` | Optional | webp, jpg | 4:3 | n/a | |
| D. Evidence graph | `public/assets/video/knowledge-graph.mp4` | **To supply** | mp4 | 16:10 | 6–12 s, loop | A real graph render or screen capture |
| D. poster | `public/assets/images/knowledge-graph-poster.webp` | Optional | webp, jpg | 16:10 | n/a | |
| E. Tasks and handoffs | `public/assets/video/task-handoff.mp4` | **To supply** | mp4 | 16:10 | 6–12 s, loop | |
| E. poster | `public/assets/images/task-handoff-poster.webp` | Optional | webp, jpg | 16:10 | n/a | |
| Sound | `public/assets/audio/ambient-sound.mp3` | Optional | mp3 | n/a | any | Looped at low volume when the visitor presses the sound button |
| Sound | `public/assets/audio/landing-narration.mp3` | Optional | mp3 | n/a | any | If you add it, also fill `NARRATION_TRANSCRIPT` in `src/lib/media.ts` |
| Model | `public/assets/models/memory-core.glb` | Optional, unused | glb | n/a | n/a | No code loads it. Three.js is only worth adding if you supply a model |

## About the hero image

Your attachment was a **screenshot of a browser window** showing a third-party design ("ORBIS Ai Assistant by Vahe Grigoryan on Dribbble", per the caption in the screenshot). The hero is the artwork area cropped out of it (browser tabs removed). The untouched screenshot is kept at `assets-source/hero-reference-original.png`; it is not served by the site.

Two consequences to decide on before publishing:

1. **The artwork contains its own lettering** ("UNLEASH INTELLIGENCE / THROUGH INTERACTION"). That text is part of the pixels, not page text. The page's real headline sits below it so they do not collide. A clean render without lettering would look better and be fully accessible.
2. **It is someone else's design.** Use it as a development reference. Replace it with your own render, or get permission, before a public launch.

## Rules the code follows

- Posters and videos are probed with a `HEAD` request and only requested when a slot is within 400px of the viewport. A path that answers with `text/html` (SPA fallback) counts as missing.
- Only one video plays at a time. None plays with sound, and none autoplays in reduced-motion mode.
- Each slot reserves its aspect ratio up front, so late-loading media never shifts the layout.
- Recommended encodes: H.264 mp4, 1280 to 1920 px wide, 2 to 4 Mbps, `-movflags +faststart`, no audio track.

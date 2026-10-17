import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest'
import { SettingsProvider } from '../app/SettingsContext'
import { MediaSlot } from './MediaSlot'

beforeAll(() => {
  // jsdom has neither of these.
  vi.stubGlobal('IntersectionObserver', class {
    constructor(private cb: (e: { isIntersecting: boolean }[]) => void) {}
    observe() { this.cb([{ isIntersecting: true }]) } // "near the viewport" immediately, so the probe really runs
    disconnect() { /* test stub */ }
  })
  window.matchMedia = window.matchMedia ?? (((q: string) => ({ matches: false, media: q, addEventListener() { /* stub */ }, removeEventListener() { /* stub */ } })) as unknown as typeof window.matchMedia)
})
afterEach(() => vi.restoreAllMocks())

describe('MediaSlot with no supplied files', () => {
  it('renders a neutral placeholder: no <video>, no <img>', async () => {
    // A SPA host answers missing files with index.html — that must count as "absent".
    vi.stubGlobal('fetch', vi.fn(() => Promise.resolve(new Response('', { status: 200, headers: { 'content-type': 'text/html' } }))))
    const { container } = render(<SettingsProvider><MediaSlot slot="story" caption="Caption" /></SettingsProvider>)
    expect(screen.getByText('Caption')).toBeInTheDocument()
    const fetchSpy = globalThis.fetch as unknown as ReturnType<typeof vi.fn>
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled()) // probe ran (video + poster)
    await waitFor(() => expect(screen.getByRole('img', { name: /media not added yet/i })).toBeInTheDocument())
    expect(container.querySelector('video')).toBeNull()
    expect(container.querySelector('img')).toBeNull()
  })
})

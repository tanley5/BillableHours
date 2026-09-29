import { describe, it, expect, vi, afterEach } from 'vitest'
import { captureLocation } from './geo.js'

describe('captureLocation', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns coordinates when geolocation succeeds', async () => {
    vi.stubGlobal('navigator', {
      geolocation: {
        getCurrentPosition: (success) =>
          success({ coords: { latitude: 40.71, longitude: -74.0 } }),
      },
    })
    const loc = await captureLocation()
    expect(loc).toEqual({
      latitude: 40.71,
      longitude: -74.0,
      location_missing: false,
    })
  })

  it('sets location_missing when geolocation is denied or unavailable', async () => {
    vi.stubGlobal('navigator', {
      geolocation: {
        getCurrentPosition: (_success, error) => error({ code: 1, message: 'denied' }),
      },
    })
    const loc = await captureLocation()
    expect(loc).toEqual({
      latitude: null,
      longitude: null,
      location_missing: true,
    })
  })

  it('sets location_missing when geolocation API is absent', async () => {
    vi.stubGlobal('navigator', {})
    const loc = await captureLocation()
    expect(loc.location_missing).toBe(true)
  })
})

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createContractorApi } from './contractor.js'

describe('createContractorApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('scopes all requests under /api/c/{token}/', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ project: { name: 'Bathtub' } }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const api = createContractorApi('tok123')
    await api.getSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/c/tok123/',
      expect.objectContaining({ method: 'GET' }),
    )
  })

  it('posts jobs, visits, photos, and resubmits on the token namespace', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const api = createContractorApi('abc')

    await api.createJob({ label: 'Bathtub' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/c/abc/jobs/')

    await api.createVisit({ date: '2026-09-01', hours: '2', notes: '' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/c/abc/visits/')

    const form = new FormData()
    await api.uploadPhoto(3, form)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/c/abc/jobs/3/photos/')

    await api.resubmitVisit(4, { hours: '1.5' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/c/abc/visits/4/resubmit/')

    await api.resubmitJob(5, { notes: 'fixed' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/c/abc/jobs/5/resubmit/')
  })

  it('surfaces revoked-token 403 clearly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ detail: 'This link has been revoked.' }),
      }),
    )
    const api = createContractorApi('revoked')
    await expect(api.getSummary()).rejects.toThrow(/revoked/i)
  })
})

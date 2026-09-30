import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createContractorApi } from './contractor.js'

describe('createContractorApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    document.cookie = 'csrftoken=test-csrf; path=/'
  })

  it('scopes all requests under /api/contractor/assignments/{id}/', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ project: { name: 'Bathtub' } }),
    })
    vi.stubGlobal('fetch', fetchMock)

    const api = createContractorApi(12)
    await api.getSummary()

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/contractor/assignments/12/',
      expect.objectContaining({ method: 'GET', credentials: 'include' }),
    )
  })

  it('posts jobs, visits, photos, and resubmits on the assignment namespace', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 9 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const api = createContractorApi(5)

    await api.createJob({ label: 'Bathtub' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractor/assignments/5/jobs/')

    await api.createVisit({ date: '2026-09-01', hours: '2', notes: '' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractor/assignments/5/visits/')

    const form = new FormData()
    await api.uploadPhoto(3, form)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractor/assignments/5/jobs/3/photos/')

    await api.resubmitVisit(4, { hours: '1.5' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractor/assignments/5/visits/4/resubmit/')

    await api.resubmitJob(5, { notes: 'fixed' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractor/assignments/5/jobs/5/resubmit/')
  })

  it('surfaces assignment errors clearly', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 400,
        json: async () => ({ detail: 'Assignment must be accepted before creating jobs.' }),
      }),
    )
    const api = createContractorApi(1)
    await expect(api.createJob({ label: 'x' })).rejects.toThrow(/accepted/i)
  })
})

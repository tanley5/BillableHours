import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createClientApi } from './client.js'

describe('createClientApi', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    document.cookie = 'csrftoken=test-csrf; path=/'
  })

  it('logs in and fetches the current user', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ email: 'owner@example.com', role: 'client' }),
      })
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ email: 'owner@example.com', role: 'client' }),
      })
    vi.stubGlobal('fetch', fetchMock)

    const api = createClientApi()
    await api.login('owner@example.com', 'secret')
    expect(fetchMock.mock.calls[0][0]).toBe('/api/auth/login/')
    expect(fetchMock.mock.calls[0][1].credentials).toBe('include')
    expect(fetchMock.mock.calls[0][1].headers['X-CSRFToken']).toBe('test-csrf')

    await api.me()
    expect(fetchMock.mock.calls[1][0]).toBe('/api/auth/me/')
  })

  it('lists projects and loads project detail, jobs, and visits', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    })
    vi.stubGlobal('fetch', fetchMock)
    const api = createClientApi()

    await api.listProjects()
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/projects/')

    await api.getProject(3)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/projects/3/')

    await api.listJobs(3)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/projects/3/jobs/')

    await api.listVisits(3)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/projects/3/visits/')
  })

  it('manages contractors and assignments without token links', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ id: 1 }),
    })
    vi.stubGlobal('fetch', fetchMock)
    const api = createClientApi()

    await api.listContractors()
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractors/')

    await api.createContractor({ name: 'Alex', email: 'a@ex.com' })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/contractors/')

    await api.createAssignment(3, {
      contractor_id: 7,
      hourly_rate: '75.00',
    })
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/projects/3/assignments/')

    await api.cancelAssignment(9)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/assignments/9/cancel/')

    await api.approveJob(4)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/jobs/4/approve/')

    await api.disputeJob(4, 'Blurry photo')
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/jobs/4/dispute/')
    expect(JSON.parse(fetchMock.mock.calls.at(-1)[1].body)).toEqual({
      comment: 'Blurry photo',
    })

    await api.approveVisit(5)
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/visits/5/approve/')

    await api.disputeVisit(5, 'Too many hours')
    expect(fetchMock.mock.calls.at(-1)[0]).toBe('/api/visits/5/dispute/')
  })

  it('exposes the CSV export URL for a project', () => {
    const api = createClientApi()
    expect(api.exportUrl(3)).toBe('/api/projects/3/export.csv')
  })
})

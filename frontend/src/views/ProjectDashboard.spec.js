import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ProjectDashboard from '../views/ProjectDashboard.vue'

const project = {
  id: 3,
  name: 'Bathtub repair',
  scope: 'Fix tub',
  budget: '2500.00',
  totals: {
    approved_hours: '2.00',
    pending_hours: '3.00',
    approved_cost: '150.00',
    pending_cost: '225.00',
  },
  assignments: [
    {
      id: 9,
      hourly_rate: '75.00',
      status: 'invited',
      contractor: { name: 'Alex', phone: '555-0100', email: '' },
    },
  ],
}

const jobs = [
  {
    id: 1,
    label: 'Bathtub',
    status: 'complete',
    is_found_issue: false,
    photos: [
      { id: 10, kind: 'before', url: '/api/photos/10/', location_missing: false },
      { id: 11, kind: 'after', url: '/api/photos/11/', location_missing: true },
    ],
    found_issues: [
      {
        id: 2,
        label: 'Broken pipe',
        status: 'complete',
        is_found_issue: true,
        photos: [
          { id: 12, kind: 'before', url: '/api/photos/12/', location_missing: false },
          { id: 13, kind: 'after', url: '/api/photos/13/', location_missing: false },
        ],
        found_issues: [],
      },
    ],
  },
]

const visits = [
  {
    id: 20,
    date: '2026-09-01',
    hours: '2.00',
    status: 'pending',
    notes: 'demo',
    client_comment: null,
  },
]

function mountDashboard(overrides = {}) {
  return mount(ProjectDashboard, {
    props: {
      project,
      jobs,
      visits,
      onApproveJob: vi.fn().mockResolvedValue({}),
      onDisputeJob: vi.fn().mockResolvedValue({}),
      onApproveVisit: vi.fn().mockResolvedValue({}),
      onDisputeVisit: vi.fn().mockResolvedValue({}),
      onCancel: vi.fn().mockResolvedValue({}),
      onAssign: vi.fn().mockResolvedValue({
        id: 10,
        status: 'invited',
        contractor: { name: 'Blair' },
      }),
      listContractors: vi.fn().mockResolvedValue([]),
      createSubJob: vi.fn().mockResolvedValue({}),
      approveSubJob: vi.fn().mockResolvedValue({}),
      denySubJob: vi.fn().mockResolvedValue({}),
      acceptSubmission: vi.fn().mockResolvedValue({}),
      rejectSubmission: vi.fn().mockResolvedValue({}),
      loadActivity: vi.fn().mockResolvedValue([]),
      exportUrl: '/api/projects/3/export.csv',
      ...overrides,
    },
    global: {
      stubs: { DragAssignBoard: true, SubJobsPanel: true },
    },
  })
}

describe('ProjectDashboard', () => {
  it('shows totals with approved and pending hours/cost separately', () => {
    const wrapper = mountDashboard()
    expect(wrapper.text()).toContain('Bathtub repair')
    expect(wrapper.text()).toContain('2.00')
    expect(wrapper.text()).toContain('3.00')
    expect(wrapper.text()).toContain('150.00')
    expect(wrapper.text()).toContain('225.00')
  })

  it('nests found issues under the parent job and shows photo timeline flags', () => {
    const wrapper = mountDashboard()
    expect(wrapper.text()).toContain('Bathtub')
    expect(wrapper.text()).toContain('Broken pipe')
    expect(wrapper.text()).toMatch(/found issue/i)
    expect(wrapper.text()).toMatch(/no location/i)
  })

  it('approves and disputes completed jobs and pending visits', async () => {
    const onApproveJob = vi.fn().mockResolvedValue({})
    const onDisputeVisit = vi.fn().mockResolvedValue({})
    const wrapper = mountDashboard({ onApproveJob, onDisputeVisit })

    await wrapper.get('[data-test="approve-job-1"]').trigger('click')
    await flushPromises()
    expect(onApproveJob).toHaveBeenCalledWith(1)

    await wrapper.get('[data-test="dispute-visit-20"]').trigger('click')
    await wrapper.get('textarea[name="dispute-comment"]').setValue('Hours look high')
    await wrapper.get('[data-test="confirm-dispute"]').trigger('click')
    await flushPromises()
    expect(onDisputeVisit).toHaveBeenCalledWith(20, 'Hours look high')
  })

  it('supports bulk-approve of selected pending/complete items', async () => {
    const onApproveJob = vi.fn().mockResolvedValue({})
    const onApproveVisit = vi.fn().mockResolvedValue({})
    const wrapper = mountDashboard({ onApproveJob, onApproveVisit })

    await wrapper.get('input[data-test="select-job-1"]').setValue(true)
    await wrapper.get('input[data-test="select-visit-20"]').setValue(true)
    await wrapper.get('[data-test="bulk-approve"]').trigger('click')
    await flushPromises()

    expect(onApproveJob).toHaveBeenCalledWith(1)
    expect(onApproveVisit).toHaveBeenCalledWith(20)
  })

  it('cancels an invited assignment', async () => {
    const onCancel = vi.fn().mockResolvedValue({ id: 9, status: 'cancelled' })
    const wrapper = mountDashboard({ onCancel })

    await wrapper.get('[data-test="cancel-9"]').trigger('click')
    await flushPromises()
    expect(onCancel).toHaveBeenCalledWith(9)
  })

  it('links to CSV export of approved entries', () => {
    const wrapper = mountDashboard()
    const exportLink = wrapper.get('[data-test="export-csv"]')
    expect(exportLink.attributes('href')).toBe('/api/projects/3/export.csv')
  })
})

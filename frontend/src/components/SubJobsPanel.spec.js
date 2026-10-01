import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SubJobsPanel from './SubJobsPanel.vue'

function mountPanel(overrides = {}) {
  return mount(SubJobsPanel, {
    props: {
      projectId: 1,
      projectFrozen: false,
      frozenReason: '',
      subJobs: [],
      createSubJob: vi.fn(),
      approveSubJob: vi.fn(),
      denySubJob: vi.fn(),
      acceptSubmission: vi.fn(),
      rejectSubmission: vi.fn(),
      reauthorizeEscrow: vi.fn(),
      detachEscrow: vi.fn(),
      loadActivity: vi.fn().mockResolvedValue([]),
      ...overrides,
    },
  })
}

describe('SubJobsPanel polish1 payment copy', () => {
  it('explains demo authorize without a card widget', () => {
    const wrapper = mountPanel()
    const note = wrapper.get('[data-test="demo-fund-note"]')
    expect(note.text()).toMatch(/demo/i)
    expect(note.text()).toMatch(/card/i)
    expect(wrapper.get('[data-test="create-fund"]').text()).toMatch(/authorize/i)
  })

  it('labels pending approval action as authorize hold', () => {
    const wrapper = mountPanel({
      subJobs: [
        {
          id: 9,
          label: 'Fix drywall',
          status: 'pending_approval',
          amount: null,
          escrow: null,
          submissions: [],
        },
      ],
    })
    expect(wrapper.get('[data-test="approve-9"]').text()).toMatch(/authorize/i)
  })
})

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { RouterLinkStub } from '@vue/test-utils'
import ContractorHome from '../views/ContractorHome.vue'

const summary = {
  project: { name: 'Bathtub repair', scope: 'Fix tub' },
  contractor: { name: 'Alex' },
  open_jobs: [
    { id: 1, label: 'Bathtub', status: 'open', is_found_issue: false, found_issues: [] },
  ],
  recent_visits: [
    { id: 10, date: '2026-09-01', hours: '2.00', status: 'pending', notes: 'demo' },
  ],
  disputed_jobs: [
    {
      id: 2,
      label: 'Mold',
      status: 'disputed',
      client_comment: 'Need clearer after photo',
    },
  ],
  disputed_visits: [
    {
      id: 11,
      date: '2026-09-02',
      hours: '8.00',
      status: 'disputed',
      client_comment: 'Hours look high',
    },
  ],
}

describe('ContractorHome', () => {
  it('shows project name and legacy open jobs', () => {
    const wrapper = mount(ContractorHome, {
      props: { summary, assignmentId: 42 },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })

    expect(wrapper.text()).toContain('Bathtub repair')
    expect(wrapper.text()).toContain('Bathtub')
  })

  it('exposes in-route and legacy job/visit actions', () => {
    const wrapper = mount(ContractorHome, {
      props: { summary, assignmentId: 42 },
      global: { stubs: { RouterLink: RouterLinkStub } },
    })
    expect(wrapper.text()).toMatch(/on my way/i)
    expect(wrapper.text()).toMatch(/start a job/i)
    expect(wrapper.text()).toMatch(/log a visit/i)
  })
})

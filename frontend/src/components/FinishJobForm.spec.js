import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import FinishJobForm from '../components/FinishJobForm.vue'

describe('FinishJobForm', () => {
  it('shows the job label and capture-enabled after-photo input', () => {
    const wrapper = mount(FinishJobForm, {
      props: {
        job: { id: 1, label: 'Bathtub', status: 'open' },
        submitFinish: vi.fn(),
      },
    })
    expect(wrapper.text()).toContain('Bathtub')
    expect(wrapper.text()).toMatch(/location is recorded/i)
    const input = wrapper.get('input[type="file"]')
    expect(input.attributes('accept')).toContain('image/*')
    expect(input.attributes('capture')).toBeDefined()
  })

  it('requires at least one after photo', async () => {
    const submitFinish = vi.fn()
    const wrapper = mount(FinishJobForm, {
      props: {
        job: { id: 1, label: 'Bathtub', status: 'open' },
        submitFinish,
      },
    })
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(submitFinish).not.toHaveBeenCalled()
    expect(wrapper.text()).toMatch(/after photo/i)
  })
})

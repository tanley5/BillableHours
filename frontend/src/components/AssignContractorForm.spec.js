import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AssignContractorForm from '../components/AssignContractorForm.vue'

describe('AssignContractorForm', () => {
  it('assigns a contractor and emits the created assignment with link', async () => {
    const assign = vi.fn().mockResolvedValue({
      id: 1,
      link: 'http://localhost/c/tok',
      contractor: { name: 'Alex' },
    })
    const wrapper = mount(AssignContractorForm, { props: { assign } })

    await wrapper.get('input[name="name"]').setValue('Alex')
    await wrapper.get('input[name="phone"]').setValue('555-0100')
    await wrapper.get('input[name="hourly_rate"]').setValue('75')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(assign).toHaveBeenCalledWith({
      name: 'Alex',
      phone: '555-0100',
      email: '',
      hourly_rate: '75',
    })
    expect(wrapper.emitted('assigned')[0][0].link).toContain('/c/tok')
  })
})

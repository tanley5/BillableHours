import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import AssignContractorForm from '../components/AssignContractorForm.vue'

describe('AssignContractorForm', () => {
  it('assigns a pool contractor and emits the created assignment', async () => {
    const assign = vi.fn().mockResolvedValue({
      id: 1,
      status: 'invited',
      contractor: { name: 'Alex' },
    })
    const listContractors = vi.fn().mockResolvedValue([
      {
        id: 7,
        name: 'Alex',
        email: 'alex@example.com',
        connect_status: 'complete',
      },
    ])
    const wrapper = mount(AssignContractorForm, { props: { assign, listContractors } })
    await flushPromises()

    await wrapper.get('select[name="contractor_id"]').setValue('7')
    await wrapper.get('input[name="hourly_rate"]').setValue('75')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(assign).toHaveBeenCalledWith({
      contractor_id: 7,
      hourly_rate: '75',
    })
    expect(wrapper.emitted('assigned')[0][0].status).toBe('invited')
  })
})

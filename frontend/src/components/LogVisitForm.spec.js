import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LogVisitForm from '../components/LogVisitForm.vue'

describe('LogVisitForm', () => {
  it('submits date, decimal hours, and notes', async () => {
    const submitVisit = vi.fn().mockResolvedValue({ id: 1 })
    const wrapper = mount(LogVisitForm, { props: { submitVisit } })

    await wrapper.get('input[name="date"]').setValue('2026-09-01')
    await wrapper.get('input[name="hours"]').setValue('3.5')
    await wrapper.get('textarea[name="notes"]').setValue('tile work')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(submitVisit).toHaveBeenCalledWith({
      date: '2026-09-01',
      hours: '3.5',
      notes: 'tile work',
    })
  })

  it('rejects hours over 16 before calling the API', async () => {
    const submitVisit = vi.fn()
    const wrapper = mount(LogVisitForm, { props: { submitVisit } })
    await wrapper.get('input[name="date"]').setValue('2026-09-01')
    await wrapper.get('input[name="hours"]').setValue('16.01')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(submitVisit).not.toHaveBeenCalled()
    expect(wrapper.text()).toMatch(/16/i)
  })
})

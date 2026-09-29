import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ResubmitForm from '../components/ResubmitForm.vue'

describe('ResubmitForm', () => {
  it('shows the client dispute comment and resubmits a visit correction', async () => {
    const resubmit = vi.fn().mockResolvedValue({ id: 12, status: 'pending' })
    const wrapper = mount(ResubmitForm, {
      props: {
        kind: 'visit',
        item: {
          id: 11,
          date: '2026-09-02',
          hours: '8.00',
          notes: 'long day',
          client_comment: 'Hours look high',
        },
        resubmit,
      },
    })

    expect(wrapper.text()).toContain('Hours look high')
    await wrapper.get('input[name="hours"]').setValue('1.5')
    await wrapper.get('textarea[name="notes"]').setValue('corrected')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(resubmit).toHaveBeenCalledWith(
      expect.objectContaining({ hours: '1.5', notes: 'corrected' }),
    )
  })

  it('resubmits a disputed job with optional label/notes', async () => {
    const resubmit = vi.fn().mockResolvedValue({ id: 3, status: 'open' })
    const wrapper = mount(ResubmitForm, {
      props: {
        kind: 'job',
        item: {
          id: 2,
          label: 'Mold',
          notes: 'old',
          client_comment: 'Need clearer after photo',
        },
        resubmit,
      },
    })
    await wrapper.get('textarea[name="notes"]').setValue('re-shot after photos')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()
    expect(resubmit).toHaveBeenCalledWith(
      expect.objectContaining({ notes: 're-shot after photos' }),
    )
  })
})

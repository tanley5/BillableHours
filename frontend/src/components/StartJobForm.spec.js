import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import StartJobForm from '../components/StartJobForm.vue'

describe('StartJobForm', () => {
  it('requires a label and lists open jobs as found-issue parents', async () => {
    const wrapper = mount(StartJobForm, {
      props: {
        openJobs: [{ id: 1, label: 'Bathtub' }],
        submitJob: vi.fn().mockResolvedValue({ id: 99 }),
      },
    })

    expect(wrapper.text()).toMatch(/location is recorded/i)
    const parent = wrapper.get('select[name="parent"]')
    expect(parent.text()).toContain('Bathtub')

    await wrapper.get('form').trigger('submit.prevent')
    expect(wrapper.emitted('submitted')).toBeFalsy()

    await wrapper.get('input[name="label"]').setValue('Broken pipe')
    await wrapper.get('select[name="parent"]').setValue('1')
    await wrapper.get('textarea[name="notes"]').setValue('leaking joint')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.props('submitJob')).toHaveBeenCalledWith(
      expect.objectContaining({
        label: 'Broken pipe',
        parent: 1,
        notes: 'leaking joint',
      }),
    )
  })

  it('uses capture-enabled camera file input for before photos', () => {
    const wrapper = mount(StartJobForm, {
      props: { openJobs: [], submitJob: vi.fn() },
    })
    const input = wrapper.get('input[type="file"]')
    expect(input.attributes('accept')).toContain('image/*')
    expect(input.attributes('capture')).toBeDefined()
    expect(input.attributes('multiple')).toBeDefined()
  })

  it('keeps form values after a failed submit', async () => {
    const submitJob = vi.fn().mockRejectedValue(new Error('upload failed'))
    const wrapper = mount(StartJobForm, {
      props: { openJobs: [], submitJob },
    })
    await wrapper.get('input[name="label"]').setValue('Drywall crack')
    await wrapper.get('textarea[name="notes"]').setValue('keep me')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.get('input[name="label"]').element.value).toBe('Drywall crack')
    expect(wrapper.get('textarea[name="notes"]').element.value).toBe('keep me')
    expect(wrapper.text()).toMatch(/upload failed/i)
  })
})

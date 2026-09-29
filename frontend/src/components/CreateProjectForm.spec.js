import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import CreateProjectForm from '../components/CreateProjectForm.vue'

describe('CreateProjectForm', () => {
  it('creates a project with name, scope, and optional budget', async () => {
    const createProject = vi.fn().mockResolvedValue({ id: 1, name: 'Bathtub repair' })
    const wrapper = mount(CreateProjectForm, { props: { createProject } })

    await wrapper.get('input[name="name"]').setValue('Bathtub repair')
    await wrapper.get('textarea[name="scope"]').setValue('Fix tub and damage')
    await wrapper.get('input[name="budget"]').setValue('2500')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(createProject).toHaveBeenCalledWith({
      name: 'Bathtub repair',
      scope: 'Fix tub and damage',
      budget: '2500',
    })
  })
})

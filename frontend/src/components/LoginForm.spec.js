import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import LoginForm from '../components/LoginForm.vue'

describe('LoginForm', () => {
  it('submits email and password', async () => {
    const login = vi.fn().mockResolvedValue({ email: 'owner@example.com' })
    const wrapper = mount(LoginForm, { props: { login } })

    await wrapper.get('input[name="email"]').setValue('owner@example.com')
    await wrapper.get('input[name="password"]').setValue('secret')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(login).toHaveBeenCalledWith('owner@example.com', 'secret')
    expect(wrapper.emitted('success')).toBeTruthy()
  })

  it('keeps credentials visible after a failed login', async () => {
    const login = vi.fn().mockRejectedValue(new Error('Invalid email or password.'))
    const wrapper = mount(LoginForm, { props: { login } })
    await wrapper.get('input[name="email"]').setValue('owner@example.com')
    await wrapper.get('input[name="password"]').setValue('wrong')
    await wrapper.get('form').trigger('submit.prevent')
    await flushPromises()

    expect(wrapper.get('input[name="email"]').element.value).toBe('owner@example.com')
    expect(wrapper.text()).toMatch(/invalid email or password/i)
  })
})

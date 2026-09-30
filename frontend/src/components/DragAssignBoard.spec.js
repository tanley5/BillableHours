import { describe, it, expect, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import DragAssignBoard from '../components/DragAssignBoard.vue'

vi.mock('vuedraggable', () => ({
  default: {
    name: 'draggable',
    props: ['list', 'modelValue'],
    emits: ['update:modelValue'],
    template: `<div class="draggable-stub"><slot name="item" v-for="element in (list || modelValue || [])" :key="element.id" :element="element" /></div>`,
  },
}))

const contractors = [
  {
    id: 1,
    name: 'Alex Ready',
    email: 'alex@ex.com',
    connect_status: 'complete',
    accept_rate: '0.75',
    rejection_count: 1,
    assigned_to_this_project: false,
    assigned_elsewhere: true,
  },
  {
    id: 2,
    name: 'Blair Blocked',
    email: 'blair@ex.com',
    connect_status: 'pending',
    accept_rate: null,
    rejection_count: 0,
    assigned_to_this_project: false,
    assigned_elsewhere: false,
  },
]

function mountBoard(overrides = {}) {
  return mount(DragAssignBoard, {
    props: {
      projectId: 3,
      assignments: [],
      listContractors: vi.fn().mockResolvedValue(contractors),
      assign: vi.fn().mockResolvedValue({
        id: 9,
        status: 'invited',
        contractor: { id: 1, name: 'Alex Ready' },
      }),
      ...overrides,
    },
  })
}

describe('DragAssignBoard', () => {
  it('shows reliability badges and connect/elsewhere markers', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    expect(wrapper.get('[data-test="reliability-1"]').text()).toMatch(/75% accept/i)
    expect(wrapper.get('[data-test="reliability-1"]').text()).toMatch(/1 rejected/i)
    expect(wrapper.get('[data-test="pool-card-1"]').text()).toMatch(/on other project/i)
    expect(wrapper.get('[data-test="pool-card-2"]').text()).toMatch(/connect incomplete/i)
  })

  it('filters the pool by search', async () => {
    const wrapper = mountBoard()
    await flushPromises()
    await wrapper.get('[data-test="pool-search"]').setValue('blair')
    expect(wrapper.find('[data-test="pool-card-2"]').exists()).toBe(true)
    expect(wrapper.find('[data-test="pool-card-1"]').exists()).toBe(false)
  })

  it('saves pending invites and rolls back failures', async () => {
    const assign = vi
      .fn()
      .mockRejectedValueOnce(new Error('Connect incomplete'))
      .mockResolvedValueOnce({
        id: 10,
        status: 'invited',
        contractor: { id: 1, name: 'Alex Ready' },
      })
    const wrapper = mountBoard({ assign })
    await flushPromises()

    // Stage both via pending v-model path
    wrapper.vm.pending = [...contractors]
    await wrapper.vm.$nextTick()
    await wrapper.get('[data-test="save-assignments"]').trigger('click')
    await flushPromises()

    expect(assign).toHaveBeenCalled()
    expect(wrapper.get('[data-test="board-error"]').text()).toMatch(/connect incomplete/i)
    // Failed contractor remains pending; successful one removed
    expect(wrapper.vm.pending.map((c) => c.id)).toEqual([1])
  })
})

<script setup>
import { onMounted, ref } from 'vue'

const props = defineProps({
  projectId: { type: [Number, String], required: true },
  projectFrozen: { type: Boolean, default: false },
  frozenReason: { type: String, default: '' },
  subJobs: { type: Array, default: () => [] },
  createSubJob: { type: Function, required: true },
  approveSubJob: { type: Function, required: true },
  denySubJob: { type: Function, required: true },
  acceptSubmission: { type: Function, required: true },
  rejectSubmission: { type: Function, required: true },
  reauthorizeEscrow: { type: Function, required: true },
  detachEscrow: { type: Function, required: true },
  loadActivity: { type: Function, required: true },
})
const emit = defineEmits(['refresh'])

const label = ref('')
const amount = ref('')
const beforeFile = ref(null)
const error = ref('')
const message = ref('')
const busy = ref(false)
const activity = ref([])
const fundAmount = ref({})
const denyReason = ref({})
const rejectReason = ref({})

async function refreshActivity() {
  activity.value = await props.loadActivity()
}

onMounted(async () => {
  try {
    await refreshActivity()
  } catch {
    // optional panel
  }
})

async function onCreate() {
  error.value = ''
  message.value = ''
  if (props.projectFrozen) {
    error.value = 'Project is frozen. Re-authorize expired escrow first.'
    return
  }
  if (!beforeFile.value) {
    error.value = 'Before photo is required.'
    return
  }
  busy.value = true
  try {
    const form = new FormData()
    form.append('label', label.value)
    form.append('amount', amount.value)
    form.append('before_photo', beforeFile.value)
    await props.createSubJob(form)
    label.value = ''
    amount.value = ''
    beforeFile.value = null
    message.value = 'Sub-job created with escrow authorized.'
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function approve(id) {
  busy.value = true
  error.value = ''
  try {
    await props.approveSubJob(id, fundAmount.value[id])
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function deny(id) {
  busy.value = true
  error.value = ''
  try {
    await props.denySubJob(id, denyReason.value[id] || '')
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function acceptSub(id) {
  busy.value = true
  try {
    await props.acceptSubmission(id)
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function rejectSub(id) {
  busy.value = true
  try {
    await props.rejectSubmission(id, rejectReason.value[id] || '')
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function reauth(id) {
  busy.value = true
  error.value = ''
  try {
    await props.reauthorizeEscrow(id)
    message.value = 'Escrow re-authorized.'
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

async function detach(id) {
  busy.value = true
  error.value = ''
  try {
    await props.detachEscrow(id)
    message.value = 'Escrow detached.'
    emit('refresh')
    await refreshActivity()
  } catch (err) {
    error.value = err.message
  } finally {
    busy.value = false
  }
}

function canDetach(sj) {
  const e = sj.escrow
  if (!e || !['requires_capture', 'requires_confirmation'].includes(e.status)) return false
  return sj.status === 'open' && !(sj.submissions?.length)
}
</script>

<template>
  <section class="panel" data-test="subjobs-panel">
    <h2>Sub-jobs</h2>
    <p v-if="projectFrozen" class="freeze" data-test="frozen-banner">
      Project frozen{{ frozenReason ? `: ${frozenReason}` : '' }}. Re-authorize expired escrow to continue.
    </p>
    <form class="create" @submit.prevent="onCreate">
      <label>Label <input v-model="label" required data-test="sj-label" :disabled="projectFrozen" /></label>
      <label>
        Amount
        <input
          v-model="amount"
          type="number"
          min="0.01"
          step="0.01"
          required
          data-test="sj-amount"
          :disabled="projectFrozen"
        />
      </label>
      <label>
        Before photo
        <input
          type="file"
          accept="image/*"
          capture
          data-test="sj-before"
          :disabled="projectFrozen"
          @change="beforeFile = $event.target.files?.[0] || null"
        />
      </label>
      <button type="submit" :disabled="busy || projectFrozen">Create &amp; fund</button>
    </form>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="message" class="ok">{{ message }}</p>

    <ul class="list">
      <li v-for="sj in subJobs" :key="sj.id" :data-test="`subjob-${sj.id}`">
        <div class="row">
          <strong>{{ sj.label }}</strong>
          <span class="status">{{ sj.status }}</span>
          <span v-if="sj.amount" class="muted">${{ sj.amount }}</span>
          <span v-if="sj.escrow" class="escrow" :data-test="`escrow-${sj.id}`">
            escrow: {{ sj.escrow.status }}
            <span v-if="sj.escrow.platform_fee_amount" class="muted">
              · fee ${{ sj.escrow.platform_fee_amount }}
            </span>
          </span>
        </div>
        <p v-if="sj.denial_reason" class="muted">Denied: {{ sj.denial_reason }}</p>

        <div v-if="sj.status === 'pending_approval'" class="actions">
          <input
            v-model="fundAmount[sj.id]"
            type="number"
            min="0.01"
            step="0.01"
            placeholder="Amount"
            :data-test="`fund-${sj.id}`"
          />
          <button
            type="button"
            :data-test="`approve-${sj.id}`"
            :disabled="projectFrozen"
            @click="approve(sj.id)"
          >
            Approve &amp; fund
          </button>
          <input v-model="denyReason[sj.id]" placeholder="Deny reason" :data-test="`deny-reason-${sj.id}`" />
          <button
            type="button"
            class="danger"
            :data-test="`deny-${sj.id}`"
            :disabled="projectFrozen"
            @click="deny(sj.id)"
          >
            Deny
          </button>
        </div>

        <div v-if="sj.escrow?.status === 'expired'" class="actions">
          <button type="button" :data-test="`reauth-${sj.id}`" @click="reauth(sj.id)">
            Re-authorize escrow
          </button>
        </div>
        <div v-if="canDetach(sj)" class="actions">
          <button type="button" class="danger" :data-test="`detach-${sj.id}`" @click="detach(sj.id)">
            Detach escrow
          </button>
        </div>

        <ul v-if="sj.submissions?.length" class="subs">
          <li v-for="sub in sj.submissions" :key="sub.id">
            Submission {{ sub.id }} · {{ sub.hours }}h · {{ sub.review_status }}
            <span v-if="sub.review_reason" class="muted"> — {{ sub.review_reason }}</span>
            <div v-if="sub.review_status === 'pending'" class="actions">
              <button
                type="button"
                :data-test="`accept-sub-${sub.id}`"
                :disabled="projectFrozen"
                @click="acceptSub(sub.id)"
              >
                Accept
              </button>
              <input v-model="rejectReason[sub.id]" placeholder="Reject reason" />
              <button
                type="button"
                class="danger"
                :data-test="`reject-sub-${sub.id}`"
                :disabled="projectFrozen"
                @click="rejectSub(sub.id)"
              >
                Reject
              </button>
            </div>
          </li>
        </ul>
      </li>
      <li v-if="!subJobs.length" class="empty">No sub-jobs yet.</li>
    </ul>

    <h3>Activity</h3>
    <ol class="activity">
      <li v-for="(e, i) in activity" :key="i">
        <time>{{ e.timestamp }}</time>
        <strong>{{ e.type }}</strong>
        <span class="muted"> · {{ e.actor }}</span>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.panel { display: grid; gap: 1rem; }
.create { display: grid; gap: 0.5rem; max-width: 24rem; }
label { display: grid; gap: 0.25rem; font-weight: 600; }
input, button { font: inherit; padding: 0.5rem 0.65rem; border-radius: 0.35rem; border: 1px solid #c5d0c4; }
button { background: #1f3d2a; color: #f4f7f2; border: none; font-weight: 700; }
button.danger { background: #6b4a3a; }
.list, .subs, .activity { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.75rem; }
.row { display: flex; gap: 0.75rem; align-items: baseline; flex-wrap: wrap; }
.status { text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.04em; color: #3d5a45; }
.escrow { font-size: 0.85rem; color: #2a4a35; }
.actions { display: flex; flex-wrap: wrap; gap: 0.4rem; margin-top: 0.4rem; }
.muted, .empty { color: #5c6b5a; }
.error { color: #8a2f1f; }
.ok { color: #1f3d2a; }
.freeze { background: #f3e6df; color: #6b4a3a; padding: 0.75rem; border-radius: 0.35rem; }
.activity time { display: block; font-size: 0.75rem; color: #5c6b5a; }
</style>

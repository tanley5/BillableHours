<script setup>
defineProps({
  summary: { type: Object, required: true },
  assignmentId: { type: [String, Number], required: true },
})
</script>

<template>
  <section class="home">
    <header>
      <p class="eyebrow">{{ summary.contractor?.name }}</p>
      <h1>{{ summary.project.name }}</h1>
      <p class="scope">{{ summary.project.scope }}</p>
    </header>

    <nav class="actions">
      <RouterLink class="btn" :to="`/contractor/assignments/${assignmentId}/jobs/new`">
        Start a job
      </RouterLink>
      <RouterLink class="btn secondary" :to="`/contractor/assignments/${assignmentId}/visits/new`">
        Log a visit
      </RouterLink>
    </nav>

    <section>
      <h2>Open jobs</h2>
      <ul v-if="summary.open_jobs?.length" class="list">
        <li v-for="job in summary.open_jobs" :key="job.id">
          <RouterLink :to="`/contractor/assignments/${assignmentId}/jobs/${job.id}/finish`">
            {{ job.label }}
          </RouterLink>
          <span v-if="job.is_found_issue" class="badge">Found issue</span>
        </li>
      </ul>
      <p v-else class="empty">No open jobs.</p>
    </section>

    <section>
      <h2>Recent visits</h2>
      <ul v-if="summary.recent_visits?.length" class="list">
        <li v-for="visit in summary.recent_visits" :key="visit.id">
          <strong>{{ visit.date }}</strong> — {{ visit.hours }}h
          <span class="muted">({{ visit.status }})</span>
        </li>
      </ul>
      <p v-else class="empty">No visits yet.</p>
    </section>

    <section v-if="summary.disputed_jobs?.length || summary.disputed_visits?.length">
      <h2>Needs your response</h2>
      <ul class="list disputes">
        <li v-for="job in summary.disputed_jobs || []" :key="`j-${job.id}`">
          <RouterLink :to="`/contractor/assignments/${assignmentId}/jobs/${job.id}/resubmit`">
            {{ job.label }}
          </RouterLink>
          <p class="comment">{{ job.client_comment }}</p>
        </li>
        <li v-for="visit in summary.disputed_visits || []" :key="`v-${visit.id}`">
          <RouterLink :to="`/contractor/assignments/${assignmentId}/visits/${visit.id}/resubmit`">
            Visit {{ visit.date }} ({{ visit.hours }}h)
          </RouterLink>
          <p class="comment">{{ visit.client_comment }}</p>
        </li>
      </ul>
    </section>
  </section>
</template>

<style scoped>
.home { display: grid; gap: 1.5rem; }
.eyebrow { margin: 0; text-transform: uppercase; letter-spacing: 0.06em; font-size: 0.75rem; color: #5c6b5a; }
h1 { margin: 0.25rem 0; font-size: 1.75rem; }
.scope { margin: 0; color: #445044; }
.actions { display: flex; gap: 0.75rem; flex-wrap: wrap; }
.btn {
  display: inline-block;
  background: #1f3d2a;
  color: #f4f7f2;
  text-decoration: none;
  padding: 0.75rem 1rem;
  border-radius: 0.4rem;
  font-weight: 600;
}
.btn.secondary { background: #3d5a45; }
h2 { margin: 0 0 0.5rem; font-size: 1.1rem; }
.list { list-style: none; padding: 0; margin: 0; display: grid; gap: 0.65rem; }
.list a { color: #1f3d2a; font-weight: 600; }
.badge {
  margin-left: 0.5rem;
  font-size: 0.75rem;
  background: #e8efe6;
  padding: 0.15rem 0.4rem;
  border-radius: 0.25rem;
}
.muted, .empty { color: #5c6b5a; }
.comment { margin: 0.25rem 0 0; color: #6b4a3a; }
</style>

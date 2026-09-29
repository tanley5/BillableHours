import { createRouter, createWebHistory } from 'vue-router'
import ContractorPage from './views/ContractorPage.vue'
import StartJobPage from './views/StartJobPage.vue'
import FinishJobPage from './views/FinishJobPage.vue'
import LogVisitPage from './views/LogVisitPage.vue'
import ResubmitPage from './views/ResubmitPage.vue'
import LandingPage from './views/LandingPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingPage },
    { path: '/c/:token', name: 'contractor-home', component: ContractorPage },
    { path: '/c/:token/jobs/new', name: 'start-job', component: StartJobPage },
    { path: '/c/:token/jobs/:jobId/finish', name: 'finish-job', component: FinishJobPage },
    { path: '/c/:token/jobs/:jobId/resubmit', name: 'resubmit-job', component: ResubmitPage, props: { kind: 'job' } },
    { path: '/c/:token/visits/new', name: 'log-visit', component: LogVisitPage },
    { path: '/c/:token/visits/:visitId/resubmit', name: 'resubmit-visit', component: ResubmitPage, props: { kind: 'visit' } },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

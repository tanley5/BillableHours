import { createRouter, createWebHistory } from 'vue-router'
import ContractorPage from './views/ContractorPage.vue'
import ContractorAssignmentsPage from './views/ContractorAssignmentsPage.vue'
import ContractorConnectPage from './views/ContractorConnectPage.vue'
import StartJobPage from './views/StartJobPage.vue'
import FinishJobPage from './views/FinishJobPage.vue'
import LogVisitPage from './views/LogVisitPage.vue'
import ResubmitPage from './views/ResubmitPage.vue'
import LandingPage from './views/LandingPage.vue'
import LoginPage from './views/LoginPage.vue'
import SetPasswordPage from './views/SetPasswordPage.vue'
import ProjectListPage from './views/ProjectListPage.vue'
import ProjectDetailPage from './views/ProjectDetailPage.vue'
import ContractorsPage from './views/ContractorsPage.vue'

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'landing', component: LandingPage },
    { path: '/app/login', name: 'login', component: LoginPage },
    { path: '/auth/set-password', name: 'set-password', component: SetPasswordPage },
    { path: '/app/projects', name: 'projects', component: ProjectListPage },
    { path: '/app/projects/:projectId', name: 'project-detail', component: ProjectDetailPage },
    { path: '/app/contractors', name: 'contractors', component: ContractorsPage },
    { path: '/contractor', name: 'contractor-home', component: ContractorAssignmentsPage },
    { path: '/contractor/connect', name: 'contractor-connect', component: ContractorConnectPage },
    { path: '/contractor/connect/return', name: 'contractor-connect-return', component: ContractorConnectPage },
    { path: '/contractor/connect/refresh', name: 'contractor-connect-refresh', component: ContractorConnectPage },
    { path: '/contractor/assignments/:assignmentId', name: 'contractor-assignment', component: ContractorPage },
    {
      path: '/contractor/assignments/:assignmentId/jobs/new',
      name: 'start-job',
      component: StartJobPage,
    },
    {
      path: '/contractor/assignments/:assignmentId/jobs/:jobId/finish',
      name: 'finish-job',
      component: FinishJobPage,
    },
    {
      path: '/contractor/assignments/:assignmentId/jobs/:jobId/resubmit',
      name: 'resubmit-job',
      component: ResubmitPage,
      props: { kind: 'job' },
    },
    {
      path: '/contractor/assignments/:assignmentId/visits/new',
      name: 'log-visit',
      component: LogVisitPage,
    },
    {
      path: '/contractor/assignments/:assignmentId/visits/:visitId/resubmit',
      name: 'resubmit-visit',
      component: ResubmitPage,
      props: { kind: 'visit' },
    },
  ],
  scrollBehavior() {
    return { top: 0 }
  },
})

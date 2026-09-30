function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseError(response) {
  let detail = `Request failed (${response.status})`
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') detail = data.detail
    else if (Array.isArray(data.non_field_errors)) detail = data.non_field_errors.join(' ')
    else if (data.detail) detail = JSON.stringify(data.detail)
    else detail = JSON.stringify(data)
  } catch {
    // keep default
  }
  const err = new Error(detail)
  err.status = response.status
  return err
}

async function request(path, { method = 'GET', body, json = true } = {}) {
  const headers = {}
  if (json && body !== undefined) {
    headers['Content-Type'] = 'application/json'
  }
  const csrf = getCookie('csrftoken')
  if (csrf && method !== 'GET' && method !== 'HEAD') {
    headers['X-CSRFToken'] = csrf
  }

  let payload = body
  if (body !== undefined && json) {
    payload = JSON.stringify(body)
  }

  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers,
    body: payload === undefined ? undefined : payload,
  })

  if (!response.ok) {
    throw await parseError(response)
  }
  if (response.status === 204) return null
  const contentType = response.headers?.get?.('content-type') || ''
  if (!contentType || contentType.includes('application/json')) {
    return response.json()
  }
  return response
}

export function createClientApi() {
  return {
    async ensureCsrf() {
      if (getCookie('csrftoken')) return
      await fetch('/api/auth/csrf/', { credentials: 'include' })
    },
    async login(email, password) {
      await this.ensureCsrf()
      return request('/api/auth/login/', {
        method: 'POST',
        body: { email, password },
      })
    },
    logout() {
      return request('/api/auth/logout/', { method: 'POST', body: {} })
    },
    me() {
      return request('/api/auth/me/')
    },
    setPassword(token, password) {
      return request('/api/auth/set-password/', {
        method: 'POST',
        body: { token, password },
      })
    },
    listProjects() {
      return request('/api/projects/')
    },
    reportDashboard() {
      return request('/api/reports/dashboard/')
    },
    createProject(payload) {
      return request('/api/projects/', { method: 'POST', body: payload })
    },
    getProject(id) {
      return request(`/api/projects/${id}/`)
    },
    listJobs(projectId) {
      return request(`/api/projects/${projectId}/jobs/`)
    },
    listVisits(projectId) {
      return request(`/api/projects/${projectId}/visits/`)
    },
    listContractors(projectId) {
      const path =
        projectId != null ? `/api/contractors/?project_id=${projectId}` : '/api/contractors/'
      return request(path)
    },
    listSubJobs(projectId) {
      return request(`/api/projects/${projectId}/sub-jobs/`)
    },
    createSubJob(projectId, formData) {
      return request(`/api/projects/${projectId}/sub-jobs/`, {
        method: 'POST',
        body: formData,
        json: false,
      })
    },
    approveSubJob(id, amount) {
      return request(`/api/sub-jobs/${id}/approve/`, { method: 'POST', body: { amount } })
    },
    denySubJob(id, reason) {
      return request(`/api/sub-jobs/${id}/deny/`, { method: 'POST', body: { reason } })
    },
    reauthorizeEscrow(id) {
      return request(`/api/sub-jobs/${id}/escrow/reauthorize/`, { method: 'POST', body: {} })
    },
    detachEscrow(id) {
      return request(`/api/sub-jobs/${id}/escrow/detach/`, { method: 'POST', body: {} })
    },
    acceptSubmission(id) {
      return request(`/api/submissions/${id}/accept/`, { method: 'POST', body: {} })
    },
    rejectSubmission(id, reason) {
      return request(`/api/submissions/${id}/reject/`, { method: 'POST', body: { reason } })
    },
    projectActivity(projectId) {
      return request(`/api/projects/${projectId}/activity/`)
    },
    createContractor(payload) {
      return request('/api/contractors/', { method: 'POST', body: payload })
    },
    resendContractorInvite(id) {
      return request(`/api/contractors/${id}/resend-invite/`, { method: 'POST', body: {} })
    },
    createAssignment(projectId, payload) {
      return request(`/api/projects/${projectId}/assignments/`, {
        method: 'POST',
        body: payload,
      })
    },
    cancelAssignment(id) {
      return request(`/api/assignments/${id}/cancel/`, { method: 'POST', body: {} })
    },
    approveJob(id) {
      return request(`/api/jobs/${id}/approve/`, { method: 'POST', body: {} })
    },
    disputeJob(id, comment) {
      return request(`/api/jobs/${id}/dispute/`, {
        method: 'POST',
        body: { comment },
      })
    },
    approveVisit(id) {
      return request(`/api/visits/${id}/approve/`, { method: 'POST', body: {} })
    },
    disputeVisit(id, comment) {
      return request(`/api/visits/${id}/dispute/`, {
        method: 'POST',
        body: { comment },
      })
    },
    exportUrl(projectId) {
      return `/api/projects/${projectId}/export.csv`
    },
  }
}

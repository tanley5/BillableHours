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

  const response = await fetch(path, {
    method,
    credentials: 'include',
    headers,
    body: body === undefined ? undefined : json ? JSON.stringify(body) : body,
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
    listProjects() {
      return request('/api/projects/')
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
    createAssignment(projectId, payload) {
      return request(`/api/projects/${projectId}/assignments/`, {
        method: 'POST',
        body: payload,
      })
    },
    revokeAssignment(id) {
      return request(`/api/assignments/${id}/revoke/`, { method: 'POST', body: {} })
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

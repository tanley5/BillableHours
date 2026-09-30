function getCookie(name) {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`))
  return match ? decodeURIComponent(match[1]) : ''
}

async function parseError(response) {
  let detail = `Request failed (${response.status})`
  try {
    const data = await response.json()
    if (typeof data.detail === 'string') detail = data.detail
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
  return response.json()
}

export function createContractorApi(assignmentId) {
  const base = `/api/contractor/assignments/${assignmentId}`

  return {
    async ensureCsrf() {
      if (getCookie('csrftoken')) return
      await fetch('/api/auth/csrf/', { credentials: 'include' })
    },
    listAssignments() {
      return request('/api/contractor/assignments/')
    },
    me() {
      return request('/api/contractor/me/')
    },
    getSummary() {
      return request(`${base}/`)
    },
    accept() {
      return request(`${base}/accept/`, { method: 'POST', body: {} })
    },
    reject() {
      return request(`${base}/reject/`, { method: 'POST', body: {} })
    },
    confirmInRoute() {
      return request(`${base}/in-route/`, { method: 'POST', body: {} })
    },
    listSubJobs() {
      return request(`${base}/sub-jobs/`)
    },
    createSubJob(formData) {
      return request(`${base}/sub-jobs/`, { method: 'POST', body: formData, json: false })
    },
    createSubmission(subJobId, formData) {
      return request(`${base}/sub-jobs/${subJobId}/submissions/`, {
        method: 'POST',
        body: formData,
        json: false,
      })
    },
    startConnect() {
      return request('/api/contractor/connect/onboard/', { method: 'POST', body: {} })
    },
    createJob(payload) {
      return request(`${base}/jobs/`, { method: 'POST', body: payload })
    },
    updateJob(id, payload) {
      return request(`${base}/jobs/${id}/`, { method: 'PATCH', body: payload })
    },
    uploadPhoto(jobId, formData) {
      return request(`${base}/jobs/${jobId}/photos/`, {
        method: 'POST',
        body: formData,
        json: false,
      })
    },
    createVisit(payload) {
      return request(`${base}/visits/`, { method: 'POST', body: payload })
    },
    resubmitVisit(id, payload) {
      return request(`${base}/visits/${id}/resubmit/`, { method: 'POST', body: payload })
    },
    resubmitJob(id, payload) {
      return request(`${base}/jobs/${id}/resubmit/`, { method: 'POST', body: payload })
    },
  }
}

/** Session helpers shared with login (no assignment required). */
export function createContractorSessionApi() {
  return {
    async ensureCsrf() {
      if (getCookie('csrftoken')) return
      await fetch('/api/auth/csrf/', { credentials: 'include' })
    },
    async login(email, password) {
      await this.ensureCsrf()
      return request('/api/auth/login/', { method: 'POST', body: { email, password } })
    },
    logout() {
      return request('/api/auth/logout/', { method: 'POST', body: {} })
    },
    me() {
      return request('/api/contractor/me/')
    },
    listAssignments() {
      return request('/api/contractor/assignments/')
    },
    startConnect() {
      return request('/api/contractor/connect/onboard/', { method: 'POST', body: {} })
    },
  }
}

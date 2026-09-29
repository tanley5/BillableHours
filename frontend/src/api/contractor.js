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

async function request(path, options = {}) {
  const response = await fetch(path, options)
  if (!response.ok) {
    throw await parseError(response)
  }
  if (response.status === 204) return null
  return response.json()
}

export function createContractorApi(token) {
  const base = `/api/c/${token}`

  return {
    getSummary() {
      return request(`${base}/`, { method: 'GET' })
    },
    createJob(payload) {
      return request(`${base}/jobs/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },
    updateJob(id, payload) {
      return request(`${base}/jobs/${id}/`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },
    uploadPhoto(jobId, formData) {
      return request(`${base}/jobs/${jobId}/photos/`, {
        method: 'POST',
        body: formData,
      })
    },
    createVisit(payload) {
      return request(`${base}/visits/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },
    resubmitVisit(id, payload) {
      return request(`${base}/visits/${id}/resubmit/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },
    resubmitJob(id, payload) {
      return request(`${base}/jobs/${id}/resubmit/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
    },
  }
}

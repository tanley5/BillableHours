function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

export async function uploadWithRetry(uploadFn, { retries = 3, delayMs = 400 } = {}) {
  let lastError
  for (let attempt = 1; attempt <= retries; attempt += 1) {
    try {
      return await uploadFn()
    } catch (err) {
      lastError = err
      if (attempt < retries) {
        await wait(delayMs * attempt)
      }
    }
  }
  throw lastError
}

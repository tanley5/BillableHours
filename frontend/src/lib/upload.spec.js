import { describe, it, expect, vi } from 'vitest'
import { uploadWithRetry } from './upload.js'

describe('uploadWithRetry', () => {
  it('retries failed uploads and eventually succeeds', async () => {
    const upload = vi
      .fn()
      .mockRejectedValueOnce(new Error('network'))
      .mockRejectedValueOnce(new Error('network'))
      .mockResolvedValueOnce({ id: 1 })

    const result = await uploadWithRetry(upload, { retries: 3, delayMs: 1 })
    expect(result).toEqual({ id: 1 })
    expect(upload).toHaveBeenCalledTimes(3)
  })

  it('throws after exhausting retries without clearing caller state responsibility', async () => {
    const upload = vi.fn().mockRejectedValue(new Error('down'))
    await expect(uploadWithRetry(upload, { retries: 2, delayMs: 1 })).rejects.toThrow(/down/)
    expect(upload).toHaveBeenCalledTimes(2)
  })
})

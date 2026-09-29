import { describe, it, expect, vi, beforeEach } from 'vitest'
import { compressImage, enforcePhotoLimits, MAX_PHOTOS_PER_KIND, MAX_PHOTO_BYTES } from './photos.js'

function makeFile(name, sizeBytes) {
  const buf = new Uint8Array(sizeBytes)
  return new File([buf], name, { type: 'image/jpeg' })
}

describe('compressImage', () => {
  beforeEach(() => {
    class FakeImage {
      constructor() {
        this.width = 4000
        this.height = 3000
        this.onload = null
        this.onerror = null
      }
      set src(_v) {
        queueMicrotask(() => this.onload && this.onload())
      }
    }
    vi.stubGlobal('Image', FakeImage)
    vi.stubGlobal('URL', {
      createObjectURL: () => 'blob:fake',
      revokeObjectURL: () => {},
    })

    const ctx = {
      drawImage: vi.fn(),
    }
    HTMLCanvasElement.prototype.getContext = vi.fn(() => ctx)
    HTMLCanvasElement.prototype.toBlob = function (cb, type, _quality) {
      cb(new Blob([new Uint8Array(1200)], { type: type || 'image/jpeg' }))
    }
  })

  it('resizes oversized images and returns a jpeg blob under the size budget', async () => {
    const file = makeFile('big.jpg', 2_000_000)
    const result = await compressImage(file, { maxDimension: 1920, quality: 0.85 })
    expect(result.type).toBe('image/jpeg')
    expect(result.size).toBeLessThan(file.size)
  })
})

describe('enforcePhotoLimits', () => {
  it('rejects more than MAX_PHOTOS_PER_KIND photos', () => {
    const files = Array.from({ length: MAX_PHOTOS_PER_KIND + 1 }, (_, i) =>
      makeFile(`p${i}.jpg`, 1000),
    )
    expect(() => enforcePhotoLimits(files)).toThrow(/at most/i)
  })

  it('rejects an individual file over MAX_PHOTO_BYTES after compression budget', () => {
    const files = [makeFile('huge.jpg', MAX_PHOTO_BYTES + 1)]
    expect(() => enforcePhotoLimits(files, { alreadyCompressed: true })).toThrow(/too large/i)
  })

  it('allows up to the max count under the size cap', () => {
    const files = Array.from({ length: MAX_PHOTOS_PER_KIND }, (_, i) =>
      makeFile(`p${i}.jpg`, 1000),
    )
    expect(() => enforcePhotoLimits(files)).not.toThrow()
  })
})

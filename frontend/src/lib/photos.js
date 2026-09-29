export const MAX_PHOTOS_PER_KIND = 10
export const MAX_PHOTO_BYTES = 5 * 1024 * 1024

export function enforcePhotoLimits(files, { alreadyCompressed = false } = {}) {
  const list = Array.from(files || [])
  if (list.length > MAX_PHOTOS_PER_KIND) {
    throw new Error(`At most ${MAX_PHOTOS_PER_KIND} photos allowed.`)
  }
  if (alreadyCompressed) {
    for (const file of list) {
      if (file.size > MAX_PHOTO_BYTES) {
        throw new Error('Photo is too large.')
      }
    }
  }
  return list
}

export async function compressImage(file, { maxDimension = 1920, quality = 0.85 } = {}) {
  const bitmapUrl = URL.createObjectURL(file)
  try {
    const img = await loadImage(bitmapUrl)
    const scale = Math.min(1, maxDimension / Math.max(img.width, img.height))
    const width = Math.max(1, Math.round(img.width * scale))
    const height = Math.max(1, Math.round(img.height * scale))

    const canvas = document.createElement('canvas')
    canvas.width = width
    canvas.height = height
    const ctx = canvas.getContext('2d')
    ctx.drawImage(img, 0, 0, width, height)

    const blob = await new Promise((resolve, reject) => {
      canvas.toBlob(
        (b) => (b ? resolve(b) : reject(new Error('Image compression failed.'))),
        'image/jpeg',
        quality,
      )
    })
    return blob
  } finally {
    URL.revokeObjectURL(bitmapUrl)
  }
}

function loadImage(src) {
  return new Promise((resolve, reject) => {
    const img = new Image()
    img.onload = () => resolve(img)
    img.onerror = () => reject(new Error('Could not read image.'))
    img.src = src
  })
}

export async function preparePhotos(fileList) {
  const files = enforcePhotoLimits(fileList)
  const prepared = []
  for (const file of files) {
    const blob = await compressImage(file)
    if (blob.size > MAX_PHOTO_BYTES) {
      throw new Error('Photo is too large after compression.')
    }
    const name = (file.name || 'photo').replace(/\.[^.]+$/, '') + '.jpg'
    prepared.push(new File([blob], name, { type: 'image/jpeg', lastModified: Date.now() }))
  }
  return prepared
}

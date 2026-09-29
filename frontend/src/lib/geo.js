export function captureLocation({ timeoutMs = 8000 } = {}) {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve({ latitude: null, longitude: null, location_missing: true })
      return
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        resolve({
          latitude: pos.coords.latitude,
          longitude: pos.coords.longitude,
          location_missing: false,
        })
      },
      () => {
        resolve({ latitude: null, longitude: null, location_missing: true })
      },
      { enableHighAccuracy: false, timeout: timeoutMs, maximumAge: 60_000 },
    )
  })
}

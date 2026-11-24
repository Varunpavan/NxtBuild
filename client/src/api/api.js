import axios from 'axios'

let baseURL = import.meta.env.VITE_API_URL

if (!baseURL) {
  if (typeof window !== 'undefined' && window.location.hostname.includes('vercel.app')) {
    baseURL = 'https://nxtbuild-gateway.onrender.com/api'
  } else if (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
    baseURL = `http://${window.location.hostname}:5050/api`
  } else {
    baseURL = 'http://localhost:5050/api'
  }
}

let api = axios.create({
  baseURL,
  timeout: 90000,  // 90s — matches Gateway's retry window for Render cold-starts
})

// Transparent retry interceptor for Render free-tier cold-starts.
// When the Gateway exhausts its own retries and returns 503 "waking up",
// the client waits 5 seconds and silently retries the original request once.
// The user stays on "Please wait..." and logs in automatically — no error shown.
const WAKEUP_PHRASE = 'waking up'
const MAX_CLIENT_RETRIES = 2
const CLIENT_RETRY_DELAY_MS = 5000

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

api.interceptors.response.use(
  response => response,
  async error => {
    const config = error.config
    if (!config) return Promise.reject(error)

    const status = error.response?.status
    const message = error.response?.data?.message || ''
    const isWakingUp = status === 503 && message.toLowerCase().includes(WAKEUP_PHRASE)

    config._retryCount = config._retryCount || 0

    if (isWakingUp && config._retryCount < MAX_CLIENT_RETRIES) {
      config._retryCount += 1
      await sleep(CLIENT_RETRY_DELAY_MS)
      return api(config)
    }

    return Promise.reject(error)
  }
)

export default api

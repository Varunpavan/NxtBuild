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
})

export default api

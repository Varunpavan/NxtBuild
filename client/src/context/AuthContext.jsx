import { createContext, useState, useEffect } from 'react'
import Cookies from 'js-cookie'
import api from '../api/api.js'

export const AuthContext = createContext()

function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  // check if a saved token exists on mount
  useEffect(() => {
    // Silently pre-warm backend microservices on Render in background
    api.get('/health').catch(() => {})

    async function loadUser() {
      let token = Cookies.get('nxtbuild_token')

      if (!token) {
        setLoading(false)
        return
      }

      api.defaults.headers.common.Authorization = `Bearer ${token}`

      try {
        let response = await api.get('/auth/me')
        setUser(response.data.user)
      } catch (err) {
        console.log(err)
        if (err.response && err.response.status === 401) {
          Cookies.remove('nxtbuild_token')
          delete api.defaults.headers.common.Authorization
        }
      } finally {
        setLoading(false)
      }
    }

    loadUser()
  }, [])

  function saveSession(token, userData) {
    Cookies.set('nxtbuild_token', token, { expires: 7 })
    api.defaults.headers.common.Authorization = `Bearer ${token}`
    setUser(userData)
  }

  async function signup(name, email, password) {
    let response = await api.post('/auth/signup', { name, email, password })
    saveSession(response.data.token, response.data.user)
  }

  async function login(email, password) {
    let response = await api.post('/auth/login', { email, password })
    saveSession(response.data.token, response.data.user)
  }

  function logout() {
    Cookies.remove('nxtbuild_token')
    delete api.defaults.headers.common.Authorization
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, signup, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider

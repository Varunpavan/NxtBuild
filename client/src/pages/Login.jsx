import { useState, useContext } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthContext } from '../context/AuthContext.jsx'
import api from '../api/api.js'
import Logo from '../components/Logo.jsx'
import '../styles/login.css'

function Login() {
  const { signup, login } = useContext(AuthContext)
  const navigate = useNavigate()
  const [isSignup, setIsSignup] = useState(false)
  const [form, setForm] = useState({ name: '', email: '', password: '' })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  function handleChange(event) {
    setForm({ ...form, [event.target.name]: event.target.value })
    setError('')
  }

  function toggleMode() {
    setIsSignup(!isSignup)
    setError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setLoading(true)
    setError('')

    try {
      if (isSignup) {
        await signup(form.name, form.email, form.password)
      } else {
        await login(form.email, form.password)
      }

      let pendingPrompt = sessionStorage.getItem('pendingPrompt')

      if (pendingPrompt) {
        sessionStorage.removeItem('pendingPrompt')
        let response = await api.post('/projects', {})
        navigate(`/builder/${response.data.project._id}`, { state: { prompt: pendingPrompt } })
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      console.log(err)
      if (err.response && err.response.data && err.response.data.message) {
        setError(err.response.data.message)
      } else if (err.response && err.response.status === 429) {
        setError('Too many requests. Please wait a minute and try again.')
      } else {
        setError('Could not reach the server. Check that it is running and try again.')
      }
      setLoading(false)
    }
  }

  return (
    <div className="login-page">
      <aside className="login-side">
        <Logo light />
        <div className="login-side-body">
          <h2 className="login-side-title">Your next website starts as a sentence.</h2>
          <p className="login-side-text">
            Log in to save your projects, pick up a chat where you left off, and download every page you build.
          </p>
        </div>
        <div className="login-sheets" aria-hidden="true">
          <div className="login-sheet login-sheet-back">
            <span className="sheet-bar"></span>
            <span className="sheet-bar sheet-bar-short"></span>
            <span className="sheet-bar"></span>
          </div>
          <div className="login-sheet login-sheet-front">
            <span className="sheet-nav"></span>
            <span className="sheet-hero">
              <i></i>
            </span>
            <span className="sheet-tiles">
              <i></i>
              <i></i>
              <i></i>
            </span>
          </div>
          <div className="login-sheet login-sheet-dashed"></div>
        </div>
      </aside>

      <main className="login-main">
        <form className="login-form" onSubmit={handleSubmit}>
          <h1 className="login-title">{isSignup ? 'Create your account' : 'Welcome back'}</h1>
          <p className="login-subtitle">
            {isSignup ? 'It takes about ten seconds.' : 'Log in to see your projects.'}
          </p>

          {isSignup && (
            <div className="field">
              <label htmlFor="name">Name</label>
              <input
                id="name"
                name="name"
                type="text"
                autoComplete="name"
                value={form.name}
                onChange={handleChange}
                required
              />
            </div>
          )}

          <div className="field">
            <label htmlFor="email">Email</label>
            <input
              id="email"
              name="email"
              type="email"
              autoComplete="email"
              value={form.email}
              onChange={handleChange}
              required
            />
          </div>

          <div className="field">
            <label htmlFor="password">Password</label>
            <input
              id="password"
              name="password"
              type="password"
              autoComplete={isSignup ? 'new-password' : 'current-password'}
              minLength="6"
              value={form.password}
              onChange={handleChange}
              required
            />
            {isSignup && <span className="field-hint">At least 6 characters.</span>}
          </div>

          {error && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}

          <button type="submit" className="btn btn-primary btn-large login-submit" disabled={loading}>
            {loading ? 'Please wait...' : isSignup ? 'Create account' : 'Log in'}
          </button>

          <p className="login-switch">
            {isSignup ? 'Already have an account?' : 'New to NxtBuild?'}
            <button type="button" className="login-switch-btn" onClick={toggleMode}>
              {isSignup ? 'Log in' : 'Create an account'}
            </button>
          </p>
        </form>
      </main>
    </div>
  )
}

export default Login

import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Token ${token}`
  if (localStorage.getItem('age_verified') === 'true') {
    config.headers['X-Age-Verified'] = 'true'
  }
  return config
})

// Auto-clear stale token on 401
api.interceptors.response.use(
  response => response,
  error => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      // Only redirect if trying to access a protected route
      if (window.location.pathname === '/profile') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export default api

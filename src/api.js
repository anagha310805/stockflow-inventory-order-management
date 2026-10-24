const API_ROOT = import.meta.env.VITE_API_URL || ''

export async function api(path, options = {}) {
  const token = localStorage.getItem('stockflow-token')
  const response = await fetch(`${API_ROOT}/api${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401 && token
      && localStorage.getItem('stockflow-token') === token
      && !path.startsWith('/auth/login')) {
      localStorage.removeItem('stockflow-token')
      localStorage.removeItem('stockflow-user')
      window.dispatchEvent(new CustomEvent('stockflow:unauthorized'))
    }
    throw new Error(body.error || 'The request could not be completed.')
  }
  return body
}

export const money = (value) => new Intl.NumberFormat('en-IN', {
  style: 'currency', currency: 'INR', maximumFractionDigits: 0,
}).format(value || 0)
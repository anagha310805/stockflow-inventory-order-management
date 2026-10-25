const rawApiRoot = (import.meta.env.VITE_API_URL || import.meta.env.VITE_API_BASE || '').replace(/\/+$/, '')
export const API_ROOT = rawApiRoot.endsWith('/api') ? rawApiRoot.slice(0, -4) : rawApiRoot

export async function api(path, options = {}) {
  const token = localStorage.getItem('stockflow-token')
  let response
  try {
    response = await fetch(`${API_ROOT}/api${path}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers,
      },
    })
  } catch (err) {
    if (err instanceof TypeError && (err.message.includes('fetch') || err.message.includes('NetworkError'))) {
      throw new Error('Unable to connect to the StockFlow server. Please check your network connection or verify that the API server is online and CORS is configured.')
    }
    throw err
  }
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

// Cliente de la API. La sesión viaja en cookie HttpOnly; el token CSRF se lee de la cookie ra_csrf
// y se envía en la cabecera X-CSRF-Token en cada operación que modifica datos.
function csrf() {
  const m = document.cookie.match(/(?:^|; )ra_csrf=([^;]+)/)
  return m ? decodeURIComponent(m[1]) : ''
}

export class ApiError extends Error {
  constructor(status, body) {
    super(body?.detail || `Error ${status}`)
    this.status = status
    this.errores = body?.errores || []
  }
}

let onUnauthorized = () => {}
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn }

export async function api(path, { method = 'GET', body } = {}) {
  const headers = { 'content-type': 'application/json' }
  if (method !== 'GET') headers['x-csrf-token'] = csrf()
  const r = await fetch(path, { method, headers, credentials: 'same-origin',
    body: body !== undefined ? JSON.stringify(body) : undefined })
  if (r.status === 204) return null
  const data = await r.json().catch(() => ({}))
  if (!r.ok) {
    if (r.status === 401 && !path.endsWith('/login')) onUnauthorized(data?.detail)
    throw new ApiError(r.status, data)
  }
  return data
}

export const qs = (o) => new URLSearchParams(Object.entries(o).filter(([, v]) => v !== '' && v != null)).toString()

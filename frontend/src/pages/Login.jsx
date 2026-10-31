import React, { useState } from 'react'
import { api } from '../api.js'

export default function Login({ onLogin, aviso, version }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (e) => {
    e.preventDefault()
    setError('')
    if (!/^[^@\s]+@[^@\s]+\.[a-z]{2,}$/i.test(email)) return setError('Escriba un correo válido')
    if (!password) return setError('Escriba su contraseña')
    setEnviando(true)
    try { const r = await api('/api/auth/login', { method: 'POST', body: { email, password } }); onLogin(r.usuario) }
    catch (err) { setError(err.message) } finally { setEnviando(false) }
  }

  return <div className="login">
    <form onSubmit={enviar} noValidate>
      <div className="marca grande"><img src="/favicon.svg" alt="" /> RedAlimenta</div>
      <p className="sub">Donativos, caducidades y entregas del banco de alimentos</p>
      {aviso && <div className="alerta warn">{aviso}</div>}
      {error && <div className="alerta error" role="alert">{error}</div>}
      <label className="campo"><span>Correo</span>
        <input type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required /></label>
      <label className="campo"><span>Contraseña</span>
        <input type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} required /></label>
      <button disabled={enviando}>{enviando ? 'Entrando…' : 'Entrar'}</button>
      {version && <p className={`amb-login ${version.ambiente}`}>Ambiente: {version.ambiente === 'prod' ? 'Producción (laboratorio)' : 'Desarrollo'} · v{version.version}</p>}
      <p className="nota">Datos 100% sintéticos con fines académicos · Banco de alimentos comunitario</p>
    </form>
  </div>
}

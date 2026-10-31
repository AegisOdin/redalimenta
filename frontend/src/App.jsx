import React, { useEffect, useState } from 'react'
import { api, setUnauthorizedHandler } from './api.js'
import Login from './pages/Login.jsx'
import Inicio from './pages/Inicio.jsx'
import Lotes from './pages/Lotes.jsx'
import Rastreo from './pages/Rastreo.jsx'
import Hogares from './pages/Hogares.jsx'
import Despensas from './pages/Despensas.jsx'
import Catalogos from './pages/Catalogos.jsx'
import Usuarios from './pages/Usuarios.jsx'
import Reportes from './pages/Reportes.jsx'

const ROL_LABEL = { admin: 'Administrador', coordinador: 'Coordinador de almacén',
  trabajador_social: 'Trabajador social', voluntario: 'Voluntario de entrega' }

// Navegación visible por rol (la autorización real se verifica en el servidor)
const MENU = [
  { id: 'inicio', label: 'Inicio', roles: ['admin', 'coordinador', 'trabajador_social', 'voluntario'], C: Inicio },
  { id: 'lotes', label: 'Lotes', roles: ['admin', 'coordinador', 'trabajador_social'], C: Lotes },
  { id: 'rastreo', label: 'Rastreo de lote', roles: ['admin', 'coordinador', 'trabajador_social'], C: Rastreo },
  { id: 'despensas', label: 'Despensas', roles: ['admin', 'coordinador', 'trabajador_social', 'voluntario'], C: Despensas },
  { id: 'hogares', label: 'Hogares', roles: ['admin', 'trabajador_social', 'voluntario', 'coordinador'], C: Hogares },
  { id: 'catalogos', label: 'Catálogos', roles: ['admin', 'coordinador'], C: Catalogos },
  { id: 'reportes', label: 'Reportes', roles: ['admin', 'coordinador'], C: Reportes },
  { id: 'usuarios', label: 'Usuarios', roles: ['admin'], C: Usuarios },
]

function ruta() { return (location.hash.replace('#/', '') || 'inicio').split('?') }

export default function App() {
  const [usuario, setUsuario] = useState(undefined)
  const [aviso, setAviso] = useState('')
  const [[pagina, query], setPagina] = useState(ruta())
  const [version, setVersion] = useState(null)
  const [menuAbierto, setMenuAbierto] = useState(false)

  useEffect(() => {
    setUnauthorizedHandler((detalle) => { setUsuario(null); setAviso(detalle || 'Su sesión terminó') })
    api('/api/auth/me').then(setUsuario).catch(() => setUsuario(null))
    api('/api/version').then(setVersion).catch(() => {})
    const h = () => { setPagina(ruta()); setMenuAbierto(false) }
    window.addEventListener('hashchange', h)
    return () => window.removeEventListener('hashchange', h)
  }, [])

  if (usuario === undefined) return <div className="cargando">Cargando…</div>
  if (!usuario) return <Login aviso={aviso} onLogin={(u) => { setAviso(''); setUsuario(u); location.hash = '#/inicio' }} version={version} />

  const visibles = MENU.filter((m) => m.roles.includes(usuario.rol))
  const actual = visibles.find((m) => m.id === pagina) || visibles[0]
  const salir = async () => { await api('/api/auth/logout', { method: 'POST' }).catch(() => {}); setUsuario(null) }

  return <div className="app">
    <aside className={menuAbierto ? 'abierto' : ''}>
      <div className="marca"><img src="/favicon.svg" alt="" /> RedAlimenta</div>
      <nav>{visibles.map((m) => <a key={m.id} href={`#/${m.id}`} className={m.id === actual.id ? 'activo' : ''}>{m.label}</a>)}</nav>
      <div className="pie-menu">
        {version && <span className={`amb ${version.ambiente}`}>{version.ambiente === 'prod' ? 'Producción' : 'Desarrollo'} · v{version.version}</span>}
      </div>
    </aside>
    <main>
      <header className="barra">
        <button className="hamb" onClick={() => setMenuAbierto(!menuAbierto)} aria-label="Menú">☰</button>
        <h1>{actual.label}</h1>
        <div className="quien"><span><b>{usuario.nombre}</b><small>{ROL_LABEL[usuario.rol]}{usuario.ruta ? ` · Ruta ${usuario.ruta}` : ''}</small></span>
          <button className="sec" onClick={salir}>Salir</button></div>
      </header>
      <section className="contenido"><actual.C usuario={usuario} query={new URLSearchParams(query || '')} /></section>
    </main>
  </div>
}

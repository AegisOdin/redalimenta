import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alerta, Campo, Modal, useMensaje } from '../ui.jsx'

const ROLES = { admin: 'Administrador', coordinador: 'Coordinador de almacén', trabajador_social: 'Trabajador social', voluntario: 'Voluntario de entrega' }

export default function Usuarios() {
  const [lista, setLista] = useState([])
  const [modal, setModal] = useState(null)
  const m = useMensaje()
  const cargar = () => api('/api/usuarios').then(setLista).catch(m.err)
  useEffect(() => { cargar() }, [])
  const guardar = async (f) => {
    try { await api(modal.id ? `/api/usuarios/${modal.id}` : '/api/usuarios', { method: modal.id ? 'PUT' : 'POST', body: { ...f, password: f.password || null, ruta: f.ruta || null } }); m.ok('Usuario guardado'); setModal(null); cargar() } catch (e) { m.err(e) }
  }
  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="filtros"><button onClick={() => setModal({})}>+ Usuario</button></div>
    <div className="tabla-scroll"><table className="tabla"><thead><tr><th>Nombre</th><th>Correo</th><th>Rol</th><th>Ruta</th><th>Estado</th><th></th></tr></thead>
      <tbody>{lista.map((u) => <tr key={u.id} className={u.activo ? '' : 'inactivo'}><td>{u.nombre}</td><td>{u.email}</td><td>{ROLES[u.rol]}</td><td>{u.ruta || '—'}</td>
        <td>{u.activo ? <span className="badge ok">Activo</span> : <span className="badge bad">Inactivo</span>}</td>
        <td className="acciones-fila"><button className="sec" onClick={() => setModal(u)}>Editar</button>
          {u.activo && <button className="peligro" onClick={async () => { try { await api(`/api/usuarios/${u.id}`, { method: 'DELETE' }); m.ok('Usuario desactivado'); cargar() } catch (e) { m.err(e) } }}>Desactivar</button>}</td></tr>)}</tbody></table></div>
    {modal && <Modal titulo={modal.id ? 'Editar usuario' : 'Nuevo usuario'} onClose={() => setModal(null)}><FormUsuario u={modal} onGuardar={guardar} /></Modal>}
  </div>
}

function FormUsuario({ u, onGuardar }) {
  const [f, setF] = useState({ email: u.email || '', nombre: u.nombre || '', rol: u.rol || 'coordinador', ruta: u.ruta || '', activo: u.activo ?? true, password: '' })
  const [err, setErr] = useState('')
  const enviar = (e) => {
    e.preventDefault()
    if (!u.id && f.password.length < 10) return setErr('La contraseña debe tener al menos 10 caracteres')
    if (f.rol === 'voluntario' && !f.ruta) return setErr('Un voluntario requiere ruta')
    onGuardar(f)
  }
  return <form className="form" onSubmit={enviar}>{err && <div className="alerta error">{err}</div>}
    <Campo label="Nombre *"><input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></Campo>
    <Campo label="Correo *"><input type="email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} /></Campo>
    <div className="grid2"><Campo label="Rol *"><select value={f.rol} onChange={(e) => setF({ ...f, rol: e.target.value })}>{Object.entries(ROLES).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Campo>
      <Campo label="Ruta (voluntarios)"><select value={f.ruta} onChange={(e) => setF({ ...f, ruta: e.target.value })}><option value="">—</option>{['Norte', 'Sur', 'Centro', 'Oriente'].map((r) => <option key={r}>{r}</option>)}</select></Campo></div>
    <Campo label={u.id ? 'Nueva contraseña (opcional)' : 'Contraseña *'} ayuda="Mínimo 10 caracteres; se guarda con Argon2id"><input type="password" autoComplete="new-password" value={f.password} onChange={(e) => setF({ ...f, password: e.target.value })} /></Campo>
    <div className="acciones"><button>Guardar</button></div></form>
}

import React, { useEffect, useState, useCallback } from 'react'
import { api, qs } from '../api.js'
import { Alerta, Campo, Modal, Paginador, useMensaje, fecha, hoyISO } from '../ui.jsx'

const RUTAS = ['Norte', 'Sur', 'Centro', 'Oriente']
const ALERG = ['gluten', 'lacteos', 'cacahuate', 'huevo', 'soya', 'mariscos', 'nueces']

function FormHogar({ inicial, onGuardar, onCancelar }) {
  const [f, setF] = useState(inicial || { clave: '', responsable: '', integrantes: 1, alergenos: [], colonia: '', ruta: 'Norte', telefono: '', activo: true })
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const enviar = (e) => {
    e.preventDefault()
    if (!/^[A-Z0-9-]{3,20}$/.test(f.clave)) return setErr('Clave: 3 a 20 caracteres en MAYÚSCULAS, números o guion')
    if (f.responsable.trim().length < 3) return setErr('Responsable: mínimo 3 caracteres')
    const n = Number(f.integrantes)
    if (!Number.isInteger(n) || n < 1 || n > 20) return setErr('Integrantes: entero entre 1 y 20')
    if (f.telefono && !/^[0-9 +-]{7,20}$/.test(f.telefono)) return setErr('Teléfono inválido')
    onGuardar({ ...f, integrantes: n, telefono: f.telefono || null })
  }
  const rac = Math.min(4, 1 + 0.5 * (Number(f.integrantes || 1) - 1))
  return <form onSubmit={enviar} className="form">
    {err && <div className="alerta error">{err}</div>}
    <div className="grid2">
      <Campo label="Clave *"><input value={f.clave} disabled={!!inicial?.id} onChange={(e) => setF({ ...f, clave: e.target.value.toUpperCase() })} placeholder="H-0200" /></Campo>
      <Campo label="Responsable *"><input value={f.responsable} onChange={set('responsable')} maxLength={120} /></Campo>
      <Campo label="Integrantes *" ayuda={`Raciones por despensa: ${rac}`}><input type="number" min="1" max="20" value={f.integrantes} onChange={set('integrantes')} /></Campo>
      <Campo label="Ruta *"><select value={f.ruta} onChange={set('ruta')}>{RUTAS.map((r) => <option key={r}>{r}</option>)}</select></Campo>
      <Campo label="Colonia *"><input value={f.colonia} onChange={set('colonia')} maxLength={120} /></Campo>
      <Campo label="Teléfono"><input value={f.telefono || ''} onChange={set('telefono')} /></Campo>
    </div>
    <fieldset className="chips"><legend>Restricciones alimentarias (bloquean productos con ese alérgeno)</legend>
      {ALERG.map((a) => <label key={a} className={f.alergenos.includes(a) ? 'on' : ''}><input type="checkbox" checked={f.alergenos.includes(a)}
        onChange={(e) => setF({ ...f, alergenos: e.target.checked ? [...f.alergenos, a] : f.alergenos.filter((x) => x !== a) })} />{a}</label>)}
    </fieldset>
    <div className="acciones"><button type="button" className="sec" onClick={onCancelar}>Cancelar</button><button>Guardar</button></div>
  </form>
}

export default function Hogares({ usuario }) {
  const [filtro, setFiltro] = useState({ q: '', ruta: '', page: 1, size: 15 })
  const [datos, setDatos] = useState({ items: [], total: 0 })
  const [modal, setModal] = useState(null)
  const m = useMensaje()
  const ts = ['trabajador_social', 'admin'].includes(usuario.rol)  // el administrador tiene todos los permisos
  const cargar = useCallback(() => api(`/api/hogares?${qs(filtro)}`).then(setDatos).catch(m.err), [filtro])
  useEffect(() => { cargar() }, [cargar])
  const accion = async (fn, t) => { try { await fn(); m.ok(t); setModal(null); cargar() } catch (e) { m.err(e) } }
  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="filtros">
      <input placeholder="Buscar clave, responsable o colonia" value={filtro.q} onChange={(e) => setFiltro({ ...filtro, q: e.target.value, page: 1 })} />
      {usuario.rol !== 'voluntario' && <select value={filtro.ruta} onChange={(e) => setFiltro({ ...filtro, ruta: e.target.value, page: 1 })}><option value="">Todas las rutas</option>{RUTAS.map((r) => <option key={r}>{r}</option>)}</select>}
      {ts && <button onClick={() => setModal({ tipo: 'nuevo' })}>+ Registrar hogar</button>}
    </div>
    <div className="tabla-scroll"><table className="tabla">
      <thead><tr><th>Clave</th><th>Responsable</th><th>Integr.</th><th>Raciones</th><th>Ruta</th><th>Alérgenos</th><th>Última entrega</th><th>Elegible</th><th></th></tr></thead>
      <tbody>{datos.items.map((h) => <tr key={h.id} className={h.activo ? '' : 'inactivo'}>
        <td data-l="Clave">{h.clave}</td><td data-l="Responsable">{h.responsable}</td><td data-l="Integrantes">{h.integrantes}</td><td data-l="Raciones">{h.raciones}</td>
        <td data-l="Ruta">{h.ruta}</td><td data-l="Alérgenos">{h.alergenos.join(', ') || '—'}</td><td data-l="Última entrega">{fecha(h.ultima_entrega)}</td>
        <td data-l="Elegible">{h.elegible ? <span className="badge ok">Sí</span> : <span className="badge warn" title={h.motivo_elegibilidad}>No</span>}</td>
        <td className="acciones-fila">{ts && h.activo && <>
          <button onClick={() => setModal({ tipo: 'solicitar', hogar: h })} disabled={!h.elegible}>Solicitar despensa</button>
          <button className="sec" onClick={() => setModal({ tipo: 'editar', hogar: h })}>Editar</button>
          <button className="peligro" onClick={() => confirm(`¿Dar de baja el hogar ${h.clave}?`) && accion(() => api(`/api/hogares/${h.id}`, { method: 'DELETE' }), 'Hogar dado de baja')}>Baja</button></>}</td>
      </tr>)}</tbody></table></div>
    <Paginador {...filtro} total={datos.total} onPage={(page) => setFiltro({ ...filtro, page })} />
    {modal?.tipo === 'nuevo' && <Modal titulo="Registrar hogar" onClose={() => setModal(null)}><FormHogar onCancelar={() => setModal(null)} onGuardar={(f) => accion(() => api('/api/hogares', { method: 'POST', body: f }), `Hogar ${f.clave} registrado`)} /></Modal>}
    {modal?.tipo === 'editar' && <Modal titulo={`Editar ${modal.hogar.clave}`} onClose={() => setModal(null)}><FormHogar inicial={modal.hogar} onCancelar={() => setModal(null)} onGuardar={(f) => accion(() => api(`/api/hogares/${modal.hogar.id}`, { method: 'PUT', body: f }), 'Hogar actualizado')} /></Modal>}
    {modal?.tipo === 'solicitar' && <Modal titulo={`Solicitar despensa · ${modal.hogar.clave}`} onClose={() => setModal(null)}><Solicitar hogar={modal.hogar} onGuardar={(f) => accion(() => api('/api/despensas', { method: 'POST', body: f }), 'Despensa solicitada')} /></Modal>}
  </div>
}

function Solicitar({ hogar, onGuardar }) {
  const [fp, setFp] = useState(hoyISO(1))
  return <form className="form" onSubmit={(e) => { e.preventDefault(); onGuardar({ hogar_id: hogar.id, fecha_programada: fp }) }}>
    <p>{hogar.responsable} · {hogar.integrantes} integrantes → <b>{hogar.raciones} raciones</b></p>
    <Campo label="Fecha programada de entrega *"><input type="date" min={hoyISO()} value={fp} onChange={(e) => setFp(e.target.value)} /></Campo>
    <div className="acciones"><button>Registrar solicitud</button></div>
  </form>
}

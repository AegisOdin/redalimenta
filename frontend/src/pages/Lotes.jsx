import React, { useEffect, useState, useCallback } from 'react'
import { api, qs } from '../api.js'
import { Alerta, Badge, Campo, Modal, Paginador, useMensaje, fecha, hoyISO, ESTADO_LABEL } from '../ui.jsx'

const ESTADOS = ['recibido', 'en_inspeccion', 'disponible', 'prioritario', 'asignado', 'entregado', 'rechazado', 'merma', 'retirado']

// Checklist distinto por tipo de producto: se guarda tal cual en el expediente de MongoDB
const CHECKLIST = {
  refrigerado: [['empaque_integro', 'Empaque íntegro', 'bool'], ['transporte_refrigerado', 'Llegó en transporte refrigerado', 'bool']],
  enlatado: [['lote_fabricante', 'Lote del fabricante', 'text'], ['estado_lata', 'Estado de la lata', ['sin_abolladuras', 'abolladura_leve', 'abombada']], ['etiqueta_legible', 'Etiqueta legible', 'bool']],
  fruta_verdura: [['grado_madurez', 'Grado de madurez', ['verde', 'pinton', 'maduro', 'sobremaduro']], ['porcentaje_danado', '% dañado', 'number']],
  granos: [['humedad_visible', 'Humedad visible', 'bool'], ['plagas', 'Presencia de plagas', 'bool']],
  panaderia: [['horas_desde_horneado', 'Horas desde horneado', 'number'], ['moho', 'Moho visible', 'bool']],
  otros: [['sello_intacto', 'Sello intacto', 'bool']],
}

function FormLote({ inicial, productos, donantes, onGuardar, onCancelar }) {
  const [f, setF] = useState(inicial || { producto_id: '', donante_id: '', cantidad_inicial: '', fecha_caducidad: hoyISO(30) })
  const [err, setErr] = useState('')
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value })
  const enviar = (e) => {
    e.preventDefault()
    if (!inicial && (!f.producto_id || !f.donante_id)) return setErr('Seleccione producto y donante')
    const c = Number(f.cantidad_inicial)
    if (!Number.isInteger(c) || c < 1 || c > 100000) return setErr('La cantidad debe ser un entero entre 1 y 100 000')
    if (f.fecha_caducidad < hoyISO()) return setErr('No se reciben lotes ya caducados')
    onGuardar({ ...f, cantidad_inicial: c, producto_id: Number(f.producto_id), donante_id: Number(f.donante_id) })
  }
  return <form onSubmit={enviar} className="form">
    {err && <div className="alerta error">{err}</div>}
    {!inicial && <Campo label="Producto *"><select value={f.producto_id} onChange={set('producto_id')} required>
      <option value="">Seleccione…</option>{productos.filter((p) => p.activo).map((p) => <option key={p.id} value={p.id}>{p.nombre}{p.refrigerado ? ' ❄' : ''}</option>)}</select></Campo>}
    <Campo label="Donante *"><select value={f.donante_id} onChange={set('donante_id')} required>
      <option value="">Seleccione…</option>{donantes.filter((d) => d.activo).map((d) => <option key={d.id} value={d.id}>{d.nombre}</option>)}</select></Campo>
    <Campo label="Cantidad (unidades) *"><input type="number" min="1" max="100000" value={f.cantidad_inicial} onChange={set('cantidad_inicial')} required /></Campo>
    <Campo label="Fecha de caducidad *"><input type="date" min={hoyISO()} value={f.fecha_caducidad} onChange={set('fecha_caducidad')} required /></Campo>
    <div className="acciones"><button type="button" className="sec" onClick={onCancelar}>Cancelar</button><button>Guardar</button></div>
  </form>
}

function FormInspeccion({ lote, producto, onGuardar, onCancelar }) {
  const items = CHECKLIST[lote.categoria] || CHECKLIST.otros
  const [chk, setChk] = useState(Object.fromEntries(items.map(([k, , t]) => [k, t === 'bool' ? (k === 'plagas' || k === 'moho' || k === 'humedad_visible' ? false : true) : Array.isArray(t) ? t[0] : ''])))
  const [temp, setTemp] = useState('')
  const [obs, setObs] = useState('')
  const [aprobado, setAprobado] = useState(true)
  const [err, setErr] = useState('')
  const refrigerado = producto?.refrigerado
  const enviar = (e) => {
    e.preventDefault()
    if (refrigerado && temp === '') return setErr('Registre la temperatura: es obligatoria para refrigerados')
    const checklist = Object.fromEntries(Object.entries(chk).map(([k, v]) => [k, typeof v === 'string' && v !== '' && !isNaN(v) && items.find((i) => i[0] === k)?.[2] === 'number' ? Number(v) : v]))
    onGuardar({ temperatura_c: temp === '' ? null : Number(temp), checklist, aprobado, observaciones: obs || null })
  }
  return <form onSubmit={enviar} className="form">
    {err && <div className="alerta error">{err}</div>}
    <p className="ayuda">Checklist de <b>{lote.categoria.replace('_', ' / ')}</b> para {lote.folio} · {lote.producto_nombre}</p>
    {refrigerado && <Campo label="Temperatura registrada (°C) *" ayuda="Cadena de frío: más de 5 °C rechaza el lote automáticamente">
      <input type="number" step="0.1" min="-30" max="60" value={temp} onChange={(e) => setTemp(e.target.value)} /></Campo>}
    {items.map(([k, label, t]) => <Campo key={k} label={label}>
      {t === 'bool' ? <select value={String(chk[k])} onChange={(e) => setChk({ ...chk, [k]: e.target.value === 'true' })}><option value="true">Sí</option><option value="false">No</option></select>
        : Array.isArray(t) ? <select value={chk[k]} onChange={(e) => setChk({ ...chk, [k]: e.target.value })}>{t.map((o) => <option key={o}>{o}</option>)}</select>
          : <input type={t} value={chk[k]} onChange={(e) => setChk({ ...chk, [k]: e.target.value })} />}
    </Campo>)}
    <Campo label="Observaciones"><textarea maxLength={500} value={obs} onChange={(e) => setObs(e.target.value)} /></Campo>
    <label className="check"><input type="checkbox" checked={aprobado} onChange={(e) => setAprobado(e.target.checked)} /> El lote aprueba la inspección visual</label>
    <div className="acciones"><button type="button" className="sec" onClick={onCancelar}>Cancelar</button><button>Registrar inspección</button></div>
  </form>
}

export default function Lotes({ usuario }) {
  const [filtro, setFiltro] = useState({ q: '', estado: '', page: 1, size: 15 })
  const [datos, setDatos] = useState({ items: [], total: 0 })
  const [productos, setProductos] = useState([])
  const [donantes, setDonantes] = useState([])
  const [modal, setModal] = useState(null)
  const m = useMensaje()
  const coord = usuario.rol === 'coordinador'
  const cargar = useCallback(() => api(`/api/lotes?${qs(filtro)}`).then(setDatos).catch(m.err), [filtro])
  useEffect(() => { cargar() }, [cargar])
  useEffect(() => { api('/api/productos').then(setProductos); api('/api/donantes').then(setDonantes) }, [])

  const accion = async (fn, texto) => { try { const r = await fn(); m.ok(typeof texto === 'function' ? texto(r) : texto); setModal(null); cargar() } catch (e) { m.err(e) } }
  const prod = (l) => productos.find((p) => p.id === l.producto_id)

  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="filtros">
      <input placeholder="Buscar folio, producto o donante" value={filtro.q} maxLength={60} onChange={(e) => setFiltro({ ...filtro, q: e.target.value, page: 1 })} />
      <select value={filtro.estado} onChange={(e) => setFiltro({ ...filtro, estado: e.target.value, page: 1 })}>
        <option value="">Todos los estados</option>{ESTADOS.map((s) => <option key={s} value={s}>{ESTADO_LABEL[s]}</option>)}</select>
      {coord && <button onClick={() => setModal({ tipo: 'nuevo' })}>+ Recibir donativo</button>}
    </div>
    <div className="tabla-scroll"><table className="tabla">
      <thead><tr><th>Folio</th><th>Producto</th><th>Donante</th><th>Caduca</th><th>Disponible</th><th>Estado</th><th></th></tr></thead>
      <tbody>{datos.items.map((l) => <tr key={l.id}>
        <td data-l="Folio"><a href={`#/rastreo?folio=${l.folio}`}>{l.folio}</a></td>
        <td data-l="Producto">{l.producto_nombre}</td><td data-l="Donante">{l.donante_nombre}</td>
        <td data-l="Caduca">{fecha(l.fecha_caducidad)}</td><td data-l="Disponible">{l.cantidad_disponible} / {l.cantidad_inicial}</td>
        <td data-l="Estado"><Badge estado={l.estado} />{l.motivo && <small className="motivo">{l.motivo}</small>}</td>
        <td className="acciones-fila">
          {coord && l.estado === 'recibido' && <button className="sec" onClick={() => accion(() => api(`/api/lotes/${l.id}/iniciar-inspeccion`, { method: 'POST' }), `Lote ${l.folio} en inspección`)}>Iniciar inspección</button>}
          {coord && ['recibido', 'en_inspeccion'].includes(l.estado) && <button onClick={() => setModal({ tipo: 'inspeccion', lote: l })}>Inspeccionar</button>}
          {coord && ['recibido', 'en_inspeccion'].includes(l.estado) && <button className="sec" onClick={() => setModal({ tipo: 'editar', lote: l })}>Editar</button>}
          {coord && l.estado === 'recibido' && <button className="peligro" onClick={() => confirm(`¿Eliminar el lote ${l.folio} capturado por error?`) && accion(() => api(`/api/lotes/${l.id}`, { method: 'DELETE' }), 'Lote eliminado')}>Eliminar</button>}
          {usuario.rol === 'admin' && !['retirado', 'rechazado'].includes(l.estado) && <button className="peligro" onClick={() => setModal({ tipo: 'retiro', lote: l })}>Retiro sanitario</button>}
        </td></tr>)}</tbody></table></div>
    <Paginador {...filtro} total={datos.total} onPage={(page) => setFiltro({ ...filtro, page })} />

    {modal?.tipo === 'nuevo' && <Modal titulo="Recibir donativo" onClose={() => setModal(null)}>
      <FormLote productos={productos} donantes={donantes} onCancelar={() => setModal(null)}
        onGuardar={(f) => accion(() => api('/api/lotes', { method: 'POST', body: f }), (r) => `Lote ${r.folio} recibido; pendiente de inspección`)} /></Modal>}
    {modal?.tipo === 'editar' && <Modal titulo={`Corregir ${modal.lote.folio}`} onClose={() => setModal(null)}>
      <FormLote inicial={{ donante_id: modal.lote.donante_id, cantidad_inicial: modal.lote.cantidad_inicial, fecha_caducidad: modal.lote.fecha_caducidad }} productos={productos} donantes={donantes}
        onCancelar={() => setModal(null)} onGuardar={(f) => accion(() => api(`/api/lotes/${modal.lote.id}`, { method: 'PUT', body: { cantidad_inicial: f.cantidad_inicial, fecha_caducidad: f.fecha_caducidad, donante_id: f.donante_id } }), 'Lote corregido')} /></Modal>}
    {modal?.tipo === 'inspeccion' && <Modal titulo="Inspección del lote" onClose={() => setModal(null)}>
      <FormInspeccion lote={modal.lote} producto={prod(modal.lote)} onCancelar={() => setModal(null)}
        onGuardar={(f) => accion(() => api(`/api/lotes/${modal.lote.id}/inspeccion`, { method: 'POST', body: f }), (r) => `Resultado: ${ESTADO_LABEL[r.estado]}${r.motivo ? ' — ' + r.motivo : ''}`)} /></Modal>}
    {modal?.tipo === 'retiro' && <Modal titulo={`Retiro sanitario ${modal.lote.folio}`} onClose={() => setModal(null)}><Retiro lote={modal.lote} onHecho={(t) => { m.ok(t); cargar() }} /></Modal>}
  </div>
}

function Retiro({ lote, onHecho }) {
  const [motivo, setMotivo] = useState('')
  const [res, setRes] = useState(null)
  const [err, setErr] = useState(null)
  const enviar = async (e) => {
    e.preventDefault()
    if (motivo.trim().length < 5) return setErr('Describa el motivo (mínimo 5 caracteres)')
    try { const r = await api(`/api/lotes/${lote.id}/retiro-sanitario`, { method: 'POST', body: { motivo } }); setRes(r); onHecho(`Lote ${lote.folio} retirado`) } catch (e2) { setErr(e2.message) }
  }
  if (res) return <div><p><b>{res.despensas_canceladas.length}</b> despensas canceladas: {res.despensas_canceladas.join(', ') || '—'}</p>
    <h4>Hogares que ya recibieron el lote (avisar)</h4>
    {res.hogares_a_avisar.length ? <table><thead><tr><th>Hogar</th><th>Responsable</th><th>Teléfono</th><th>Despensa</th></tr></thead>
      <tbody>{res.hogares_a_avisar.map((h) => <tr key={h.despensa}><td>{h.clave}</td><td>{h.responsable}</td><td>{h.telefono}</td><td>{h.despensa}</td></tr>)}</tbody></table> : <p>Ningún hogar lo ha recibido.</p>}</div>
  return <form onSubmit={enviar} className="form">
    <p className="alerta warn">Se cancelarán las despensas pendientes que contengan {lote.folio} y se listarán los hogares que ya lo recibieron.</p>
    {err && <div className="alerta error">{err}</div>}
    <Campo label="Motivo reportado por el donante *"><textarea value={motivo} maxLength={255} onChange={(e) => setMotivo(e.target.value)} /></Campo>
    <div className="acciones"><button className="peligro">Confirmar retiro</button></div>
  </form>
}

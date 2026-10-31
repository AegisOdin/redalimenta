import React, { useEffect, useState, useCallback } from 'react'
import { api, qs } from '../api.js'
import { Alerta, Badge, Campo, Modal, Paginador, useMensaje, fecha, fechaHora, ESTADO_LABEL } from '../ui.jsx'

const ESTADOS = ['solicitada', 'aprobada', 'en_preparacion', 'lista', 'entregada', 'rechazada', 'cancelada', 'no_recogida']
const PASOS = ['solicitada', 'aprobada', 'en_preparacion', 'lista', 'entregada']
// Quién puede ejecutar cada transición (espejo de rules.TRANSICIONES en el backend)
const PERMISO = { aprobada: ['trabajador_social'], rechazada: ['trabajador_social'], en_preparacion: ['coordinador'],
  lista: ['coordinador'], entregada: ['voluntario'], no_recogida: ['coordinador'], cancelada: ['admin', 'trabajador_social'] }
const VERBO = { aprobada: 'Aprobar', rechazada: 'Rechazar', en_preparacion: 'Armar (FEFO)', lista: 'Marcar lista',
  entregada: 'Confirmar entrega', no_recogida: 'No recogida', cancelada: 'Cancelar' }
const PIDE_MOTIVO = ['cancelada', 'no_recogida']

function Detalle({ d, usuario, onAccion }) {
  const [motivo, setMotivo] = useState('')
  const [resultado, setResultado] = useState(null)
  const [item, setItem] = useState({ lote_id: '', cantidad: 1 })
  const posibles = d.transiciones.filter((t) => PERMISO[t]?.includes(usuario.rol))
  const ir = async (t) => {
    if (PIDE_MOTIVO.includes(t) && motivo.trim().length < 3) return alert('Indique el motivo')
    const r = await onAccion(() => api(`/api/despensas/${d.id}/transicion/${t}`, { method: 'POST', body: { motivo: motivo || null } }), `Despensa ${d.folio}: ${ESTADO_LABEL[t]}`)
    if (r && (r.omitidos_por_alergeno || r.faltantes)) setResultado(r)
  }
  const idx = PASOS.indexOf(d.estado)
  return <div>
    <ol className="pasos">{PASOS.map((p, i) => <li key={p} className={i < idx || d.estado === 'entregada' ? 'hecho' : i === idx ? 'actual' : ''}>{ESTADO_LABEL[p]}</li>)}</ol>
    {idx < 0 && <p><Badge estado={d.estado} /> {d.motivo_cierre}</p>}
    <dl className="ficha">
      <dt>Hogar</dt><dd>{d.hogar.clave} · {d.hogar.responsable} ({d.hogar.colonia}, ruta {d.hogar.ruta})</dd>
      <dt>Raciones</dt><dd>{d.raciones}</dd><dt>Fecha programada</dt><dd>{fecha(d.fecha_programada)}</dd>
      <dt>Alérgenos bloqueados</dt><dd>{d.hogar.alergenos.join(', ') || 'ninguno'}</dd>
      {d.entregada_en && <><dt>Entregada</dt><dd>{fechaHora(d.entregada_en)}</dd></>}
    </dl>
    {d.detalle.length > 0 && <table><thead><tr><th>Lote</th><th>Producto</th><th>Caduca</th><th>Cant.</th></tr></thead>
      <tbody>{d.detalle.map((x) => <tr key={x.lote_id}><td>{x.folio_lote}</td><td>{x.producto}</td><td>{fecha(x.caducidad)}</td><td>{x.cantidad}</td></tr>)}</tbody></table>}
    {resultado && <div className="alerta warn">
      {resultado.omitidos_por_alergeno.length > 0 && <p>Omitidos por alérgeno: {resultado.omitidos_por_alergeno.map((o) => `${o.producto} (${o.alergenos.join(', ')})`).join('; ')}</p>}
      {resultado.faltantes.length > 0 && <p>Sin existencia suficiente: {resultado.faltantes.map((o) => `${o.producto} (faltan ${o.faltan})`).join('; ')}</p>}
    </div>}
    {usuario.rol === 'coordinador' && d.estado === 'en_preparacion' && <form className="fila-form" onSubmit={(e) => { e.preventDefault(); onAccion(() => api(`/api/despensas/${d.id}/items`, { method: 'POST', body: { lote_id: Number(item.lote_id), cantidad: Number(item.cantidad) } }), 'Producto agregado') }}>
      <input type="number" placeholder="ID de lote" min="1" value={item.lote_id} onChange={(e) => setItem({ ...item, lote_id: e.target.value })} required />
      <input type="number" min="1" max="1000" value={item.cantidad} onChange={(e) => setItem({ ...item, cantidad: e.target.value })} required />
      <button className="sec">Agregar lote manualmente</button></form>}
    {posibles.length > 0 && <div className="transiciones">
      {posibles.some((t) => PIDE_MOTIVO.includes(t)) && <Campo label="Motivo (para cancelar / no recogida)"><input value={motivo} onChange={(e) => setMotivo(e.target.value)} maxLength={255} /></Campo>}
      <div className="acciones">{posibles.map((t) => <button key={t} className={['rechazada', 'cancelada', 'no_recogida'].includes(t) ? 'peligro' : ''} onClick={() => ir(t)}>{VERBO[t]}</button>)}</div>
    </div>}
  </div>
}

export default function Despensas({ usuario, query }) {
  const [filtro, setFiltro] = useState({ q: '', estado: usuario.rol === 'voluntario' ? 'lista' : '', page: 1, size: 15 })
  const [datos, setDatos] = useState({ items: [], total: 0 })
  const [sel, setSel] = useState(null)
  const m = useMensaje()
  const cargar = useCallback(() => api(`/api/despensas?${qs(filtro)}`).then(setDatos).catch(m.err), [filtro])
  useEffect(() => { cargar() }, [cargar])
  useEffect(() => { const id = query.get('id'); if (id) api(`/api/despensas/${id}`).then(setSel).catch(m.err) }, [])
  const onAccion = async (fn, texto) => {
    try { const r = await fn(); m.ok(texto); cargar(); setSel(r.despensa || r); return r } catch (e) { m.err(e); return null }
  }
  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="filtros">
      <input placeholder="Buscar folio, hogar o responsable" value={filtro.q} onChange={(e) => setFiltro({ ...filtro, q: e.target.value, page: 1 })} />
      <select value={filtro.estado} onChange={(e) => setFiltro({ ...filtro, estado: e.target.value, page: 1 })}>
        <option value="">Todos los estados</option>{ESTADOS.map((s) => <option key={s} value={s}>{ESTADO_LABEL[s]}</option>)}</select>
    </div>
    {usuario.rol === 'trabajador_social' && <p className="ayuda">Para solicitar una despensa, vaya a <a href="#/hogares">Hogares</a> y elija un hogar elegible.</p>}
    <div className="tabla-scroll"><table className="tabla">
      <thead><tr><th>Folio</th><th>Hogar</th><th>Ruta</th><th>Raciones</th><th>Programada</th><th>Estado</th></tr></thead>
      <tbody>{datos.items.map((d) => <tr key={d.id} className="clic" onClick={() => setSel(d)}>
        <td data-l="Folio"><a href={`#/despensas?id=${d.id}`} onClick={(e) => e.preventDefault()}>{d.folio}</a></td><td data-l="Hogar">{d.hogar.clave} · {d.hogar.responsable}</td>
        <td data-l="Ruta">{d.hogar.ruta}</td><td data-l="Raciones">{d.raciones}</td><td data-l="Programada">{fecha(d.fecha_programada)}</td><td data-l="Estado"><Badge estado={d.estado} /></td></tr>)}</tbody></table></div>
    <Paginador {...filtro} total={datos.total} onPage={(page) => setFiltro({ ...filtro, page })} />
    {sel && <Modal titulo={`Despensa ${sel.folio}`} onClose={() => setSel(null)}><Detalle d={sel} usuario={usuario} onAccion={onAccion} /></Modal>}
  </div>
}

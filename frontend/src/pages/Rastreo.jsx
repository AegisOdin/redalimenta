import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alerta, Badge, fechaHora, useMensaje } from '../ui.jsx'

const TIPO = { lote_recibido: 'Recepción', lote_inspeccionado: 'Inspección', inspeccion_iniciada: 'Inicio de inspección',
  lote_asignado: 'Asignado a despensa', asignacion_liberada: 'Asignación liberada', lote_entregado: 'Entregado a hogar',
  lote_retirado: 'Retiro sanitario', estado_lote: 'Cambio de estado', lote_corregido: 'Corrección', lote_eliminado: 'Eliminado' }

export default function Rastreo({ query }) {
  const [folio, setFolio] = useState(query.get('folio') || '')
  const [exp, setExp] = useState(null)
  const [hogares, setHogares] = useState(null)
  const m = useMensaje()
  const buscar = async (f = folio) => {
    m.clear(); setExp(null); setHogares(null)
    if (!f.trim()) return
    try {
      const [e, h] = await Promise.all([api(`/api/trazabilidad/lotes/${encodeURIComponent(f.trim())}`), api(`/api/trazabilidad/lotes/${encodeURIComponent(f.trim())}/hogares`)])
      setExp(e); setHogares(h.hogares)
    } catch (e) { m.err(e) }
  }
  useEffect(() => { if (folio) buscar(folio) }, [])
  const x = exp?.expediente
  return <div>
    <p className="ayuda">El expediente se consulta en <b>MongoDB</b>: cada lote guarda su checklist propio y la línea de tiempo completa de eventos.</p>
    <form className="filtros" onSubmit={(e) => { e.preventDefault(); buscar() }}>
      <input placeholder="Folio del lote, p. ej. S-00001" value={folio} onChange={(e) => setFolio(e.target.value)} />
      <button>Rastrear</button>
    </form>
    <Alerta msg={m.msg} onClose={m.clear} />
    {exp && !x && <div className="alerta warn">El lote existe en PostgreSQL pero su expediente aún no se sincroniza ({exp.eventos_pendientes_de_sincronizar} eventos en outbox).</div>}
    {x && <div className="dos-col">
      <div className="tarjeta">
        <h2>{x.folio_lote} · {x.producto}</h2>
        <dl className="ficha">
          <dt>Estado actual</dt><dd><Badge estado={exp.estado_actual || x.estado} /></dd>
          <dt>Categoría</dt><dd>{x.categoria}{x.refrigerado ? ' (refrigerado)' : ''}</dd>
          <dt>Donante</dt><dd>{x.donante} ({x.donante_tipo})</dd>
          <dt>Cantidad recibida</dt><dd>{x.cantidad}</dd>
          <dt>Caducidad</dt><dd>{x.fecha_caducidad}</dd>
          <dt>Alérgenos</dt><dd>{x.alergenos?.join(', ') || 'ninguno'}</dd>
          {exp.eventos_pendientes_de_sincronizar > 0 && <><dt>Pendientes</dt><dd className="warn-txt">{exp.eventos_pendientes_de_sincronizar} eventos por sincronizar</dd></>}
        </dl>
        {x.inspeccion && <><h3>Inspección</h3><dl className="ficha">
          {x.inspeccion.temperatura_c != null && <><dt>Temperatura</dt><dd>{x.inspeccion.temperatura_c} °C</dd></>}
          {Object.entries(x.inspeccion.checklist || {}).map(([k, v]) => <React.Fragment key={k}><dt>{k.replaceAll('_', ' ')}</dt><dd>{Array.isArray(v) ? v.join(' · ') : String(v)}</dd></React.Fragment>)}
          <dt>Resultado</dt><dd><Badge estado={x.inspeccion.resultado} /></dd></dl></>}
        {x.retiro && <div className="alerta error"><b>Retiro sanitario:</b> {x.retiro.motivo}</div>}
        <h3>Hogares que recibieron este lote</h3>
        {hogares?.length ? <ul className="lista">{hogares.map((h) => <li key={h.despensa + h.hogar_id}><b>{h.hogar_clave}</b> · {h.cantidad} u. · {h.despensa} · {fechaHora(h.ts)}</li>)}</ul> : <p>Aún ningún hogar.</p>}
      </div>
      <div className="tarjeta"><h2>Línea de tiempo</h2>
        <ol className="timeline">{x.eventos.map((e) => <li key={e.event_id}>
          <time>{fechaHora(e.ts)}</time><b>{TIPO[e.tipo] || e.tipo}</b>
          <span>{e.despensa && `Despensa ${e.despensa}`}{e.cantidad && e.tipo !== 'lote_recibido' ? ` · ${e.cantidad} u.` : ''}{e.hogar_clave ? ` · hogar ${e.hogar_clave}` : ''}{e.resultado ? ` · ${e.resultado}` : ''}{e.motivo ? ` · ${e.motivo}` : ''}</span>
        </li>)}</ol></div>
    </div>}
  </div>
}

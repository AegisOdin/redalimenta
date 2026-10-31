import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Badge, fecha } from '../ui.jsx'

export default function Inicio({ usuario }) {
  const [d, setD] = useState(null)
  useEffect(() => {
    const r = usuario.rol
    Promise.all([
      r !== 'voluntario' ? api('/api/lotes?estado=prioritario&size=8') : null,
      r !== 'voluntario' ? api('/api/lotes?estado=disponible&size=1') : null,
      api(`/api/despensas?size=8${r === 'voluntario' ? '&estado=lista' : ''}`),
      r !== 'voluntario' ? api('/api/lotes?estado=recibido&size=1') : null,
    ]).then(([prio, disp, desp, rec]) => setD({ prio, disp, desp, rec })).catch(() => {})
  }, [usuario])
  if (!d) return <p>Cargando…</p>
  return <div className="inicio">
    {usuario.rol !== 'voluntario' && <div className="kpis">
      <div className="kpi"><span>Lotes disponibles</span><b>{d.disp.total}</b></div>
      <div className="kpi warn"><span>Prioritarios (≤ 3 días)</span><b>{d.prio.total}</b></div>
      <div className="kpi"><span>Por inspeccionar</span><b>{d.rec.total}</b></div>
      <div className="kpi"><span>Despensas registradas</span><b>{d.desp.total}</b></div>
    </div>}
    <div className="dos-col">
      {d.prio && <div className="tarjeta"><h2>Lotes prioritarios</h2><p className="ayuda">Se asignan primero (FEFO) y solo a despensas que salen en las próximas 48 h.</p>
        <table><thead><tr><th>Folio</th><th>Producto</th><th>Caduca</th><th>Disp.</th></tr></thead>
          <tbody>{d.prio.items.map((l) => <tr key={l.id}><td>{l.folio}</td><td>{l.producto_nombre}</td><td>{fecha(l.fecha_caducidad)}</td><td>{l.cantidad_disponible}</td></tr>)}</tbody></table></div>}
      <div className="tarjeta"><h2>{usuario.rol === 'voluntario' ? 'Despensas listas en mi ruta' : 'Despensas recientes'}</h2>
        <table><thead><tr><th>Folio</th><th>Hogar</th><th>Estado</th></tr></thead>
          <tbody>{d.desp.items.map((x) => <tr key={x.id}><td><a href={`#/despensas?id=${x.id}`}>{x.folio}</a></td><td>{x.hogar.clave} · {x.hogar.responsable}</td><td><Badge estado={x.estado} /></td></tr>)}</tbody></table></div>
    </div>
  </div>
}

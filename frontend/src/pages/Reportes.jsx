import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alerta, useMensaje, ESTADO_LABEL } from '../ui.jsx'

const Barras = ({ filas, campo = 'kg', etiqueta = 'categoria', unidad = 'kg' }) => {
  const max = Math.max(1, ...filas.map((f) => f[campo]))
  return <div className="barras">{filas.map((f) => <div key={f[etiqueta]} className="barra-fila">
    <span>{f[etiqueta].replace('_', ' / ')}</span><div className="pista"><div style={{ width: `${(f[campo] / max) * 100}%` }} /></div>
    <b>{Number(f[campo]).toLocaleString('es-MX', { maximumFractionDigits: 1 })} {unidad}</b></div>)}
    {!filas.length && <p className="ayuda">Sin datos en el periodo.</p>}</div>
}

export default function Reportes() {
  const hoy = new Date()
  const [p, setP] = useState({ anio: hoy.getFullYear(), mes: hoy.getMonth() + 1 })
  const [r, setR] = useState(null)
  const m = useMensaje()
  useEffect(() => { api(`/api/reportes/mensual?anio=${p.anio}&mes=${p.mes}`).then(setR).catch(m.err) }, [p])
  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="filtros">
      <select value={p.mes} onChange={(e) => setP({ ...p, mes: Number(e.target.value) })}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i + 1}>{new Date(2000, i, 1).toLocaleString('es-MX', { month: 'long' })}</option>)}</select>
      <input type="number" min="2020" max="2100" value={p.anio} onChange={(e) => setP({ ...p, anio: Number(e.target.value) })} />
    </div>
    {r && <>
      <div className="kpis">
        <div className="kpi"><span>Kilos distribuidos</span><b>{r.total_kg.toLocaleString('es-MX', { maximumFractionDigits: 1 })}</b></div>
        <div className="kpi"><span>Hogares atendidos</span><b>{r.hogares_atendidos}</b></div>
        <div className="kpi"><span>Despensas entregadas</span><b>{r.despensas_entregadas}</b></div>
        <div className="kpi warn"><span>Merma (kg)</span><b>{r.merma_por_categoria.reduce((a, x) => a + x.kg, 0).toLocaleString('es-MX', { maximumFractionDigits: 1 })}</b></div>
      </div>
      <div className="dos-col">
        <div className="tarjeta"><h2>Kilos distribuidos por categoría · {r.periodo}</h2><Barras filas={r.kilos_distribuidos} /></div>
        <div className="tarjeta"><h2>Merma por categoría · {r.periodo}</h2><Barras filas={r.merma_por_categoria} /></div>
        <div className="tarjeta"><h2>Lotes por estado (actual)</h2><Barras filas={r.lotes_por_estado.map((x) => ({ ...x, estado: ESTADO_LABEL[x.estado] }))} campo="n" etiqueta="estado" unidad="" /></div>
      </div></>}
  </div>
}

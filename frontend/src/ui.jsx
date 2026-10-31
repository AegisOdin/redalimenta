import React, { useState } from 'react'

export const ESTADO_LABEL = {
  recibido: 'Recibido', en_inspeccion: 'En inspección', disponible: 'Disponible', rechazado: 'Rechazado',
  prioritario: 'Prioritario', asignado: 'Asignado', entregado: 'Entregado', merma: 'Merma', retirado: 'Retirado',
  solicitada: 'Solicitada', aprobada: 'Aprobada', en_preparacion: 'En preparación', lista: 'Lista',
  entregada: 'Entregada', rechazada: 'Rechazada', cancelada: 'Cancelada', no_recogida: 'No recogida',
}
const TONO = {
  disponible: 'ok', entregado: 'ok', entregada: 'ok', lista: 'ok', aprobada: 'info', en_preparacion: 'info',
  en_inspeccion: 'info', recibido: 'neutral', solicitada: 'neutral', asignado: 'neutral',
  prioritario: 'warn', merma: 'bad', rechazado: 'bad', retirado: 'bad', rechazada: 'bad', cancelada: 'bad',
  no_recogida: 'warn',
}
export const Badge = ({ estado }) => <span className={`badge ${TONO[estado] || 'neutral'}`}>{ESTADO_LABEL[estado] || estado}</span>

export function Alerta({ msg, onClose }) {
  if (!msg) return null
  return <div className={`alerta ${msg.tipo}`} role="status">
    <div><strong>{msg.tipo === 'ok' ? 'Listo. ' : 'No se pudo completar. '}</strong>{msg.texto}
      {msg.errores?.length > 0 && <ul>{msg.errores.map((e, i) => <li key={i}><b>{e.campo}</b>: {e.mensaje}</li>)}</ul>}
    </div>
    <button className="link" onClick={onClose} aria-label="Cerrar">×</button>
  </div>
}

export function useMensaje() {
  const [msg, setMsg] = useState(null)
  const ok = (texto) => setMsg({ tipo: 'ok', texto })
  const err = (e) => setMsg({ tipo: 'error', texto: e.message, errores: e.errores })
  return { msg, ok, err, clear: () => setMsg(null) }
}

export function Paginador({ page, size, total, onPage }) {
  const paginas = Math.max(1, Math.ceil(total / size))
  return <div className="paginador">
    <span>{total} registros · página {page} de {paginas}</span>
    <div>
      <button className="sec" disabled={page <= 1} onClick={() => onPage(page - 1)}>Anterior</button>
      <button className="sec" disabled={page >= paginas} onClick={() => onPage(page + 1)}>Siguiente</button>
    </div>
  </div>
}

export function Modal({ titulo, children, onClose }) {
  return <div className="modal-fondo" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <div className="modal" role="dialog" aria-label={titulo}>
      <header><h3>{titulo}</h3><button className="link" onClick={onClose} aria-label="Cerrar">×</button></header>
      {children}
    </div>
  </div>
}

export const Campo = ({ label, children, ayuda }) =>
  <label className="campo"><span>{label}</span>{children}{ayuda && <small>{ayuda}</small>}</label>

export const fecha = (s) => s ? new Date(s.length === 10 ? s + 'T12:00:00' : s).toLocaleDateString('es-MX',
  { day: '2-digit', month: 'short', year: 'numeric' }) : '—'
export const fechaHora = (s) => s ? new Date(s).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' }) : '—'
export const hoyISO = (dias = 0) => { const d = new Date(); d.setDate(d.getDate() + dias); return d.toISOString().slice(0, 10) }

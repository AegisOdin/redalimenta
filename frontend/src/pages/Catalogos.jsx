import React, { useEffect, useState } from 'react'
import { api } from '../api.js'
import { Alerta, Campo, Modal, useMensaje } from '../ui.jsx'

const CATS = ['refrigerado', 'enlatado', 'fruta_verdura', 'granos', 'panaderia', 'otros']
const ALERG = ['gluten', 'lacteos', 'cacahuate', 'huevo', 'soya', 'mariscos', 'nueces']

export default function Catalogos({ usuario }) {
  const [donantes, setDonantes] = useState([])
  const [productos, setProductos] = useState([])
  const [modal, setModal] = useState(null)
  const m = useMensaje()
  const admin = usuario.rol === 'admin'
  const cargar = () => { api('/api/donantes').then(setDonantes); api('/api/productos').then(setProductos) }
  useEffect(cargar, [])
  const guardar = async (url, method, body, t) => { try { await api(url, { method, body }); m.ok(t); setModal(null); cargar() } catch (e) { m.err(e) } }
  return <div>
    <Alerta msg={m.msg} onClose={m.clear} />
    <div className="dos-col">
      <div className="tarjeta"><div className="tit-acc"><h2>Donantes</h2>{(admin || usuario.rol === 'coordinador') && <button onClick={() => setModal({ tipo: 'donante' })}>+ Donante</button>}</div>
        <table><thead><tr><th>Nombre</th><th>Tipo</th><th></th></tr></thead><tbody>{donantes.map((d) => <tr key={d.id} className={d.activo ? '' : 'inactivo'}>
          <td>{d.nombre}</td><td>{d.tipo}</td><td className="acciones-fila">{admin && <><button className="sec" onClick={() => setModal({ tipo: 'donante', d })}>Editar</button>
            {d.activo && <button className="peligro" onClick={() => guardar(`/api/donantes/${d.id}`, 'DELETE', undefined, 'Donante desactivado')}>Baja</button>}</>}</td></tr>)}</tbody></table></div>
      <div className="tarjeta"><div className="tit-acc"><h2>Productos</h2>{admin && <button onClick={() => setModal({ tipo: 'producto' })}>+ Producto</button>}</div>
        <p className="ayuda">“Unidades por ración” &gt; 0 lo incluye en la canasta que se arma automáticamente con FEFO.</p>
        <table><thead><tr><th>Nombre</th><th>Categoría</th><th>Alérgenos</th><th>u/ración</th><th></th></tr></thead><tbody>{productos.map((p) => <tr key={p.id} className={p.activo ? '' : 'inactivo'}>
          <td>{p.nombre}{p.refrigerado && ' ❄'}</td><td>{p.categoria}</td><td>{p.alergenos.join(', ') || '—'}</td><td>{p.unidades_por_racion}</td>
          <td className="acciones-fila">{admin && <button className="sec" onClick={() => setModal({ tipo: 'producto', p })}>Editar</button>}</td></tr>)}</tbody></table></div>
    </div>
    {modal?.tipo === 'donante' && <Modal titulo={modal.d ? 'Editar donante' : 'Nuevo donante'} onClose={() => setModal(null)}>
      <FormDonante d={modal.d} onGuardar={(f) => guardar(modal.d ? `/api/donantes/${modal.d.id}` : '/api/donantes', modal.d ? 'PUT' : 'POST', f, 'Donante guardado')} /></Modal>}
    {modal?.tipo === 'producto' && <Modal titulo={modal.p ? 'Editar producto' : 'Nuevo producto'} onClose={() => setModal(null)}>
      <FormProducto p={modal.p} onGuardar={(f) => guardar(modal.p ? `/api/productos/${modal.p.id}` : '/api/productos', modal.p ? 'PUT' : 'POST', f, 'Producto guardado')} /></Modal>}
  </div>
}

function FormDonante({ d, onGuardar }) {
  const [f, setF] = useState(d || { nombre: '', tipo: 'supermercado', contacto: '', activo: true })
  return <form className="form" onSubmit={(e) => { e.preventDefault(); if (f.nombre.trim().length < 3) return alert('Nombre: mínimo 3 caracteres'); onGuardar(f) }}>
    <Campo label="Nombre *"><input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} maxLength={120} /></Campo>
    <Campo label="Tipo *"><select value={f.tipo} onChange={(e) => setF({ ...f, tipo: e.target.value })}><option>supermercado</option><option>productor</option><option>particular</option></select></Campo>
    <Campo label="Contacto"><input value={f.contacto || ''} onChange={(e) => setF({ ...f, contacto: e.target.value })} maxLength={120} /></Campo>
    <div className="acciones"><button>Guardar</button></div></form>
}

function FormProducto({ p, onGuardar }) {
  const [f, setF] = useState(p || { nombre: '', categoria: 'enlatado', refrigerado: false, alergenos: [], peso_unitario_kg: '1', unidades_por_racion: '0', activo: true })
  return <form className="form" onSubmit={(e) => { e.preventDefault(); if (!(Number(f.peso_unitario_kg) > 0)) return alert('Peso debe ser mayor que 0'); onGuardar(f) }}>
    <Campo label="Nombre *"><input value={f.nombre} onChange={(e) => setF({ ...f, nombre: e.target.value })} /></Campo>
    <div className="grid2">
      <Campo label="Categoría *"><select value={f.categoria} onChange={(e) => setF({ ...f, categoria: e.target.value, refrigerado: e.target.value === 'refrigerado' || f.refrigerado })}>{CATS.map((c) => <option key={c}>{c}</option>)}</select></Campo>
      <Campo label="Peso unitario (kg) *"><input type="number" step="0.001" min="0.001" value={f.peso_unitario_kg} onChange={(e) => setF({ ...f, peso_unitario_kg: e.target.value })} /></Campo>
      <Campo label="Unidades por ración"><input type="number" step="0.5" min="0" max="20" value={f.unidades_por_racion} onChange={(e) => setF({ ...f, unidades_por_racion: e.target.value })} /></Campo>
      <label className="check"><input type="checkbox" checked={f.refrigerado} onChange={(e) => setF({ ...f, refrigerado: e.target.checked })} /> Requiere cadena de frío</label>
    </div>
    <fieldset className="chips"><legend>Alérgenos</legend>{ALERG.map((a) => <label key={a} className={f.alergenos.includes(a) ? 'on' : ''}><input type="checkbox" checked={f.alergenos.includes(a)} onChange={(e) => setF({ ...f, alergenos: e.target.checked ? [...f.alergenos, a] : f.alergenos.filter((x) => x !== a) })} />{a}</label>)}</fieldset>
    <div className="acciones"><button>Guardar</button></div></form>
}

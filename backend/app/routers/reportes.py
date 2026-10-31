from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..db import get_db
from ..security import requiere

router = APIRouter(prefix="/api/reportes", tags=["reportes"])


@router.get("/mensual")
def mensual(anio: int = Query(default_factory=lambda: date.today().year, ge=2020, le=2100),
            mes: int = Query(default_factory=lambda: date.today().month, ge=1, le=12),
            db: Session = Depends(get_db), _=Depends(requiere("admin", "coordinador"))):
    p = {"ini": date(anio, mes, 1), "fin": date(anio + (mes == 12), mes % 12 + 1, 1)}
    kilos = db.execute(text("""
        SELECT pr.categoria, COALESCE(SUM(dd.cantidad * pr.peso_unitario_kg),0) AS kg
        FROM despensas d JOIN despensa_detalle dd ON dd.despensa_id = d.id
        JOIN lotes l ON l.id = dd.lote_id JOIN productos pr ON pr.id = l.producto_id
        WHERE d.estado = 'entregada' AND d.entregada_en >= :ini AND d.entregada_en < :fin
        GROUP BY pr.categoria ORDER BY kg DESC"""), p).mappings().all()
    merma = db.execute(text("""
        SELECT pr.categoria, COUNT(*) AS lotes, COALESCE(SUM(l.cantidad_disponible * pr.peso_unitario_kg),0) AS kg
        FROM lotes l JOIN productos pr ON pr.id = l.producto_id
        WHERE l.estado = 'merma' AND l.fecha_caducidad >= :ini AND l.fecha_caducidad < :fin
        GROUP BY pr.categoria ORDER BY kg DESC"""), p).mappings().all()
    hogares = db.execute(text("""
        SELECT COUNT(DISTINCT hogar_id) AS hogares, COUNT(*) AS despensas
        FROM despensas WHERE estado='entregada' AND entregada_en >= :ini AND entregada_en < :fin"""), p).mappings().one()
    estados = db.execute(text("SELECT estado, COUNT(*) n FROM lotes GROUP BY estado ORDER BY estado")).mappings().all()
    return {"periodo": f"{anio}-{mes:02d}",
            "kilos_distribuidos": [{"categoria": r["categoria"], "kg": float(r["kg"])} for r in kilos],
            "total_kg": float(sum(r["kg"] for r in kilos)),
            "merma_por_categoria": [{"categoria": r["categoria"], "lotes": r["lotes"], "kg": float(r["kg"])} for r in merma],
            "hogares_atendidos": hogares["hogares"], "despensas_entregadas": hogares["despensas"],
            "lotes_por_estado": [dict(r) for r in estados]}

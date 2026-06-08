import os

path = 'src/modules/analytics/routers.py'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

kpis_endpoint = """
def diff_hours(d1_str, d2_str):
    if not d1_str or not d2_str:
        return None
    try:
        fmt = "%Y-%m-%d %H:%M:%S"
        t1 = datetime.strptime(d1_str, fmt)
        t2 = datetime.strptime(d2_str, fmt)
        if t1 > t2:
            return 0.0
        return (t2 - t1).total_seconds() / 3600.0
    except:
        return None

def parse_tiempo_estimado(tiempo_str: str) -> float:
    if not tiempo_str:
        return 0.0
    t = tiempo_str.lower()
    try:
        num_part = ''.join([c for c in t if c.isdigit() or c == '.'])
        num = float(num_part) if num_part else 0.0
        if "dia" in t or "día" in t:
            return num * 24.0
        elif "min" in t:
            return num / 60.0
        return num
    except:
        return 0.0

from sqlalchemy.orm import joinedload
from src.modules.operations.models import AnalisisIA, Cotizacion

@router.get("/kpis")
def obtener_kpis(
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    \"\"\"Obtener analíticas operacionales y KPIs para el dashboard del taller (por tenant).\"\"\"
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="El usuario no pertenece a un tenant")

    # Obtener todos los incidentes del tenant actual
    incidentes = db.query(Incidente).options(
        joinedload(Incidente.analisis_ia),
        joinedload(Incidente.cotizaciones)
    ).filter(Incidente.tenant_id == current_user.tenant_id).all()

    total_incidentes = len(incidentes)
    if total_incidentes == 0:
        return {
            "tiempo_promedio_asignacion_horas": 0,
            "tiempo_promedio_llegada_horas": 0,
            "incidentes_por_tipo": {},
            "zonas_con_mas_incidentes": {},
            "tasa_cancelados_porcentaje": 0,
            "cumplimiento_sla_porcentaje": 0,
            "total_incidentes": 0
        }

    tiempos_asignacion = []
    tiempos_llegada = []
    incidentes_por_tipo = {}
    zonas_counter = {}
    cancelados = 0
    sla_cumplidos = 0
    sla_totales = 0

    for inc in incidentes:
        ta = diff_hours(inc.fecha, inc.fecha_asignacion)
        if ta is not None:
            tiempos_asignacion.append(ta)

        t_llegada = inc.fecha_llegada or (inc.fecha_finalizacion if inc.estado.lower() == 'resuelto' else None)
        tl = diff_hours(inc.fecha_asignacion, t_llegada)
        if tl is not None:
            tiempos_llegada.append(tl)

        clasificacion = "Otros"
        if inc.analisis_ia and inc.analisis_ia.Clasificacion:
            c = inc.analisis_ia.Clasificacion.lower()
            if "bater" in c: clasificacion = "Batería"
            elif "llanta" in c or "neumático" in c or "pinchazo" in c: clasificacion = "Llanta"
            elif "motor" in c: clasificacion = "Motor"
            elif "choque" in c or "colisión" in c: clasificacion = "Choque"
            else: clasificacion = inc.analisis_ia.Clasificacion
        
        incidentes_por_tipo[clasificacion] = incidentes_por_tipo.get(clasificacion, 0) + 1

        if inc.coordenadagps:
            try:
                partes = inc.coordenadagps.split(',')
                if len(partes) == 2:
                    lat = round(float(partes[0].strip()), 2)
                    lng = round(float(partes[1].strip()), 2)
                    zona_clave = f"{lat}, {lng}"
                    zonas_counter[zona_clave] = zonas_counter.get(zona_clave, 0) + 1
            except:
                pass

        if inc.estado.lower() == "cancelado":
            cancelados += 1

        if inc.estado.lower() == "resuelto" and inc.fecha_finalizacion:
            cot_aceptada = next((c for c in inc.cotizaciones if c.estado == "Aceptada"), None)
            if cot_aceptada and cot_aceptada.tiempo_estimado:
                t_estimado_horas = parse_tiempo_estimado(cot_aceptada.tiempo_estimado)
                t_real_horas = diff_hours(inc.fecha_asignacion, inc.fecha_finalizacion)
                
                sla_totales += 1
                if t_real_horas is not None and t_estimado_horas > 0:
                    if t_real_horas <= (t_estimado_horas * 1.20):
                        sla_cumplidos += 1

    avg_asignacion = sum(tiempos_asignacion) / len(tiempos_asignacion) if tiempos_asignacion else 0
    avg_llegada = sum(tiempos_llegada) / len(tiempos_llegada) if tiempos_llegada else 0
    porcentaje_cancelados = (cancelados / total_incidentes) * 100
    porcentaje_sla = (sla_cumplidos / sla_totales * 100) if sla_totales > 0 else 100.0

    top_zonas = dict(sorted(zonas_counter.items(), key=lambda item: item[1], reverse=True)[:5])

    return {
        "tiempo_promedio_asignacion_horas": round(avg_asignacion, 2),
        "tiempo_promedio_llegada_horas": round(avg_llegada, 2),
        "incidentes_por_tipo": incidentes_por_tipo,
        "zonas_con_mas_incidentes": top_zonas,
        "tasa_cancelados_porcentaje": round(porcentaje_cancelados, 2),
        "cumplimiento_sla_porcentaje": round(porcentaje_sla, 2),
        "total_incidentes": total_incidentes
    }
"""

with open(path, 'w', encoding='utf-8') as f:
    f.write(content + "\n" + kpis_endpoint)

print("analytics/routers.py patched")

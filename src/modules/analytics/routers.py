from src.core.database import get_db
from src.modules.iam.dependencies import get_current_user

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Dict, Any
from datetime import datetime, timedelta

from src.modules.operations.models import Incidente
from src.modules.catalog.models import Taller
from src.modules.operations.models import Pago
from src.modules.iam.models import Usuario
from sqlalchemy import or_

router = APIRouter(
    prefix="/reportes",
    tags=["Reportes y Estadísticas"]
)

from typing import Optional

@router.get("/taller/stats")
def get_taller_stats(
    taller_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    talleres_ids = []
    if current_user.talleres:
        talleres_ids = [current_user.talleres[0].Id]
    elif current_user.rol and current_user.rol.Nombre == "Admin Tenant":
        if taller_id:
            t = db.query(Taller).filter(Taller.Id == taller_id, Taller.tenant_id == current_user.tenant_id).first()
            if t:
                talleres_ids = [t.Id]
        else:
            talleres_ids = [t.Id for t in db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).all()]
    else:
        raise HTTPException(status_code=403, detail="Solo talleres o administradores pueden ver reportes")
    
    # 1. Conteo de incidentes por estado
    stats_estado = []
    if talleres_ids:
        stats_estado = db.query(
            Incidente.estado, 
            func.count(Incidente.id)
        ).filter(Incidente.taller_id.in_(talleres_ids)).group_by(Incidente.estado).all()
    
    estado_dict = {estado: count for estado, count in stats_estado}
    
    # 2. Ingresos totales (Pagos completados)
    total_ingresos = 0
    if talleres_ids:
        total_ingresos = db.query(func.sum(Pago.monto_total)).join(Incidente).filter(
            Incidente.taller_id.in_(talleres_ids),
            Pago.estado == "Completado"
        ).scalar() or 0
    
    # 3. Incidentes en los últimos 7 días (para gráfico lineal)
    hoy = datetime.now()
    hace_7_dias = hoy - timedelta(days=7)
    
    incidentes_recientes = []
    if talleres_ids:
        incidentes_recientes = db.query(Incidente).filter(
            Incidente.taller_id.in_(talleres_ids),
            Incidente.fecha >= hace_7_dias.strftime("%Y-%m-%d")
        ).all()
    
    series_incidentes = {}
    for i in range(7):
        dia = (hoy - timedelta(days=i)).strftime("%Y-%m-%d")
        series_incidentes[dia] = 0
        
    for inc in incidentes_recientes:
        dia_inc = inc.fecha[:10]
        if dia_inc in series_incidentes:
            series_incidentes[dia_inc] += 1
            
    chart_data = [{"fecha": k, "cantidad": v} for k, v in sorted(series_incidentes.items())]

    balance_tenant = 0
    if current_user.tenant_id:
        from src.modules.saas.models import Tenant
        tenant = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()
        if tenant:
            balance_tenant = tenant.balance

    return {
        "resumen": {
            "total_incidentes": sum(estado_dict.values()),
            "resueltos": estado_dict.get("finalizado", 0),
            "pendientes": estado_dict.get("taller asignado", 0) + estado_dict.get("en camino", 0),
            "ingresos_totales": total_ingresos,
            "balance_plataforma": balance_tenant
        },
        "por_estado": estado_dict,
        "historico_7_dias": chart_data
    }

@router.get("/taller/export/{format}")
def export_taller_data(
    format: str,
    taller_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user)
):
    talleres_ids = []
    identificador = "tenant"
    if current_user.talleres:
        talleres_ids = [current_user.talleres[0].Id]
        identificador = str(current_user.talleres[0].Id)
    elif current_user.rol and current_user.rol.Nombre == "Admin Tenant":
        if taller_id:
            t = db.query(Taller).filter(Taller.Id == taller_id, Taller.tenant_id == current_user.tenant_id).first()
            if t:
                talleres_ids = [t.Id]
                identificador = str(t.Id)
        else:
            talleres_ids = [t.Id for t in db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).all()]
    else:
        raise HTTPException(status_code=403, detail="Solo talleres o administradores pueden exportar datos")
    
    incidentes = []
    if talleres_ids:
        incidentes = db.query(Incidente).filter(Incidente.taller_id.in_(talleres_ids)).all()
    
    import pandas as pd
    import io
    from fastapi.responses import StreamingResponse, Response

    data = []
    for inc in incidentes:
        pago = db.query(Pago).filter(Pago.incidente_id == inc.id, Pago.estado == "Completado").first()
        data.append({
            "ID": inc.id,
            "Fecha": inc.fecha,
            "Estado": inc.estado,
            "Coordenadas": inc.coordenadagps,
            "Monto": pago.monto_total if pago else 0,
            "Metodo Pago": pago.metodo if pago else "N/A"
        })
    
    df = pd.DataFrame(data)
    
    if format == "csv":
        stream = io.StringIO()
        df.to_csv(stream, index=False)
        response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
        response.headers["Content-Disposition"] = f"attachment; filename=reporte_{identificador}.csv"
        return response
        
    elif format == "xml":
        xml_data = df.to_xml(index=False)
        return Response(content=xml_data, media_type="application/xml", headers={
            "Content-Disposition": f"attachment; filename=reporte_{identificador}.xml"
        })
        
    elif format == "pdf":
        try:
            from fpdf import FPDF
        except ImportError:
            raise HTTPException(status_code=501, detail="Exportación a PDF requiere la librería 'fpdf2'. Instálala con 'pip install fpdf2'.")

        titulo = f"Reporte de Taller: {current_user.talleres[0].Nombre}" if current_user.talleres else f"Reporte del Tenant"

        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(40, 10, titulo)
        pdf.ln(10)
        pdf.set_font("Arial", '', 10)
        pdf.cell(40, 10, f"Fecha de Generación: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        pdf.ln(20)
        
        # Header
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(20, 10, "ID", 1)
        pdf.cell(40, 10, "Fecha", 1)
        pdf.cell(40, 10, "Estado", 1)
        pdf.cell(30, 10, "Monto", 1)
        pdf.ln()
        
        # Rows
        pdf.set_font("Arial", '', 10)
        for row in data:
            pdf.cell(20, 10, str(row["ID"]), 1)
            pdf.cell(40, 10, str(row["Fecha"][:10]), 1)
            pdf.cell(40, 10, str(row["Estado"]), 1)
            pdf.cell(30, 10, str(row["Monto"]), 1)
            pdf.ln()
            
        pdf_output = pdf.output(dest='S')
        return Response(content=pdf_output, media_type="application/pdf", headers={
            "Content-Disposition": f"attachment; filename=reporte_taller_{taller.Id}.pdf"
        })
        
    else:
        raise HTTPException(status_code=400, detail="Formato no soportado")


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
    """Obtener analíticas operacionales y KPIs para el dashboard del taller (por tenant)."""
    if not current_user.tenant_id:
        raise HTTPException(status_code=400, detail="El usuario no pertenece a un tenant")

    if current_user.talleres:
        taller_id = current_user.talleres[0].Id
        incidentes = db.query(Incidente).options(
            joinedload(Incidente.analisis_ia),
            joinedload(Incidente.cotizaciones)
        ).filter(
            Incidente.taller_id == taller_id
        ).all()
    else:
        talleres_ids = [t.Id for t in db.query(Taller).filter(Taller.tenant_id == current_user.tenant_id).all()]
        incidentes = db.query(Incidente).options(
            joinedload(Incidente.analisis_ia),
            joinedload(Incidente.cotizaciones)
        ).filter(
            or_(
                Incidente.tenant_id == current_user.tenant_id,
                Incidente.taller_id.in_(talleres_ids) if talleres_ids else False
            )
        ).all()

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

    balance_tenant = 0
    from src.modules.saas.models import Tenant
    tenant = db.query(Tenant).filter(Tenant.Id == current_user.tenant_id).first()
    if tenant:
        balance_tenant = tenant.balance

    return {
        "tiempo_promedio_asignacion_horas": round(avg_asignacion, 2),
        "tiempo_promedio_llegada_horas": round(avg_llegada, 2),
        "incidentes_por_tipo": incidentes_por_tipo,
        "zonas_con_mas_incidentes": top_zonas,
        "tasa_cancelados_porcentaje": round(porcentaje_cancelados, 2),
        "cumplimiento_sla_porcentaje": round(porcentaje_sla, 2),
        "total_incidentes": total_incidentes,
        "balance_plataforma": balance_tenant
    }

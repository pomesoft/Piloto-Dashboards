from io import BytesIO
from pathlib import Path
import os
import pytest
import pandas as pd
from openpyxl import Workbook
from core.management import (read_management,validate_management,reconcile_management,
                             management_metrics,availability,management_dictionary)

FILES={
 'proyeccion':'Proyeccion de Cobranzas Pendientes de Cobro_aba542c8-0757-435d-9027-64880e89bf3b.xlsx',
 'morosos_sucursal':'Informes Gerencial - Morosos por Sucursal_eed5ebf6-da13-4259-a370-3379d79fc757.xlsx',
 'planes_gerencial':'Informes Gerencial - Prestamos por Plan_0c38d975-dfab-4e20-817e-e3e8800cabd5.xlsx',
 'morosos_plan':'Informes Gerencial - Morosos por Plan_57389cbc-fb8e-44ab-85bc-7b63e36c9153.xlsx',
}

def real_report(kind):
    p=Path(os.environ.get('REPORTS_DIR',str(Path.home()/'Downloads')))/FILES[kind]
    if not p.exists():
        pytest.skip('Archivo gerencial real no disponible')
    return read_management(p.read_bytes(),p.name,kind)

@pytest.mark.parametrize('kind,n,h,controls,differences',[
 ('proyeccion',27,9,12,0),('planes_gerencial',6,9,8,0),
 ('morosos_plan',6,13,12,1),('morosos_sucursal',2,13,12,1)])
def test_real_management_reports(kind,n,h,controls,differences):
    r=real_report(kind);d,q=validate_management(r);c=reconcile_management(r)
    assert len(d)==n and d.incluido.all()
    assert list(r.headers.values())==[h]
    assert len(c)==controls
    assert c.estado.eq('Diferencia').sum()==differences
    assert not r.rows[r.rows.clasificacion.eq('total')].empty
    assert d.fila.notna().all()
    if kind.startswith('morosos'):
        diff=c[c.estado.eq('Diferencia')].iloc[0]
        assert diff.componente=='moroso_capital'
        assert diff.original==pytest.approx(156168.39)
        assert diff.detalle==pytest.approx(1103831.57)
        assert diff.diferencia==pytest.approx(947663.18)
        assert c.estado.str.startswith('No agregable').sum()==2
        assert all('porcentaje' not in key.lower() for key in management_metrics(d,kind))

def test_projection_metrics_and_year_context():
    r=real_report('proyeccion');d=r.data
    assert d.periodo.min()==pd.Timestamp('2026-04-01')
    assert d.periodo.max()==pd.Timestamp('2028-06-01')
    assert len(d[d.anio.eq(2026)])==9
    assert len(d[d.anio.eq(2027)])==12
    assert len(d[d.anio.eq(2028)])==6
    m=management_metrics(d,'proyeccion')
    assert m['Capital pendiente proyectado']==pytest.approx(1113831.57)
    assert m['Suma de componentes proyectados']==pytest.approx(1954986.02)
    assert management_metrics(d.iloc[:0],'proyeccion')['Suma de componentes proyectados'] is None

def test_plan_totals_not_percentage_rates():
    r=real_report('planes_gerencial');m=management_metrics(r.data,r.kind)
    assert m['Préstamos reportados por plan']==14
    assert m['Saldo vencido reportado por plan']==pytest.approx(788631.93)
    assert r.data.interes_rotulado_porcentaje.max()>100
    assert r.data.plan.map(type).eq(str).all()

def test_availability_never_promotes_par_or_effectiveness():
    empty=availability({})
    assert empty.Estado.str.startswith('Pendiente').all()
    invalid=availability({'proyeccion':{'data':pd.DataFrame({'incluido':[False]})}})
    assert invalid.Estado.str.startswith('Pendiente').all()
    loaded=availability({k:True for k in FILES})
    assert (~loaded.Estado.str.startswith('Pendiente')).sum()==3
    for word in ['PAR30','Efectividad','Puntualidad','Recuperación','Roll rates','Rentabilidad']:
        assert loaded[loaded.Indicador.str.contains(word,regex=False)].Estado.eq('Pendiente de datos').all()
    assert set(management_dictionary().Unidad)=={'ARS','préstamos'}

def test_shifted_header_duplicates_missing_and_invalid_month():
    w=Workbook();s=w.active;s.append(['Título']);s.append(['Parámetro:','texto']);s.append([2026,'Capital','Interes','Seguro'])
    s.append(['Enero',10,2,0]);s.append(['Enero',10,2,0]);s.append(['Febrero',None,2,0]);s.append(['Mes inventado',3,2,0]);s.append(['Total',23,8,0])
    b=BytesIO();w.save(b)
    r=read_management(b.getvalue(),'prueba.xlsx','proyeccion');d,q=validate_management(r)
    assert list(r.headers.values())==[3]
    assert len(d)==3 and d.duplicado_potencial.sum()==2
    assert d.incluido.sum()==1
    assert r.rows.clasificacion.eq('rechazada').sum()==1
    assert q.motivo.str.contains('ausente').any()
    assert management_metrics(d[d.incluido],r.kind)['Capital pendiente proyectado'] is None

def test_wrong_management_schema_fails():
    w=Workbook();w.active.append(['Plan','Capital'])
    b=BytesIO();w.save(b)
    with pytest.raises(ValueError,match='encabezado'):
        read_management(b.getvalue(),'incorrecto.xlsx','planes_gerencial')

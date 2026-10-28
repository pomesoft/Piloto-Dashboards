"""Reportes gerenciales agregados: conservar su granularidad, sin unir préstamos."""
from io import BytesIO
import pandas as pd
import openpyxl
from .reader import Report
from .normalization import label, identifier, number, parse_date
from .metrics import total

MANAGEMENT_NAMES = {
    'proyeccion': 'Proyección de cobranzas pendientes',
    'planes_gerencial': 'Gerencial · Préstamos por plan',
    'morosos_plan': 'Gerencial · Morosos por plan',
    'morosos_sucursal': 'Gerencial · Morosos por sucursal',
}
MONTHS = {label(n):i+1 for i,n in enumerate(['Enero','Febrero','Marzo','Abril','Mayo','Junio','Julio','Agosto','Septiembre','Octubre','Noviembre','Diciembre'])}
MOROSO_HEADERS = ['capital','interes','seguro','cuota','punitorios','capital','interes','seguro','cuota','','punit','monto']
MOROSO_COLUMNS = ['bloque_cobrado_capital','bloque_cobrado_interes','bloque_cobrado_seguro','bloque_cobrado_cuota','bloque_cobrado_punitorios','moroso_capital','moroso_interes','moroso_seguro','moroso_cuota','porcentaje_reportado','porcentaje_punit_reportado','monto_reportado']
PLAN_HEADERS = ['plan','prestamos','capital','interes','seguro','monto_s_iva','monto_iva','monto_total','saldo_venc']
PLAN_COLUMNS = ['plan','prestamos_reportados','capital_reportado','interes_rotulado_porcentaje','seguro_reportado','monto_s_iva_rotulado_porcentaje','monto_iva_reportado','monto_total_reportado','saldo_venc_reportado']
NONADDITIVE = {'porcentaje_reportado','porcentaje_punit_reportado'}

def read_management(content,filename,kind):
    if kind not in MANAGEMENT_NAMES:
        raise ValueError('Tipo gerencial desconocido')
    wb=openpyxl.load_workbook(BytesIO(content),data_only=False)
    details=[];audit=[];params={};headers={};warnings=[]
    for ws in wb:
        rows=list(ws.iter_rows()); h=None
        for i,row in enumerate(rows):
            vals=[label(c.value) for c in row]
            if kind=='proyeccion':
                found=len(vals)>=4 and vals[1:4]==['capital','interes','seguro']
            elif kind=='planes_gerencial':
                found=vals[:len(PLAN_HEADERS)]==PLAN_HEADERS
            else:
                dimension='plan' if kind=='morosos_plan' else 'sucursal'
                found=vals[:13]==[dimension]+MOROSO_HEADERS
            if found:
                h=i;break
        if h is None:
            warnings.append(f'{ws.title}: hoja sin encabezado compatible; no se interpreta.')
            continue
        if kind.startswith('morosos'):
            group_labels={label(c.value) for c in rows[h-1]} if h else set()
            if not {'cobrado','moroso'}.issubset(group_labels):
                raise ValueError('Faltan rótulos de grupos Cobrado/Moroso del formato gerencial.')
        headers[ws.title]=h+1
        params[ws.title]={str(r[0].value).strip().rstrip(':').strip():r[1].value for r in rows[:h] if len(r)>1 and r[0].value and ':' in str(r[0].value)}
        year=None
        columns=['periodo','capital_pendiente_proyectado','interes_pendiente_proyectado','seguro_pendiente_proyectado'] if kind=='proyeccion' else (PLAN_COLUMNS if kind=='planes_gerencial' else [('plan' if kind=='morosos_plan' else 'sucursal')]+MOROSO_COLUMNS)
        for line,row in enumerate(rows[h if kind=='proyeccion' else h+1:],h+1 if kind=='proyeccion' else h+2):
            first=label(row[0].value)
            original=[c.value for c in row]
            record={'archivo':filename,'hoja':ws.title,'fila':line,'etiqueta_original':row[0].value}
            if not any(v is not None and str(v).strip() for v in original):
                category='vacía'
            elif kind=='proyeccion' and [label(c.value) for c in row[1:4]]==['capital','interes','seguro']:
                y=number(row[0].value)
                if pd.isna(y) or y!=int(y) or not 1900<=y<=2200:
                    raise ValueError('Año de proyección inválido')
                year=int(y);category='agrupación'
                record['anio']=year
            elif first in ('total','total_general','subtotal','sub_total'):
                category='subtotal' if 'sub' in first else 'total'
                record['anio']=year
            elif kind=='proyeccion':
                category='detalle' if first in MONTHS and year is not None else 'rechazada'
                if category=='detalle':
                    record['periodo']=pd.Timestamp(year,MONTHS[first],1)
                    record['anio']=year
            else:
                category='detalle' if first else 'rechazada'
            if category in ('detalle','subtotal','total'):
                for column,cell in zip(columns[1:],row[1:]):
                    record[column+'_original']=cell.value
                    record[column]=number(cell.value)
                if kind!='proyeccion' and category=='detalle':
                    record[columns[0]]=identifier(row[0])
                if category=='detalle':
                    details.append(record.copy())
            record['clasificacion']=category
            audit.append(record)
    if not headers:
        raise ValueError('No se encontró el encabezado esperado del reporte gerencial.')
    data=pd.DataFrame(details)
    if data.empty:
        data=pd.DataFrame(columns=columns+['archivo','hoja','fila','etiqueta_original'])
    if kind.startswith('morosos'):
        warnings += [
            'El bloque izquierdo está rotulado Cobrado en el archivo. Sus campos se conservan con ese prefijo, pero Capital/Interes coinciden con importes originados del gerencial de planes: no se interpretan como capital/interés efectivamente recuperados.',
            'Moroso es la clasificación del sistema, sin definición de atraso por días ni corte informado. Los porcentajes se conservan por segmento y no se suman ni se usan como PAR.',
        ]
    if kind=='planes_gerencial':
        warnings.append('Interes % y Monto S/IVA % contienen magnitudes monetarias en el ejemplo. Se conservan con nombre explícito y no se presentan como tasas; definición pendiente.')
    if kind=='proyeccion':
        warnings.append('Proyección mensual agregada de pendientes: no es cobro realizado ni promesa de cobro. No tiene préstamo, cuota, día de vencimiento ni fecha de corte; no permite separar mora de vencimientos futuros.')
    return Report(kind,data,pd.DataFrame(audit),params,headers,warnings)

def money_columns(report):
    return [c for c in report.data if c not in {'archivo','hoja','fila','etiqueta_original','periodo','anio','plan','sucursal'} and not c.endswith('_original') and c not in NONADDITIVE]

def validate_management(report,tolerance=.02):
    d=report.data.copy();issues=[];d['valido']=True
    def add(mask,message,blocking=False):
        for idx in d.index[mask]:
            issues.append({'archivo':d.at[idx,'archivo'],'hoja':d.at[idx,'hoja'],'fila':d.at[idx,'fila'],'motivo':message,'bloqueante':blocking})
        if blocking:
            d.loc[mask,'valido']=False
    key=['hoja','periodo'] if report.kind=='proyeccion' else ['hoja','plan' if 'plan' in d else 'sucursal']
    d['duplicado_potencial']=d.duplicated(key,keep=False)
    add(d.duplicado_potencial,'Segmento/mes duplicado: excluido para evitar doble conteo',True)
    if report.kind=='proyeccion':
        add(d.periodo.isna(),'Período mensual inválido',True)
    for c in money_columns(report):
        add(d[c].isna(),c+': ausente o inválido; total no disponible')
        add(d[c].lt(0),c+': negativo conservado para revisión')
    for c in NONADDITIVE & set(d):
        add(d[c].isna() | d[c].lt(0) | d[c].gt(100),c+': porcentaje ausente o fuera de 0–100; no se agrega')
    d['incluido']=d.valido
    return d,pd.DataFrame(issues,columns=['archivo','hoja','fila','motivo','bloqueante'])

def reconcile_management(report,tolerance=.02):
    results=[]
    for _,r in report.rows[report.rows.clasificacion.isin(['total','subtotal'])].iterrows():
        pop=report.data[report.data.hoja.eq(r.hoja)]
        if r.clasificacion=='subtotal':
            if report.kind!='proyeccion' or pd.isna(r.get('anio')):
                continue
            pop=pop[pop.anio.eq(r.anio)]
        for c in money_columns(report):
            original=r.get(c)
            if original is None or pd.isna(original):
                continue
            calc=total(pop,c)
            diff=None if calc is None else calc-original
            threshold=0 if c=='prestamos_reportados' else tolerance
            results.append({'hoja':r.hoja,'fila_control':r.fila,'nivel':r.clasificacion,'anio':r.get('anio'),'componente':c,'original':original,'detalle':calc,'diferencia':diff,'estado':'No disponible' if diff is None else ('Dentro de tolerancia' if abs(diff)<=threshold else 'Diferencia')})
        for c in NONADDITIVE & set(r.index):
            if pd.notna(r[c]):
                results.append({'hoja':r.hoja,'fila_control':r.fila,'nivel':r.clasificacion,'componente':c,'original':r[c],'detalle':None,'diferencia':None,'estado':'No agregable: porcentaje de Total sin fórmula validada'})
    return pd.DataFrame(results)

def management_metrics(d,kind):
    if kind=='proyeccion':
        parts=[total(d,c) for c in ['capital_pendiente_proyectado','interes_pendiente_proyectado','seguro_pendiente_proyectado']]
        return {'Capital pendiente proyectado':parts[0],'Interés pendiente proyectado':parts[1],'Seguro pendiente proyectado':parts[2],
                'Suma de componentes proyectados':None if any(v is None for v in parts) else sum(parts)}
    if kind=='planes_gerencial':
        return {'Préstamos reportados por plan':total(d,'prestamos_reportados'),'Capital originado reportado':total(d,'capital_reportado'),
                'Monto contractual reportado':total(d,'monto_total_reportado'),'Saldo vencido reportado por plan':total(d,'saldo_venc_reportado')}
    return {'Capital del bloque Moroso (suma de segmentos)':total(d,'moroso_capital'),
            'Interés del bloque Moroso (suma de segmentos)':total(d,'moroso_interes'),
            'Cuota del bloque Moroso (suma de segmentos)':total(d,'moroso_cuota')}

def availability(reports):
    """El estado depende de archivos efectivamente cargados, no de nombres conocidos."""
    loaded={k for k,v in reports.items() if not isinstance(v,dict) or ('data' in v and v['data'].incluido.any())}
    rows=[]
    def row(name,state,source,missing):
        rows.append({'Indicador':name,'Estado':state,'Fuente disponible':source,'Alcance o datos faltantes':missing})
    row('Pendientes de cobro por mes','Disponible con alcance limitado' if 'proyeccion' in loaded else 'Pendiente de fuente',
        MANAGEMENT_NAMES['proyeccion'] if 'proyeccion' in loaded else 'No cargada',
        'Suma mensual de capital, interés y seguro. Sin corte, detalle de cuota ni día de vencimiento; no mide efectividad ni mora.')
    row('Préstamos y saldo vencido reportado por plan','Disponible con alcance limitado' if 'planes_gerencial' in loaded else 'Pendiente de fuente',
        MANAGEMENT_NAMES['planes_gerencial'] if 'planes_gerencial' in loaded else 'No cargada',
        'Saldo Venc del sistema, sin desglose por capital ni antigüedad y sin corte explícito; no equivale a capital en riesgo.')
    morosos=loaded & {'morosos_plan','morosos_sucursal'}
    row('Distribución del bloque Moroso por plan/sucursal','Disponible con observaciones' if morosos else 'Pendiente de fuente',
        ', '.join(MANAGEMENT_NAMES[k] for k in sorted(morosos)) or 'No cargada',
        'Clasificación agregada del sistema. Conciliar cada fuente: los totales de capital pueden diferir del detalle. Los porcentajes no se suman; requiere definición y corte.')
    row('Mora por días 1–30, 31–60, 61–90 y más de 90; PAR30/PAR60/PAR90 y capital en riesgo','Pendiente de datos',
        'Los gerenciales solo aportan segmentos agregados' if morosos else 'Sin cronograma por cuota',
        'Faltan préstamo/cuota identificados, cronograma con fechas exactas, saldo exigible, capital de cada préstamo en riesgo, imputaciones, población total comparable y fecha de corte.')
    row('Efectividad de cobranza sobre obligaciones exigibles','Pendiente de datos','La proyección es de pendientes, no de exigible original' if 'proyeccion' in loaded else 'Sin obligaciones exigibles',
        'Faltan exigible original por cuota/período, pagos imputados, equivalencias validadas y mismo corte/población. No dividir cobros de otra fuente por pendientes.')
    row('Puntualidad y primera cuota impaga','Pendiente de datos','Los agregados no identifican cuotas',
        'Faltan vencimientos exactos, cuota identificada, pagos e imputaciones y corte.')
    row('Recuperación de deuda vencida','Pendiente de datos','Saldo Venc o bloque Moroso son una fotografía agregada',
        'Faltan saldo vencido inicial por deuda y pagos posteriores imputados a esa deuda, con cortes comparables.')
    row('Roll rates, curación y mora por cohortes','Pendiente de datos','Sin historia por préstamo/cuota',
        'Faltan cortes sucesivos, estados de atraso y movimientos por préstamo/cuota; los meses de proyección no son historia de mora.')
    row('Rentabilidad neta, costo de fondeo y pérdida crediticia','Pendiente de datos','Sin costos ni pérdidas validadas',
        'Faltan flujos, costos, fondeo, impuestos, bajas y recuperos; no inferir rentabilidad de intereses pactados.')
    return pd.DataFrame(rows)

def management_dictionary():
    records=[]
    definitions=[
        ('proyeccion','Capital pendiente proyectado','Σ capital_pendiente_proyectado','mes','Período mensual del reporte','ARS','No cobro efectivo; no cronograma de cuotas'),
        ('proyeccion','Interés pendiente proyectado','Σ interes_pendiente_proyectado','mes','Período mensual del reporte','ARS','Interés pendiente, no ganancia'),
        ('proyeccion','Seguro pendiente proyectado','Σ seguro_pendiente_proyectado','mes','Período mensual del reporte','ARS','Según componente exportado'),
        ('proyeccion','Suma de componentes proyectados','Σ capital + interés + seguro','mes','Período mensual del reporte','ARS','No incluye impuestos/punitorios no desglosados; no importe contractual completo'),
        ('planes_gerencial','Préstamos reportados por plan','Σ prestamos_reportados','plan','Originación según parámetros; sin corte de saldo','préstamos','No identifica préstamos; no se agrega a Préstamos Detalle'),
        ('planes_gerencial','Capital originado reportado','Σ capital_reportado','plan','Originación según parámetros','ARS','Fuente independiente de Préstamos Detalle'),
        ('planes_gerencial','Monto contractual reportado','Σ monto_total_reportado','plan','Originación según parámetros','ARS','No desembolso ni ganancia'),
        ('planes_gerencial','Saldo vencido reportado por plan','Σ saldo_venc_reportado','plan','Corte no informado en el archivo','ARS','Según sistema; no capital vencido ni PAR; falta corte y definición'),
    ]
    for kind in ('morosos_plan','morosos_sucursal'):
        for name,comp in [('Capital','capital'),('Interés','interes'),('Cuota','cuota')]:
            definitions.append((kind,name+' del bloque Moroso (suma de segmentos)','Σ moroso_'+comp,'plan' if kind.endswith('plan') else 'sucursal','Corte no informado en el archivo','ARS','Según clasificación del sistema; puede no conciliar con Total; no representa un tramo de atraso'))
    for kind,name,formula,grain,temporal,unit,limit in definitions:
        records.append({'Métrica':name,'Fórmula':formula,'Fuente':MANAGEMENT_NAMES[kind],'Granularidad':grain,'Fecha aplicada':temporal,'Exclusiones':'Controles y filas rechazadas; segmentos/meses duplicados excluidos. Ausencias no se convierten en cero.','Unidad':unit,'Interpretación y limitaciones':limit})
    return pd.DataFrame(records)

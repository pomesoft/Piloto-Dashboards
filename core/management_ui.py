"""Presentación de fuentes agregadas independientes."""
from hashlib import sha256
from datetime import datetime
from zoneinfo import ZoneInfo
from zipfile import BadZipFile
from openpyxl.utils.exceptions import InvalidFileException
import pandas as pd
import plotly.express as px
import streamlit as st
from .management import (MANAGEMENT_NAMES,read_management,validate_management,reconcile_management,
                         management_metrics,availability,management_dictionary,NONADDITIVE)
from .normalization import label,safe_csv
from .presentation import cards,table,fmt

@st.cache_data(show_spinner='Leyendo reporte gerencial…',max_entries=8,ttl=3600)
def cached_management(content,name,kind,session_id='legacy'):
    return read_management(content,name,kind)

def load_management(tolerance,policy=None):
    sources={}
    with st.expander('Reportes gerenciales y proyección',expanded=False):
        st.caption('Fuentes agregadas independientes · ARS fijo')
        for kind,name in MANAGEMENT_NAMES.items():
            if policy is not None and (not policy.permits(kind) or policy.scoped):
                continue
            upload=st.file_uploader(name,type=['xlsx'],key='upload_'+kind)
            if upload is None:
                continue
            try:
                fingerprint=sha256(upload.getvalue()).hexdigest()
                previous=st.session_state.get('source_hash_'+kind)
                if previous is not None and previous!=fingerprint:
                    for key in list(st.session_state):
                        if key.startswith('f_'+kind+'_'):
                            del st.session_state[key]
                st.session_state['source_hash_'+kind]=fingerprint
                if previous!=fingerprint:
                    st.session_state['source_loaded_'+kind]=datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).isoformat(timespec='seconds')
                r=cached_management(upload.getvalue(),upload.name,kind,st.session_state.get('_source_session','local'))
                d,q=validate_management(r,tolerance)
                selected=d[d.incluido]
                if d.hoja.nunique()>1:
                    sheet=st.selectbox('Hoja · '+name,sorted(d.hoja.unique()),key='f_'+kind+'_hoja')
                    selected=selected[selected.hoja.eq(sheet)]
                    st.caption('Se consulta una hoja por vez para evitar sumar poblaciones sin validar.')
                for dim in ['plan','sucursal']:
                    if dim in d:
                        values=st.multiselect('Filtro '+dim+' · '+name,sorted(d[dim].dropna().unique()),key='f_'+kind+'_'+dim)
                        if values:
                            selected=selected[selected[dim].isin(values)]
                if kind=='proyeccion' and not d.empty:
                    years=st.multiselect('Años de proyección',sorted(d.anio.dropna().astype(int).unique().tolist()),key='f_'+kind+'_anio')
                    if years:
                        selected=selected[selected.anio.isin(years)]
                    months=st.multiselect('Meses (1–12)',list(range(1,13)),key='f_'+kind+'_mes')
                    if months:
                        selected=selected[selected.periodo.dt.month.isin(months)]
                sources[kind]={'report':r,'data':d,'view':selected,'issues':q,'controls':reconcile_management(r,tolerance)}
            except (ValueError,TypeError,KeyError,OSError,BadZipFile,InvalidFileException) as exc:
                st.error(name+': '+str(exc))
    return sources

def show_scopes(sources):
    for kind,src in sources.items():
        r=src['report']
        dates=[]
        for p in r.parameters.values():
            dates.append(' · '.join(f'{k}: {v or "no informado"}' for k,v in p.items()))
        filters={k[len('f_'+kind+'_'):]:v for k,v in st.session_state.items() if k.startswith('f_'+kind+'_') and v}
        st.markdown('### '+MANAGEMENT_NAMES[kind])
        st.info('ARS fijo · Universo agregado según parámetros: '+' / '.join(dates)+f' · {len(src["view"])} segmentos/meses incluidos · Filtros: {filters or "ninguno"}')
        st.write('Archivo:',r.rows.archivo.iloc[0] if not r.rows.empty else 'Sin filas')
        st.write('Encabezados detectados (fila):',r.headers)
        for sheet,params in r.parameters.items():
            st.table(pd.DataFrame([(k,str(v) if v not in (None,'') else 'No informado') for k,v in params.items()],columns=['Parámetro','Valor']),alt='Parámetros de '+MANAGEMENT_NAMES[kind])
        for warning in r.warnings:
            st.warning(warning)
        if kind=='proyeccion':
            st.caption('El período de préstamos del encabezado define originaciones incluidas; los meses proyectados son otro eje temporal. Corte de pendientes no informado.')
        else:
            st.caption('Corte de saldo/morosidad no informado. La fecha Hasta de préstamos no sustituye el corte de cobro ni de vencimientos.')

def show_management(src,kind):
    r=src['report'];d=src['view']
    st.subheader(MANAGEMENT_NAMES[kind])
    for warning in r.warnings:
        st.warning(warning)
    c=src['controls']
    differences=c[c.estado.eq('Diferencia')] if not c.empty else c
    if not differences.empty:
        st.error('El detalle no concilia con los controles originales. Las tarjetas suman segmentos válidos, sin sustituirlos por el Total inconsistente. Revisa Calidad y conciliación.')
    if d.empty:
        st.info('Resultado vacío: no hay segmentos/meses válidos para los filtros seleccionados.')
    else:
        reference='Meses proyectados seleccionados; corte no informado' if kind=='proyeccion' else 'Corte no informado'
        cards(management_metrics(d,kind),'ARS',MANAGEMENT_NAMES[kind]+' · '+reference)
        if kind=='proyeccion':
            c=['capital_pendiente_proyectado','interes_pendiente_proyectado','seguro_pendiente_proyectado']
            # Las claves de mes repetidas entre hojas no se consolidan sin una población validada.
            chart=d.melt(id_vars=['periodo','hoja'],value_vars=c,var_name='Concepto',value_name='ARS')
            fig=px.line(chart,x='periodo',y='ARS',color='Concepto',line_dash='hoja',markers=True,title='Pendientes proyectados por mes',labels={'periodo':'Mes proyectado','hoja':'Hoja'})
        else:
            dimension='plan' if 'plan' in d else 'sucursal'
            value='saldo_venc_reportado' if kind=='planes_gerencial' else 'moroso_cuota'
            chart=d.sort_values(value,ascending=False)
            fig=px.bar(chart,x=dimension,y=value,color='hoja',title='Saldo vencido reportado por plan' if kind=='planes_gerencial' else 'Cuota del bloque Moroso por segmento',labels={dimension:dimension.capitalize(),value:'ARS'})
            segment=st.selectbox('Abrir segmento agregado',['Todos']+sorted(d[dimension].dropna().unique().tolist()),key='f_'+kind+'_segment')
            if segment!='Todos':
                table(d[d[dimension].eq(segment)],kind+'_segmento')
            if kind.startswith('morosos'):
                st.caption('Porcentajes originales por segmento, en escala 0–100. Definición pendiente: no son PAR ni se promedian o suman.')
                table(d[[dimension,'hoja','fila']+sorted(NONADDITIVE)],kind+'_porcentajes')
        fig.update_layout(separators=',.')
        st.plotly_chart(fig,width='stretch',alt=MANAGEMENT_NAMES[kind]+' por mes o segmento en ARS',key=kind+'_gerencial_chart')
        table(d,kind+'_gerencial_detalle')

def show_availability(sources):
    state=availability(sources)
    st.subheader('Indicadores habilitados por los reportes cargados')
    table(state[~state.Estado.str.startswith('Pendiente')],'indicadores_habilitados')
    st.subheader('Indicadores pendientes de datos')
    table(state[state.Estado.str.startswith('Pendiente')],'indicadores_pendientes')

def show_management_quality(sources):
    for kind,src in sources.items():
        r=src['report']; d=src['data']; q=src['issues']; c=src['controls']
        st.subheader(MANAGEMENT_NAMES[kind])
        st.caption('Conciliación de la población original por hoja; subtotales anuales solo contra sus meses. Porcentajes no agregables. No se suman fuentes por plan y sucursal.')
        st.write({'Segmentos/meses aceptados':int(d.valido.sum()),'Segmentos/meses excluidos':int((~d.valido).sum()),'Filas rechazadas':int(r.rows.clasificacion.eq('rechazada').sum()),'Diferencias de control':int(c.estado.eq('Diferencia').sum()) if not c.empty else 0})
        for warning in r.warnings:
            st.warning(warning)
        table(q,kind+'_incidencias')
        table(c,kind+'_conciliacion')
        with st.expander('Filas clasificadas y controles · '+MANAGEMENT_NAMES[kind]):
            table(r.rows,kind+'_filas')

def add_management_to_archive(archive,sources,tolerance):
    import json
    for kind,src in sources.items():
        r=src['report']
        archive.writestr(kind+'_incidencias.csv',safe_csv(src['issues']))
        archive.writestr(kind+'_conciliacion.csv',safe_csv(src['controls']))
        archive.writestr(kind+'_clasificacion.csv',safe_csv(r.rows))
        archive.writestr(kind+'_alcance.json',json.dumps({'parametros':r.parameters,'encabezados':r.headers,'advertencias':r.warnings,'moneda':'ARS','tolerancia':tolerance,'filtros':{k:str(v) for k,v in st.session_state.items() if k.startswith('f_'+kind+'_')}},ensure_ascii=False,default=str,indent=2))

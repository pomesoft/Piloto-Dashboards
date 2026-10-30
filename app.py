"""Dashboard local de préstamos y cobranzas. Ejecutar: streamlit run app.py."""
import json
from contextlib import nullcontext
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from datetime import date
from datetime import datetime
from zoneinfo import ZoneInfo
from uuid import uuid4
import pandas as pd
import streamlit as st
from core.zip_upload import read_zip_reports
from core.reader import read_report
from core.validation import validate,reconcile,coverage
from core.normalization import label,parse_date,safe_csv
from core.metrics import metrics,dictionary,total,ratio
from core.presentation import cards,table,filters,bars,trend,comparison,fmt
from core.management import management_dictionary,MANAGEMENT_NAMES
from core.interface import PAGES,QUESTIONS,management_help,quality_configuration,short_reference,show_universe
from core.management_ui import (load_management,show_management,show_availability,
                                show_management_quality,add_management_to_archive)
from core.access import setup_access, scoped_report
from core.chat_ui import show_chat

st.set_page_config(page_title='Gestión de cartera',page_icon='📊',layout='wide')
access_policy=setup_access(st)
st.session_state.setdefault('_source_session',uuid4().hex)
st.title('Gestión de préstamos y cobranzas')
if st.session_state.get('show_management_questions',False):
    st.subheader('Preguntas que responde el dashboard')
    st.table(QUESTIONS,alt='Cinco preguntas de gestión y las vistas donde consultarlas')
st.caption('Panel operativo · fuentes independientes · procesamiento local en memoria')

@st.cache_data(show_spinner='Leyendo y validando estructura…',max_entries=6,ttl=3600)
def cached_read(content,name,kind,session_id):
    return read_report(content,name,kind)

def reset():
    for k in list(st.session_state):
        if k.startswith('f_') or k.endswith('_segment'):
            del st.session_state[k]

st.sidebar.image(str(Path(__file__).resolve().parent/'assets'/'logoSM.png'),width=200,alt='SystemMaster')
st.sidebar.title('Navegación')
page=st.sidebar.radio('Ir a',PAGES,key='navigation',label_visibility='collapsed')
tolerance,am,bm=quality_configuration(page)
names={'prestamos':'Préstamos Detalle','cobranzas':'Cobranzas Detalle','cartera':'Saldo de la Cartera'}
reports={}; config={}; all_data={}; views={}; periods={}; issues={}; controls={}; scopes={}
with st.sidebar.expander('Carga de archivos y filtros',expanded=False):
    zip_upload=st.file_uploader('Adjuntar Todo',type=['zip'],key='upload_all',help='Adjunta un ZIP con los siete reportes Excel. Se reconocen por el comienzo del nombre.')
    zip_sources={}
    if zip_upload is not None:
        try:
            zip_sources,zip_messages=read_zip_reports(zip_upload.getvalue())
            for message in zip_messages:
                st.warning(message)
            st.caption(f'ZIP: {len(zip_sources)} reportes reconocidos. Los archivos individuales tienen prioridad.')
        except Exception as exc:
            st.error(f'No se pudo abrir el ZIP: {exc}')
    st.caption('Archivos XLSX · Moneda: ARS fijo')
    st.button('Restablecer filtros',on_click=reset,key='reset_filters')
    for kind,name in names.items():
        if not access_policy.permits(kind):
            continue
        upload=st.file_uploader(name,type=['xlsx'],key='upload_'+kind)
        if upload is None:
            upload=zip_sources.get(kind)
        if upload is None:
            continue
        try:
            fingerprint=sha256(upload.getvalue()).hexdigest()
            previous=st.session_state.get('source_hash_'+kind)
            if previous is not None and previous!=fingerprint:
                for state_key in list(st.session_state):
                    if state_key.startswith('f_'+kind+'_') or (kind=='cartera' and state_key in ('declare_cutoff','cutoff_cartera')):
                        del st.session_state[state_key]
            st.session_state['source_hash_'+kind]=fingerprint
            if previous!=fingerprint:
                st.session_state['source_loaded_'+kind]=datetime.now(ZoneInfo('America/Argentina/Buenos_Aires')).isoformat(timespec='seconds')
            original_report=cached_read(upload.getvalue(),upload.name,kind,st.session_state['_source_session'])
            report=scoped_report(original_report,access_policy)
            reports[kind]=report
            with st.expander('Corte de cartera') if kind=='cartera' else nullcontext():
                currency='ARS'
                cutoff=None; declared=False
                if kind=='cartera':
                    source_cuts=[parse_date(v) for p in report.parameters.values() for k,v in p.items() if label(k)=='cobro_hasta']
                    cuts={v for v in source_cuts if pd.notna(v)}
                    if len(cuts)==1 and len(source_cuts)==len([v for v in source_cuts if pd.notna(v)]):
                        cutoff=next(iter(cuts)).date()
                        st.write('Corte informado:',cutoff.strftime('%d/%m/%Y'))
                    else:
                        st.warning('El corte no está informado de forma única. Decláralo para habilitar métricas de cartera.')
                        confirm=st.checkbox('Declarar fecha de corte',key='declare_cutoff')
                        selected=st.date_input('Corte de cartera declarado',value=None,key='cutoff_cartera')
                        if confirm and selected:
                            cutoff=selected; declared=True
                config[kind]={'moneda':currency,'corte':cutoff,'declarado':declared}
            d,q=validate(original_report,am,bm,tolerance)
            d=access_policy.restrict(d,kind)
            if access_policy.scoped:
                q=q.merge(d[['hoja','fila']].drop_duplicates(),on=['hoja','fila'],how='inner')
            all_data[kind]=d; issues[kind]=q; controls[kind]=pd.DataFrame() if access_policy.scoped else reconcile(report,tolerance)
            filtered,period=filters(d,kind,report)
            views[kind]=filtered[filtered.incluido]; periods[kind]=period
        except Exception as exc:
            # Los mensajes no contienen valores personales ni se registran datos.
            st.error(f'{name}: no se pudo procesar. {type(exc).__name__}: {exc}')
            reports.pop(kind,None)

    management=load_management(tolerance,access_policy,zip_sources)

with st.sidebar:
    management_help()

for kind in reports:
    scopes[kind]=names[kind]+' · '+short_reference(kind,config[kind],periods[kind])

if not reports and not management:
    st.info('Abre Carga de archivos y filtros para incorporar las fuentes disponibles.')

def ready(kind):
    if kind not in views:
        st.info('Fuente faltante: carga '+names[kind]+'.')
        return False
    if kind=='cartera' and not config[kind]['corte']:
        st.info('Declara el corte de cartera. Puedes revisar su calidad y sus registros mientras tanto.')
        return False
    return True

show_chat(reports,all_data,periods,config,management,access_policy,
          {'tolerance':tolerance,'anulado':am,'bonif':bm})

if page=='Resumen':
    st.subheader('Situación de las fuentes cargadas')
    wanted={'cartera':['Capital pendiente','Saldo contractual pendiente','Préstamos con saldo'],'prestamos':['Capital colocado'],'cobranzas':['Total cobrado']}
    for kind in ['cartera','prestamos','cobranzas']:
        if kind in views and ready(kind):
            values=metrics(views[kind],kind)
            cards({k:values[k] for k in wanted[kind]},config[kind]['moneda'],scopes[kind])
    flows=[kind for kind in ('prestamos','cobranzas') if kind in views]
    if flows:
        for col,kind in zip(st.columns(len(flows)),flows):
            with col:
                key='summary_p' if kind=='prestamos' else 'summary_c'
                trend(views[kind],kind,'ARS',key,chart_type='bar',title='Colocación' if kind=='prestamos' else 'Cobranzas')
        for col,kind in zip(st.columns(len(flows)),flows):
            with col:
                key='summary_p_evolution' if kind=='prestamos' else 'summary_c_evolution'
                title='Evolución del capital colocado' if kind=='prestamos' else 'Evolución de la cobranza'
                trend(views[kind],kind,'ARS',key,monthly=True,title=title)
    if management:
        st.info('Los nuevos agregados se consultan en Proyección y morosidad y en Colocación. No se suman al detalle ni entre reportes por plan y sucursal.')
    show_availability(management)
elif page in ('Colocación','Cobranzas','Cartera'):
    kind={'Colocación':'prestamos','Cobranzas':'cobranzas','Cartera':'cartera'}[page]
    st.subheader(page)
    if ready(kind):
        d=views[kind]; currency=config[kind]['moneda']
        if d.empty:
            st.info('Resultado vacío: no hay registros válidos con los filtros actuales. No equivale a una fuente con importe cero.')
        else:
            cards(metrics(d,kind),currency,scopes[kind])
            st.caption(f'Cobertura de identificación de clientes: {d.cliente.notna().sum()} / {len(d)} registros. Los clientes se consolidan por entidad y código de cliente.')
            if kind!='cartera':
                # Aplicar mismos filtros dimensionales a la base, conservando el período anterior.
                base=all_data[kind][all_data[kind].incluido]
                for c in ['entidad','sucursal','plan','estado','usuario','tipo_de_pago']:
                    chosen=st.session_state.get('f_'+kind+'_'+c,[])
                    if chosen and c in base:
                        base=base[base[c].astype(str).isin(chosen)]
                comparison(base,reports[kind],periods[kind],currency)
                trend(d,kind,currency,'detail_'+kind,chart_type='line')
            amount={'prestamos':'capital','cobranzas':'cobrado','cartera':'saldo_capital'}[kind]
            a,b=st.columns(2)
            with a:
                bars(d,amount,'plan','Distribución por plan',currency,kind+'_plan')
            with b:
                bars(d,amount,'entidad','Distribución por entidad',currency,kind+'_entity')
            if kind=='prestamos':
                dim=st.selectbox('Distribución adicional',['estado','usuario'])
                bars(d,amount,dim,'Distribución por '+dim,currency,kind+'_extra')
                st.caption('Cancelado se conserva como préstamo pagado/terminado posible. No se interpreta como anulado. Los intereses pactados no son ganancia.')
            if kind=='cobranzas':
                st.caption('Anulado y Bonif usan los mapeos configurados. No se resta Bonif a Cobrado. Las filas representan imputaciones, no recibos ni transacciones.')
                composition=pd.DataFrame({'Concepto':['Capital','Intereses','Seguro','Punitorios','No explicado'],'Importe':[total(d,c) for c in ['capital','interes','seguro','punitorios','importe_no_explicado']]})
                st.bar_chart(composition.set_index('Concepto'),y='Importe',color='#127F8C')
                st.warning('El importe no explicado podría incluir componentes fiscales. Solicitar validación al sistema de origen.')
                bars(d,amount,'tipo_de_pago','Importe por medio de pago',currency,kind+'_payment')
                by=d.groupby('tipo_de_pago',dropna=False).cobrado.sum(min_count=1).reset_index()
                by['Participación']=by.cobrado.map(lambda v:ratio(v,total(d,'cobrado')))
                table(by,'medios')
            if kind=='cartera':
                st.caption('Cuotas impagas: definición pendiente. Tasa: definición y escala pendientes; no se calcula promedio financiero. Una fotografía no reconstruye saldos históricos.')
                if d.cliente.notna().all() and d.saldo_capital.notna().all():
                    top=d.groupby(['grupo_1','cliente']).saldo_capital.sum().nlargest(10).reset_index()
                    top['Deudor']=['Deudor '+str(i+1) for i in range(len(top))]
                    st.bar_chart(top.set_index('Deudor'),y='saldo_capital',color='#127F8C')
                    st.caption('Concentración por entidad y cliente. Identificadores ocultos; se consultan explícitamente en el detalle.')
            st.subheader('Detalle filtrado')
            table(d,kind+'_detalle',True)
    if kind=='prestamos' and 'planes_gerencial' in management:
        st.divider()
        show_management(management['planes_gerencial'],'planes_gerencial')
elif page=='Proyección y morosidad':
    st.subheader('Proyección y morosidad reportada')
    st.caption('Reportes agregados en ARS. Cada fuente conserva población, filtros, controles y granularidad propios. Una fila por plan/sucursal no identifica una cuota ni un préstamo.')
    if not management:
        st.info('Carga un reporte en Reportes gerenciales y proyección desde la barra lateral.')
    else:
        chosen=st.selectbox('Reporte agregado',list(management),format_func=lambda k:MANAGEMENT_NAMES[k],key='management_report')
        show_management(management[chosen],chosen)
    show_availability(management)
elif page=='Calidad y conciliación':
    if not access_policy.audit:
        st.info('No tienes permiso para consultar auditoría y conciliaciones.')
        st.stop()
    st.subheader('Calidad y conciliación')
    st.caption('Conciliación contra detalles originales completos, antes de filtros y exclusiones de negocio. Cada control se compara por separado con su hoja y nivel. Las métricas usan solo registros incluidos.')
    if reports or management:
        bundle=BytesIO()
        with ZipFile(bundle,'w',ZIP_DEFLATED) as archive:
            for kind,r in reports.items():
                archive.writestr(kind+'_incidencias.csv',safe_csv(issues[kind]))
                archive.writestr(kind+'_conciliacion.csv',safe_csv(controls[kind]))
                archive.writestr(kind+'_clasificacion.csv',safe_csv(r.rows.clasificacion.value_counts().rename_axis('clasificacion').reset_index(name='filas')))
                archive.writestr(kind+'_alcance.json',json.dumps({'parametros':r.parameters,'encabezados':r.headers,'configuracion':config[kind],'tolerancia':tolerance,'mapeo_anulado':am,'mapeo_bonif':bm,'filtros':{k:str(v) for k,v in st.session_state.items() if k.startswith('f_'+kind+'_')}},ensure_ascii=False,default=str,indent=2))
            add_management_to_archive(archive,management,tolerance)
        st.download_button('Descargar informe de calidad completo (ZIP)',bundle.getvalue(),'informe_calidad.zip','application/zip')
    for kind,r in reports.items():
        st.markdown('### '+names[kind])
        d=all_data[kind]; q=issues[kind]
        st.write({'Detalles aceptados':int(d.valido.sum()),'Detalles excluidos por validación':int((~d.valido).sum()),'Filas rechazadas':int(r.rows.clasificacion.eq('rechazada').sum()),'Detalles observados':int(q[['hoja','fila']].drop_duplicates().shape[0]),'Agrupaciones y controles excluidos':int(r.rows.clasificacion.isin(['agrupación','subtotal','total']).sum()),'Incluidos en métricas antes de filtros':int(d.incluido.sum())})
        st.write('Clasificación de filas',r.rows.clasificacion.value_counts())
        table(q,kind+'_incidencias')
        table(controls[kind],kind+'_conciliacion')
        with st.expander('Duplicados potenciales y observaciones de detalle'):
            table(d[d.duplicado_potencial],kind+'_duplicados',True)
            table(d,kind+'_auditoria_detalle',True)
        with st.expander('Filas clasificadas y controles originales'):
            table(r.rows,kind+'_filas',True)
        if kind=='cobranzas':
            st.write('Mapeo Anulado aplicado',am)
            st.write('Mapeo Bonif aplicado',bm)
            st.write('Valores reales y conteos de Anulado y Bonif')
            for field in ['anulado','bonif']:
                st.dataframe(d[field].fillna('(vacío)').astype(str).value_counts().rename_axis(field).reset_index(name='filas'),hide_index=True)
            ambiguous=d[d.anulado_interpretado.isna() | d.bonif_interpretada.isna()]
            st.write('Impacto bruto de registros con mapeo ambiguo (no suma válida de cobros):',fmt(total(ambiguous,'cobrado')))
            table(ambiguous,'cobros_ambiguos',True)
    show_management_quality(management)
    st.info('Cruces no habilitados: los códigos de préstamo difieren entre fuentes y los gerenciales no incluyen claves individuales. Una futura integración requiere equivalencias explícitas, cardinalidad y cobertura validadas. La API de unión incluida agrega cobros antes de unir y devuelve claves sin correspondencia.')
elif page=='Diccionario de métricas':
    st.subheader('Diccionario de métricas')
    table(pd.concat([dictionary(),management_dictionary()],ignore_index=True),'diccionario')
    st.caption('Cero se muestra como 0,00 cuando está respaldado por datos completos. Ausencia, fuente faltante, resultado vacío y denominadores cero se presentan por separado.')

elif page=='Detalle de Universo':
    show_universe(reports,names,config,views,periods,management)

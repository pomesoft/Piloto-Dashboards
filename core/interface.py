"""Navegación, ayuda de gestión y metadatos de las fuentes."""
import json
import pandas as pd
import streamlit as st
from .normalization import DEFAULT_FLAGS,label
from .management import MANAGEMENT_NAMES

PAGES=['Resumen','Colocación','Cobranzas','Cartera','Proyección y morosidad',
       'Calidad y conciliación','Diccionario de métricas','Detalle de Universo']
QUESTIONS=pd.DataFrame([
 ('¿Cuánto capital colocamos y en qué planes?','Colocación'),
 ('¿Cómo evolucionaron los cobros y por qué medios?','Cobranzas'),
 ('¿Qué saldo queda y qué deudores concentran capital?','Cartera'),
 ('¿En qué meses se ubican los pendientes reportados?','Proyección y morosidad'),
 ('¿Qué segmentos o diferencias requieren revisión?','Gerenciales y Calidad y conciliación'),
],columns=['Pregunta de gestión','Dónde consultarla'])
VIEWS=pd.DataFrame([
 ('Resumen','Ubicar las cifras principales y sus alcances'),
 ('Colocación','Explorar capital, planes, estados y usuarios'),
 ('Cobranzas','Consultar cobros, conceptos y medios de pago'),
 ('Cartera','Revisar saldos y concentración al corte'),
 ('Proyección y morosidad','Explorar meses y segmentos reportados'),
 ('Calidad y conciliación','Revisar diferencias y filas observadas'),
 ('Diccionario de métricas','Entender fórmulas, fuentes y limitaciones'),
 ('Detalle de Universo','Consultar el alcance y los parámetros de cada archivo'),
],columns=['Vista','Para qué se usa'])

def management_help():
    st.toggle('Preguntas que responde el dashboard',key='show_management_questions')
    with st.expander('Detalle de las vistas'):
        st.table(VIEWS,alt='Opciones de navegación y utilidad de cada vista')

def quality_configuration(page):
    defaults={'tolerance':.02,'blank':'No anulado (regla declarada)',
              'bonifblank':'Sin bonificación (regla declarada)','custom':'{}','customb':'{}'}
    settings=dict(st.session_state.get('_quality_settings',defaults))
    if page=='Calidad y conciliación':
        with st.expander('Configuración de validación',expanded=False):
            for key,value in settings.items():
                st.session_state.setdefault('q_'+key,value)
            settings['tolerance']=st.number_input('Tolerancia monetaria absoluta',min_value=0.,step=.01,key='q_tolerance')
            st.caption('Tolerancia absoluta en ARS. Se informan diferencias sin modificar los valores originales.')
            settings['blank']=st.selectbox('Anulado vacío',['No anulado (regla declarada)','Ambiguo: excluir hasta validar'],key='q_blank')
            settings['bonifblank']=st.selectbox('Bonif vacío',['Sin bonificación (regla declarada)','Ambiguo: observar'],key='q_bonifblank')
            settings['custom']=st.text_area('Mapeo adicional Anulado (JSON)',key='q_custom')
            settings['customb']=st.text_area('Mapeo adicional Bonif (JSON)',key='q_customb')
    try:
        a=json.loads(settings['custom']);b=json.loads(settings['customb'])
        if not isinstance(a,dict) or not isinstance(b,dict) or any(v is not None and not isinstance(v,bool) for v in list(a.values())+list(b.values())):
            raise ValueError()
    except (ValueError,TypeError):
        st.error('Mapeo inválido: usa un objeto JSON con valores true, false o null.')
        st.stop()
    st.session_state['_quality_settings']=settings
    am=DEFAULT_FLAGS|{label(k):v for k,v in a.items()}
    bm=DEFAULT_FLAGS|{label(k):v for k,v in b.items()}
    am['']=False if settings['blank'].startswith('No') else None
    bm['']=False if settings['bonifblank'].startswith('Sin') else None
    return settings['tolerance'],am,bm

def short_reference(kind,cfg,period=None):
    if kind=='cartera':
        cutoff=cfg['corte']
        return 'Corte '+(cutoff.strftime('%d/%m/%Y') if cutoff else 'pendiente')
    return ' a '.join(v.strftime('%d/%m/%Y') for v in period) if period else 'Período sin definir'

def show_universe(reports,names,config,views,periods,management):
    st.subheader('Detalle de Universo')
    st.caption('Alcance, cobertura, parámetros de exportación y filtros de cada archivo. ARS fijo para todas las fuentes.')
    if not reports and not management:
        st.info('No hay fuentes cargadas. Abre Carga de archivos y filtros para incorporar los reportes.')
        return
    st.warning('Los archivos pueden tener poblaciones, períodos y cortes distintos. No se suman fuentes ni se cruzan códigos sin equivalencias validadas.')
    for kind,r in reports.items():
        st.markdown('### '+names[kind])
        cfg=config[kind]
        entities=', '.join(r.data.grupo_1.dropna().astype(str).unique()) or 'Sin identificar'
        branches=', '.join(r.data.sucursal.dropna().astype(str).unique()) if 'sucursal' in r.data else 'Sin dimensión validada'
        filename=r.rows.archivo.iloc[0] if not r.rows.empty else 'Sin filas exportadas'
        details=[('Archivo',filename),('Moneda','ARS'),('Universo / entidades',entities),('Sucursales',branches),
                 ('Granularidad','Imputación a cuota' if kind=='cobranzas' else 'Préstamo por entidad'),
                 ('Detalles originales',str(len(r.data))),('Detalles válidos con filtros',str(len(views[kind]))),
                 ('Referencia seleccionada',short_reference(kind,cfg,periods[kind]))]
        if kind=='cartera':
            details.append(('Origen del corte','Declarado' if cfg['declarado'] else ('Informado' if cfg['corte'] else 'No informado')))
        st.table(pd.DataFrame(details,columns=['Dato','Valor']),alt='Universo de '+names[kind])
        for sheet,params in r.parameters.items():
            st.markdown('**Parámetros originales · '+sheet+'**')
            st.table(pd.DataFrame([(k,str(v) if v not in (None,'') else 'No informado') for k,v in params.items()],columns=['Parámetro','Valor']),alt='Parámetros originales de '+names[kind])
        active={k[len('f_'+kind+'_'):]:str(v) for k,v in st.session_state.items() if k.startswith('f_'+kind+'_') and v}
        st.write('Filtros activos:',active or 'Ninguno')
        st.write('Encabezados detectados (fila):',r.headers)
        for warning in r.warnings:
            st.warning(warning)
    from .management_ui import show_scopes
    show_scopes(management)

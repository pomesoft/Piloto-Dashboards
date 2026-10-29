"""Chat nativo en el tema existente; historial privado con vencimiento."""
import json
import time
import secrets
import re
import pandas as pd
import streamlit as st
from .analytics_context import build_context, context_signature
from .chat_config import read_config
from .query_service import QueryService
from .presentation import fmt
from .chat_quota import LIMIT, browser_quota, reserve_question, take_reserved_question


def floating_chat():
    """Acceso persistente; estilos limitados al botón y su panel de chat."""
    st.html('''<style>
    .st-key-chat_launcher {
        position: fixed;
        right: max(24px, env(safe-area-inset-right));
        bottom: max(24px, env(safe-area-inset-bottom));
        z-index: 1000;
        width: fit-content;
    }
    .st-key-chat_launcher button {
        background-color: #1565C0;
        border-color: #1565C0;
        color: #FFFFFF;
        border-radius: 999px;
        padding: 0.65rem 1rem;
        min-height: 48px;
        box-shadow: 0 4px 18px rgba(23, 43, 77, 0.16);
    }
    .st-key-chat_launcher button:hover,
    .st-key-chat_launcher button:active,
    .st-key-chat_launcher button[aria-expanded="true"] {
        background-color: #0D47A1;
        border-color: #0D47A1;
        color: #FFFFFF;
    }
    .st-key-chat_launcher button:focus-visible {
        outline: 3px solid #64B5F6;
        outline-offset: 3px;
    }
    .st-key-chat_launcher button p {
        font-size: 0.85rem;
        font-weight: 500;
    }
    [data-testid="stPopoverBody"]:has(.st-key-chat_panel) {
        width: min(440px, calc(100vw - 32px));
        max-height: min(680px, calc(100dvh - 112px));
        overflow-y: auto;
        overscroll-behavior: contain;
    }
    @media (max-width: 600px) {
        .st-key-chat_launcher {
            right: max(16px, env(safe-area-inset-right));
            bottom: max(16px, env(safe-area-inset-bottom));
        }
    }
    </style>''')
    return st.popover('Conversá con tus datos', icon=':material/smart_toy:',
                      help='Abrir el chatbot analítico', key='chat_launcher')


def session_for(state, signature, ttl, now=None):
    now = time.monotonic() if now is None else now
    session = state.get('_chat_session')
    changed = session is not None and session['signature'] != signature
    if session is None or changed or now-session['touched'] > ttl:
        session = {'id': secrets.token_hex(16), 'signature': signature,
                   'touched': now, 'history': [], 'turns': [], 'refs': {}, 'last_query': None}
        state['_chat_session'] = session
    return session, changed


def render_result(result):
    status = result['status']
    if status == 'definitions':
        st.write('Definiciones del diccionario del dashboard')
        st.dataframe(pd.DataFrame(result['definitions']), hide_index=True, alt='Definiciones documentadas recuperadas para la pregunta')
        return
    if 'metadata' not in result:
        (st.error if status in ('error', 'denied') else st.info)(result.get('message', 'Sin resultado.'))
        return
    meta = result['metadata']
    metric = result.get('metric')
    if metric:
        values = result.get('values', [])
        if len(values) == 1 and set(values[0]) == {'Valor'}:
            value = values[0]['Valor']
            limited=' · Alcance limitado al archivo' if not meta['coverage_confirmed'] or meta['excluded'] else ''
            st.write(f'**{metric}: {fmt(value, "Proporción" in metric or "Concentración" in metric)}**'+limited)
        elif values:
            st.write('**'+metric+'**')
            st.dataframe(pd.DataFrame(values), hide_index=True, alt='Resultado calculado sobre la fuente consultada')
        if 'change_ratio' in result:
            st.write('Diferencia:', fmt(result['difference']), '· Variación:', fmt(result['change_ratio'], True))
            st.caption('Anterior: '+' a '.join(result['previous_period'])+' · '+result['condition'])
    if result.get('message'):
        (st.info if status != 'ok' else st.caption)(result['message'])
    if meta.get('definition'):
        st.caption(meta['definition'])
    if metric == 'Préstamos otorgados':
        st.caption('“Colocados” se consulta como préstamos otorgados incluidos. Cancelado no equivale a anulado; solo se restringe a Vigente cuando se solicita o está filtrado.')
    if 'records' in result:
        st.dataframe(pd.DataFrame(result['records']), hide_index=True, alt='Detalle autorizado de la consulta')
        st.caption(f'Página desde registro {result["offset"]+1} · Total: {meta["rows"]} · '+('Hay más registros; pide la siguiente página.' if result['has_more'] else 'Fin del detalle.'))
    st.caption('Fuente: '+meta['source']+' · Moneda: ARS · Período: '+(' a '.join(map(str, meta['period'])) if meta['period'] else 'según parámetros del archivo')+' · Corte: '+(meta['cutoff'] or 'no informado'))
    st.caption('Filtros aplicados: '+json.dumps(meta['filters'], ensure_ascii=False, default=str))
    st.caption('Archivo: '+', '.join(meta['files'])+' · Hojas: '+', '.join(meta['sheets']))
    st.caption('Actualización de origen: no informada · Cargado en esta sesión: '+(meta['loaded_at'] or 'no informado'))
    if 'client_coverage' in meta:
        c=meta['client_coverage']
        st.caption(f'Identificación de clientes: {c["identified"]} / {c["rows"]} registros.')
    for warning in meta['warnings']:
        if 'Cobertura temporal' in warning or 'excluidos' in warning or 'conciliación' in warning:
            st.warning(warning)
        else:
            st.caption(warning)


def show_chat(reports, data, periods, config, management, policy, rules):
    settings = read_config(st)
    sources = build_context(reports, data, periods, config, management, st.session_state)
    signature = context_signature(sources, policy, rules)
    session, changed = session_for(st.session_state, signature, settings.session_ttl)
    quota = browser_quota(st.session_state)
    reserved_question = take_reserved_question(st.session_state, quota, signature)
    with floating_chat(), st.container(key='chat_panel'):
        st.subheader('Conversá con tus datos')
        st.caption('Consultas en español · Solo lectura · Usa los filtros activos de cada fuente')
        if quota.get('error'):
            st.warning('No se pudo acceder al almacenamiento local. Habilítalo en tu navegador para usar el chat.')
        elif not quota['ready']:
            st.caption('Verificando preguntas disponibles…')
        elif quota['used'] >= LIMIT:
            st.info('Alcanzaste el límite de 5 preguntas en este navegador.')
        else:
            st.caption(f'Preguntas disponibles: {LIMIT-quota["used"]} de {LIMIT}.')
        if changed:
            st.info('Cambió el alcance de los datos. Se inició una conversación para los filtros y archivos actuales.')
        if st.button('Nueva conversación', key='chat_clear'):
            st.session_state.pop('_chat_session', None)
            st.rerun()
        if not sources:
            st.info('Carga una fuente para comenzar.')
            return
        if not settings.api_key:
            st.info('Chat preparado. Falta configurar OPENAI_API_KEY en el servidor.')
        st.caption('Modelo: '+settings.model+' · Consultas por documento: '+('habilitadas por el servidor' if policy.personal else 'sin permiso'))
        for turn in session['turns']:
            with st.chat_message('user'):
                st.text(re.sub(r'\[persona_[0-9a-f]+\]', '[documento reservado]', turn['question']))
            with st.chat_message('assistant'):
                if turn.get('clarification'):
                    st.write(turn['clarification'])
                for result in turn['results']:
                    render_result(result)
        submitted = st.chat_input('Ej.: ¿Cuántos préstamos del plan 106 tenemos colocados?',
                                 key='analytics_question', disabled=not bool(settings.api_key) or not quota['ready'] or bool(quota.get('error')) or quota['used'] >= LIMIT or bool(st.session_state.get('_chat_pending')), max_chars=2000)
        if submitted:
            if reserve_question(st.session_state, quota, submitted, signature):
                st.rerun()
            return
        question = reserved_question
        if not question:
            return
        session['touched'] = time.monotonic()
        try:
            from .chat_agent import answer
            service = QueryService(sources, policy, session['refs'], last_query=session['last_query'])
            with st.spinner('Consultando los datos…'):
                turn = answer(settings, service, question, session['history'])
            session['turns'] = (session['turns']+[turn])[-12:]
            session['last_query'] = service.last_query
            session['history'].extend([{'role': 'user', 'content': turn['question']},
                {'role': 'assistant', 'content': turn.get('clarification') or ('Estados de las herramientas: '+', '.join(r['status'] for r in turn['results'])+'. '+('Usa la consulta anterior válida para seguimientos.' if service.last_query else 'No se estableció una población para seguimiento.'))}])
            session['history'] = session['history'][-12:]
            retained=json.dumps([session['history'],session['last_query']],default=str)
            session['refs']={k:v for k,v in session['refs'].items() if k in retained}
        except ImportError:
            st.error('Faltan dependencias del chat. Instala requirements.txt en el entorno del servidor.')
            return
        except Exception:
            session['last_query']=None
            session['history']=[]
            session['refs']={}
            st.error('No se pudo completar la consulta. Revisa la configuración de OpenAI o inténtalo nuevamente. No se obtuvo un resultado verificable.')
            return
        st.rerun()

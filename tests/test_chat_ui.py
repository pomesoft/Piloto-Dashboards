"""Interfaz real con AppTest y agente sustituido, sin llamadas a OpenAI."""
from pathlib import Path
from io import BytesIO
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from streamlit.delta_generator import DeltaGenerator
from core.access import AccessPolicy
from core.chat_config import ChatConfig
from tests.test_chat_queries import loan, source
from tests.test_core import fixture
from core.reader import SCHEMAS
from openpyxl import Workbook

APP = Path(__file__).resolve().parents[1]/'app.py'


def synthetic_upload():
    w = Workbook(); sheet = w.active
    sheet.append(['Prestamos Desde:', '01/09/2026'])
    sheet.append(['Prestamos Hasta:', '31/10/2026'])
    sheet.append(SCHEMAS['prestamos'])
    sheet.append(['Entidad']); sheet.append(['Sucursal'])
    sheet.append(loan('1')); sheet.append(loan('2', status='Cancelado'))
    sheet.append(['SubTotal Sucursal']); sheet.append(['SubTotal Comercio'])
    b = BytesIO(); w.save(b); b.name = 'sintetico.xlsx'
    return b


def run_app(policy=AccessPolicy(), key='synthetic-test-key'):
    from contextlib import ExitStack
    stack = ExitStack()
    upload = synthetic_upload()
    uploader = lambda *args, **kw: upload if kw.get('key') == 'upload_prestamos' else None
    stack.enter_context(patch.object(DeltaGenerator, 'file_uploader', uploader))
    stack.enter_context(patch('streamlit.file_uploader', uploader))
    stack.enter_context(patch('core.access.policy_from_settings', return_value=policy))
    stack.enter_context(patch('core.chat_ui.read_config', return_value=ChatConfig(api_key=key)))
    def quota(state):
        used=state.get('_test_browser_used',0)
        pending=state.get('_chat_pending')
        accepted=False
        if pending and state.get('_test_last_request')!=pending['id'] and used<5:
            used+=1
            state['_test_browser_used']=used
            state['_test_last_request']=pending['id']
            accepted=True
        return {'ready':True,'used':used,'error':False,
                'request_id':pending['id'] if pending else None,'accepted':accepted}
    stack.enter_context(patch('core.chat_ui.browser_quota',side_effect=quota))
    return stack, AppTest.from_file(APP, default_timeout=30)


def fake_answer(config, service, question, history=()):
    from core.chat_agent import protect_question
    safe = protect_question(question, service.private_refs)
    if 'vigentes' in question:
        request = {'inherit': True, 'filters': {'estado': ['Vigente']}}
    elif 'DNI' in question:
        request = {'source': 'prestamos', 'metric': 'Préstamos otorgados', 'client_ref': next(iter(service.private_refs))}
    else:
        request = {'source': 'prestamos', 'metric': 'Préstamos otorgados', 'filters': {'plan': ['106']}}
    service.execute(request)
    return {'question': safe, 'results': service.results, 'clarification': None, 'explanation': 'included'}


def test_chat_submission_followup_clear_and_scope_reset():
    stack, at = run_app()
    with stack, patch('core.chat_agent.answer', fake_answer):
        at.run(); assert not at.exception
        at.chat_input(key='analytics_question').set_value('¿Plan 106?').run()
        assert not at.exception
        assert any('Préstamos otorgados: 2,00' in v.value for v in at.markdown)
        at.chat_input(key='analytics_question').set_value('¿Y de esos cuántos vigentes?').run()
        assert not at.exception
        assert any('Préstamos otorgados: 1,00' in v.value for v in at.markdown)
        at.multiselect(key='f_prestamos_estado').select('Vigente').run()
        assert not at.session_state['_chat_session']['turns']
        at.button(key='chat_clear').click().run()
        assert not at.session_state['_chat_session']['history']


def test_personal_default_is_server_denied_even_if_widget_state_tampered():
    stack, at = run_app()
    with stack, patch('core.chat_agent.answer', fake_answer):
        at.run(); at.sidebar.radio[0].set_value('Colocación').run()
        assert at.checkbox(key='prestamos_detalle_pii').disabled
        at.session_state['prestamos_detalle_pii'] = True
        at.run()
        assert all('documento' not in df.value.columns for df in at.dataframe)
        at.chat_input(key='analytics_question').set_value('DNI 2323232323').run()
        assert not at.exception
        assert any('Acceso no autorizado' in e.value for e in at.error)
        assert '2323232323' not in str(at.session_state['_chat_session']['history'])


def test_missing_key_no_query_and_failure_does_not_save_partial_results():
    stack, at = run_app(key='')
    with stack:
        at.run()
        assert at.chat_input(key='analytics_question').disabled
        assert any('OPENAI_API_KEY' in x.value for x in at.info)
    stack, at = run_app()
    with stack, patch('core.chat_agent.answer', side_effect=RuntimeError('secret-exception')):
        at.run(); at.chat_input(key='analytics_question').set_value('Plan 106').run()
        assert any('No se pudo completar' in x.value for x in at.error)
        assert 'secret-exception' not in str([x.value for x in at.error])
        assert not at.session_state['_chat_session']['turns']


def test_five_questions_then_block_even_after_new_conversation():
    stack,at=run_app()
    with stack,patch('core.chat_agent.answer',side_effect=fake_answer) as answer:
        at.run()
        for _ in range(5):
            at.chat_input(key='analytics_question').set_value('Plan 106').run()
            assert not at.exception
        assert answer.call_count==5
        assert at.chat_input(key='analytics_question').disabled
        assert any('límite de 5 preguntas' in e.value for e in at.info)
        at.button(key='chat_clear').click().run()
        assert at.chat_input(key='analytics_question').disabled
        assert answer.call_count==5

"""Casos sintéticos aislados: jamás se cargan como cifras reales del dashboard."""
from dataclasses import replace
from datetime import date
import pandas as pd
import pytest
from core.access import AccessPolicy, policy_from_settings, scoped_report
from core.analytics_context import SourceContext, context_signature
from core.query_service import QueryService
from core.chat_ui import session_for
from core.chat_agent import protect_question
from core.validation import validate
from tests.test_core import fixture


def loan(key, document='2323232323', plan='106 - Plan prueba', status='Vigente', capital=100, day='01/10/2026'):
    return ['001', 'Persona prueba', document, key, day, 3, plan, capital, 2, 0, 102, 0, 102, status, 'Operador']


def source(rows=None):
    r = fixture('prestamos', rows or [loan('01'), loan('02', status='Cancelado'), loan('03', document='00000001', plan='108')])
    r.parameters = {'Sheet': {'Prestamos Desde': '01/09/2026', 'Prestamos Hasta': '31/10/2026'}}
    return SourceContext(r, validate(r)[0], period=(date(2026, 10, 1), date(2026, 10, 29)), fingerprint='test')


def service(src=None, policy=None):
    return QueryService({'prestamos': src or source()}, policy or AccessPolicy(personal=True), {'persona_test': '2323232323'})


def query(**kwargs):
    return dict(source='prestamos', metric='Préstamos otorgados', **kwargs)


def test_plan_106_matches_independent_count_and_dashboard():
    s = service()
    r = s.execute(query(filters={'plan': ['106']}))
    d = s.sources['prestamos'].data
    independent = d[d.incluido & d.plan.eq('106 - Plan prueba')]
    expected = len(set(zip(independent.grupo_1, independent.prestamo)))
    assert r['values'] == [{'Valor': expected}] == [{'Valor': 2}]
    from core.metrics import metrics
    assert expected == metrics(independent, 'prestamos')['Préstamos otorgados']


def test_dni_and_followup_preserve_population():
    s = service()
    assert s.execute(query(client_ref='persona_test'))['values'] == [{'Valor': 2}]
    r = s.execute({'inherit': True, 'filters': {'estado': ['Vigente']}})
    assert r['values'] == [{'Valor': 1}]
    assert s.last_query['client_ref'] == 'persona_test'


def test_plan_followup_and_active_filters():
    s = service(replace(source(), filters={'plan': ['106 - Plan prueba']}))
    assert s.execute(query())['values'] == [{'Valor': 2}]
    assert s.execute({'inherit': True, 'filters': {'estado': ['Vigente']}})['values'] == [{'Valor': 1}]
    conflict = s.execute(query(filters={'plan': ['108']}))
    assert conflict['status'] == 'clarification'
    assert s.execute(query(filters={'plan': ['108']}, override_filters=True))['values'] == [{'Valor': 1}]


def test_duplicate_keys_excluded_not_silently_counted():
    s = service(source([loan('01'), loan('01'), loan('02')]))
    r = s.execute(query())
    assert r['values'] == [{'Valor': 1}]
    assert r['metadata']['excluded'] == 2
    assert any('excluidos' in v for v in r['metadata']['warnings'])


def test_duplicate_codes_in_different_entities_count_separately():
    src = source()
    d = src.data.iloc[[0, 0]].copy()
    d['grupo_1'] = ['A', 'B']; d['entidad'] = ['A', 'B']
    src.data = d
    assert service(src).execute(query())['values'] == [{'Valor': 2}]


def test_zero_missing_empty_unknown_are_distinct():
    s = service(source([loan('01', capital=0)]))
    assert s.execute({'source': 'prestamos', 'metric': 'Capital colocado'})['values'] == [{'Valor': 0.0}]
    r = s.execute(query(filters={'plan': ['999']}))
    assert r['status'] == 'empty' and r['values'] == [{'Valor': 0}]
    r = service(source([loan('01', capital=None)])).execute({'source': 'prestamos', 'metric': 'Capital colocado'})
    assert r['status'] == 'unavailable' and r['values'] == [{'Valor': None}]
    assert s.execute({'source': 'cartera', 'metric': 'Capital pendiente'})['status'] == 'unavailable'
    assert s.execute({'source': 'prestamos', 'metric': 'rentabilidad inventada'})['status'] == 'clarification'


def test_dni_absence_never_claims_client_does_not_exist():
    s = service(); s.private_refs['missing'] = '9999999999'
    r = s.execute(query(client_ref='missing'))
    assert r['status'] == 'empty'
    assert 'no acredita' in r['metadata']['warnings'][0]
    assert r['metadata']['lookup_state']=='not_found_in_source'


def test_document_format_and_empty_scope_are_distinct_from_absent_record():
    s=service(source([loan('1',document='2.323.232.323',day='01/09/2026')]))
    r=s.execute(query(client_ref='persona_test'))
    assert r['status']=='empty' and r['metadata']['lookup_state']=='outside_result'
    r=s.execute(query(client_ref='persona_test',period=['2026-09-01','2026-09-30']))
    assert r['values']==[{'Valor':1}]


def test_denied_dni_detail_and_source():
    s = service(policy=AccessPolicy(personal=False, detail=False))
    assert s.execute(query(client_ref='persona_test')) == {'status': 'denied', 'message': 'Acceso no autorizado.', 'evidence_id': '1'}
    assert s.execute(query(operation='detail'))['status'] == 'denied'
    s = service(policy=AccessPolicy(sources=()))
    assert s.execute(query())['status'] == 'denied'
    assert s.catalog()['sources'] == {}


def test_server_scope_cannot_be_overridden():
    src = source(); src.data.loc[src.data.index[0], 'entidad'] = 'Otra entidad'
    s = service(src, AccessPolicy(entities=('Entidad',)))
    assert s.execute(query())['values'] == [{'Valor': 2}]
    assert s.execute(query(filters={'entidad': ['Otra entidad']}, override_filters=True))['values'] == [{'Valor': 0}]
    scoped = scoped_report(src.report, AccessPolicy(entities=('Entidad',)))
    assert scoped.parameters == {}
    assert scoped.rows.clasificacion.eq('detalle').all()


def test_detail_pages_do_not_disclose_pii_without_permission():
    s = service(source([loan(str(i)) for i in range(25)]), AccessPolicy())
    r = s.execute(query(operation='detail'))
    assert len(r['records']) == 20 and r['has_more']
    assert not {'documento', 'apellido_y_nombre', 'cliente', 'prestamo'} & set(r['records'][0])
    assert 'fila' in r['records'][0]
    r = s.execute({'inherit': True, 'offset': 20})
    assert len(r['records']) == 5 and not r['has_more']


def test_ambiguous_plan_requires_clarification():
    s = service(source([loan('1', plan='106 - A'), loan('2', plan='106 - B')]))
    assert s.execute(query(filters={'plan': ['106']}))['status'] == 'clarification'


def test_monthly_comparison_direct_and_coverage():
    s = service(source([loan('1', capital=200), loan('2', day='01/09/2026', capital=100)]))
    r = s.execute({'source': 'prestamos', 'metric': 'Capital colocado', 'operation': 'compare'})
    assert r['values'] == [{'Período': 'Actual', 'Valor': 200.0}, {'Período': 'Anterior', 'Valor': 100.0}]
    assert r['difference'] == 100 and r['change_ratio'] == 1
    assert r['previous_period'] == ['2026-09-01', '2026-09-29']
    assert s.execute({'source': 'prestamos', 'metric': 'Capital colocado', 'operation': 'compare',
                      'period': ['2026-10-02', '2026-10-29']})['status'] == 'unavailable'
    assert s.execute({'source': 'prestamos', 'metric': 'Capital colocado', 'operation': 'compare',
                      'period': ['2026-09-01', '2026-09-29']})['status'] == 'unavailable'


def test_zero_previous_period_variation_unavailable():
    s = service(source([loan('1'), loan('2', capital=0, day='01/09/2026')]))
    r = s.execute({'source': 'prestamos', 'metric': 'Capital colocado', 'operation': 'compare'})
    assert r['difference'] == 100 and r['change_ratio'] is None


def test_unknown_coverage_never_reported_complete():
    src = source(); src.report.parameters = {}
    r = service(src).execute(query())
    assert r['metadata']['coverage_confirmed'] is False


def test_scope_and_references_do_not_cross_sessions():
    a, _ = session_for({}, 'signature', 60, now=0)
    b, _ = session_for({}, 'signature', 60, now=0)
    assert a['id'] != b['id'] and a['refs'] is not b['refs']
    state = {'_chat_session': a}; a['refs']['x'] = 'private'
    new, changed = session_for(state, 'changed', 60, now=1)
    assert changed and not new['refs']
    expired, _ = session_for(state, 'changed', 60, now=100)
    assert expired['id'] != new['id']


def test_signatures_invalidate_on_rule_policy_source_filter_changes():
    src = source(); p = AccessPolicy()
    baseline = context_signature({'prestamos': src}, p, {})
    assert baseline != context_signature({'prestamos': src}, replace(p, personal=True), {})
    assert baseline != context_signature({'prestamos': replace(src, fingerprint='new')}, p, {})
    assert baseline != context_signature({'prestamos': replace(src, filters={'plan': ['106']})}, p, {})
    assert baseline != context_signature({'prestamos': src}, p, {'tolerance': 1})


def test_document_redaction_and_private_refs():
    refs = {}
    safe = protect_question('DNI 2323232323 y documento 23.232.323', refs)
    assert '2323232323' not in safe and '23.232.323' not in safe
    assert set(refs.values()) == {'2323232323', '23232323'}
    assert '106' in protect_question('plan 106', refs)


def test_oidc_identity_only_from_server_and_deny_by_default():
    settings = {'mode': 'oidc', 'users': {'issuer|user': {'entities': ['A'], 'personal': True}}}
    assert not policy_from_settings(settings).allowed
    assert not policy_from_settings(settings, {'iss': 'issuer', 'sub': 'unknown'}).allowed
    assert policy_from_settings(settings, {'iss': 'issuer', 'sub': 'user'}).personal
    assert not policy_from_settings({}).personal


def test_document_multiple_clients_requires_explicit_resolution():
    src=source()
    src.data.loc[src.data.index[1], 'cliente']='otro-cliente'
    s=service(src)
    assert s.execute(query(client_ref='persona_test'))['status']=='clarification'
    assert s.execute(query(client_ref='persona_test',combine_document_matches=True))['values']==[{'Valor':2}]
    assert s.execute({'inherit':True,'filters':{'estado':['Vigente']}})['values']==[{'Valor':1}]


def test_grouped_amounts_match_direct_and_incomplete_group_not_partial():
    s=service(source([loan('1',capital=100),loan('2',capital=200),loan('3',plan='108',capital=None)]))
    r=s.execute({'source':'prestamos','metric':'Capital colocado','group_by':'plan'})
    assert r['status']=='unavailable'
    assert r['values']==[{'plan':'106 - Plan prueba','Valor':300.0},{'plan':'108','Valor':None}]


def test_quality_requires_audit_and_does_not_replace_followup_population():
    s=service(source([loan('1'),loan('1'),loan('2')]))
    r=s.execute({'source':'prestamos','operation':'quality'})
    assert r['values'][1]['Valor']==2
    s=service(policy=AccessPolicy(audit=False))
    assert s.execute({'source':'prestamos','operation':'quality'})['status']=='denied'


def test_management_aggregate_has_own_filters_and_cannot_answer_dni():
    from core.management import read_management,validate_management,PLAN_HEADERS
    from io import BytesIO
    from openpyxl import Workbook
    w=Workbook();sh=w.active;sh.append(PLAN_HEADERS)
    sh.append(['106',2,100,2,0,102,0,102,20]);sh.append(['108',3,200,4,0,204,0,204,40])
    b=BytesIO();w.save(b)
    report=read_management(b.getvalue(),'sintetico.xlsx','planes_gerencial')
    src=SourceContext(report,validate_management(report)[0],filters={'plan':['106']})
    s=QueryService({'planes_gerencial':src},AccessPolicy(personal=True),{'private':'2323232323'})
    r=s.execute({'source':'planes_gerencial','metric':'Préstamos reportados por plan'})
    assert r['values']==[{'Valor':2.0}]
    assert s.execute({'source':'planes_gerencial','metric':'Préstamos reportados por plan','client_ref':'private'})['status']=='unavailable'
    s.policy=AccessPolicy(entities=('A',))
    assert s.execute({'source':'planes_gerencial','metric':'Préstamos reportados por plan'})['status']=='denied'


def test_failed_query_cannot_reuse_unrelated_previous_population():
    s=service(policy=AccessPolicy(personal=False))
    assert s.execute(query())['status']=='ok'
    assert s.execute(query(client_ref='persona_test'))['status']=='denied'
    assert s.last_query is None
    assert s.execute({'inherit':True,'filters':{'estado':['Vigente']}})['status']=='clarification'

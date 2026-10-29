from core.chat_quota import reserve_question,take_reserved_question


def test_reservation_requires_storage_ack_before_execution_and_is_once_only():
    state={}
    assert reserve_question(state,{'ready':True,'used':0},'Pregunta','scope')
    pending=state['_chat_pending']
    assert take_reserved_question(state,{'ready':True},'scope') is None
    ack={'ready':True,'used':1,'request_id':pending['id'],'accepted':True}
    assert take_reserved_question(state,ack,'scope')=='Pregunta'
    assert take_reserved_question(state,ack,'scope') is None


def test_limit_storage_failure_and_stale_scope_never_execute():
    for quota in ({'ready':False,'used':0},{'ready':True,'used':5},
                  {'ready':True,'used':0,'error':True}):
        assert not reserve_question({},quota,'Pregunta','scope')
    state={}
    reserve_question(state,{'ready':True,'used':4},'Última pregunta','scope')
    ack={'ready':True,'used':5,'request_id':state['_chat_pending']['id'],'accepted':True}
    assert take_reserved_question(state,ack,'otro-scope') is None
    assert '_chat_pending' not in state


def test_denied_reservation_does_not_reach_model():
    state={}
    reserve_question(state,{'ready':True,'used':4},'Pregunta','scope')
    ack={'ready':True,'used':5,'request_id':state['_chat_pending']['id'],'accepted':False}
    assert take_reserved_question(state,ack,'scope') is None

"""Cupo por navegador: reserva persistida antes de invocar el modelo."""
import secrets
import streamlit as st

LIMIT = 5
STORAGE_KEY = 'piloto-dashboard.chat.questions.v1'

_QUOTA = st.components.v2.component(
    'chat_local_quota',
    html='<span aria-hidden="true"></span>',
    js='''
const instances = new WeakMap();
export default function(component) {
  const { parentElement, data, setStateValue } = component;
  let instance = instances.get(parentElement);
  if (!instance) {
    instance = { last: null, data: null, publish: null };
    instances.set(parentElement, instance);
  }
  instance.data = data;
  instance.publish = setStateValue;
  const emit = (value) => {
    const encoded = JSON.stringify(value);
    if (instance.last !== encoded) {
      instance.last = encoded;
      instance.publish('quota', value);
    }
  };
  const sync = async () => {
    const current = instance.data;
    try {
      if (!navigator.locks) throw new Error('storage unavailable');
      await navigator.locks.request(current.storage_key, () => {
        const raw = localStorage.getItem(current.storage_key);
        const saved = raw === null ? {used: 0, requests: []} : JSON.parse(raw);
        if (!Number.isInteger(saved.used) || saved.used < 0 || saved.used > 5 ||
            !Array.isArray(saved.requests) || saved.requests.length > 5 ||
            saved.requests.some(id => typeof id !== 'string')) throw new Error('invalid quota');
        let accepted = false;
        if (current.request_id) {
          accepted = saved.requests.includes(current.request_id);
          if (!accepted && saved.used < 5) {
            saved.used += 1;
            saved.requests.push(current.request_id);
            accepted = true;
          }
        }
        // También comprueba escritura: no habilitar el chat si el navegador la bloquea.
        localStorage.setItem(current.storage_key, JSON.stringify(saved));
        emit({used: saved.used, error: false, request_id: current.request_id, accepted});
      });
    } catch (_) {
      emit({used: 5, error: true, request_id: current.request_id, accepted: false});
    }
  };
  if (!instance.listener) {
    instance.listener = event => {
      if (event.key === instance.data.storage_key || event.key === null) sync();
    };
    window.addEventListener('storage', instance.listener);
  }
  sync();
  return () => {
    window.removeEventListener('storage', instance.listener);
    instances.delete(parentElement);
  };
}
''')


def browser_quota(state):
    pending = state.get('_chat_pending')
    result = _QUOTA(key='chat_browser_quota',
        data={'storage_key': STORAGE_KEY, 'request_id': pending['id'] if pending else None},
        default={'quota': None}, on_quota_change=lambda: None, height=0)
    value = result.quota
    if not isinstance(value, dict):
        return {'ready': False, 'used': LIMIT, 'error': False}
    used = value.get('used')
    if type(used) is not int or not 0 <= used <= LIMIT:
        return {'ready': False, 'used': LIMIT, 'error': True}
    state['_chat_quota_used'] = max(state.get('_chat_quota_used', 0), used)
    return {**value, 'used': state['_chat_quota_used'], 'ready': True}


def reserve_question(state, quota, question, signature):
    if not quota.get('ready') or quota.get('error') or quota['used'] >= LIMIT or state.get('_chat_pending'):
        return False
    state['_chat_pending'] = {'id': secrets.token_hex(16), 'question': question, 'signature': signature}
    return True


def take_reserved_question(state, quota, signature):
    pending = state.get('_chat_pending')
    if not pending or quota.get('request_id') != pending['id']:
        return None
    if not quota.get('ready'):
        return None
    state.pop('_chat_pending', None)
    if quota.get('error') or not quota.get('accepted') or pending['signature'] != signature:
        return None
    return pending['question']

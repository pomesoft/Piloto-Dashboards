"""Política de servidor común para dashboard, exportaciones y chat."""
from dataclasses import dataclass
from dataclasses import replace


@dataclass(frozen=True)
class AccessPolicy:
    subject: str = 'local'
    allowed: bool = True
    personal: bool = False
    detail: bool = True
    audit: bool = True
    sources: tuple | None = None
    entities: tuple | None = None
    branches: tuple | None = None

    def permits(self, source):
        return self.allowed and (self.sources is None or source in self.sources)

    def restrict(self, data, source):
        if not self.permits(source):
            raise PermissionError('Acceso no autorizado.')
        out = data
        for column, values in [('entidad', self.entities), ('sucursal', self.branches)]:
            if values is not None:
                if column not in out:
                    raise PermissionError('La fuente no permite aplicar el alcance autorizado.')
                out = out[out[column].astype(str).isin(values)]
        return out.copy()

    @property
    def scoped(self):
        return self.entities is not None or self.branches is not None


def scoped_report(report, policy):
    """Los controles de población completa no se exponen a usuarios parciales."""
    data = policy.restrict(report.data, report.kind)
    if not policy.scoped:
        return report
    keys = data[['hoja', 'fila']].drop_duplicates()
    rows = report.rows.merge(keys, on=['hoja', 'fila'], how='inner')
    return replace(report, data=data, rows=rows, parameters={},
                   warnings=['Alcance restringido por permisos. Controles globales y parámetros originales ocultos.'])


def policy_from_settings(settings, claims=None):
    mode = settings.get('mode', 'local')
    if mode == 'local':
        entry = settings.get('local', {})
        subject = 'local'
    elif mode == 'oidc':
        claims = claims or {}
        # issuer + sub: nunca se acepta identidad proporcionada por el chat.
        subject = str(claims.get('iss', '')) + '|' + str(claims.get('sub', ''))
        entry = settings.get('users', {}).get(subject)
        if not claims.get('sub') or entry is None:
            return AccessPolicy(subject=subject, allowed=False)
    else:
        return AccessPolicy(allowed=False)
    return AccessPolicy(subject=subject, allowed=True,
        personal=entry.get('personal', False) is True,
        detail=entry.get('detail', True) is True,
        audit=entry.get('audit', mode == 'local') is True,
        sources=tuple(entry['sources']) if 'sources' in entry else None,
        entities=tuple(entry['entities']) if 'entities' in entry else None,
        branches=tuple(entry['branches']) if 'branches' in entry else None)


def setup_access(st):
    try:
        settings = dict(st.secrets.get('access', {}))
    except FileNotFoundError:
        settings = {}
    if settings.get('mode', 'local') == 'local':
        if st.get_option('server.address') not in ('127.0.0.1', 'localhost', '::1'):
            st.error('El modo local requiere escuchar en 127.0.0.1. Configura OIDC para uso compartido.')
            st.stop()
        policy = policy_from_settings(settings)
    else:
        if not st.user.is_logged_in:
            st.info('Inicia sesión para consultar el dashboard.')
            if st.button('Iniciar sesión'):
                st.login()
            st.stop()
        policy = policy_from_settings(settings, dict(st.user))
        if st.sidebar.button('Cerrar sesión'):
            st.session_state.clear()
            st.logout()
            st.stop()
    if not policy.allowed:
        st.session_state.clear()
        st.error('Tu usuario no tiene acceso a este dashboard.')
        st.stop()
    previous=st.session_state.get('_access_policy')
    if previous is not None and previous != policy:
        st.session_state.clear()
    st.session_state['_access_policy'] = policy
    return policy

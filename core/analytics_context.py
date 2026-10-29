"""Instantánea de fuentes, filtros y reglas; sin estado global de usuarios."""
from dataclasses import dataclass, field
from hashlib import sha256
import json

DIMENSIONS = ('entidad', 'sucursal', 'plan', 'estado', 'usuario', 'tipo_de_pago', 'hoja', 'anio', 'mes')


@dataclass
class SourceContext:
    report: object
    data: object
    filters: dict = field(default_factory=dict)
    period: tuple | None = None
    cutoff: object = None
    fingerprint: str = ''
    loaded_at: str = ''
    controls: object = None


def build_context(reports, data, periods, config, management, state):
    sources = {}
    for kind, report in reports.items():
        sources[kind] = SourceContext(report, data[kind], period=periods.get(kind),
            cutoff=config[kind].get('corte'))
    for kind, src in management.items():
        sources[kind] = SourceContext(src['report'], src['data'], controls=src['controls'])
    for kind, src in sources.items():
        src.filters = {dim: state['f_'+kind+'_'+dim] for dim in DIMENSIONS
                       if state.get('f_'+kind+'_'+dim) not in (None, [])}
        src.fingerprint = state.get('source_hash_'+kind, '')
        src.loaded_at = state.get('source_loaded_'+kind, '')
    return sources


def context_signature(sources, policy, rules):
    payload = {kind: {'hash': src.fingerprint, 'filters': src.filters,
                     'period': src.period, 'cutoff': src.cutoff}
               for kind, src in sources.items()}
    return sha256(json.dumps([payload, vars(policy), rules], default=str,
                             sort_keys=True).encode()).hexdigest()

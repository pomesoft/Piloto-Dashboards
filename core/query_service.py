"""Consultas de solo lectura: operaciones permitidas, nunca código del modelo."""
from dataclasses import dataclass, field
import re
import math
import pandas as pd
from .analytics_context import DIMENSIONS
from .metrics import metrics, dictionary, unique_loans, total, ratio, previous_period
from .management import management_metrics, management_dictionary, MANAGEMENT_NAMES
from .normalization import label
from .validation import coverage

SOURCE_NAMES = {'prestamos': 'Préstamos Detalle', 'cobranzas': 'Cobranzas Detalle',
                'cartera': 'Saldo de la Cartera', **MANAGEMENT_NAMES}
PRIVATE = {'apellido_y_nombre', 'documento', 'cuil', 'cliente', 'prestamo', 'solicitud'}


def document_key(value):
    if value is None or pd.isna(value):
        return None
    text=str(value).strip()
    return re.sub(r'[.\s-]', '', text) if re.fullmatch(r'[\d.\s-]+', text) else text


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.date().isoformat()
    if hasattr(value, 'item'):
        return clean(value.item())
    return value


class QueryProblem(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def apply_dimensions(data, filters):
    out = data
    for dim, selected in filters.items():
        if dim not in DIMENSIONS:
            raise QueryProblem('unsupported', 'Ese filtro no está habilitado.')
        if not selected:
            continue
        if dim == 'mes' and 'periodo' in out:
            out = out[out.periodo.dt.month.isin([int(v) for v in selected])]
        elif dim not in out:
            raise QueryProblem('unavailable', 'La fuente no dispone de la dimensión solicitada.')
        else:
            out = out[out[dim].astype(str).isin([str(v) for v in selected])]
    return out.copy()


def metric_values(data, source):
    return metrics(data, source) if source in ('prestamos', 'cobranzas', 'cartera') else management_metrics(data, source)


@dataclass
class QueryService:
    sources: dict
    policy: object
    private_refs: dict = field(default_factory=dict)
    results: list = field(default_factory=list)
    last_query: dict | None = None
    max_calls: int = 8

    def catalog(self):
        definitions = pd.concat([dictionary(), management_dictionary()], ignore_index=True)
        return {'sources': {kind: {'name': SOURCE_NAMES[kind],
                    'metrics': list(metric_values(src.data.iloc[:0], kind)),
                    'dimensions': [d for d in DIMENSIONS if d in src.data or (d == 'mes' and 'periodo' in src.data)],
                    'active_filters': clean(src.filters), 'period': [str(v) for v in src.period] if src.period else None,
                    'cutoff': str(src.cutoff) if src.cutoff else None}
                for kind, src in self.sources.items() if self.policy.permits(kind)},
                'definitions': definitions.to_dict('records'),
                'personal_allowed': self.policy.personal, 'detail_allowed': self.policy.detail}

    def resolve_plan(self, data, value):
        if 'plan' not in data:
            raise QueryProblem('unavailable', 'La fuente no contiene planes.')
        options = data.plan.dropna().astype(str).unique().tolist()
        exact = [v for v in options if v == value]
        if exact:
            return exact[0]
        matches = [v for v in options if re.match(r'^'+re.escape(value)+r'(?:\s*-|\s|$)', v)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise QueryProblem('clarification', 'El código corresponde a varios planes. Selecciona el nombre completo en el filtro del dashboard.')
        return value

    def execute(self, request):
        if len(self.results) >= self.max_calls:
            self.last_query = None
            result = {'status': 'limit', 'message': 'Se alcanzó el límite de consultas por pregunta.',
                      'evidence_id': str(len(self.results)+1)}
            self.results.append(result)
            return result
        try:
            result, effective = self._execute(request)
        except PermissionError:
            result, effective = {'status': 'denied', 'message': 'Acceso no autorizado.'}, None
        except QueryProblem as exc:
            result, effective = {'status': exc.status, 'message': exc.message}, None
        except (KeyError, ValueError, TypeError):
            result, effective = {'status': 'error', 'message': 'No se pudo completar la consulta. Revisa los filtros o inténtalo nuevamente.'}, None
        result = clean(result)
        result['evidence_id'] = str(len(self.results) + 1)
        self.results.append(result)
        if effective is not None:
            self.last_query = effective
        elif result['status'] not in ('ok', 'definitions'):
            # Un seguimiento nunca debe heredar otra población tras una consulta fallida.
            self.last_query = None
        return result

    def _execute(self, request):
        inherited = dict(self.last_query or {}) if request.get('inherit') else {}
        if request.get('inherit') and not inherited:
            raise QueryProblem('clarification', 'No hay una consulta anterior válida. Indica la población que quieres consultar.')
        q = inherited | {k: v for k, v in request.items() if v is not None and k != 'inherit'}
        source = q.get('source')
        if not self.policy.permits(source):
            raise PermissionError()
        if q.get('client_ref') and not self.policy.personal:
            raise PermissionError()
        if source not in self.sources:
            raise QueryProblem('unavailable', 'La fuente necesaria no está cargada.')
        src = self.sources[source]
        # Reaplicar autorización incluso si la UI ya restringió la fuente.
        raw = self.policy.restrict(src.data, source)
        filters = dict(inherited.get('filters', src.filters))
        for dim, values in (request.get('filters') or {}).items():
            if dim not in DIMENSIONS:
                raise QueryProblem('unsupported', 'Ese filtro no está habilitado.')
            if dim in filters and filters[dim] and values and set(map(str, values)) != set(map(str, filters[dim])) and not request.get('override_filters'):
                raise QueryProblem('clarification', 'La pregunta contradice un filtro activo. Confirma si deseas reemplazarlo.')
            filters[dim] = values
        if source == 'cartera' and not src.cutoff:
            raise QueryProblem('unavailable', 'Falta informar o declarar el corte de cartera.')
        for dim in filters:
            if dim == 'plan' and filters[dim]:
                filters[dim] = [self.resolve_plan(raw, str(v)) for v in filters[dim]]
            elif dim == 'estado' and filters[dim] and 'estado' in raw:
                normalized = [label(v).removesuffix('s') for v in filters[dim]]
                matches = raw.estado.dropna().astype(str).unique()
                filters[dim] = [v for v in matches if label(v) in normalized]
                if not filters[dim]:
                    raise QueryProblem('clarification', 'El estado solicitado no coincide con los estados de la fuente.')
        population = apply_dimensions(raw, filters)
        document_coverage = None
        if 'documento' in population:
            document_coverage = {'identified': int(population.documento.notna().sum()), 'rows': len(population)}
        excluded = int((~population.incluido).sum())
        base = population[population.incluido].copy()
        client_ref = q.get('client_ref')
        if client_ref:
            if client_ref not in self.private_refs:
                raise QueryProblem('clarification', 'Indica el documento del cliente en tu pregunta.')
            if 'documento' not in base:
                raise QueryProblem('unavailable', 'La fuente no contiene Documento. No se deduce DNI a partir de CUIL.')
            # Documento se compara como texto; no se infiere identidad entre entidades.
            doc = document_key(self.private_refs[client_ref])
            source_matches = raw.documento.map(document_key).eq(doc)
            population = population[population.documento.map(document_key).eq(doc)]
            identities = population[['grupo_1', 'cliente']].drop_duplicates()
            if len(identities) > 1 and not q.get('combine_document_matches'):
                raise QueryProblem('clarification', 'El documento está asociado a varios clientes o entidades. Acota la entidad o confirma si deseas contar todos los préstamos asociados a ese documento.')
            excluded = int((~population.incluido).sum())
            base = population[population.incluido].copy()
        period = q.get('period', src.period)
        if source in ('prestamos', 'cobranzas'):
            if not period or len(period) != 2:
                raise QueryProblem('clarification', 'Completa las dos fechas del período.')
            start, end = (pd.Timestamp(v) for v in period)
            if pd.isna(start) or pd.isna(end) or start > end or start.tzinfo or end.tzinfo:
                raise QueryProblem('clarification', 'El período no es válido.')
            datecol = 'fec_cobro' if source == 'cobranzas' else 'fecha'
            data = base[base[datecol].between(start, end)]
            period = [start.date().isoformat(), end.date().isoformat()]
            ranges = coverage(src.report)
            covered = len(ranges) == 1 and pd.notna(ranges[0][1]) and pd.notna(ranges[0][2]) and start >= ranges[0][1] and end <= ranges[0][2]
        elif source == 'proyeccion' and period:
            if len(period) != 2:
                raise QueryProblem('clarification', 'Indica ambas fechas de proyección.')
            start, end = (pd.Timestamp(v) for v in period)
            if pd.isna(start) or pd.isna(end) or start > end:
                raise QueryProblem('clarification', 'El período no es válido.')
            data = base[base.periodo.between(start, end)]
            covered = False
        else:
            if request.get('period'):
                raise QueryProblem('unavailable', 'La fuente es una fotografía o agregado: no permite reconstruir otro período.')
            data, covered = base, False
        if source in MANAGEMENT_NAMES and 'hoja' in data and data.hoja.nunique() > 1:
            raise QueryProblem('clarification', 'Selecciona una hoja: no se suman poblaciones gerenciales entre hojas.')
        metric = q.get('metric')
        operation = q.get('operation', 'aggregate')
        group = q.get('group_by')
        if group and (group not in DIMENSIONS or group not in data):
            raise QueryProblem('unavailable', 'La agrupación solicitada no está disponible.')
        effective = {'source': source, 'filters': filters, 'period': period,
                     'client_ref': client_ref, 'metric': metric, 'group_by': group,
                     'operation': operation, 'offset': q.get('offset', 0),
                     'combine_document_matches': q.get('combine_document_matches', False)}
        meta = {'source': SOURCE_NAMES[source], 'source_key': source,
                'filters': filters, 'period': period, 'cutoff': str(src.cutoff) if src.cutoff else None,
                'origin_updated_at': None, 'loaded_at': src.loaded_at or None,
                'files': sorted(src.report.rows.archivo.dropna().astype(str).unique()) if 'archivo' in src.report.rows else [],
                'sheets': sorted(data.hoja.dropna().astype(str).unique()) if 'hoja' in data else [],
                'coverage_confirmed': bool(covered), 'rows': len(data), 'excluded': excluded,
                'warnings': ['Resultado limitado al archivo cargado; no acredita existencia o ausencia en el sistema de origen.']}
        if 'cliente' in data:
            meta['client_coverage'] = {'identified': int(data.cliente.notna().sum()), 'rows': len(data)}
            if data.cliente.isna().any():
                meta['warnings'].append('La cantidad de clientes comprende solo códigos identificados; hay registros sin cliente.')
        if client_ref and document_coverage and document_coverage['identified'] < document_coverage['rows']:
            meta['warnings'].append('Existen registros sin Documento. La búsqueda no cubre esos registros.')
        if client_ref:
            meta['lookup_state'] = ('included' if len(data) else
                ('excluded_only' if len(population) and not population.incluido.any() else
                 ('outside_result' if source_matches.any() else 'not_found_in_source')))
            if not len(data):
                meta['warnings'].append({
                    'excluded_only':'El documento tiene registros en el alcance, pero están excluidos por validación.',
                    'outside_result':'El documento aparece en la fuente autorizada, pero no hay préstamos incluidos con estos filtros y período.',
                    'not_found_in_source':'Documento no encontrado en esta fuente autorizada; no prueba inexistencia del cliente en el sistema.'
                }[meta['lookup_state']])
        if not covered:
            meta['warnings'].append('Cobertura temporal completa no confirmada; no se presenta como total de toda la organización.')
        if excluded:
            meta['warnings'].append('Hay registros excluidos por las reglas de calidad. El resultado corresponde a registros incluidos.')
        if source in MANAGEMENT_NAMES:
            meta['warnings'].extend(src.report.warnings)
        if metric:
            definitions = dictionary() if source in ('prestamos', 'cobranzas', 'cartera') else management_dictionary()
            matching = definitions[definitions.Métrica.eq(metric)]
            if not matching.empty:
                meta['definition'] = matching.iloc[0]['Fórmula']+' · '+matching.iloc[0]['Interpretación y limitaciones']
        if src.controls is not None and not src.controls.empty and src.controls.estado.eq('Diferencia').any():
            meta['warnings'].append('La fuente presenta diferencias de conciliación. Se usan segmentos válidos, no el Total original.')
        if operation == 'detail':
            if not self.policy.detail:
                raise PermissionError()
            offset = int(q.get('offset', 0))
            if offset < 0 or offset > 100000:
                raise QueryProblem('limit', 'Página fuera del límite permitido.')
            columns = [c for c in data if not c.endswith('_original') and c not in PRIVATE]
            if self.policy.personal:
                columns = [c for c in data if not c.endswith('_original')]
            records = data.iloc[offset:offset+20][columns].to_dict('records')
            # El detalle se muestra localmente: nunca se envía al modelo.
            return {'status': 'ok' if len(data) else 'empty', 'message': 'Detalle de registros incluidos.',
                    'records': records, 'offset': offset, 'has_more': offset+20 < len(data),
                    'metadata': meta}, effective
        if operation == 'quality':
            if not self.policy.audit:
                raise PermissionError()
            return {'status': 'ok', 'message': 'Calidad de la población dimensional consultada; las métricas excluyen registros bloqueados.',
                    'values': [{'Concepto': 'Registros incluidos', 'Valor': int(population.incluido.sum())},
                               {'Concepto': 'Registros excluidos', 'Valor': int((~population.incluido).sum())},
                               {'Concepto': 'Duplicados potenciales', 'Valor': int(population.duplicado_potencial.sum())}],
                    'metric': 'Calidad de la fuente', 'metadata': meta}, None
        if metric not in metric_values(data.iloc[:0], source):
            raise QueryProblem('clarification', 'Selecciona una métrica disponible del diccionario. Capital colocado y monto contractual son distintos.')
        if operation == 'compare':
            if source not in ('prestamos', 'cobranzas') or group:
                raise QueryProblem('unavailable', 'La comparación mensual requiere una fuente de detalle sin agrupación.')
            comparable = previous_period(*period, ranges[0][1], ranges[0][2]) if len(ranges) == 1 else None
            if not comparable:
                raise QueryProblem('unavailable', 'Comparación no disponible: se requieren meses equivalentes cubiertos por los parámetros del reporte.')
            a, b, condition = comparable
            prior = base[base[datecol].between(a, b)]
            current_value = metric_values(data, source)[metric] if len(data) else None
            prior_value = metric_values(prior, source)[metric] if len(prior) else None
            delta = None if current_value is None or prior_value is None else float(current_value-prior_value)
            return {'status': 'ok' if delta is not None else 'unavailable', 'metric': metric,
                    'values': [{'Período': 'Actual', 'Valor': current_value}, {'Período': 'Anterior', 'Valor': prior_value}],
                    'difference': delta, 'change_ratio': ratio(delta, prior_value),
                    'previous_period': [str(a.date()), str(b.date())], 'condition': condition,
                    'metadata': meta}, effective
        if operation != 'aggregate':
            raise QueryProblem('unsupported', 'Operación no habilitada.')
        if group:
            values = [{group: segment, 'Valor': metric_values(part, source)[metric]}
                      for segment, part in data.groupby(group, dropna=False)]
            if len(values) > 100:
                raise QueryProblem('limit', 'Hay más de cien grupos. Acota los filtros para obtener una respuesta completa.')
        else:
            values = [{'Valor': metric_values(data, source)[metric]}]
        missing = any(v['Valor'] is None or pd.isna(v['Valor']) for v in values)
        status = 'empty' if data.empty else ('unavailable' if missing else 'ok')
        return {'status': status, 'metric': metric, 'values': values,
                'message': 'Sin registros incluidos en el alcance consultado.' if data.empty else ('La métrica tiene datos faltantes; no se calcula un total parcial.' if missing else 'Resultado verificado sobre registros incluidos.'),
                'metadata': meta}, effective

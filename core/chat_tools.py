"""Contratos tipados de herramientas. El modelo no recibe registros personales."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
from langchain_core.tools import tool
from .analytics_context import DIMENSIONS

Source = Literal['prestamos', 'cobranzas', 'cartera', 'proyeccion', 'planes_gerencial', 'morosos_plan', 'morosos_sucursal']
Dimension = Literal['entidad', 'sucursal', 'plan', 'estado', 'usuario', 'tipo_de_pago', 'hoja', 'anio', 'mes']


class FilterTerm(BaseModel):
    model_config = ConfigDict(extra='forbid')
    dimension: Dimension
    values: list[str] = Field(max_length=30)


class QueryInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    source: Source | None
    metric: str | None = Field(max_length=150)
    operation: Literal['aggregate', 'compare', 'detail', 'quality'] | None
    filters: list[FilterTerm] | None = Field(description='Solo condiciones explícitas del usuario; null conserva filtros activos.', max_length=9)
    period: list[str] | None = Field(description='Dos fechas ISO inclusivas si el usuario pide otro período. null conserva el activo.', max_length=2)
    group_by: Dimension | None
    client_ref: str | None = Field(description='Referencia privada opaca extraída del mensaje. Nunca un documento literal.', max_length=80)
    combine_document_matches: bool | None = Field(description='true solo si el usuario confirma contar todos los clientes asociados al mismo documento; null conserva la decisión anterior.')
    inherit: bool
    override_filters: bool = Field(description='true únicamente cuando el usuario confirma reemplazar filtros contradictorios.')
    offset: int | None = Field(ge=0, le=100000)


def make_tools(service):
    @tool(args_schema=QueryInput)
    def consultar_datos(**kwargs) -> dict:
        """Consulta las fuentes autorizadas usando métricas del catálogo.

        Todos los cálculos se ejecutan en el servidor. No une fuentes.
        Para seguimientos usar inherit=true y null en campos no modificados.
        Un resultado vacío no prueba inexistencia del cliente en el sistema.
        """
        terms = kwargs.pop('filters')
        terms = [term.model_dump() if isinstance(term, FilterTerm) else term for term in terms] if terms else None
        if terms:
            dimensions = [term['dimension'] if isinstance(term, dict) else term.dimension for term in terms]
            if len(dimensions) != len(set(dimensions)):
                return {'status': 'clarification', 'message': 'Indica una sola condición por dimensión.'}
        kwargs['filters'] = {term['dimension']: term['values'] for term in terms} if terms else None
        result = service.execute(kwargs)
        # Archivo/hoja/fila y detalle se conservan solo para la UI local.
        public = {k: v for k, v in result.items() if k != 'records'}
        if 'metadata' in public:
            public['metadata'] = {k: v for k, v in public['metadata'].items() if k not in ('files', 'sheets')}
        return public

    @tool
    def consultar_definiciones(consulta: str) -> dict:
        """Recupera definiciones documentadas y fuentes disponibles; no calcula cifras.

        Usar para entender términos del dashboard y los límites de sus datos.
        """
        catalog = service.catalog()
        tokens = set(consulta.lower().split())
        definitions = catalog['definitions']
        ranked = sorted(definitions, key=lambda row: -len(tokens & set(str(row).lower().split())))
        result = {'status': 'definitions', 'definitions': ranked[:8], 'sources': catalog['sources'],
                  'evidence_id': 'definicion_'+str(len(service.results)+1)}
        service.results.append(result)
        return result

    return [consultar_datos, consultar_definiciones]

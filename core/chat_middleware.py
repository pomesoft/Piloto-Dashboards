"""Límites y errores sin registrar prompts, documentos o excepciones externas."""
from langchain.agents.middleware import wrap_tool_call, wrap_model_call
from langchain_core.messages import ToolMessage


@wrap_tool_call
def safe_tools(request, handler):
    try:
        return handler(request)
    except Exception:
        # No incluir str(exc): podría contener argumentos o datos personales.
        return ToolMessage(content='La consulta no pudo completarse. No hay resultados verificables.',
                           tool_call_id=request.tool_call['id'])


@wrap_model_call
def bounded_model(request, handler):
    # Las herramientas mutan solo contexto conversacional local: ejecutarlas en serie.
    return handler(request.override(model_settings={**request.model_settings,
                                                    'parallel_tool_calls': False, 'strict': True}))

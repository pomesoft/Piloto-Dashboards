"""Configuración exclusiva del servidor. No crea ni imprime credenciales."""
from dataclasses import dataclass, field
import os


@dataclass(frozen=True)
class ChatConfig:
    api_key: str = field(default='', repr=False)
    model: str = 'gpt-5.5'
    timeout: float = 40
    max_tokens: int = 2000
    session_ttl: int = 1800


def read_config(st):
    try:
        settings = dict(st.secrets.get('chat', {}))
    except FileNotFoundError:
        settings = {}
    return ChatConfig(api_key=os.environ.get('OPENAI_API_KEY') or settings.get('api_key', ''),
        model=os.environ.get('OPENAI_MODEL') or settings.get('model', 'gpt-5.5'),
        timeout=min(max(float(settings.get('timeout', 40)), 5), 60),
        max_tokens=min(max(int(settings.get('max_tokens', 2000)), 256), 4000),
        session_ttl=min(max(int(settings.get('session_ttl', 1800)), 60), 3600))

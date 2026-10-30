"""Reconocimiento de reportes ZIP, sin extraer archivos al disco."""
from io import BytesIO
from zipfile import ZipFile
import unicodedata

PREFIXES = {
    'proyeccion': 'Proyeccion de Cobranzas Pendientes de Cobro',
    'morosos_sucursal': 'Informes Gerencial - Morosos por Sucursal',
    'planes_gerencial': 'Informes Gerencial - Prestamos por Plan',
    'morosos_plan': 'Informes Gerencial - Morosos por Plan',
    'cartera': 'Saldo de la Cartera',
    'cobranzas': 'Cobranzas Detalle',
    'prestamos': 'Prestamos Detalle',
}

def normalized(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value) if not unicodedata.combining(c)).casefold().strip()

def read_zip_reports(content):
    sources, messages = {}, []
    with ZipFile(BytesIO(content)) as archive:
        entries = archive.infolist()
        if len(entries) > 1000 or sum(e.file_size for e in entries) > 300 * 1024 * 1024:
            raise ValueError('El ZIP supera el límite de 1000 archivos o 300 MB descomprimidos.')
        for entry in entries:
            name = entry.filename.replace('\\', '/').rsplit('/', 1)[-1]
            if entry.is_dir() or not name.lower().endswith('.xlsx') or name.startswith('~$'):
                continue
            kind = next((k for k, prefix in PREFIXES.items() if normalized(name).startswith(normalized(prefix))), None)
            if kind is None:
                messages.append(f'Archivo no reconocido: {name}')
                continue
            if kind in sources:
                raise ValueError(f'Hay más de un archivo para {PREFIXES[kind]}. Deja uno solo en el ZIP.')
            source = BytesIO(archive.read(entry))
            source.name = name
            sources[kind] = source
    if not sources:
        messages.append('El ZIP no contiene reportes Excel reconocidos.')
    return sources, messages

"""Lectura en memoria y trazabilidad de todas las filas."""
from dataclasses import dataclass
from io import BytesIO
import pandas as pd
import openpyxl
from .normalization import label, identifier, number, parse_date

SCHEMAS = {
 'prestamos': 'Cliente|Apellido y Nombre|Documento|Prestamo|Fecha|Cuotas|Plan|Capital|Interes|Seguro|Importe S/IVA|IVA|Monto|Estado|Usuario'.split('|'),
 'cobranzas': 'Cliente|Apellido y Nombre|Documento|Prestamo|Cuota|Plan|Fec. Cobro|Capital|Interes|Seguro|Punitorios|Cobrado|Tipo de Pago|Bonif|Anulado'.split('|'),
 'cartera': 'Cliente|Apellido y Nombre|CUIL|Prestamo|Solicitud|Fecha|Fecha Ult. Vto.|Plan|Tasa|Cuotas|Cuotas Impagas'.split('|') + ['Capital','Interes','Interes IVA','Monto']*3,
}
IDS = {'cliente','documento','cuil','prestamo','solicitud','plan'}
DATES = {'fecha','fec_cobro','fecha_ult_vto'}
TEXT = IDS | DATES | {'apellido_y_nombre','estado','usuario','tipo_de_pago','bonif','anulado'}

@dataclass
class Report:
    kind: str
    data: pd.DataFrame
    rows: pd.DataFrame
    parameters: dict
    headers: dict
    warnings: list

def read_report(content, filename, kind):
    wb = openpyxl.load_workbook(BytesIO(content), data_only=False)
    records, audit, params, headers, warnings = [], [], {}, {}, []
    expected = [label(c) for c in SCHEMAS[kind]]
    for ws in wb.worksheets:
        h = None
        cells = list(ws.iter_rows())
        for i,row in enumerate(cells):
            vals = [label(c.value) for c in row]
            if {'cliente','prestamo','plan'}.issubset(vals):
                h = i
                break
        if h is None:
            warnings.append(f'Hoja {ws.title}: no se encontró encabezado de detalle.')
            continue
        raw_headers = [label(c.value) for c in cells[h]]
        columns = []
        group = ''
        for j,name in enumerate(raw_headers):
            if kind == 'cartera' and h > 0:
                g = label(cells[h-1][j].value)
                if g in ('otorgado','cobrado','saldo'):
                    group = g
                if name in ('capital','interes','interes_iva','monto'):
                    name = f'{group}_{name}'
            columns.append(name or f'columna_{j+1}')
        required = expected if kind != 'cartera' else expected[:11] + [f'{g}_{c}' for g in ('otorgado','cobrado','saldo') for c in ('capital','interes','interes_iva','monto')]
        missing = set(required)-set(columns)
        if missing:
            raise ValueError(f'{ws.title}: faltan columnas: {", ".join(sorted(missing))}')
        headers[ws.title] = h+1
        params[ws.title] = {str(r[0].value).strip().rstrip(':').strip(): r[1].value for r in cells[:h] if len(r)>1 and r[0].value and ':' in str(r[0].value)}
        context = []
        last_subtotal = None
        for idx,row in enumerate(cells[h+1:], h+2):
            r = {col: (identifier(c) if col in IDS else c.value) for col,c in zip(columns,row)}
            r.update(archivo=filename, hoja=ws.title, fila=idx)
            first = label(row[0].value)
            nonempty = [c for c in row if c.value is not None and str(c.value).strip()]
            if not nonempty:
                category = 'vacía'
            elif first.startswith('subtotal') or first.startswith('sub_total'):
                category = 'subtotal'
                r['nivel_control'] = 'sucursal' if 'sucursal' in first else ('comercio' if 'comercio' in first else 'desconocido')
                r['grupo_1'] = context[0] if context else None
                r['grupo_2'] = context[1] if len(context)>1 else None
                last_subtotal = r['nivel_control']
            elif first in ('total','total_general'):
                category = 'total'
                r['nivel_control'] = 'general'
            elif len(nonempty) == 1 and isinstance(row[0].value,str) and not r.get('prestamo'):
                category = 'agrupación'
                value = str(row[0].value).strip()
                if last_subtotal == 'comercio':
                    context = [value]
                elif last_subtotal == 'sucursal' and context:
                    context = [context[0],value]
                else:
                    context.append(value)
                last_subtotal = None
            elif r.get('prestamo'):
                category = 'detalle'
                r['grupo_1'] = context[0] if context else None
                r['grupo_2'] = context[1] if len(context)>1 else None
                r['contexto'] = ' / '.join(context)
                records.append(r)
            else:
                category = 'rechazada'
            r['clasificacion'] = category
            audit.append(r.copy())
        # Los nombres de nivel se confirman solo mediante subtotales explícitos.
        levels = {r.get('nivel_control') for r in audit if r['hoja']==ws.title}
        if not {'comercio','sucursal'}.issubset(levels):
            warnings.append(f'{ws.title}: contexto conservado como grupos sin semántica confirmada.')
    if not headers:
        raise ValueError('No se encontró una hoja compatible con el tipo de reporte seleccionado.')
    df = pd.DataFrame(records)
    if df.empty:
        df = pd.DataFrame(columns=columns+['archivo','hoja','fila','grupo_1','grupo_2','contexto'])
    for col in columns:
        if col in DATES:
            df[col+'_original'] = df[col]
            df[col] = df[col].map(parse_date)
        elif col not in TEXT and not col.startswith('columna_'):
            df[col+'_original'] = df[col]
            df[col] = df[col].map(number)
    if {'comercio','sucursal'}.issubset({r.get('nivel_control') for r in audit}):
        df['entidad'] = df['grupo_1']
        df['sucursal'] = df['grupo_2']
    return Report(kind, df, pd.DataFrame(audit), params, headers, warnings)

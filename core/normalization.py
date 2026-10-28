"""Conversión explícita, sin convertir ausencias en cero."""
import re
import unicodedata
from datetime import date, datetime
import pandas as pd

def label(value):
    s = unicodedata.normalize('NFKD', '' if value is None or pd.isna(value) else str(value)).encode('ascii', 'ignore').decode().lower().strip()
    return re.sub(r'[^a-z0-9]+', '_', s).strip('_')

def identifier(cell):
    v = cell.value
    if v is None or str(v).strip() == '':
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        s = str(int(v)) if float(v).is_integer() else str(v)
        fmt = cell.number_format
        if re.fullmatch(r'0+', fmt or '') and float(v).is_integer():
            s = s.zfill(len(fmt))
        return s
    return str(v).strip()

def number(value):
    if value is None or str(value).strip() == '':
        return float('nan')
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    s = str(value).strip().replace('$', '').replace(' ', '').replace('\u00a0', '')
    if ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif re.fullmatch(r'-?\d{1,3}(\.\d{3})+', s):
        s = s.replace('.', '')
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return float('nan')

def parse_date(value):
    if value is None or str(value).strip() == '':
        return pd.NaT
    if isinstance(value, (datetime, date)):
        return pd.Timestamp(value).normalize()
    if isinstance(value, (float, int)):
        from openpyxl.utils.datetime import from_excel
        try:
            return pd.Timestamp(from_excel(value)).normalize()
        except (ValueError, OverflowError, TypeError):
            return pd.NaT
    return pd.to_datetime(str(value).strip(), dayfirst=True, errors='coerce')

def flag(value, mapping):
    return mapping.get(label(value))

DEFAULT_FLAGS = {'': False, 'no': False, 'n': False, '0': False,
                 'false': False, 'si': True, 's': True, '1': True, 'true': True, 'x': True}

def safe_csv(df):
    out = df.copy()
    for col in out:
        out[col] = out[col].map(lambda x: "'" + x if isinstance(x, str) and x.lstrip().startswith(('=', '+', '-', '@', '\t', '\r', '\n')) else x)
    return out.to_csv(index=False, sep=';', decimal=',').encode('utf-8-sig')

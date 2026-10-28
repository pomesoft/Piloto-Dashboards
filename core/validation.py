import pandas as pd
from .normalization import flag, label, number, DEFAULT_FLAGS, parse_date

def validate(report, anulados=None, bonificaciones=None, tolerance=0.02):
    d = report.data.copy()
    issues = []
    def note(mask, message, blocking=False):
        for i in d.index[mask]:
            issues.append({'archivo':d.at[i,'archivo'],'hoja':d.at[i,'hoja'],'fila':d.at[i,'fila'],'motivo':message,'bloqueante':blocking})
        if blocking:
            d.loc[mask,'valido'] = False
    d['valido'] = True
    key = ['grupo_1','prestamo']
    d['duplicado_potencial'] = d.duplicated([c for c in d if not c.endswith('_original') and c not in ('archivo','hoja','fila','valido','clasificacion')], keep=False) if report.kind=='cobranzas' else d.duplicated(key,keep=False)
    note(d['duplicado_potencial'], 'Duplicado potencial: revisar; no se elimina. Claves no únicas bloquean métricas de préstamos/cartera.', report.kind!='cobranzas')
    note(d.prestamo.isna() | d.grupo_1.isna(), 'Clave de préstamo o entidad sin identificar', True)
    note(d.cliente.isna(), 'Cliente ausente: cobertura de identificación incompleta')
    datecol = 'fec_cobro' if report.kind=='cobranzas' else 'fecha'
    note(d[datecol].isna(), 'Fecha inválida o ausente', True)
    if 'fecha_ult_vto' in d:
        note(d.fecha_ult_vto.isna(), 'Fecha de último vencimiento inválida o ausente; no se usa para calcular mora')
    for c in [c for c in d if c.endswith('_original') and c[:-9] in d]:
        field = c[:-9]
        if pd.api.types.is_numeric_dtype(d[field]):
            note(d[field].isna(), f'{field}: importe/cantidad ausente o inválido')
            note(d[field].lt(0), f'{field}: valor negativo conservado para revisión')
    if report.kind=='prestamos':
        note(~d.estado.map(label).isin(['vigente','cancelado']), 'Estado desconocido: excluido hasta validar', True)
    if report.kind=='cobranzas':
        am = DEFAULT_FLAGS if anulados is None else anulados
        bm = DEFAULT_FLAGS if bonificaciones is None else bonificaciones
        d['anulado_interpretado'] = d.anulado.map(lambda v: flag(v,am))
        d['bonif_interpretada'] = d.bonif.map(lambda v: flag(v,bm))
        note(d.anulado_interpretado.isna(), 'Anulado ambiguo: excluido del cobro válido', True)
        note(d.bonif_interpretada.isna(), 'Bonif ambiguo: no se modifica Cobrado')
        d['incluido'] = d.valido & d.anulado_interpretado.eq(False)
        d['importe_no_explicado'] = d.cobrado - d[['capital','interes','seguro','punitorios']].sum(axis=1,min_count=4)
        note(d.importe_no_explicado.abs().gt(tolerance), 'Cobrado difiere de componentes: posible componente fiscal; validar')
    else:
        d['incluido'] = d.valido
    if report.kind=='cartera':
        for comp in ('capital','interes','interes_iva','monto'):
            c = 'diferencia_'+comp
            d[c] = d['otorgado_'+comp]-d['cobrado_'+comp]-d['saldo_'+comp]
            note(d[c].abs().gt(tolerance), f'Otorgado − Cobrado ≠ Saldo ({comp})')
    return d, pd.DataFrame(issues,columns=['archivo','hoja','fila','motivo','bloqueante'])

def reconcile(report, tolerance=0.02):
    """Cada control contra su propio nivel, hoja y población; nunca sumar controles."""
    result=[]
    for _,r in report.rows[report.rows.clasificacion.isin(['total','subtotal'])].iterrows():
        population = report.data[report.data.hoja.eq(r.hoja)]
        level = r.get('nivel_control')
        if level=='desconocido':
            continue
        if level in ('comercio','sucursal'):
            population = population[population.grupo_1.eq(r.get('grupo_1'))]
        if level=='sucursal':
            population = population[population.grupo_2.eq(r.get('grupo_2'))]
        for c in population.select_dtypes('number').columns:
            if c in ('fila',) or c.endswith('_original') or c not in r or pd.isna(r[c]):
                continue
            original=number(r[c])
            if pd.isna(original):
                continue
            calc=population[c].sum(min_count=len(population)) if len(population) else float('nan')
            result.append({'hoja':r.hoja,'fila_control':r.fila,'nivel':level,'grupo_1':r.get('grupo_1'),'grupo_2':r.get('grupo_2'),'componente':c,'original':original,'detalle':calc,'diferencia':calc-original,'estado':'No disponible' if pd.isna(calc) else ('Dentro de tolerancia' if abs(calc-original)<=tolerance else 'Diferencia')})
        original=number(r.get('prestamo'))
        if pd.notna(original):
            result.append({'hoja':r.hoja,'fila_control':r.fila,'nivel':level,'componente':'filas_detalle','original':original,'detalle':len(population),'diferencia':len(population)-original,'estado':'Coincide' if len(population)==original else 'Diferencia'})
    return pd.DataFrame(result)

def coverage(report):
    ranges=[]
    for sheet,p in report.parameters.items():
        prefix='Cobranzas' if report.kind=='cobranzas' else 'Prestamos'
        normalized={label(k):v for k,v in p.items()}
        ranges.append((sheet,parse_date(normalized.get(label(prefix+' Desde'))),parse_date(normalized.get(label(prefix+' Hasta')))))
    return ranges

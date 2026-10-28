import calendar
import pandas as pd

def total(d,c):
    # Una suma parcial no se presenta como total si faltan componentes.
    if d.empty or c not in d or d[c].isna().any():
        return None
    return float(d[c].sum())

def ratio(a,b):
    return None if a is None or b is None or pd.isna(a) or pd.isna(b) or b==0 else a/b

def unique_loans(d):
    return len(d[['grupo_1','prestamo']].drop_duplicates()) if not d.empty else 0

def clients(d):
    return len(d.dropna(subset=['cliente'])[['grupo_1','cliente']].drop_duplicates())

def metrics(d,kind):
    n=unique_loans(d)
    if kind=='prestamos':
        return {'Capital colocado':total(d,'capital'),'Préstamos otorgados':n,
                'Ticket promedio':ratio(total(d,'capital'),n),'Clientes con préstamos':clients(d),
                'Monto contractual originado':total(d,'monto'),
                'Plazo promedio (cuotas)':None if d.empty or d.cuotas.isna().any() else d.cuotas.mean()}
    if kind=='cobranzas':
        return {'Total cobrado':total(d,'cobrado'),'Capital recuperado':total(d,'capital'),
                'Intereses cobrados':total(d,'interes'),'Punitorios cobrados':total(d,'punitorios'),
                'Seguros cobrados':total(d,'seguro'),'Imputaciones de cobro':len(d),
                'Préstamos con cobros':n,'Importe no explicado':total(d,'importe_no_explicado')}
    positive=d[d.saldo_monto.gt(0)]
    return {'Capital pendiente':total(d,'saldo_capital'),'Saldo contractual pendiente':total(d,'saldo_monto'),
            'Intereses pendientes':total(d,'saldo_interes'),'IVA de intereses pendiente':total(d,'saldo_interes_iva'),
            'Préstamos con saldo':unique_loans(positive),'Clientes con saldo':clients(positive),
            'Capital pendiente promedio por préstamo':ratio(total(d,'saldo_capital'),unique_loans(positive)),
            'Capital recuperado acumulado de la población':total(d,'cobrado_capital'),
            'Proporción de capital recuperado':ratio(total(d,'cobrado_capital'),total(d,'otorgado_capital')),
            'Concentración de capital en 10 deudores':concentration(d),
            'Cuotas impagas reportadas (definición pendiente)':total(d,'cuotas_impagas')}

def concentration(d):
    if d.empty or d.cliente.isna().any() or d.saldo_capital.isna().any() or d.saldo_capital.lt(0).any():
        return None
    a=d.groupby(['grupo_1','cliente']).saldo_capital.sum().nlargest(10).sum()
    return ratio(a,total(d,'saldo_capital'))

def previous_period(start,end,coverage_start,coverage_end):
    """Comparación mensual: mes completo o mismo día, nunca duración supuesta."""
    start,end=pd.Timestamp(start),pd.Timestamp(end)
    if start.day!=1 or start.month!=end.month or start.year!=end.year:
        return None
    prev_end=start-pd.Timedelta(days=1)
    prev_start=prev_end.replace(day=1)
    full=end.day==calendar.monthrange(end.year,end.month)[1]
    if not full:
        if end.day>prev_end.day:
            return None
        prev_end=prev_start.replace(day=end.day)
    if pd.isna(coverage_start) or pd.isna(coverage_end) or prev_start<coverage_start or end>coverage_end:
        return None
    return prev_start,prev_end,'mes completo' if full else f'mes incompleto, hasta día {end.day}'

def compatible(reports,currencies):
    if len(reports)<2:
        return False
    # El mismo nombre de entidad no prueba la misma población de origen.
    return False

def authorized_join(loans,payments,mapping):
    """API opcional: equivalencias explícitas y unión m:1 tras agregar cobros.
    Columnas del mapa: entidad_origen, prestamo_origen, entidad_destino, prestamo_destino.
    No se invoca automáticamente en el dashboard.
    """
    a=['entidad_origen','prestamo_origen']; b=['entidad_destino','prestamo_destino']
    if mapping.duplicated(a).any() or mapping.duplicated(b).any():
        raise ValueError('Equivalencias sin cardinalidad uno a uno')
    if loans.duplicated(['grupo_1','prestamo']).any():
        raise ValueError('Préstamos no únicos en la entidad')
    agg=payments.groupby(['grupo_1','prestamo'],dropna=False).cobrado.sum(min_count=1).reset_index()
    mapped=agg.merge(mapping,left_on=['grupo_1','prestamo'],right_on=a,how='left',validate='one_to_one',indicator=True)
    unmatched=mapped[mapped._merge.eq('left_only')].copy()
    matched=mapped[mapped._merge.eq('both')]
    out=loans.merge(matched[b+['cobrado']],left_on=['grupo_1','prestamo'],right_on=b,how='left',validate='one_to_one')
    return out,unmatched

def dictionary():
    definitions={
      'prestamos':[
        ('Capital colocado','Σ capital','moneda','Capital de préstamos válidos; no monto contractual'),
        ('Préstamos otorgados','claves distintas (entidad, préstamo)','préstamos','Sin duplicados de clave'),
        ('Ticket promedio','Σ capital / préstamos otorgados','moneda/préstamo','Denominador cero: No disponible'),
        ('Clientes con préstamos','claves distintas (entidad, cliente)','clientes','Con cobertura identificada'),
        ('Monto contractual originado','Σ monto','moneda','Incluye conceptos pactados; no desembolso'),
        ('Plazo promedio (cuotas)','media de cuotas','cuotas','Periodicidad no validada; no meses')],
      'cobranzas':[(n,f,u,l) for n,f,u,l in [
        ('Total cobrado','Σ cobrado','moneda','No se resta Bonif otra vez'),
        ('Capital recuperado','Σ capital','moneda','Movimientos no anulados'),
        ('Intereses cobrados','Σ interes','moneda','No representa ganancia neta'),
        ('Punitorios cobrados','Σ punitorios','moneda','Movimientos no anulados'),
        ('Seguros cobrados','Σ seguro','moneda','Movimientos no anulados'),
        ('Imputaciones de cobro','número de filas válidas no anuladas','imputaciones','No hay identificador de recibo'),
        ('Préstamos con cobros','claves distintas (entidad, préstamo)','préstamos','Pagos parciales conservados'),
        ('Participación por medio de pago','Σ cobrado del medio / Σ cobrado','proporción','Denominador cero: No disponible'),
        ('Importe no explicado','cobrado − capital − interes − seguro − punitorios','moneda','Podría incluir impuestos; validar')]],
      'cartera':[
        ('Capital pendiente','Σ saldo_capital','moneda','No equivale a capital vencido'),
        ('Saldo contractual pendiente','Σ saldo_monto','moneda','Fotografía, no flujo'),
        ('Intereses pendientes','Σ saldo_interes','moneda','Pactados pendientes'),
        ('IVA de intereses pendiente','Σ saldo_interes_iva','moneda','Según reporte'),
        ('Préstamos con saldo','claves únicas con saldo_monto > 0','préstamos','Población del reporte'),
        ('Clientes con saldo','clientes únicos con saldo_monto > 0','clientes','Cobertura de identificación'),
        ('Capital pendiente promedio por préstamo','Σ saldo_capital / préstamos con saldo','moneda/préstamo','No disponible si denominador cero'),
        ('Capital recuperado acumulado de la población','Σ cobrado_capital','moneda','Acumulado del universo seleccionado'),
        ('Proporción de capital recuperado','Σ cobrado_capital / Σ otorgado_capital','proporción','No efectividad de cobranza del período'),
        ('Concentración de capital en 10 deudores','capital de 10 principales clientes / capital pendiente','proporción','Consolidación por entidad y cliente; no agrupa personas entre entidades'),
        ('Cuotas impagas reportadas (definición pendiente)','Σ cuotas_impagas','cuotas','No se interpreta como cuotas vencidas')]
    }
    rows=[]
    for kind,defs in definitions.items():
        for name,formula,unit,limit in defs:
            exclusions='claves/fechas inválidas; anulados y Anulado ambiguo; duplicados potenciales de cobro conservados' if kind=='cobranzas' else 'claves/fechas inválidas; claves duplicadas; estados desconocidos en Préstamos'
            rows.append({'Métrica':name,'Fórmula':formula,'Fuente':kind,'Granularidad':'imputación a cuota' if kind=='cobranzas' else 'préstamo por entidad','Fecha aplicada':'Fec. Cobro' if kind=='cobranzas' else ('corte informado o declarado' if kind=='cartera' else 'Fecha préstamo'),'Exclusiones':exclusions,'Unidad':unit,'Interpretación y limitaciones':limit+'; datos ausentes no se convierten en cero; importes negativos se conservan observados.'})
    return pd.DataFrame(rows)


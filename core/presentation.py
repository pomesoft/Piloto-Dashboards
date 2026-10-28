import pandas as pd
import plotly.express as px
import streamlit as st
from .normalization import safe_csv
from .metrics import total, ratio, previous_period

PRIVATE={'apellido_y_nombre','documento','cuil','cliente','prestamo','solicitud'}

def fmt(v,percent=False):
    if v is None or pd.isna(v):
        return 'No disponible'
    return (f'{v*100:,.1f} %' if percent else f'{v:,.2f}').replace(',','X').replace('.',',').replace('X','.')

def cards(values,currency,caption):
    entries=list(values.items())
    for offset in range(0,len(entries),4):
        for col,(name,v) in zip(st.columns(min(4,len(entries)-offset)),entries[offset:offset+4]):
            with col:
                is_pct='Proporción' in name or 'Concentración' in name
                st.metric(name,fmt(v,is_pct),border=True)
                count=any(t in name for t in ['Préstamos','Clientes','cuotas','Cuotas','Imputaciones'])
                st.caption(caption+' · '+('proporción' if is_pct else ('cantidad' if count else currency)))

def table(df,key,private=False):
    reveal=st.checkbox('Mostrar identificadores personales en este detalle',key=key+'_pii') if private else False
    visible=df.copy()
    if not reveal:
        visible=visible.drop(columns=[c for c in visible if c in PRIVATE],errors='ignore')
    st.dataframe(visible,hide_index=True,width='stretch',alt='Tabla de resultados o controles con trazabilidad')
    st.download_button('Descargar tabla CSV',safe_csv(visible),file_name=key+'.csv',mime='text/csv',key=key+'_csv')

def filters(d,kind,report):
    filtered=d.copy()
    with st.expander('Filtros · '+kind,expanded=False):
        for c in ['entidad','sucursal','plan','estado','usuario','tipo_de_pago']:
            if c in d and d[c].notna().any():
                options=sorted(d[c].dropna().astype(str).unique())
                chosen=st.multiselect(c.replace('_',' ').capitalize(),options,key='f_'+kind+'_'+c)
                if chosen:
                    filtered=filtered[filtered[c].astype(str).isin(chosen)]
        datecol='fec_cobro' if kind=='cobranzas' else 'fecha'
        period=None
        if kind!='cartera' and d[datecol].notna().any():
            from .validation import coverage
            ranges=coverage(report)
            starts=[r[1] for r in ranges if pd.notna(r[1])]
            ends=[r[2] for r in ranges if pd.notna(r[2])]
            lo=min(starts) if starts else d[datecol].min()
            hi=max(ends) if ends else d[datecol].max()
            period=st.date_input('Período de '+('cobro' if kind=='cobranzas' else 'colocación'),value=(lo.date(),hi.date()),key='f_'+kind+'_period')
            if len(period)==2:
                filtered=filtered[filtered[datecol].between(pd.Timestamp(period[0]),pd.Timestamp(period[1]))]
            else:
                filtered=filtered.iloc[0:0]
                st.info('Completa las dos fechas del período.')
    return filtered,period

def bars(d,value,dimension,title,currency,key):
    if dimension not in d or d.empty:
        return
    summary=d.groupby(dimension,dropna=False)[value].agg(lambda s:s.sum(min_count=len(s))).reset_index().sort_values(value,ascending=False)
    fig=px.bar(summary,x=dimension,y=value,title=title,labels={value:currency,dimension:dimension.capitalize()},color_discrete_sequence=['#127F8C'])
    fig.update_layout(separators=',.')
    st.plotly_chart(fig,width='stretch',key=key+'_chart',alt=title+' en '+currency)
    segment=st.selectbox('Ver registros del segmento', ['Todos']+summary[dimension].dropna().astype(str).tolist(),key=key+'_segment')
    if segment!='Todos':
        table(d[d[dimension].astype(str).eq(segment)],key+'_drill',True)

def trend_data(d,kind,frequency):
    datecol='fec_cobro' if kind=='cobranzas' else 'fecha'
    amount='cobrado' if kind=='cobranzas' else 'capital'
    if d.empty:
        return pd.DataFrame(columns=[datecol,amount,'miles_ars'])
    grouped=d.set_index(datecol)[amount].resample(frequency).agg(lambda s:s.sum(min_count=len(s)) if len(s) else float('nan')).reset_index()
    grouped['miles_ars']=grouped[amount]/1000
    return grouped

def trend_figure(d,kind,currency,frequency='MS',chart_type='line',title=None):
    datecol='fec_cobro' if kind=='cobranzas' else 'fecha'
    amount='cobrado' if kind=='cobranzas' else 'capital'
    grouped=trend_data(d,kind,frequency)
    chart_title=title or ('Cobranzas' if kind=='cobranzas' else 'Colocación')
    args=dict(x=datecol,y='miles_ars',title=chart_title,
              labels={'miles_ars':'Miles de '+currency,datecol:'Fecha'},
              custom_data=[amount],color_discrete_sequence=['#127F8C'])
    fig=px.bar(grouped,**args) if chart_type=='bar' else px.line(grouped,markers=True,**args)
    if chart_type!='bar':
        fig.update_traces(connectgaps=False,line_shape='linear')
    fig.update_traces(hovertemplate='%{x|%d/%m/%Y}<br>'+currency+' %{customdata[0]:,.2f}<extra></extra>')
    fig.update_layout(separators=',.',height=360,margin=dict(l=24,r=24,t=64,b=36),title_font_size=24,
                      yaxis=dict(tickformat=',.0f',rangemode='tozero'),
                      xaxis=dict(tickformat='%m/%y' if frequency=='MS' else '%d/%m',title=None))
    return fig

def trend(d,kind,currency,key,chart_type='line',monthly=False,title=None):
    if d.empty:
        st.info('Sin registros para mostrar una tendencia.')
        return
    frequency='Mensual' if monthly else st.selectbox('Frecuencia', ['Diaria','Semanal','Mensual'],index=2,key=key+'_frequency')
    freq={'Diaria':'D','Semanal':'W-MON','Mensual':'MS'}[frequency]
    fig=trend_figure(d,kind,currency,freq,chart_type,title)
    st.plotly_chart(fig,width='stretch',key=key+'_trend',alt='Evolución temporal de '+kind+' en '+currency)
    st.caption('Escala: miles de ARS. El cursor muestra el importe exacto. Los intervalos sin registros quedan sin dato.'+(' Semanas terminadas el lunes.' if frequency=='Semanal' else ''))

def comparison(d,report,period,currency):
    from .validation import coverage
    ranges=coverage(report)
    comparable=None
    if period and len(period)==2 and len(ranges)==1:
        comparable=previous_period(*period,ranges[0][1],ranges[0][2])
    if not comparable:
        st.caption('Comparación no disponible: se requieren meses equivalentes cubiertos por los parámetros del reporte.')
        return
    start,end,condition=comparable
    datecol='fec_cobro' if report.kind=='cobranzas' else 'fecha'
    value='cobrado' if report.kind=='cobranzas' else 'capital'
    current=total(d[d[datecol].between(pd.Timestamp(period[0]),pd.Timestamp(period[1]))],value)
    prior=total(d[d[datecol].between(start,end)],value)
    growth=ratio(None if current is None or prior is None else current-prior,prior)
    st.write(f'Comparación mensual ({condition}): {fmt(current)} frente a {fmt(prior)} {currency}. Variación: {fmt(growth,True)}. Anterior: {start:%d/%m/%Y} a {end:%d/%m/%Y}.')

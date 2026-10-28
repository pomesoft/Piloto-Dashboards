from contextlib import contextmanager
from datetime import date
from io import BytesIO
from pathlib import Path
from unittest.mock import patch
import json
import numpy as np
import pandas as pd
import pytest
from streamlit.delta_generator import DeltaGenerator
from streamlit.testing.v1 import AppTest
from core.presentation import trend_data,trend_figure
from core.interface import QUESTIONS,VIEWS,PAGES
from tests.test_core import FILES
from tests.test_management import FILES as MANAGEMENT_FILES

def test_trends_preserve_amounts_gaps_and_units():
    d=pd.DataFrame({'fecha':pd.to_datetime(['2026-01-02','2026-01-10','2026-03-01']),
                    'capital':[10000.,5000.,0.]})
    g=trend_data(d,'prestamos','MS')
    assert g.capital.iloc[0]==15000 and g.miles_ars.iloc[0]==15
    assert pd.isna(g.capital.iloc[1])
    assert g.capital.iloc[2]==0
    a=trend_figure(d,'prestamos','ARS',chart_type='bar')
    b=trend_figure(d,'prestamos','ARS',chart_type='line')
    assert a.data[0].type=='bar' and b.data[0].type=='scatter'
    assert b.data[0].mode=='lines+markers' and not b.data[0].connectgaps
    assert b.data[0].line.shape=='linear'
    assert np.asarray(a.data[0].customdata)[0,0]==15000
    assert 'Miles de ARS' in a.layout.yaxis.title.text
    assert a.layout.separators==',.'

@contextmanager
def loaded_app():
    uploads={}
    for kind,name in (FILES|MANAGEMENT_FILES).items():
        p=Path.home()/'Downloads'/name
        if not p.exists():
            pytest.skip('Fuente real no disponible')
        f=BytesIO(p.read_bytes());f.name=p.name;uploads['upload_'+kind]=f
    def uploader(*args,**kwargs):
        return uploads.get(kwargs.get('key'))
    with patch.object(DeltaGenerator,'file_uploader',uploader),patch('streamlit.file_uploader',uploader):
        at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=45)
        at.session_state['declare_cutoff']=True
        at.session_state['cutoff_cartera']=date(2026,10,20)
        at.run()
        yield at

def chart_specs(at):
    return [json.loads(c.proto.spec) for c in at.get('plotly_chart')]

def test_navigation_universe_and_requested_help():
    with loaded_app() as at:
        assert not at.exception
        assert at.sidebar.radio[0].options[-1]=='Detalle de Universo'
        assert [e.label for e in at.sidebar.expander if e.label in (
            'Carga de archivos y filtros','Preguntas que responde el dashboard','Detalle de las vistas'
        )]==['Carga de archivos y filtros','Preguntas que responde el dashboard','Detalle de las vistas']
        assert at.sidebar.button(key='reset_filters')
        assert len(at.sidebar.table)==2
        assert not at.sidebar.number_input and not at.sidebar.text_area
        assert len(QUESTIONS)==5 and len(VIEWS)==8
        assert len(at.table)==2
        assert not any('Universo:' in e.value for e in at.info)
        assert not any('Parámetros originales' in e.label for e in at.expander)
        at.sidebar.radio[0].set_value('Detalle de Universo').run()
        assert not at.exception
        headings=[e.value for e in at.markdown]
        assert sum(v.startswith('### ') for v in headings)==7
        assert any('Universo / entidades' in t.value.to_string() for t in at.table)
        assert any('Cobro Hasta' in t.value.to_string() for t in at.table)
        at.sidebar.radio[0].set_value('Cobranzas').run()
        assert not at.exception
        assert not any('Universo:' in e.value for e in at.info)
        assert not any('Parámetros originales' in e.label for e in at.expander)

def test_summary_types_and_detail_lines():
    with loaded_app() as at:
        specs=chart_specs(at)
        assert [x['data'][0]['type'] for x in specs]==['bar','bar','scatter','scatter']
        assert [x['layout']['title']['text'] for x in specs]==['Colocación','Cobranzas','Evolución del capital colocado','Evolución de la cobranza']
        assert all(x['layout']['yaxis']['title']['text']=='Miles de ARS' for x in specs)
        for page in ('Colocación','Cobranzas'):
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception
            assert chart_specs(at)[0]['data'][0]['type']=='scatter'

def test_quality_configuration_persists_between_views():
    with loaded_app() as at:
        at.sidebar.radio[0].set_value('Calidad y conciliación').run()
        at.number_input(key='q_tolerance').set_value(.15).run()
        at.selectbox(key='q_blank').set_value('Ambiguo: excluir hasta validar').run()
        assert not at.exception
        at.sidebar.radio[0].set_value('Resumen').run()
        assert not at.exception
        assert at.session_state['_quality_settings']['tolerance']==.15
        assert at.session_state['_quality_settings']['blank'].startswith('Ambiguo')
        at.sidebar.radio[0].set_value('Calidad y conciliación').run()
        assert not at.exception
        assert at.number_input(key='q_tolerance').value==.15
        assert at.selectbox(key='q_blank').value.startswith('Ambiguo')

from pathlib import Path
from io import BytesIO
from datetime import date
from unittest.mock import patch
import pytest
from streamlit.testing.v1 import AppTest
from streamlit.delta_generator import DeltaGenerator
from tests.test_management import FILES as NEW_FILES
from tests.test_core import FILES as DETAIL_FILES
import os

@pytest.mark.parametrize('kinds',[[k] for k in NEW_FILES]+[list(NEW_FILES),list(NEW_FILES)+list(DETAIL_FILES)])
def test_management_uploads_pages_and_quality(kinds):
    uploads={}
    for kind in kinds:
        p=Path(os.environ.get('REPORTS_DIR',str(Path.home()/'Downloads')))/(NEW_FILES|DETAIL_FILES)[kind]
        if not p.exists():
            pytest.skip('Archivo real no disponible')
        f=BytesIO(p.read_bytes());f.name=p.name
        uploads['upload_'+kind]=f
    def uploader(*args,**kwargs):
        return uploads.get(kwargs.get('key'))
    with patch.object(DeltaGenerator,'file_uploader',uploader),patch('streamlit.file_uploader',uploader):
        at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=45)
        at.session_state['declare_cutoff']=True
        at.session_state['cutoff_cartera']=date(2026,10,20)
        at.run()
        assert not at.exception
        assert any('ARS fijo' in e.value for e in at.caption)
        available=[f.value for f in at.dataframe if 'Estado' in f.value and 'Indicador' in f.value]
        assert len(available)==2
        assert any(f.Indicador.str.contains('PAR30',regex=False).any() for f in available)
        at.sidebar.radio[0].set_value('Proyección y morosidad').run()
        assert not at.exception
        for kind in [k for k in kinds if k in NEW_FILES]:
            at.selectbox(key='management_report').set_value(kind).run()
            assert not at.exception
            assert len(at.metric)>0
            assert len(at.get('download_button'))>0
            if kind.startswith('morosos'):
                assert any('no concilia' in e.value for e in at.error)
        if len(kinds)>1:
            at.selectbox(key='management_report').set_value('proyeccion').run()
            at.multiselect(key='f_proyeccion_anio').set_value([2028]).run()
            at.multiselect(key='f_proyeccion_mes').set_value([12]).run()
            assert not at.exception
            assert any('Resultado vacío' in e.value for e in at.info)
            at.button(key='reset_filters').click().run()
            assert not at.exception
            assert at.multiselect(key='f_proyeccion_anio').value==[]
        at.sidebar.radio[0].set_value('Colocación').run()
        assert not at.exception
        at.sidebar.radio[0].set_value('Calidad y conciliación').run()
        assert not at.exception
        if 'morosos_plan' in kinds:
            tables=[f.value for f in at.dataframe if 'componente' in f.value and 'diferencia' in f.value]
            assert any(t.componente.eq('moroso_capital').any() and t.diferencia.round(2).eq(947663.18).any() for t in tables)
        at.sidebar.radio[0].set_value('Diccionario de métricas').run()
        assert not at.exception
        assert at.dataframe[0].value.Métrica.str.contains('Saldo vencido reportado').any()

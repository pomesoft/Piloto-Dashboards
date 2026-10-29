from streamlit.testing.v1 import AppTest
import pytest
from pathlib import Path
from io import BytesIO
from datetime import date
from unittest.mock import patch
from streamlit.delta_generator import DeltaGenerator
from tests.test_core import FILES
from core.access import AccessPolicy

@pytest.mark.parametrize('page',['Resumen','Colocación','Cobranzas','Cartera','Proyección y morosidad','Calidad y conciliación','Diccionario de métricas','Detalle de Universo'])
def test_pages_without_sources(page):
    at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=30).run()
    at.sidebar.radio[0].set_value(page).run()
    assert not at.exception

@pytest.mark.parametrize('kinds',[
 ['prestamos'],['cobranzas'],['cartera'],
 ['prestamos','cobranzas'],['prestamos','cartera'],['cobranzas','cartera'],
 ['prestamos','cobranzas','cartera']])
def test_real_sources_all_pages(kinds):
    uploads={}
    for kind in kinds:
        p=Path.home()/'Downloads'/FILES[kind]
        if not p.exists():
            pytest.skip('Archivo real no disponible')
        f=BytesIO(p.read_bytes());f.name=p.name
        uploads['upload_'+kind]=f
    def uploader(*args,**kwargs):
        return uploads.get(kwargs.get('key'))
    # Este caso verifica la visualización autorizada; el acceso predeterminado
    # sin permiso personal se prueba por separado en test_chat_ui.py.
    with patch.object(DeltaGenerator,'file_uploader',uploader),patch('streamlit.file_uploader',uploader),patch('core.access.policy_from_settings',return_value=AccessPolicy(personal=True)):
        at=AppTest.from_file(Path(__file__).resolve().parents[1]/'app.py',default_timeout=45)
        at.session_state['declare_cutoff']=True
        # Fecha SOLO para probar UI; no se guarda como supuesto de los archivos.
        at.session_state['cutoff_cartera']=date(2026,10,19)
        at.run()
        assert not at.exception
        assert not at.error
        assert not at.text_input
        assert len(at.metric)>0
        assert any('Moneda: ARS' in e.value for e in at.caption)
        for page in ['Colocación','Cobranzas','Cartera','Calidad y conciliación','Diccionario de métricas','Detalle de Universo']:
            at.sidebar.radio[0].set_value(page).run()
            assert not at.exception
            assert not at.error
        if len(kinds)==3:
            at.sidebar.radio[0].set_value('Colocación').run()
            plan=at.multiselect(key='f_prestamos_plan').options[0]
            at.multiselect(key='f_prestamos_plan').select(plan).run()
            assert not at.exception and not at.error
            assert at.multiselect(key='f_prestamos_plan').value==[plan]
            detail=at.dataframe[-1].value
            assert detail.plan.eq(plan).all()
            assert not {'cliente','documento','cuil','apellido_y_nombre','prestamo'} & set(detail.columns)
            at.checkbox(key='prestamos_detalle_pii').check().run()
            assert 'cliente' in at.dataframe[-1].value
            assert len(at.get('download_button'))>0
            at.date_input(key='f_prestamos_period').set_value((date(2020,1,1),date(2020,1,2))).run()
            assert not at.exception
            assert any('Resultado vacío' in e.value for e in at.info)
            at.button(key='reset_filters').click().run()
            assert not at.exception and not at.error
            assert at.multiselect(key='f_prestamos_plan').value==[]

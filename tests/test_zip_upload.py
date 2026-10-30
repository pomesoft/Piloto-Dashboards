from io import BytesIO
from zipfile import ZipFile
from core.zip_upload import PREFIXES, read_zip_reports

def test_zip_recognizes_all_prefixes_in_folders():
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        for prefix in PREFIXES.values():
            archive.writestr('reportes/' + prefix + '[GUID].xlsx', b'excel')
    sources, messages = read_zip_reports(data.getvalue())
    assert set(sources) == set(PREFIXES)
    assert not messages
    assert all(s.getvalue() == b'excel' for s in sources.values())

def test_zip_rejects_duplicate_sources():
    import pytest
    data = BytesIO()
    with ZipFile(data, 'w') as archive:
        archive.writestr('Prestamos Detalle[a].xlsx', b'a')
        archive.writestr('Prestamos Detalle[b].xlsx', b'b')
    with pytest.raises(ValueError, match='más de un archivo'):
        read_zip_reports(data.getvalue())

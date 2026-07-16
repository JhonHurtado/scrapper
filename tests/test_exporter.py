# tests/test_exporter.py
import json
import pytest


@pytest.fixture
def setup_db_with_places(tmp_path, monkeypatch):
    from backend.config import config
    monkeypatch.setattr(config, "db_path", tmp_path / "test.db")
    monkeypatch.setattr("backend.exporters.json_exporter.OUTPUT_DIR", tmp_path / "output")
    monkeypatch.setattr("backend.exporters.json_exporter.BY_CITY_DIR", tmp_path / "output" / "by_city")
    from backend.database.db import close_db, init_db
    from backend.database.models import Place, save_place
    close_db()
    init_db()
    save_place(Place(name="Plaza de Bolívar", city="Bogotá",
                     department="Cundinamarca", category="monuments",
                     description="Plaza histórica"))
    save_place(Place(name="Cerro de Monserrate", city="Bogotá",
                     department="Cundinamarca", category="viewpoints"))
    save_place(Place(name="El Peñol", city="Guatapé",
                     department="Antioquia", category="nature"))
    yield tmp_path
    close_db()


def test_export_creates_main_json(setup_db_with_places):
    from backend.exporters.json_exporter import export_json
    path = export_json()
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["metadata"]["total_places"] == 3
    assert len(data["places"]) == 3


def test_export_creates_by_city_files(setup_db_with_places):
    from backend.exporters.json_exporter import export_json, BY_CITY_DIR
    export_json()
    bogota_file = BY_CITY_DIR / "bogota.json"
    assert bogota_file.exists()
    data = json.loads(bogota_file.read_text(encoding="utf-8"))
    assert data["metadata"]["total_places"] == 2


def test_export_uses_camel_case_keys(setup_db_with_places):
    from backend.exporters.json_exporter import export_json
    path = export_json()
    data = json.loads(path.read_text(encoding="utf-8"))
    place = data["places"][0]
    assert "shortDescription" in place
    assert "mainImage" in place
    assert "short_description" not in place

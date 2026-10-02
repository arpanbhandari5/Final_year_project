from app import app
from scripts.import_onet import import_onet
from storage import OnetInterest, OnetOccupation, OnetSkill, db


def test_onet_import_seeds_normalized_tables_idempotently():
    first = import_onet("28.0", "2026")
    second = import_onet("28.0", "2026")
    assert first["occupations"] == second["occupations"] > 0
    assert first["skills"] == second["skills"] > 0
    with app.app_context():
        assert OnetOccupation.query.count() == first["occupations"]
        assert OnetSkill.query.count() == first["skills"]
        assert OnetInterest.query.count() == first["interests"]
        assert OnetOccupation.query.filter_by(release_version="28.0").first() is not None


def test_occupation_search_and_soc_lookup():
    client = app.test_client()
    with app.app_context():
        code = OnetOccupation.query.order_by(OnetOccupation.onet_soc_code.asc()).first().onet_soc_code
    search = client.get(f"/api/occupations/search?q={code}")
    assert search.status_code == 200
    assert any(item["onet_soc_code"] == code for item in search.json["occupations"])
    detail = client.get(f"/api/occupations/{code}")
    assert detail.status_code == 200
    assert detail.json["occupation"]["provenance"]["source"] == "O*NET 28.0 Database"
    assert detail.json["occupation"]["tasks"]


def test_occupation_compare_and_missing_data_fallbacks():
    client = app.test_client()
    with app.app_context():
        codes = [row.onet_soc_code for row in OnetOccupation.query.order_by(OnetOccupation.onet_soc_code.asc()).limit(2).all()]
    comparison = client.get(f"/api/occupations/{codes[0]}/compare?compare_to={codes[1]}")
    assert comparison.status_code == 200
    assert "shared_skills" in comparison.json
    missing = client.get("/api/occupations/99-9999.00")
    assert missing.status_code == 404
    assert missing.json["fallback"] is True
    missing_compare = client.get(f"/api/occupations/{codes[0]}/compare?compare_to=99-9999.00")
    assert missing_compare.status_code == 404
    assert missing_compare.json["fallback"] is True

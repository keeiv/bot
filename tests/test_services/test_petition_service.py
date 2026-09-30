from datetime import date
import json

from src.services.petition_service import PetitionService


def test_sign_tracks_streak_and_persists(tmp_path):
    data_file = tmp_path / "petition.json"
    service = PetitionService(str(data_file))

    assert service.sign(123, date(2026, 8, 17)) == 1
    assert service.sign(123, date(2026, 8, 17)) == 1
    assert service.sign(123, date(2026, 8, 18)) == 2
    assert service.sign(123, date(2026, 8, 20)) == 1

    with data_file.open(encoding="utf-8") as file:
        assert json.load(file) == {"123": {"streak": 1, "last_sign": "2026-08-20"}}

from datetime import date
from pathlib import Path
from typing import Any

import pytest

import base
import db
import virais
from metricas import Video

CANAL: dict[str, Any] = {"nome": "Pequeno", "handle": "@p", "pais": "BR", "inscritos": 20_000, "avatar": "http://a"}


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "teste.db")
    db.iniciar()


def test_regra_viral_nos_limites() -> None:
    assert virais.eh_viral(1_000_000, 50_000)
    assert not virais.eh_viral(999_999, 1_000)
    assert not virais.eh_viral(5_000_000, 50_001)
    assert not virais.eh_viral(5_000_000, None)  # inscritos ocultos: não dá para dizer que é pequeno
    assert not virais.eh_viral(None, 1_000)      # busca sem contagem de views


def test_gravar_e_listar_com_razao() -> None:
    virais.gravar(Video("v1", "Hit", 2_000_000, 45, date(2026, 9, 1)), "UCp", CANAL, "pt", "termo")
    [v] = virais.listar()
    assert v["razao"] == 100.0 and v["short"] is True and v["termo"] == "termo"
    assert base.avatar_url("UCp") == "http://a"  # canal fora da base ainda tem avatar


def test_regravar_atualiza_views_e_mantem_adicionado(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(virais, "agora", lambda: "2026-09-01T00:00:00")
    virais.gravar(Video("v1", "Hit", 2_000_000, 600, date(2026, 8, 1)), "UCp", CANAL, "pt", "a")
    monkeypatch.setattr(virais, "agora", lambda: "2026-09-30T00:00:00")
    virais.gravar(Video("v1", "Hit", 3_000_000, 600, date(2026, 8, 1)), "UCp", CANAL, "pt", "b")
    [v] = virais.listar()
    assert v["views"] == 3_000_000 and v["adicionado"] == "2026-09-01T00:00:00" and v["termo"] == "a"


def test_videos_da_base_entram_se_batem_a_regra() -> None:
    canal = {"id": "UCb", "nome": "Base", "handle": "@b", "avatar": "x", "pais": "US", "criado": "2026-01-01",
             "primeiro_video": "2026-08-01", "formato": "longo", "inscritos": 40_000, "views_total": 1,
             "qtd_videos": 2}
    base.gravar(canal, [Video("b1", "Viral", 1_500_000, 600, date(2026, 8, 1)),
                        Video("b2", "Normal", 20_000, 600, date(2026, 8, 5))], "en", ["x"])
    assert [v["video_id"] for v in virais.listar()] == ["b1"]

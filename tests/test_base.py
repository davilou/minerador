from datetime import date
from pathlib import Path
from typing import Any

import pytest

import base
import db
from metricas import Video

HOJE = date(2026, 9, 30)


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "teste.db")
    db.iniciar()


def canal(views: int = 500_000, **extra: Any) -> dict[str, Any]:
    return {"id": "UC1", "nome": "Canal", "handle": "@canal", "avatar": "http://a", "pais": "BR",
            "criado": "2026-09-01", "primeiro_video": "2026-09-20", "formato": "longo",
            "inscritos": 1000, "views_total": views, "qtd_videos": 2} | extra


VIDEOS = [Video("v1", "Primeiro", 400_000, 600, date(2026, 9, 20)),
          Video("v2", "Segundo", 100_000, 90, date(2026, 9, 25))]


def test_gravar_de_novo_soma_termos_e_mantem_favorito() -> None:
    base.gravar(canal(), VIDEOS, "pt", ["b", "a"])
    assert base.favoritar("UC1", True)
    base.gravar(canal(views=900_000, nome="Novo nome"), VIDEOS, "en", ["c", "a"])

    [c] = base.listar(HOJE)
    assert c["termos"] == ["a", "b", "c"]
    assert c["favorito"] is True
    assert c["nome"] == "Novo nome" and c["views_total"] == 900_000
    assert c["idioma"] == "pt"  # idioma da primeira mineração que achou o canal


def test_card_traz_metricas_e_abas() -> None:
    base.gravar(canal(), VIDEOS, "pt", ["a"])
    [c] = base.listar(HOJE)
    assert c["dias_postando"] == 10
    assert c["videos_mes"] == 6 and c["views_mes"] == 1_500_000
    assert c["tracao_30d"] == 500_000
    assert [t["id"] for t in c["top"]] == ["v1", "v2"] and c["top"][1]["short"] is True
    assert set(c["abas"]) == {"todos", "explodindo", "novos", "tracao"}
    assert c["subida_dia"] is None  # uma foto só


def test_canal_que_voltou_conta_so_a_fase_atual() -> None:
    antigos = [Video("velho", "Hit de 2021", 5_000_000, 600, date(2021, 3, 1))]
    novos = [Video("n1", "Volta 1", 80_000, 600, date(2026, 9, 22)),
             Video("n2", "Volta 2", 30_000, 600, date(2026, 9, 26))]
    base.gravar(canal(views=5_110_000, primeiro_video="2021-03-01", qtd_videos=3), antigos + novos, "pt", ["a"])
    [c] = base.listar(HOJE)
    assert c["inicio_fase"] == "2026-09-22" and c["dias_postando"] == 8
    assert c["hiato_dias"] == (date(2026, 9, 22) - date(2021, 3, 1)).days
    assert c["views_fase"] == 110_000 and c["videos_mes"] == 8
    assert "explodindo" in c["abas"]  # 8 dias, 110 mil na fase — o hit de 2021 não conta
    assert "novos" in c["abas"]


NUMEROS = {"UC1": {"nome": "Canal", "avatar": "http://b", "inscritos": 2000, "views_total": 800_000, "videos": 3}}


def test_atualizar_numeros_grava_views_videos_novos_e_foto() -> None:
    base.gravar(canal(), VIDEOS, "pt", ["a"])
    novo = Video("v3", "Novo", 70_000, 600, date(2026, 9, 29))
    base.atualizar_numeros(NUMEROS, {"v2": 350_000}, {"UC1": [novo]})
    [c] = base.listar(HOJE)
    assert c["views_total"] == 800_000 and c["qtd_videos"] == 3 and c["avatar"] == "http://b"
    assert [(t["id"], t["views"]) for t in c["top"]] == [("v1", 400_000), ("v2", 350_000), ("v3", 70_000)]


def test_subida_mede_soma_dos_videos_nao_total_do_canal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(base, "agora", lambda: "2026-09-29T00:00:00")
    base.gravar(canal(), VIDEOS, "pt", ["a"])  # foto 1: vídeos somam 500 mil
    monkeypatch.setattr(base, "agora", lambda: "2026-09-30T00:00:00")
    # o total do canal na API não mexeu, mas v2 subiu 250 mil e entrou v3 com 70 mil
    parado = {"UC1": NUMEROS["UC1"] | {"views_total": 500_000}}
    base.atualizar_numeros(parado, {"v2": 350_000}, {"UC1": [Video("v3", "Novo", 70_000, 600, date(2026, 9, 29))]})
    [c] = base.listar(HOJE)
    assert c["subida_dia"] == 320_000
    assert "subindo" in c["abas"]


def test_favoritar_canal_inexistente() -> None:
    assert base.favoritar("UC-nao-existe", True) is False

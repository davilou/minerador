import shutil
from collections.abc import Iterator
from datetime import date
from pathlib import Path

import pytest

import base
import candidatos
import db
import nichos
import placar
import sugestoes
from metricas import Video


@pytest.fixture(autouse=True)
def isolado(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "teste.db")
    db.iniciar()
    shutil.copy(nichos.ARQUIVO, tmp_path / "nichos.json")
    monkeypatch.setattr(nichos, "ARQUIVO", tmp_path / "nichos.json")
    nichos.carregar.cache_clear()
    nichos._por_termo.cache_clear()
    yield
    nichos.carregar.cache_clear()
    nichos._por_termo.cache_clear()


def canal_na_base(cid: str, titulos: list[str], termos: list[str]) -> None:
    canal = {"id": cid, "nome": f"Canal {cid}", "handle": "@x", "avatar": "x", "pais": "BR", "criado": "2026-01-01",
             "primeiro_video": "2026-08-01", "formato": "longo", "inscritos": 1_000, "views_total": 1, "qtd_videos": 1}
    videos = [Video(f"{cid}-{i}", t, 10, 600, date(2026, 8, 1)) for i, t in enumerate(titulos)]
    base.gravar(canal, videos, "pt", termos)


def test_ler_resposta_do_autocompletar() -> None:
    resposta = 'window.google.ac.h(["x",[["x a",0,[512]],["x b",0,[512,433]]],{"k":1}])'
    assert sugestoes.ler(resposta) == ["x a", "x b"]


def test_de_titulos_gera_com_categoria_e_evidencia() -> None:
    for cid in ("UC1", "UC2", "UC3"):
        canal_na_base(cid, ["Carl Jung e a sombra", "outro vídeo"], ["estoicismo"])
    assert candidatos.de_titulos("pt") == 1
    [c] = candidatos.listar()
    assert (c["termo"], c["origem"], c["categoria"], c["status"]) == ("carl jung", "titulos", "autoajuda", "novo")
    assert c["evidencia"].startswith("3 canais: Canal UC1")
    assert candidatos.de_titulos("pt") == 0  # já é candidato: não volta


def test_de_autocompletar_parte_do_que_rende_e_pula_conhecido(monkeypatch: pytest.MonkeyPatch) -> None:
    placar.registrar("pt", {"estoicismo": (10, 2), "nada": (10, 0)})
    sementes: list[str] = []

    def sugerir(semente: str, hl: str, gl: str) -> list[str]:
        sementes.append(semente)
        return ["estoicismo marco aurélio", "estoicismo frases", "estoicismo sêneca", "estoicismo epicteto"]

    monkeypatch.setattr(sugestoes, "sugerir", sugerir)
    candidatos._gravar("pt", "titulos", [("estoicismo frases", None, "x")])
    assert candidatos.de_autocompletar("pt") == candidatos.POR_SEMENTE
    assert sementes == ["estoicismo"]
    novos = {c["termo"]: c for c in candidatos.listar() if c["origem"] == "autocompletar"}
    assert set(novos) == {"estoicismo marco aurélio", "estoicismo sêneca", "estoicismo epicteto"}
    assert all(c["categoria"] == "autoajuda" for c in novos.values())


def test_para_testar_filtra_categoria_e_tira_quem_ja_aprovou() -> None:
    candidatos._gravar("pt", "titulos", [("sem cat", None, ""), ("de games", "games", ""),
                                          ("de historia", "historia", ""), ("ja rendeu", None, "")])
    placar.registrar("pt", {"ja rendeu": (5, 1)})
    assert set(candidatos.para_testar("pt", ["historia"], 10)) == {"sem cat", "de historia"}
    assert candidatos.pendentes() == {"pt": 3}


def test_revisar_descarta_quem_nao_rendeu() -> None:
    candidatos._gravar("pt", "titulos", [("fraco", None, ""), ("forte", None, "")])
    for _ in range(candidatos.DESCARTE_BUSCAS):
        placar.registrar("pt", {"fraco": (5, 0), "forte": (5, 1)})
    assert candidatos.revisar("pt") == 1
    status = {c["termo"]: c["status"] for c in candidatos.listar()}
    assert status == {"fraco": "descartado", "forte": "novo"}


def test_promover_poe_no_nichos_e_some_dos_pendentes() -> None:
    candidatos._gravar("pt", "titulos", [("carl jung", "autoajuda", "")])
    assert candidatos.promover("carl jung", "pt", "autoajuda", None) == "autoajuda"
    assert "carl jung" in nichos.termos("pt", ["autoajuda"])
    assert candidatos.listar()[0]["status"] == "promovido" and candidatos.pendentes() == {}
    with pytest.raises(ValueError):
        candidatos.promover("não existe", "pt", "autoajuda", None)

from pathlib import Path

import pytest

import db
import placar


@pytest.fixture(autouse=True)
def banco_temporario(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "teste.db")
    db.iniciar()


def item(termo: str, canal: str) -> dict[str, str]:
    return {"termo": termo, "canal_id": canal, "video_id": f"{termo}-{canal}"}


def test_contar_canais_distintos_e_aprovados() -> None:
    itens = [item("a", "UC1"), item("a", "UC1"), item("a", "UC2"), item("b", "UC2")]
    achados = [{"id": "UC2", "termos": ["a", "b"]}]
    assert placar.contar(["a", "b", "c"], itens, achados) == {"a": (2, 1), "b": (1, 1), "c": (0, 0)}


def test_registrar_soma_e_marca_quem_nao_rende() -> None:
    for _ in range(placar.NAO_RENDE_BUSCAS):
        placar.registrar("pt", {"bom": (5, 1), "ruim": (8, 0)})
    linhas = {r["termo"]: r for r in placar.listar()}
    assert (linhas["bom"]["buscas"], linhas["bom"]["canais"], linhas["bom"]["aprovados"]) == (3, 15, 3)
    assert linhas["ruim"]["nao_rende"] and not linhas["bom"]["nao_rende"]
    assert placar.rendendo("pt", 5) == ["bom"]


def test_aposentar_tira_da_lista_e_do_autocompletar() -> None:
    placar.registrar("en", {"x": (3, 2)})
    assert placar.aposentar("x", "en", True)
    assert placar.aposentados("en") == {"x"} and placar.aposentados("pt") == set()
    assert placar.rendendo("en", 5) == []
    assert not placar.aposentar("nunca buscado", "en", True)


def test_importar_do_historico_ignora_termo_que_falhou() -> None:
    params = {"termos": ["ok", "falhou"], "hl": "pt", "gl": "BR", "periodo": "7d", "por_termo": 40}
    db.cache_gravar("ok|pt|BR|7d|40", [{"canal_id": "UC1"}, {"canal_id": "UC2"}, {"canal_id": "UC1"}])
    id_ = db.criar_mineracao(params)
    db.atualizar(id_, status="pronto", resultado=[{"id": "UC1", "termos": ["ok"]}], erro="1 termo de fora")
    assert placar.importar_do_historico() == 1
    [linha] = placar.listar()
    assert (linha["termo"], linha["buscas"], linha["canais"], linha["aprovados"]) == ("ok", 1, 2, 1)

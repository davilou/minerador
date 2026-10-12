import shutil
from collections import defaultdict
from collections.abc import Iterator
from pathlib import Path

import pytest

import nichos


def test_arquivo_valido_e_grande() -> None:
    dados = nichos.carregar()
    assert len(dados) >= 25
    for idioma in nichos.MERCADOS:
        assert len(nichos.termos(idioma, list(dados))) >= 90


def test_termo_nao_aparece_em_duas_categorias() -> None:
    """categorias_de depende disso: termo repetido entre categorias ficaria ambíguo."""
    donos: dict[str, set[str]] = defaultdict(set)
    for cid, cat in nichos.carregar().items():
        for idioma in nichos.MERCADOS:
            for t in cat[idioma]:
                donos[t.lower()].add(cid)
    ambiguos = {t: c for t, c in donos.items() if len(c) > 1}
    assert not ambiguos


def test_categorias_de_ignora_termo_digitado_a_mao() -> None:
    assert nichos.categorias_de(["Stoicism", "termo meu qualquer", "minecraft"]) == ["autoajuda", "games"]


def test_termos_recusa_idioma_ou_categoria_desconhecidos() -> None:
    with pytest.raises(ValueError):
        nichos.termos("fr", ["historia"])
    with pytest.raises(ValueError):
        nichos.termos("pt", ["nao_existe"])


@pytest.fixture
def copia(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    destino = tmp_path / "nichos.json"
    shutil.copy(nichos.ARQUIVO, destino)
    monkeypatch.setattr(nichos, "ARQUIVO", destino)
    nichos.carregar.cache_clear()
    nichos._por_termo.cache_clear()
    yield destino
    nichos.carregar.cache_clear()
    nichos._por_termo.cache_clear()


def test_serializar_reproduz_o_arquivo(copia: Path) -> None:
    assert nichos._serializar(nichos.carregar()) == copia.read_text(encoding="utf-8")


def test_adicionar_termo_em_categoria_existente(copia: Path) -> None:
    assert nichos.adicionar("carl jung explica", "pt", "autoajuda") == "autoajuda"
    assert "carl jung explica" in nichos.termos("pt", ["autoajuda"])
    assert nichos.categorias_de(["carl jung explica"]) == ["autoajuda"]


def test_adicionar_cria_categoria_nova(copia: Path) -> None:
    assert nichos.adicionar("billionaire ceo", "en", None, "Romance de Bilionário") == "romance_de_bilionario"
    cat = nichos.carregar()["romance_de_bilionario"]
    assert cat["nome"] == "Romance de Bilionário" and cat["en"] == ["billionaire ceo"] and cat["pt"] == []


def test_adicionar_recusa_repetido_e_categoria_errada(copia: Path) -> None:
    with pytest.raises(ValueError):
        nichos.adicionar("Minecraft", "en", "games")  # já existe (com outra caixa)
    with pytest.raises(ValueError):
        nichos.adicionar("termo novo", "pt", "nao_existe")
    with pytest.raises(ValueError):
        nichos.adicionar("termo novo", "pt", None, "História")  # id 'historia' já existe

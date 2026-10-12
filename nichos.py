"""
Nichos da varredura geral: categorias com termos-semente por idioma, em nichos.json (editável).
Também diz a categoria de um canal pelos termos que o acharam.
"""

from __future__ import annotations

import copy
import json
import re
import unicodedata
from functools import cache
from pathlib import Path
from typing import Any

ARQUIVO = Path(__file__).parent / "nichos.json"
MERCADOS: dict[str, str] = {"pt": "BR", "en": "US", "es": "MX", "de": "DE"}  # idioma -> país da busca


@cache
def carregar() -> dict[str, dict[str, Any]]:
    dados: dict[str, dict[str, Any]] = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    for cid, cat in dados.items():
        faltam = set(MERCADOS) - cat.keys()
        if "nome" not in cat or faltam:
            raise ValueError(f"nichos.json: categoria {cid!r} sem nome ou sem idiomas {sorted(faltam)}")
    return dados


def termos(idioma: str, categorias: list[str]) -> list[str]:
    if idioma not in MERCADOS:
        raise ValueError(f"idioma sem mercado definido: {idioma!r}")
    dados = carregar()
    desconhecidas = set(categorias) - dados.keys()
    if desconhecidas:
        raise ValueError(f"categorias desconhecidas: {sorted(desconhecidas)}")
    return list(dict.fromkeys(t for c in categorias for t in dados[c][idioma]))


@cache
def _por_termo() -> dict[str, str]:
    return {t.lower(): cid for cid, cat in carregar().items() for i in MERCADOS for t in cat[i]}


def categorias_de(termos_do_canal: list[str]) -> list[str]:
    """Categorias (ids) dos termos que acharam o canal; termo digitado à mão não tem categoria."""
    mapa = _por_termo()
    return sorted({mapa[t.lower()] for t in termos_do_canal if t.lower() in mapa})


def resumo() -> list[dict[str, Any]]:
    """Para o painel: id, nome e quantos termos cada categoria tem por idioma."""
    return [{"id": cid, "nome": cat["nome"], "termos": {i: len(cat[i]) for i in MERCADOS}}
            for cid, cat in carregar().items()]


def _serializar(dados: dict[str, dict[str, Any]]) -> str:
    """Mesmo formato do arquivo escrito à mão: uma linha por idioma."""
    blocos = []
    for cid, cat in dados.items():
        linhas = [f'    "nome": {json.dumps(cat["nome"], ensure_ascii=False)}']
        linhas += [f'    "{i}": {json.dumps(cat[i], ensure_ascii=False)}' for i in MERCADOS]
        blocos.append(f"  {json.dumps(cid)}: {{\n" + ",\n".join(linhas) + "\n  }")
    return "{\n" + ",\n".join(blocos) + "\n}\n"


def _id_de(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")


def adicionar(termo: str, idioma: str, categoria: str | None, nome_nova: str | None = None) -> str:
    """
    Põe o termo no nichos.json (promoção de um candidato). Com nome_nova, cria a categoria.
    Recusa termo que já existe em qualquer categoria: categorias_de ficaria ambíguo. Devolve o id.
    """
    if idioma not in MERCADOS:
        raise ValueError(f"idioma sem mercado definido: {idioma!r}")
    if termo.strip().lower() in _por_termo():
        raise ValueError(f"termo já está no nichos.json: {termo!r}")
    dados = copy.deepcopy(carregar())
    if nome_nova:
        categoria = _id_de(nome_nova)
        if not categoria or categoria in dados:
            raise ValueError(f"categoria já existe ou nome inválido: {nome_nova!r}")
        dados[categoria] = {"nome": nome_nova.strip()} | {i: [] for i in MERCADOS}
    elif categoria not in dados:
        raise ValueError(f"categoria desconhecida: {categoria!r}")
    dados[categoria][idioma].append(termo.strip())
    temporario = ARQUIVO.with_suffix(".tmp")
    temporario.write_text(_serializar(dados), encoding="utf-8")
    temporario.replace(ARQUIVO)
    carregar.cache_clear()
    _por_termo.cache_clear()
    return categoria

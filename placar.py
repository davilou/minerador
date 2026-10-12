"""
Placar dos termos: quanto cada busca rende. Por termo e idioma, soma as buscas, os canais distintos
que ela trouxe e quantos passaram no filtro da mineração. É o que diz qual termo não vale a busca
(o orçamento é curto: busca em massa leva 403) e qual candidato merece virar semente.
"""

from __future__ import annotations

from collections import defaultdict
from contextlib import closing
from typing import Any

import db
import nichos

# Termo buscado tantas vezes sem aprovar nenhum canal: o painel marca "não rende".
NAO_RENDE_BUSCAS = 3

Contagem = tuple[int, int]  # (canais distintos trazidos, canais aprovados)


def contar(buscados: list[str], itens: list[dict[str, Any]], achados: list[dict[str, Any]]) -> dict[str, Contagem]:
    """Placar de uma mineração. itens = vídeos das buscas com item["termo"]; achados = canais aprovados."""
    canais: dict[str, set[str]] = defaultdict(set)
    for item in itens:
        canais[item["termo"]].add(item["canal_id"])
    aprovados: dict[str, int] = defaultdict(int)
    for canal in achados:
        for termo in canal["termos"]:
            aprovados[termo] += 1
    return {t: (len(canais[t]), aprovados[t]) for t in buscados}


def registrar(idioma: str, contagem: dict[str, Contagem]) -> None:
    with closing(db.conectar()) as con, con:
        con.executemany(
            "INSERT INTO termo_placar (termo, idioma, buscas, canais, aprovados, ultima) VALUES (?, ?, 1, ?, ?, ?) "
            "ON CONFLICT(termo, idioma) DO UPDATE SET buscas = buscas + 1, canais = canais + excluded.canais, "
            "aprovados = aprovados + excluded.aprovados, ultima = excluded.ultima",
            [(t, idioma, c, a, db.agora()) for t, (c, a) in contagem.items()])


def listar() -> list[dict[str, Any]]:
    with closing(db.conectar()) as con:
        rows = con.execute("SELECT * FROM termo_placar ORDER BY aprovados DESC, buscas").fetchall()
    return [dict(r) | {"aposentado": bool(r["aposentado"]), "categorias": nichos.categorias_de([r["termo"]]),
                       "nao_rende": r["buscas"] >= NAO_RENDE_BUSCAS and r["aprovados"] == 0}
            for r in rows]


def aposentar(termo: str, idioma: str, valor: bool) -> bool:
    """Termo aposentado fica fora da varredura. Devolve False se o termo nunca foi buscado."""
    with closing(db.conectar()) as con, con:
        cur = con.execute("UPDATE termo_placar SET aposentado = ? WHERE termo = ? AND idioma = ?",
                          (int(valor), termo, idioma))
    return cur.rowcount > 0


def aposentados(idioma: str) -> set[str]:
    with closing(db.conectar()) as con:
        return {r["termo"] for r in con.execute(
            "SELECT termo FROM termo_placar WHERE idioma = ? AND aposentado = 1", (idioma,))}


def rendendo(idioma: str, limite: int) -> list[str]:
    """Os termos que mais aprovam canal por busca: sementes boas para o autocompletar."""
    with closing(db.conectar()) as con:
        return [r["termo"] for r in con.execute(
            "SELECT termo FROM termo_placar WHERE idioma = ? AND aprovados > 0 AND aposentado = 0 "
            "ORDER BY CAST(aprovados AS REAL) / buscas DESC, aprovados DESC LIMIT ?", (idioma, limite))]


def importar_do_historico() -> int:
    """
    Uma vez só: monta o placar das minerações feitas antes dele existir. Os canais trazidos saem da
    busca em cache; mineração incompleta só conta o termo que tem busca em cache (o resto falhou).
    """
    cache: dict[tuple[str, ...], set[str]] = {}
    for chave, itens in db.cache_todos():
        cache[tuple(chave.split("|"))] = {i["canal_id"] for i in itens}
    buscados_em = {(k[0], k[1]) for k in cache}  # (termo, hl)
    total: dict[tuple[str, str], list[int]] = defaultdict(lambda: [0, 0, 0])
    for m in db.listar_mineracoes(limite=10_000):
        completa = db.ler_mineracao(m["id"])
        if completa is None or completa["status"] != "pronto":
            continue
        p = completa["parametros"]
        achados = completa["resultado"] or []
        for termo in p["termos"]:
            if completa["erro"] and (termo, p["hl"]) not in buscados_em:
                continue
            busca = (termo, p["hl"], p["gl"], p["periodo"], str(p["por_termo"]))
            soma = total[(termo, p["hl"])]
            soma[0] += 1
            soma[1] += len(cache.get(busca, set()))
            soma[2] += sum(termo in c["termos"] for c in achados)
    with closing(db.conectar()) as con, con:
        con.executemany(
            "INSERT OR IGNORE INTO termo_placar (termo, idioma, buscas, canais, aprovados, ultima) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [(t, i, b, c, a, db.agora()) for (t, i), (b, c, a) in total.items()])
    return len(total)

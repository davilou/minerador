"""
Termos candidatos: o ciclo que acha nicho que ninguém pôs no nichos.json.
Nascem dos títulos dos canais aprovados (titulos.py) e do autocompletar a partir dos termos que
mais rendem (sugestoes.py), entram numa fatia da varredura, e o placar decide: candidato que
aprova canal fica esperando promoção no painel; o que não aprova em DESCARTE_BUSCAS buscas sai.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from contextlib import closing
from typing import Any

import db
import nichos
import placar
import sugestoes
import titulos

DESCARTE_BUSCAS = 2
MIN_CANAIS_TITULO = 3  # expressão de título vira candidato se aparece em tantos canais diferentes
POR_ORIGEM = 15  # candidatos novos por idioma e origem, a cada geração
SEMENTES_AUTOCOMPLETAR = 8  # termos que mais rendem, por idioma, usados de semente
POR_SEMENTE = 3


def _conhecidos(idioma: str) -> set[str]:
    """Tudo que já foi termo nesse idioma: semente, buscado à mão, ou candidato (até recusado)."""
    with closing(db.conectar()) as con:
        buscados = {r["termo"] for r in con.execute("SELECT termo FROM termo_placar WHERE idioma = ?", (idioma,))}
        sugeridos = {r["termo"] for r in con.execute("SELECT termo FROM termo_candidato WHERE idioma = ?", (idioma,))}
    return {t.lower() for t in set(nichos.termos(idioma, list(nichos.carregar()))) | buscados | sugeridos}


def _gravar(idioma: str, origem: str, novos: list[tuple[str, str | None, str]]) -> int:
    """novos = [(termo, categoria, evidência)]."""
    with closing(db.conectar()) as con, con:
        cur = con.executemany(
            "INSERT OR IGNORE INTO termo_candidato (termo, idioma, origem, categoria, evidencia, status, adicionado) "
            "VALUES (?, ?, ?, ?, ?, 'novo', ?)", [(t, idioma, origem, c, e, db.agora()) for t, c, e in novos])
    return cur.rowcount


def _canais_com_titulos(idioma: str) -> tuple[dict[str, list[str]], dict[str, tuple[str, list[str]]]]:
    """Títulos por canal (base + virais) e, por canal, o nome e os termos que o acharam."""
    por_canal: dict[str, list[str]] = defaultdict(list)
    info: dict[str, tuple[str, list[str]]] = {}
    with closing(db.conectar()) as con:
        for r in con.execute("SELECT c.id, c.nome, c.termos, v.titulo FROM canal c JOIN video v ON v.canal_id = c.id "
                             "WHERE c.idioma = ?", (idioma,)):
            por_canal[r["id"]].append(r["titulo"])
            info[r["id"]] = (r["nome"], json.loads(r["termos"]))
        for r in con.execute("SELECT canal_id, canal_nome, termo, titulo FROM viral WHERE idioma = ?", (idioma,)):
            por_canal[r["canal_id"]].append(r["titulo"])
            info.setdefault(r["canal_id"], (r["canal_nome"], [r["termo"]]))
    return por_canal, info


def de_titulos(idioma: str) -> int:
    por_canal, info = _canais_com_titulos(idioma)
    achados = titulos.diversos(titulos.frequentes(por_canal, _conhecidos(idioma), MIN_CANAIS_TITULO), POR_ORIGEM)
    novos = []
    for termo, canais in achados:
        votos = Counter(c for cid in canais for c in nichos.categorias_de(info[cid][1]))
        nomes = sorted(info[cid][0] for cid in canais)
        evidencia = f"{len(canais)} canais: {', '.join(nomes[:3])}{'…' if len(nomes) > 3 else ''}"
        novos.append((termo, votos.most_common(1)[0][0] if votos else None, evidencia))
    return _gravar(idioma, "titulos", novos)


def de_autocompletar(idioma: str) -> int:
    conhecidos = _conhecidos(idioma)
    novos: list[tuple[str, str | None, str]] = []
    for semente in placar.rendendo(idioma, SEMENTES_AUTOCOMPLETAR):
        categorias = nichos.categorias_de([semente])
        frescas = [s for s in sugestoes.sugerir(semente, idioma, nichos.MERCADOS[idioma])
                   if s.lower() not in conhecidos and titulos.acrescenta(semente, s)][:POR_SEMENTE]
        conhecidos |= {s.lower() for s in frescas}
        novos += [(s, categorias[0] if categorias else None, f"autocompletar de “{semente}”") for s in frescas]
    return _gravar(idioma, "autocompletar", novos[:POR_ORIGEM])


def gerar() -> dict[str, int]:
    """Gera candidatos em todos os idiomas. Custo: zero de cota; ~8 consultas ao autocompletar por idioma."""
    feitos = {"titulos": 0, "autocompletar": 0}
    for idioma in nichos.MERCADOS:
        feitos["titulos"] += de_titulos(idioma)
        feitos["autocompletar"] += de_autocompletar(idioma)
    return feitos


_COM_PLACAR = ("SELECT c.*, COALESCE(p.buscas, 0) AS buscas, COALESCE(p.canais, 0) AS canais, "
               "COALESCE(p.aprovados, 0) AS aprovados FROM termo_candidato c "
               "LEFT JOIN termo_placar p ON p.termo = c.termo AND p.idioma = c.idioma")


def listar() -> list[dict[str, Any]]:
    with closing(db.conectar()) as con:
        return [dict(r) for r in con.execute(_COM_PLACAR + " ORDER BY c.adicionado DESC")]


def para_testar(idioma: str, categorias: list[str], limite: int) -> list[str]:
    """Os que entram na varredura: novos, ainda sem canal aprovado, da categoria marcada ou sem categoria."""
    with closing(db.conectar()) as con:
        linhas = con.execute(_COM_PLACAR + " WHERE c.idioma = ? AND c.status = 'novo' AND COALESCE(p.aprovados, 0) = 0 "
                             "ORDER BY buscas, c.adicionado", (idioma,)).fetchall()
    return [r["termo"] for r in linhas if r["categoria"] is None or r["categoria"] in categorias][:limite]


def pendentes() -> dict[str, int]:
    """Por idioma, quantos candidatos ainda esperam teste (para a estimativa da varredura)."""
    with closing(db.conectar()) as con:
        return {r["idioma"]: r["n"] for r in con.execute(
            "SELECT c.idioma, COUNT(*) AS n FROM termo_candidato c LEFT JOIN termo_placar p "
            "ON p.termo = c.termo AND p.idioma = c.idioma WHERE c.status = 'novo' AND COALESCE(p.aprovados, 0) = 0 "
            "GROUP BY c.idioma")}


def revisar(idioma: str) -> int:
    """Depois de uma mineração: candidato que já teve DESCARTE_BUSCAS buscas sem aprovar nada sai."""
    with closing(db.conectar()) as con, con:
        cur = con.execute(
            "UPDATE termo_candidato SET status = 'descartado' WHERE idioma = ? AND status = 'novo' AND termo IN "
            "(SELECT termo FROM termo_placar WHERE idioma = ? AND buscas >= ? AND aprovados = 0)",
            (idioma, idioma, DESCARTE_BUSCAS))
    return cur.rowcount


def _status(termo: str, idioma: str, status: str) -> bool:
    with closing(db.conectar()) as con, con:
        cur = con.execute("UPDATE termo_candidato SET status = ? WHERE termo = ? AND idioma = ?",
                          (status, termo, idioma))
    return cur.rowcount > 0


def recusar(termo: str, idioma: str) -> bool:
    return _status(termo, idioma, "recusado")


def promover(termo: str, idioma: str, categoria: str | None, nome_nova: str | None) -> str:
    """Candidato vira semente no nichos.json; devolve o id da categoria. ValueError se não der."""
    if not any(c["termo"] == termo and c["idioma"] == idioma for c in listar()):
        raise ValueError(f"candidato não existe: {termo!r} ({idioma})")
    cid = nichos.adicionar(termo, idioma, categoria, nome_nova)
    _status(termo, idioma, "promovido")
    return cid

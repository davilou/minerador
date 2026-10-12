"""
A base acumulada: cada canal aprovado numa mineração entra aqui uma vez só e vai
ganhando termos e fotos dos números. É o que o painel de cards navega.
"""

from __future__ import annotations

import json
from collections import defaultdict
from contextlib import closing
from datetime import date, datetime
from typing import Any

import abas
import nichos
from db import agora, conectar
from metricas import Video, inicio_fase

_ATUALIZAVEIS = ("nome", "handle", "avatar", "pais", "criado", "primeiro_video", "formato",
                 "inscritos", "views_total", "qtd_videos")


def gravar(canal: dict[str, Any], videos: list[Video], idioma: str, termos: list[str]) -> None:
    """Insere o canal ou atualiza o que já existe, somando termos. Favorito e 'adicionado' ficam."""
    agora_ = agora()
    with closing(conectar()) as con, con:
        row = con.execute("SELECT termos FROM canal WHERE id = ?", (canal["id"],)).fetchone()
        todos_termos = sorted(set(termos) | set(json.loads(row["termos"]) if row else []))
        valores = {k: canal[k] for k in _ATUALIZAVEIS}
        sets = ", ".join(f"{k} = excluded.{k}" for k in _ATUALIZAVEIS)
        con.execute(
            f"INSERT INTO canal (id, idioma, termos, adicionado, atualizado, {', '.join(valores)}) "
            f"VALUES (?, ?, ?, ?, ?, {', '.join('?' * len(valores))}) "
            f"ON CONFLICT(id) DO UPDATE SET {sets}, termos = excluded.termos, atualizado = excluded.atualizado",
            (canal["id"], idioma, json.dumps(todos_termos, ensure_ascii=False), agora_, agora_, *valores.values()))
        _gravar_videos(con, canal["id"], videos)
        _foto(con, canal["id"], agora_, canal["inscritos"], canal["views_total"], canal["qtd_videos"])


def _gravar_videos(con: Any, canal_id: str, videos: list[Video]) -> None:
    con.executemany("INSERT OR REPLACE INTO video VALUES (?, ?, ?, ?, ?, ?)",
                    [(v.id, canal_id, v.titulo, v.views, v.duracao_s, v.publicado.isoformat()) for v in videos])


def _foto(con: Any, canal_id: str, em: str, inscritos: int | None, views: int, qtd: int) -> None:
    """Foto dos números. views_videos (soma das views dos vídeos) é o que mede subida: o total
    do canal na API fica parado por horas, a view de cada vídeo sobe quase em tempo real."""
    soma = con.execute("SELECT coalesce(sum(views), 0) FROM video WHERE canal_id = ?", (canal_id,)).fetchone()[0]
    con.execute("INSERT OR REPLACE INTO foto (canal_id, em, inscritos, views_total, qtd_videos, views_videos) "
                "VALUES (?, ?, ?, ?, ?, ?)", (canal_id, em, inscritos, views, qtd, soma))


def atualizar_numeros(canais: dict[str, dict[str, Any]], views_videos: dict[str, int],
                      novos: dict[str, list[Video]]) -> None:
    """Grava números relidos e vídeos novos de cada canal, e tira uma foto nova (depois dos vídeos)."""
    agora_ = agora()
    with closing(conectar()) as con, con:
        con.executemany("UPDATE video SET views = ? WHERE id = ?", [(v, vid) for vid, v in views_videos.items()])
        for cid, videos in novos.items():
            _gravar_videos(con, cid, videos)
        for cid, c in canais.items():
            con.execute("UPDATE canal SET nome = ?, avatar = ?, inscritos = ?, views_total = ?, "
                        "qtd_videos = ?, atualizado = ? WHERE id = ?",
                        (c["nome"], c["avatar"], c["inscritos"], c["views_total"], c["videos"], agora_, cid))
            _foto(con, cid, agora_, c["inscritos"], c["views_total"], c["videos"])


def ultima_foto() -> datetime | None:
    """Quando os números foram lidos pela última vez (mineração ou Atualizar)."""
    with closing(conectar()) as con:
        row = con.execute("SELECT max(em) AS em FROM foto").fetchone()
    return None if row["em"] is None else datetime.fromisoformat(row["em"])


def ids_canais() -> list[str]:
    with closing(conectar()) as con:
        return [r["id"] for r in con.execute("SELECT id FROM canal")]


def ids_videos() -> list[str]:
    with closing(conectar()) as con:
        return [r["id"] for r in con.execute("SELECT id FROM video")]


def avatar_url(canal_id: str) -> str | None:
    with closing(conectar()) as con:
        row = con.execute("SELECT avatar FROM canal WHERE id = ? UNION ALL "
                          "SELECT url FROM avatar_url WHERE canal_id = ?", (canal_id, canal_id)).fetchone()
    return None if row is None else str(row[0])


def favoritar(canal_id: str, valor: bool) -> bool:
    """False se o canal não existe."""
    with closing(conectar()) as con, con:
        cur = con.execute("UPDATE canal SET favorito = ? WHERE id = ?", (int(valor), canal_id))
    return cur.rowcount == 1


def meta_ler(chave: str) -> str | None:
    with closing(conectar()) as con:
        row = con.execute("SELECT valor FROM meta WHERE chave = ?", (chave,)).fetchone()
    return None if row is None else str(row["valor"])


def meta_gravar(chave: str, valor: str) -> None:
    with closing(conectar()) as con, con:
        con.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (chave, valor))


def listar(hoje: date) -> list[dict[str, Any]]:
    """Todos os canais já com as métricas dos cards e as abas em que cada um aparece."""
    with closing(conectar()) as con:
        canais = [dict(r) for r in con.execute("SELECT * FROM canal")]
        videos: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in con.execute("SELECT * FROM video ORDER BY views DESC"):
            videos[r["canal_id"]].append(dict(r))
        fotos: dict[str, list[abas.Foto]] = defaultdict(list)
        # Fotos de antes da coluna views_videos existir não servem para medir subida.
        for r in con.execute("SELECT canal_id, em, views_videos FROM foto WHERE views_videos IS NOT NULL"):
            fotos[r["canal_id"]].append(abas.Foto(datetime.fromisoformat(r["em"]), r["views_videos"]))
    return [_card(c, videos[c["id"]], fotos[c["id"]], hoje) for c in canais]


def _card(c: dict[str, Any], videos: list[dict[str, Any]], fotos: list[abas.Foto], hoje: date) -> dict[str, Any]:
    vb = [abas.VideoBase(v["views"], date.fromisoformat(v["publicado"])) for v in videos]
    # Canal que voltou de hiato conta idade, ritmo e "explodindo" só com os vídeos da fase atual.
    inicio, hiato = inicio_fase([v.publicado for v in vb])
    fase = [v for v in vb if v.publicado >= inicio]
    views_fase = sum(v.views for v in fase)
    dias = abas.dias_postando(inicio, hoje)
    tracao, outlier, subida = abas.tracao_recente(vb, hoje), abas.fator_outlier(vb), abas.subida_por_dia(fotos)
    return c | {
        "termos": json.loads(c["termos"]), "categorias": nichos.categorias_de(json.loads(c["termos"])),
        "favorito": bool(c["favorito"]),
        "url": f"https://www.youtube.com/channel/{c['id']}",
        "inicio_fase": inicio.isoformat(), "hiato_dias": hiato, "views_fase": views_fase,
        "dias_postando": dias, "videos_mes": abas.por_mes(len(fase), dias),
        "views_mes": abas.por_mes(views_fase, dias), "tracao_30d": tracao,
        "fator_outlier": outlier, "subida_dia": subida,
        "abas": abas.abas_do_canal(views_fase, dias, tracao, outlier, subida, bool(c["favorito"])),
        "top": [{"id": v["id"], "titulo": v["titulo"], "views": v["views"], "short": v["duracao_s"] <= 180}
                for v in videos[:3]],
    }

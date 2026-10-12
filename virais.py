"""
Aba "Virais": vídeos com 1 mi+ views de canais pequenos, qualquer que seja a idade ou o tamanho
da biblioteca do canal. A busca já traz esses vídeos; aqui eles são guardados em vez de descartados.
"""

from __future__ import annotations

from contextlib import closing
from typing import Any

import nichos
from db import agora, conectar
from metricas import SHORT_MAX_S, Video

VIRAL_MIN_VIEWS = 1_000_000
PEQUENO_MAX_INSCRITOS = 50_000
DESCRICAO = (f"Vídeos com {VIRAL_MIN_VIEWS // 1_000_000} mi+ views de canais com até "
             f"{PEQUENO_MAX_INSCRITOS // 1000} mil inscritos")


def eh_viral(views: int | None, inscritos: int | None) -> bool:
    """Inscritos ocultos (None) ficam de fora: sem eles não dá para dizer que o canal é pequeno."""
    return (views is not None and inscritos is not None
            and views >= VIRAL_MIN_VIEWS and inscritos <= PEQUENO_MAX_INSCRITOS)


def gravar(video: Video, canal_id: str, canal: dict[str, Any], idioma: str, termo: str) -> None:
    """Insere ou atualiza o vídeo; 'adicionado' e o primeiro termo que o achou ficam."""
    agora_ = agora()
    with closing(conectar()) as con, con:
        con.execute(
            "INSERT INTO viral (video_id, canal_id, titulo, views, duracao_s, publicado, canal_nome, "
            "canal_handle, canal_pais, inscritos, idioma, termo, adicionado, atualizado) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(video_id) DO UPDATE SET views = excluded.views, inscritos = excluded.inscritos, "
            "titulo = excluded.titulo, atualizado = excluded.atualizado",
            (video.id, canal_id, video.titulo, video.views, video.duracao_s, video.publicado.isoformat(),
             canal["nome"], canal["handle"], canal["pais"], canal["inscritos"], idioma, termo, agora_, agora_))
        con.execute("INSERT OR REPLACE INTO avatar_url VALUES (?, ?)", (canal_id, canal["avatar"]))


def ids() -> list[str]:
    with closing(conectar()) as con:
        return [r["video_id"] for r in con.execute("SELECT video_id FROM viral")]


def atualizar_views(views: dict[str, int]) -> None:
    agora_ = agora()
    with closing(conectar()) as con, con:
        con.executemany("UPDATE viral SET views = ?, atualizado = ? WHERE video_id = ?",
                        [(v, agora_, vid) for vid, v in views.items()])


_DA_BASE = """
    SELECT v.id AS video_id, v.canal_id, v.titulo, v.views, v.duracao_s, v.publicado,
           c.nome AS canal_nome, c.handle AS canal_handle, c.pais AS canal_pais, c.inscritos,
           c.idioma, json_extract(c.termos, '$[0]') AS termo, c.adicionado, c.atualizado
    FROM video v JOIN canal c ON c.id = v.canal_id
    WHERE v.views >= ? AND c.inscritos <= ? AND v.id NOT IN (SELECT video_id FROM viral)
"""


def listar() -> list[dict[str, Any]]:
    """Virais guardados + vídeos dos canais da base que batem a mesma regra."""
    with closing(conectar()) as con:
        linhas = [dict(r) for r in con.execute("SELECT * FROM viral")]
        linhas += [dict(r) for r in con.execute(_DA_BASE, (VIRAL_MIN_VIEWS, PEQUENO_MAX_INSCRITOS))]
    return [v | {"short": v["duracao_s"] <= SHORT_MAX_S, "categorias": nichos.categorias_de([v["termo"] or ""]),
                 "razao": round(v["views"] / max(v["inscritos"], 1), 1)}
            for v in linhas if eh_viral(v["views"], v["inscritos"])]

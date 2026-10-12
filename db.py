"""SQLite: cache das buscas do yt-dlp e histórico das minerações. Uma conexão por chamada (thread-safe)."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ARQUIVO = Path(__file__).parent / "minerador.db"

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS busca_cache (
    chave TEXT PRIMARY KEY, canais TEXT NOT NULL, criado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mineracao (
    id INTEGER PRIMARY KEY AUTOINCREMENT, criado TEXT NOT NULL, parametros TEXT NOT NULL,
    status TEXT NOT NULL, fase TEXT NOT NULL DEFAULT '', atual INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL DEFAULT 0, unidades INTEGER NOT NULL DEFAULT 0,
    erro TEXT, resultado TEXT
);
CREATE TABLE IF NOT EXISTS canal (
    id TEXT PRIMARY KEY, nome TEXT NOT NULL, handle TEXT NOT NULL, avatar TEXT NOT NULL,
    pais TEXT NOT NULL, idioma TEXT NOT NULL, criado TEXT NOT NULL, primeiro_video TEXT NOT NULL,
    formato TEXT NOT NULL, inscritos INTEGER, views_total INTEGER NOT NULL,
    qtd_videos INTEGER NOT NULL, termos TEXT NOT NULL, favorito INTEGER NOT NULL DEFAULT 0,
    adicionado TEXT NOT NULL, atualizado TEXT NOT NULL,
    categoria TEXT, faceless REAL, monetizado INTEGER  -- fases 3 e 4
);
CREATE TABLE IF NOT EXISTS video (
    id TEXT PRIMARY KEY, canal_id TEXT NOT NULL REFERENCES canal(id), titulo TEXT NOT NULL,
    views INTEGER NOT NULL, duracao_s INTEGER NOT NULL, publicado TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS video_canal ON video(canal_id);
CREATE TABLE IF NOT EXISTS foto (
    canal_id TEXT NOT NULL REFERENCES canal(id), em TEXT NOT NULL, inscritos INTEGER,
    views_total INTEGER NOT NULL, qtd_videos INTEGER NOT NULL, PRIMARY KEY (canal_id, em)
);
CREATE TABLE IF NOT EXISTS meta (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS viral (
    video_id TEXT PRIMARY KEY, canal_id TEXT NOT NULL, titulo TEXT NOT NULL, views INTEGER NOT NULL,
    duracao_s INTEGER NOT NULL, publicado TEXT NOT NULL, canal_nome TEXT NOT NULL,
    canal_handle TEXT NOT NULL, canal_pais TEXT NOT NULL, inscritos INTEGER NOT NULL,
    idioma TEXT NOT NULL, termo TEXT NOT NULL, adicionado TEXT NOT NULL, atualizado TEXT NOT NULL
);
-- avatar de canal que não está na base (dono de um viral)
CREATE TABLE IF NOT EXISTS avatar_url (canal_id TEXT PRIMARY KEY, url TEXT NOT NULL);
-- quanto cada termo rende: canais distintos que a busca trouxe e quantos passaram no filtro
CREATE TABLE IF NOT EXISTS termo_placar (
    termo TEXT NOT NULL, idioma TEXT NOT NULL, buscas INTEGER NOT NULL DEFAULT 0,
    canais INTEGER NOT NULL DEFAULT 0, aprovados INTEGER NOT NULL DEFAULT 0,
    aposentado INTEGER NOT NULL DEFAULT 0, ultima TEXT NOT NULL, PRIMARY KEY (termo, idioma)
);
-- termo sugerido (títulos dos aprovados, autocompletar) à espera de teste na varredura
CREATE TABLE IF NOT EXISTS termo_candidato (
    termo TEXT NOT NULL, idioma TEXT NOT NULL, origem TEXT NOT NULL, categoria TEXT,
    evidencia TEXT NOT NULL, status TEXT NOT NULL, adicionado TEXT NOT NULL, PRIMARY KEY (termo, idioma)
);
"""


def conectar() -> sqlite3.Connection:
    con = sqlite3.connect(ARQUIVO, timeout=10)
    con.row_factory = sqlite3.Row
    return con


def iniciar() -> None:
    with closing(conectar()) as con, con:
        con.executescript(_ESQUEMA)
        colunas = {r["name"] for r in con.execute("PRAGMA table_info(foto)")}
        if "views_videos" not in colunas:  # base criada antes de a subida usar a soma dos vídeos
            con.execute("ALTER TABLE foto ADD COLUMN views_videos INTEGER")


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def cache_ler(chave: str, validade: timedelta) -> list[dict[str, Any]] | None:
    """Busca guardada, ou None se não existe ou passou da validade (o YouTube já mudou)."""
    with closing(conectar()) as con:
        row = con.execute("SELECT canais, criado FROM busca_cache WHERE chave = ?", (chave,)).fetchone()
    if row is None or datetime.now() - datetime.fromisoformat(row["criado"]) > validade:
        return None
    return list(json.loads(row["canais"]))


def cache_todos() -> list[tuple[str, list[dict[str, Any]]]]:
    with closing(conectar()) as con:
        return [(r["chave"], json.loads(r["canais"])) for r in con.execute("SELECT chave, canais FROM busca_cache")]


def cache_gravar(chave: str, itens: list[dict[str, Any]]) -> None:
    with closing(conectar()) as con, con:
        con.execute("INSERT OR REPLACE INTO busca_cache VALUES (?, ?, ?)",
                    (chave, json.dumps(itens, ensure_ascii=False), agora()))


def criar_mineracao(parametros: dict[str, Any], status: str = "rodando") -> int:
    """status 'na fila' para as minerações de uma varredura, que rodam uma depois da outra."""
    with closing(conectar()) as con, con:
        cur = con.execute("INSERT INTO mineracao (criado, parametros, status) VALUES (?, ?, ?)",
                          (agora(), json.dumps(parametros, ensure_ascii=False), status))
    assert cur.lastrowid is not None
    return cur.lastrowid


def atualizar(id_: int, **campos: Any) -> None:
    permitidos = {"status", "fase", "atual", "total", "unidades", "erro", "resultado"}
    if not campos.keys() <= permitidos:
        raise ValueError(f"campos desconhecidos: {campos.keys() - permitidos}")
    if "resultado" in campos:
        campos["resultado"] = json.dumps(campos["resultado"], ensure_ascii=False)
    sets = ", ".join(f"{k} = ?" for k in campos)
    with closing(conectar()) as con, con:
        con.execute(f"UPDATE mineracao SET {sets} WHERE id = ?", (*campos.values(), id_))


def _linha(row: sqlite3.Row, com_resultado: bool) -> dict[str, Any]:
    d = dict(row)
    d["parametros"] = json.loads(d["parametros"])
    resultado = d.pop("resultado")
    if com_resultado:
        d["resultado"] = json.loads(resultado) if resultado else None
    return d


def ler_mineracao(id_: int) -> dict[str, Any] | None:
    with closing(conectar()) as con:
        row = con.execute("SELECT * FROM mineracao WHERE id = ?", (id_,)).fetchone()
    return None if row is None else _linha(row, com_resultado=True)


def listar_mineracoes(limite: int = 30) -> list[dict[str, Any]]:
    with closing(conectar()) as con:
        rows = con.execute("SELECT * FROM mineracao ORDER BY id DESC LIMIT ?", (limite,)).fetchall()
    return [_linha(r, com_resultado=False) for r in rows]


def marcar_orfas() -> None:
    """Mineração 'rodando' ou 'na fila' quando o servidor sobe morreu junto com o processo anterior."""
    with closing(conectar()) as con, con:
        con.execute("UPDATE mineracao SET status = 'erro', erro = 'servidor reiniciado no meio' "
                    "WHERE status IN ('rodando', 'na fila')")

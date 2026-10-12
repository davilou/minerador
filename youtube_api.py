"""
YouTube Data API v3 só para o que é barato: channels.list, playlistItems.list e videos.list
custam 1 unidade por chamada (até 50 itens). Search.list (100 unidades) nunca é usado aqui.
"""

from __future__ import annotations

import os
import re
from collections.abc import Iterator
from datetime import date
from pathlib import Path
from typing import Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from metricas import Video, duracao_segundos

# YOUTUBE_API_KEY no ambiente tem precedência; senão, a linha YOUTUBE_API_KEY=... do .env na raiz
# (fora do git — ver .env.example).
_ARQUIVO_ENV = Path(__file__).resolve().parent / ".env"


def carregar_chave() -> str:
    if chave := os.environ.get("YOUTUBE_API_KEY"):
        return chave
    if _ARQUIVO_ENV.exists():
        m = re.search(r"^YOUTUBE_API_KEY=(.+)$", _ARQUIVO_ENV.read_text(encoding="utf-8"), re.MULTILINE)
        if m and (chave := m.group(1).strip().strip('"')):
            return chave
    raise RuntimeError(f"chave da YouTube Data API não encontrada: defina YOUTUBE_API_KEY no ambiente "
                       f"ou em {_ARQUIVO_ENV} (modelo em .env.example)")


def em_lotes(ids: list[str], n: int = 50) -> Iterator[list[str]]:
    for i in range(0, len(ids), n):
        yield ids[i:i + n]


class ApiYouTube:
    def __init__(self, chave: str) -> None:
        self._yt = build("youtube", "v3", developerKey=chave, cache_discovery=False)
        self.unidades = 0  # custo acumulado, para mostrar no painel

    def _chamar(self, pedido: Any) -> dict[str, Any]:
        self.unidades += 1
        resposta: dict[str, Any] = pedido.execute()
        return resposta

    def canais(self, ids: list[str]) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for lote in em_lotes(ids):
            r = self._chamar(self._yt.channels().list(part="snippet,statistics", id=",".join(lote)))
            for it in r.get("items", []):
                s, sn = it["statistics"], it["snippet"]
                out[it["id"]] = {
                    "nome": sn["title"], "handle": sn.get("customUrl", ""),
                    "avatar": sn["thumbnails"].get("medium", sn["thumbnails"]["default"])["url"],
                    "criado": sn["publishedAt"][:10], "pais": sn.get("country", ""),
                    "inscritos": None if s.get("hiddenSubscriberCount") else int(s.get("subscriberCount", 0)),
                    "views_total": int(s.get("viewCount", 0)), "videos": int(s.get("videoCount", 0)),
                }
        return out

    def ids_uploads(self, canal_id: str, limite: int) -> list[str]:
        playlist = "UU" + canal_id[2:]  # playlist de uploads = id do canal com UC -> UU
        ids: list[str] = []
        token: str | None = None
        while len(ids) < limite:
            try:
                r = self._chamar(self._yt.playlistItems().list(
                    part="contentDetails", playlistId=playlist, maxResults=50, pageToken=token))
            except HttpError as e:
                if e.resp.status == 404:  # canal sem upload público
                    return []
                raise
            ids += [i["contentDetails"]["videoId"] for i in r["items"]]
            token = r.get("nextPageToken")
            if not token:
                break
        return ids[:limite]

    def views_videos(self, ids: list[str]) -> dict[str, int]:
        """Só as views atuais (1 unidade a cada 50 vídeos). Vídeo apagado some do retorno."""
        out: dict[str, int] = {}
        for lote in em_lotes(ids):
            r = self._chamar(self._yt.videos().list(part="statistics", id=",".join(lote)))
            out |= {it["id"]: int(it["statistics"].get("viewCount", 0)) for it in r.get("items", [])}
        return out

    def videos(self, ids: list[str]) -> list[Video]:
        out: list[Video] = []
        for lote in em_lotes(ids):
            r = self._chamar(self._yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(lote)))
            for it in r.get("items", []):
                out.append(Video(
                    id=it["id"], titulo=it["snippet"]["title"],
                    views=int(it["statistics"].get("viewCount", 0)),
                    # estreia/live agendada vem sem duração: conta 0 e metricas.formato a ignora
                    duracao_s=duracao_segundos(it["contentDetails"].get("duration", "P0D")),
                    publicado=date.fromisoformat(it["snippet"]["publishedAt"][:10]),
                ))
        return out

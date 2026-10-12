"""
Busca no YouTube pelo yt-dlp — não gasta a cota de Search da API (100 unidades por busca,
a que estoura). Cada busca fica 12 h em cache no SQLite: repetir o termo nesse prazo é instantâneo.
"""

from __future__ import annotations

import logging
import time
import urllib.parse
from datetime import timedelta
from typing import Any

import yt_dlp

import db

log = logging.getLogger("minerador.busca")

# Busca repetida dentro disso volta do cache; depois, o YouTube já mostra outra coisa.
VALIDADE_CACHE = timedelta(hours=12)

# Filtro "sp" da página de resultados. Conferido pela data real dos vídeos (API) em 2026-09-30:
# "este ano" = últimos 12 meses, "este mês" = 30 dias, "esta semana" = ~7 dias, "hoje" = últimas 24 h.
PERIODOS: dict[str, str] = {
    "qualquer": "",
    "12m": "EgIIBQ%3D%3D",
    "12m_views": "CAMSAggF",
    "30d": "EgIIBA%3D%3D",
    "30d_views": "CAMSAggE",
    "7d": "EgIIAw%3D%3D",
    "7d_views": "CAMSAggD",
    "24h": "EgIIAg%3D%3D",
    "24h_views": "CAMSAggC",
}


def _url(termo: str, hl: str, gl: str, periodo: str) -> str:
    if periodo not in PERIODOS:
        raise ValueError(f"período desconhecido: {periodo!r} (use {list(PERIODOS)})")
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(termo)}&hl={hl}&gl={gl}"
    return url + (f"&sp={PERIODOS[periodo]}" if PERIODOS[periodo] else "")


class BuscaBloqueada(RuntimeError):
    """O YouTube recusou a busca (HTTP 403) mesmo depois de esperar: insistir só piora o bloqueio."""


# Depois de ~250 buscas seguidas o YouTube passa a responder 403, e o bloqueio durou horas
# (varredura de 2026-09-30). Pausa entre buscas de rede para não chegar lá.
ESPERAS_BLOQUEIO_S = (20, 60)
PAUSA_ENTRE_BUSCAS_S = 1.5


class _Ouvinte:
    """Logger do yt-dlp. Guarda erros e avisos: o 403 numa página de continuação não levanta
    exceção, só corta o resultado (busca de 150 vídeos volta com 0 ou 5, sem erro nenhum)."""

    def __init__(self) -> None:
        self.mensagens: list[str] = []

    def debug(self, msg: str) -> None:
        pass

    def info(self, msg: str) -> None:
        pass

    def warning(self, msg: str) -> None:
        self.mensagens.append(msg)

    def error(self, msg: str) -> None:
        self.mensagens.append(msg)

    @property
    def bloqueou(self) -> bool:
        return any("403" in m for m in self.mensagens)


def _extrair(url: str, quantidade: int, termo: str) -> dict[str, Any]:
    for espera in (*ESPERAS_BLOQUEIO_S, None):
        ouvinte = _Ouvinte()
        opts = {"quiet": True, "extract_flat": True, "playlistend": quantidade, "logger": ouvinte}
        try:
            with yt_dlp.YoutubeDL(opts) as y:
                r: dict[str, Any] = y.extract_info(url, download=False)
            if not ouvinte.bloqueou:
                time.sleep(PAUSA_ENTRE_BUSCAS_S)
                return r
        except yt_dlp.utils.DownloadError as e:
            if "403" not in str(e):
                raise
        if espera is None:
            raise BuscaBloqueada(f"YouTube bloqueou a busca de {termo!r} (HTTP 403)")
        log.warning("403 na busca de %r; esperando %s s", termo, espera)
        time.sleep(espera)
    raise AssertionError("inalcançável")


def buscar(termo: str, hl: str, gl: str, periodo: str, quantidade: int) -> list[dict[str, Any]]:
    """Vídeos do resultado: [{video_id, canal_id, views, duracao}]. Sem canal_id (mix, playlist) sai."""
    chave = f"{termo}|{hl}|{gl}|{periodo}|{quantidade}"
    guardado = db.cache_ler(chave, VALIDADE_CACHE)
    if guardado is not None:
        return guardado
    r = _extrair(_url(termo, hl, gl, periodo), quantidade, termo)
    itens = [{"video_id": e["id"], "canal_id": e["channel_id"], "views": e.get("view_count"),
              "duracao": e.get("duration")}
             for e in r["entries"] if e.get("channel_id")]
    if itens:  # vazio pode ser bloqueio silencioso; guardar envenenaria o termo por 12 h
        db.cache_gravar(chave, itens)
    return itens

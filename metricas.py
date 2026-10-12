"""
Regras que decidem o ranking — funções puras, sem rede nem disco.

Idade real conta do primeiro vídeo, não da criação do canal: canal comprado ou
reaproveitado aparece "de 2019" e só começou a postar há dois meses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Literal

SHORT_MAX_S = 180  # Shorts vão até 3 min desde out/2024
FATIA_DOMINANTE = 0.8  # 80%+ de um formato define o canal; abaixo disso é misto
DORMENCIA_MIN_DIAS = 180  # 6 meses sem postar: o que vem depois é uma fase nova do canal

Formato = Literal["longo", "shorts", "misto"]

_DURACAO = re.compile(r"^P(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?)?$")


@dataclass(frozen=True)
class Video:
    id: str
    titulo: str
    views: int
    duracao_s: int
    publicado: date

    @property
    def eh_short(self) -> bool:
        return self.duracao_s <= SHORT_MAX_S


@dataclass(frozen=True)
class Filtros:
    max_videos: int
    min_views: int
    idade_max_dias: int


def duracao_segundos(iso: str) -> int:
    """'PT1H2M3S' -> 3723. Live agendada vem 'P0D' -> 0."""
    m = _DURACAO.match(iso)
    if not m:
        raise ValueError(f"duração ISO 8601 inválida: {iso!r}")
    d, h, mi, s = (int(g) if g else 0 for g in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def passa_prefiltro(qtd_videos: int, views_total: int, f: Filtros) -> bool:
    """Corte barato, só com o que channels.list devolve (1 unidade a cada 50 canais)."""
    return 0 < qtd_videos <= f.max_videos and views_total >= f.min_views


def formato(videos: list[Video]) -> Formato:
    validos = [v for v in videos if v.duracao_s > 0]  # live agendada não tem duração
    if not validos:
        raise ValueError("canal sem vídeo com duração — não dá para classificar")
    shorts = sum(v.eh_short for v in validos)
    if shorts / len(validos) >= FATIA_DOMINANTE:
        return "shorts"
    if (len(validos) - shorts) / len(validos) >= FATIA_DOMINANTE:  # não 1 - 0.8: dá 0.1999…
        return "longo"
    return "misto"


def inicio_fase(datas: list[date]) -> tuple[date, int | None]:
    """
    Início da fase atual do canal: o primeiro vídeo depois do hiato de DORMENCIA_MIN_DIAS+ mais
    recente, ou o primeiro vídeo se nunca parou. Devolve (início, dias do hiato ou None).
    Canal que postou em 2021, parou e voltou em setembro é um canal de setembro.
    """
    if not datas:
        raise ValueError("canal sem vídeos — fase indefinida")
    ordenadas = sorted(datas)
    for anterior, seguinte in zip(reversed(ordenadas[:-1]), reversed(ordenadas[1:])):
        if (seguinte - anterior).days >= DORMENCIA_MIN_DIAS:
            return seguinte, (seguinte - anterior).days
    return ordenadas[0], None


def idade_dias(videos: list[Video], hoje: date) -> int:
    """Dias desde o início da fase atual (não da criação do canal nem do vídeo mais antigo)."""
    return (hoje - inicio_fase([v.publicado for v in videos])[0]).days


def resumir(videos: list[Video], hoje: date) -> dict[str, object]:
    """Métricas do canal a partir dos vídeos públicos (mais fiel que o total do canal)."""
    inicio, hiato = inicio_fase([v.publicado for v in videos])
    idade = (hoje - inicio).days
    views = sum(v.views for v in videos)
    top = sorted(videos, key=lambda v: -v.views)[:3]
    return {
        "formato": formato(videos),
        "primeiro_video": min(v.publicado for v in videos).isoformat(),
        "inicio_fase": inicio.isoformat(),
        "hiato_dias": hiato,
        "idade_dias": idade,
        "views_videos": views,
        "qtd_analisada": len(videos),
        "views_por_video": views // len(videos),
        "views_por_dia": views // max(idade, 1),  # canal de hoje não divide por zero
        "top": [{"id": v.id, "titulo": v.titulo, "views": v.views, "short": v.eh_short} for v in top],
    }

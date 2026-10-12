"""
Regras das abas do painel (Explodindo, Novos, Outliers, Tração, Subindo) — funções puras.

Os limites moram aqui, num lugar só, para ajustar depois de ver resultado real.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

EXPLODINDO_DIAS = 15          # "Explodindo Agora": postando há menos de 15 dias…
EXPLODINDO_VIEWS = 50_000     # …e com mais de 50 mil views (100 mil do Niche Finder deixava canal de 11 dias com 87 mil de fora)
NOVO_DIAS = 60                # "Canais Novos": postando há até 60 dias
OUTLIER_FATOR = 20            # "Outliers": um vídeo com 20x+ a média dos outros (5x pegava 85% da base: um hit carregar canal novo é o normal)
TRACAO_DIAS = 30              # "Tração Recente": vídeos dos últimos 30 dias…
TRACAO_VIEWS = 100_000        # …somam 100 mil views ou mais
SUBIDA_MIN_DIAS = 0.5         # duas fotos com menos de 12 h entre si dão ruído, não crescimento

DESCRICOES: dict[str, str] = {
    "explodindo": f"Menos de {EXPLODINDO_DIAS} dias postando e mais de {EXPLODINDO_VIEWS:,} views".replace(",", "."),
    "novos": f"Até {NOVO_DIAS} dias postando",
    "outliers": f"Um vídeo com {OUTLIER_FATOR}x ou mais a média dos outros vídeos do canal",
    "tracao": f"Vídeos dos últimos {TRACAO_DIAS} dias somam {TRACAO_VIEWS:,}+ views".replace(",", "."),
    "subindo": "Mais views ganhas por dia entre as duas últimas atualizações (use Atualizar números)",
    "favoritos": "Canais marcados com o coração",
    "todos": "Tudo que já foi minerado",
}


@dataclass(frozen=True)
class VideoBase:
    views: int
    publicado: date


@dataclass(frozen=True)
class Foto:
    """Números do canal num instante (uma linha da tabela snapshot)."""
    em: datetime
    views: int  # soma das views dos vídeos do canal naquele instante


def dias_postando(primeiro_video: date, hoje: date) -> int:
    return max((hoje - primeiro_video).days, 0)


def por_mes(quantidade: int, dias: int) -> int:
    """Ritmo mensal. Canal de poucos dias é extrapolado — é o que o card promete ("views/mês")."""
    return round(quantidade * 30 / max(dias, 1))


def tracao_recente(videos: list[VideoBase], hoje: date) -> int:
    corte = hoje - timedelta(days=TRACAO_DIAS)
    return sum(v.views for v in videos if v.publicado >= corte)


def fator_outlier(videos: list[VideoBase]) -> float | None:
    """Views do maior vídeo ÷ média dos outros. None com menos de 2 vídeos (não há 'outros')."""
    if len(videos) < 2:
        return None
    ordenados = sorted((v.views for v in videos), reverse=True)
    media_outros = sum(ordenados[1:]) / len(ordenados[1:])
    return ordenados[0] / max(media_outros, 1)  # outros com 0 views não dividem por zero


def subida_por_dia(fotos: list[Foto]) -> int | None:
    """
    Views ganhas por dia entre a última foto e a mais recente com SUBIDA_MIN_DIAS+ antes dela.
    Não usa só as duas últimas: um "Atualizar" logo depois de outro esvaziaria a aba.
    """
    if not fotos:
        return None
    *anteriores, ultima = sorted(fotos, key=lambda f: f.em)
    distantes = [f for f in anteriores if (ultima.em - f.em).total_seconds() / 86400 >= SUBIDA_MIN_DIAS]
    if not distantes:
        return None
    anterior = distantes[-1]
    dias = (ultima.em - anterior.em).total_seconds() / 86400
    return round((ultima.views - anterior.views) / dias)


def abas_do_canal(views_total: int, dias: int, tracao: int, outlier: float | None,
                  subida: int | None, favorito: bool) -> list[str]:
    abas = ["todos"]
    if dias < EXPLODINDO_DIAS and views_total > EXPLODINDO_VIEWS:
        abas.append("explodindo")
    if dias <= NOVO_DIAS:
        abas.append("novos")
    if outlier is not None and outlier >= OUTLIER_FATOR:
        abas.append("outliers")
    if tracao >= TRACAO_VIEWS:
        abas.append("tracao")
    if subida is not None and subida > 0:
        abas.append("subindo")
    if favorito:
        abas.append("favoritos")
    return abas

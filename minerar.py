"""
Uma mineração: busca (yt-dlp, sem cota) -> pré-filtro (channels.list, barato)
-> aprofundamento só nos que passaram (uploads + vídeos) -> filtro de idade real.
Quem passa entra na base acumulada (base.py).
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from collections.abc import Callable
from concurrent.futures import CancelledError, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from yt_dlp.utils import DownloadError

import base
import busca
import candidatos
import db
import placar
import virais
from metricas import Filtros, Video, passa_prefiltro, resumir
from youtube_api import ApiYouTube

log = logging.getLogger("minerador.minerar")

BUSCAS_PARALELAS = 2  # com 4, ~250 buscas seguidas levaram 403 do YouTube (2026-09-30)
MARGEM_UPLOADS = 10  # videoCount do canal e a playlist de uploads às vezes divergem por alguns vídeos

Progresso = Callable[[str, int, int], None]  # (fase, atual, total)


@dataclass(frozen=True)
class Parametros:
    termos: list[str]
    hl: str
    gl: str
    periodo: str
    por_termo: int
    filtros: Filtros


@dataclass
class Resultado:
    achados: list[dict[str, Any]] = field(default_factory=list)
    falhas: list[str] = field(default_factory=list)  # termos que ficaram sem busca
    bloqueado: bool = False  # o YouTube passou a recusar as buscas (403)

    def aviso(self) -> str | None:
        if not self.falhas:
            return None
        if self.bloqueado:
            causa = "o YouTube bloqueou as buscas (403); rode de novo mais tarde, o que já foi buscado está em cache"
        else:
            causa = "erro na busca, detalhes no minerador.log"
        return f"{len(self.falhas)} termo(s) ficaram de fora: {causa}"


def _buscar_todos(p: Parametros, progresso: Progresso, r: Resultado) -> list[dict[str, Any]]:
    """
    Vídeos das buscas, cada um com o termo que o achou (item["termo"]). Termo que falha vai para
    r.falhas sem derrubar os outros; bloqueio do YouTube cancela as buscas restantes (insistir piora).
    """
    itens: list[dict[str, Any]] = []
    parar = threading.Event()  # levantada pela própria busca bloqueada, antes de a próxima começar

    def buscar_um(termo: str) -> list[dict[str, Any]]:
        if parar.is_set():
            raise CancelledError
        try:
            return busca.buscar(termo, p.hl, p.gl, p.periodo, p.por_termo)
        except busca.BuscaBloqueada:
            parar.set()
            raise

    progresso("buscando", 0, len(p.termos))
    with ThreadPoolExecutor(BUSCAS_PARALELAS) as ex:
        futuros = {ex.submit(buscar_um, t): t for t in p.termos}
        for i, fut in enumerate(as_completed(futuros), 1):
            termo = futuros[fut]
            try:
                itens += [item | {"termo": termo} for item in fut.result()]
            except busca.BuscaBloqueada:
                r.bloqueado = True
                r.falhas.append(termo)
            except CancelledError:
                r.falhas.append(termo)
            except DownloadError:
                log.exception("busca de %r falhou", termo)
                r.falhas.append(termo)
            progresso("buscando", i, len(p.termos))
    return itens


def _coletar_virais(itens: list[dict[str, Any]], canais: dict[str, dict[str, Any]],
                    api: ApiYouTube, idioma: str) -> int:
    """Guarda os vídeos 1 mi+ de canal pequeno que a busca trouxe. ~1 unidade a cada 50 vídeos."""
    candidatos = {i["video_id"]: i for i in itens
                  if i["canal_id"] in canais and virais.eh_viral(i["views"], canais[i["canal_id"]]["inscritos"])}
    gravados = 0
    for v in api.videos(list(candidatos)):  # título, data e views exatas (a busca arredonda)
        item = candidatos[v.id]
        if virais.eh_viral(v.views, canais[item["canal_id"]]["inscritos"]):
            virais.gravar(v, item["canal_id"], canais[item["canal_id"]], idioma, item["termo"])
            gravados += 1
    return gravados


def _aprofundar(cid: str, info: dict[str, Any], api: ApiYouTube,
                hoje: date) -> tuple[dict[str, Any], list[Video]] | None:
    ids = api.ids_uploads(cid, limite=info["videos"] + MARGEM_UPLOADS)
    videos = api.videos(ids)
    if not any(v.duracao_s > 0 for v in videos):  # só live agendada ou nada público
        return None
    canal = ({"id": cid, "url": f"https://www.youtube.com/channel/{cid}", "qtd_videos": info["videos"]}
             | info | resumir(videos, hoje))
    return canal, videos


def executar(p: Parametros, api: ApiYouTube, progresso: Progresso, hoje: date) -> Resultado:
    r = Resultado()
    itens = _buscar_todos(p, progresso, r)
    termos_por_canal: dict[str, set[str]] = defaultdict(set)
    for item in itens:
        termos_por_canal[item["canal_id"]].add(item["termo"])

    progresso("lendo canais", 0, len(termos_por_canal))
    canais = api.canais(list(termos_por_canal))
    _coletar_virais(itens, canais, api, p.hl)
    pre_aprovados = {cid: c for cid, c in canais.items()
                     if passa_prefiltro(c["videos"], c["views_total"], p.filtros)}

    for i, (cid, info) in enumerate(pre_aprovados.items(), 1):
        progresso("aprofundando", i, len(pre_aprovados))
        a = _aprofundar(cid, info, api, hoje)
        if a and a[0]["idade_dias"] <= p.filtros.idade_max_dias:
            termos = sorted(termos_por_canal[cid])
            base.gravar(a[0], a[1], p.hl, termos)
            r.achados.append(a[0] | {"termos": termos})
    r.achados.sort(key=lambda c: -c["views_por_video"])
    falhas = set(r.falhas)
    placar.registrar(p.hl, placar.contar([t for t in p.termos if t not in falhas], itens, r.achados))
    candidatos.revisar(p.hl)
    return r


def atualizar_base(api: ApiYouTube) -> dict[str, int]:
    """
    Relê números de canais e vídeos, e busca os uploads novos de cada canal.
    Custo: ~1 unidade por canal (1ª página de uploads) + 1 a cada 50 vídeos.
    """
    ids = base.ids_canais()
    canais = api.canais(ids)
    conhecidos = set(base.ids_videos())
    canal_do_video = {vid: cid for cid in canais for vid in api.ids_uploads(cid, limite=50)
                      if vid not in conhecidos}
    novos: dict[str, list[Video]] = defaultdict(list)
    for v in api.videos(list(canal_do_video)):
        novos[canal_do_video[v.id]].append(v)
    base.atualizar_numeros(canais, api.views_videos(list(conhecidos)), novos)
    virais.atualizar_views(api.views_videos(virais.ids()))
    return {"canais": len(canais), "sumiram": len(ids) - len(canais),
            "videos_novos": len(canal_do_video), "unidades": api.unidades}


def importar_historico(api: ApiYouTube, hoje: date) -> int:
    """Uma vez só: põe na base os canais das minerações feitas antes da base existir."""
    termos: dict[str, set[str]] = defaultdict(set)
    idioma: dict[str, str] = {}
    for m in db.listar_mineracoes(limite=10_000):
        completa = db.ler_mineracao(m["id"])
        for c in (completa or {}).get("resultado") or []:
            termos[c["id"]] |= set(c["termos"])
            idioma.setdefault(c["id"], m["parametros"]["hl"])
    for cid, info in api.canais(list(termos)).items():
        r = _aprofundar(cid, info, api, hoje)
        if r:
            base.gravar(r[0], r[1], idioma[cid], sorted(termos[cid]))
    return len(termos)


def virais_do_cache(api: ApiYouTube) -> int:
    """Uma vez só: garimpa os virais nas buscas que já estavam em cache antes da aba existir."""
    itens: list[dict[str, Any]] = []
    for chave, guardados in db.cache_todos():
        termo, hl = chave.split("|")[:2]
        itens += [i | {"termo": termo, "idioma": hl} for i in guardados
                  if (i.get("views") or 0) >= virais.VIRAL_MIN_VIEWS]
    canais = api.canais(list({i["canal_id"] for i in itens}))
    total = 0
    for idioma in {i["idioma"] for i in itens}:
        total += _coletar_virais([i for i in itens if i["idioma"] == idioma], canais, api, idioma)
    return total

"""Painel local do Minerador. Rodar: python -m uvicorn app:app --port 8765"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

import abas
import avatares
import base
import busca
import candidatos
import db
import nichos
import placar
import virais
from metricas import Filtros
from minerar import Parametros, atualizar_base, executar, importar_historico, virais_do_cache
from youtube_api import ApiYouTube, carregar_chave

log = logging.getLogger("minerador")
ESTATICOS = Path(__file__).parent / "static"
INDEX = ESTATICOS / "index.html"

app = FastAPI(title="Minerador")
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")
db.iniciar()
db.marcar_orfas()


def _importar_historico_uma_vez() -> None:
    """Minerações anteriores à base entram nela uma vez (reanalisa: ~2-3 unidades por canal)."""
    if base.meta_ler("historico_importado"):
        return
    try:
        n = importar_historico(ApiYouTube(carregar_chave()), date.today())
        base.meta_gravar("historico_importado", db.agora())
        log.info("histórico importado para a base: %s canais", n)
    except Exception:
        log.exception("importação do histórico falhou; tenta de novo na próxima abertura")


# Ao abrir, relê os números se a última leitura tem 12 h+. Não 6 h: o Subindo Rápido compara
# fotos com 12 h+ de distância, e foto a cada 6 h não acrescentaria nada à aba.
AUTO_ATUALIZAR_HORAS = 12
_atualizando = threading.Event()


def _atualizar_se_velho() -> None:
    ultima = base.ultima_foto()
    if ultima is None or datetime.now() - ultima < timedelta(hours=AUTO_ATUALIZAR_HORAS):
        return  # base vazia ou lida há pouco
    _atualizando.set()
    try:
        r = atualizar_base(ApiYouTube(carregar_chave()))
        log.info("atualização automática ao abrir: %s", r)
    except Exception:
        log.exception("atualização automática falhou; os números ficam os da última leitura")
    finally:
        _atualizando.clear()


def _virais_do_cache_uma_vez() -> None:
    """Buscas feitas antes da aba Virais existir: garimpa os virais delas uma vez (sem nova busca)."""
    if base.meta_ler("virais_do_cache"):
        return
    try:
        n = virais_do_cache(ApiYouTube(carregar_chave()))
        base.meta_gravar("virais_do_cache", db.agora())
        log.info("virais garimpados do cache de buscas: %s", n)
    except Exception:
        log.exception("garimpo de virais no cache falhou; tenta de novo na próxima abertura")


def _placar_do_historico_uma_vez() -> None:
    """O placar dos termos começa com as minerações feitas antes dele (sem rede, sem cota)."""
    if base.meta_ler("placar_importado"):
        return
    try:
        n = placar.importar_do_historico()
        base.meta_gravar("placar_importado", db.agora())
        log.info("placar montado a partir do histórico: %s termos", n)
    except Exception:
        log.exception("montar o placar pelo histórico falhou; tenta de novo na próxima abertura")


def _ao_abrir() -> None:
    _placar_do_historico_uma_vez()
    _importar_historico_uma_vez()
    _virais_do_cache_uma_vez()
    _atualizar_se_velho()


threading.Thread(target=_ao_abrir, daemon=True).start()

# Preenchido por janela.py quando roda como app desktop; no modo navegador fica None.
_mostrar_janela: Callable[[], None] | None = None


def registrar_janela(mostrar: Callable[[], None]) -> None:
    global _mostrar_janela
    _mostrar_janela = mostrar


class Pedido(BaseModel):
    termos: list[str] = Field(min_length=1)
    hl: str = "pt"
    gl: str = "BR"
    periodo: str = "12m"
    por_termo: int = Field(100, ge=10, le=300)
    max_videos: int = Field(30, ge=1, le=200)
    min_views: int = Field(100_000, ge=0)
    idade_max_dias: int = Field(180, ge=1)

    @field_validator("termos")
    @classmethod
    def _limpar_termos(cls, termos: list[str]) -> list[str]:
        limpos = list(dict.fromkeys(t.strip() for t in termos if t.strip()))
        if not limpos:
            raise ValueError("informe ao menos um termo de busca")
        return limpos

    @field_validator("periodo")
    @classmethod
    def _periodo_conhecido(cls, periodo: str) -> str:
        if periodo not in busca.PERIODOS:
            raise ValueError(f"período desconhecido: {periodo}")
        return periodo

    def parametros(self) -> Parametros:
        return Parametros(self.termos, self.hl, self.gl, self.periodo, self.por_termo,
                          Filtros(self.max_videos, self.min_views, self.idade_max_dias))


def _rodar(id_: int, pedido: Pedido) -> bool:
    """Roda a mineração; devolve True se o YouTube bloqueou as buscas (a fila deve parar)."""
    try:
        api = ApiYouTube(carregar_chave())

        def progresso(fase: str, atual: int, total: int) -> None:
            db.atualizar(id_, fase=fase, atual=atual, total=total, unidades=api.unidades)

        r = executar(pedido.parametros(), api, progresso, date.today())
        # status pronto com erro preenchido = terminou, mas com termos de fora (o painel avisa)
        db.atualizar(id_, status="pronto", fase="pronto", resultado=r.achados, unidades=api.unidades,
                     erro=r.aviso())
        return r.bloqueado
    except Exception as e:
        log.exception("mineração %s falhou", id_)
        db.atualizar(id_, status="erro", erro=f"{type(e).__name__}: {e}")
        return False


@app.get("/")
def index() -> FileResponse:
    return FileResponse(INDEX)


@app.post("/janela/mostrar", status_code=204)
def mostrar_janela() -> Response:
    """Segunda abertura do app chama aqui para trazer a janela já aberta à frente."""
    if _mostrar_janela is None:
        raise HTTPException(404, "rodando sem janela (modo navegador)")
    _mostrar_janela()
    return Response(status_code=204)


class Favorito(BaseModel):
    valor: bool


@app.get("/api/canais")
def canais() -> dict[str, Any]:
    ultima = base.ultima_foto()
    return {"canais": base.listar(date.today()), "descricoes": abas.DESCRICOES | {"virais": virais.DESCRICAO},
            "atualizando": _atualizando.is_set(), "ultima_atualizacao": ultima.isoformat() if ultima else None}


@app.get("/api/virais")
def listar_virais() -> list[dict[str, Any]]:
    return virais.listar()


@app.get("/api/avatar/{canal_id}")
def avatar(canal_id: str) -> FileResponse:
    url = base.avatar_url(canal_id)
    if url is None:
        raise HTTPException(404, "canal não está na base")
    try:
        arquivo = avatares.caminho(canal_id, url)
    except (OSError, ValueError) as e:
        log.warning("avatar de %s falhou: %s", canal_id, e)
        raise HTTPException(502, "não deu para baixar o avatar") from e
    return FileResponse(arquivo, media_type="image/jpeg", headers={"Cache-Control": "max-age=604800"})


@app.post("/api/canais/{canal_id}/favorito", status_code=204)
def favoritar(canal_id: str, corpo: Favorito) -> Response:
    if not base.favoritar(canal_id, corpo.valor):
        raise HTTPException(404, "canal não está na base")
    return Response(status_code=204)


@app.post("/api/base/atualizar")
def atualizar() -> dict[str, int]:
    """Relê números de todos os canais e vídeos da base; é o que alimenta a aba Subindo Rápido."""
    return atualizar_base(ApiYouTube(carregar_chave()))


class PedidoVarredura(BaseModel):
    idiomas: list[str] = Field(min_length=1)
    categorias: list[str] = Field(min_length=1)
    periodo: str = "7d_views"
    # 40 = ~2 páginas de busca por termo; 100 eram ~5 e a varredura levou 403 do YouTube
    por_termo: int = Field(40, ge=10, le=300)
    max_videos: int = Field(30, ge=1, le=200)
    min_views: int = Field(50_000, ge=0)
    idade_max_dias: int = Field(60, ge=1)
    # fatia de candidatos (descoberta de nichos) testada junto, por idioma; 0 = só as sementes
    candidatos: int = Field(15, ge=0, le=100)


@app.get("/api/nichos")
def listar_nichos() -> dict[str, Any]:
    return {"categorias": nichos.resumo(), "mercados": nichos.MERCADOS, "pendentes": candidatos.pendentes()}


def _termos_da_varredura(idioma: str, p: PedidoVarredura) -> list[str]:
    """Sementes das categorias, menos as aposentadas no placar, mais a fatia de candidatos a testar."""
    try:
        sementes = nichos.termos(idioma, p.categorias)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    fora = placar.aposentados(idioma)
    termos = [t for t in sementes if t not in fora] + candidatos.para_testar(idioma, p.categorias, p.candidatos)
    if not termos:
        raise HTTPException(422, f"nenhum termo para buscar em {idioma}: todos aposentados")
    return list(dict.fromkeys(termos))


@app.post("/api/varredura")
def varredura(p: PedidoVarredura) -> dict[str, list[int]]:
    """Uma mineração por idioma, com os termos das categorias escolhidas; rodam em fila, uma por vez."""
    fila: list[tuple[int, Pedido]] = []
    for idioma in p.idiomas:
        pedido = Pedido(termos=_termos_da_varredura(idioma, p), hl=idioma, gl=nichos.MERCADOS[idioma], periodo=p.periodo,
                        por_termo=p.por_termo, max_videos=p.max_videos, min_views=p.min_views,
                        idade_max_dias=p.idade_max_dias)
        fila.append((db.criar_mineracao(pedido.model_dump() | {"varredura": p.categorias}, "na fila"), pedido))

    def rodar_fila() -> None:
        for n, (id_, pedido) in enumerate(fila):
            db.atualizar(id_, status="rodando")
            if _rodar(id_, pedido):  # bloqueado: os próximos idiomas só levariam 403 também
                for resto, _ in fila[n + 1:]:
                    db.atualizar(resto, status="erro",
                                 erro="cancelada: o YouTube bloqueou as buscas; rode de novo mais tarde")
                return

    threading.Thread(target=rodar_fila, daemon=True).start()
    return {"ids": [id_ for id_, _ in fila]}


class Termo(BaseModel):
    termo: str = Field(min_length=1)
    idioma: str


class Promocao(Termo):
    categoria: str | None = None
    nome_nova: str | None = None  # cria a categoria com esse nome


class Aposentadoria(Termo):
    valor: bool


@app.get("/api/descoberta")
def descoberta() -> dict[str, Any]:
    return {"candidatos": candidatos.listar(), "placar": placar.listar()}


@app.post("/api/descoberta/gerar")
def gerar_candidatos() -> dict[str, int]:
    """Candidatos dos títulos da base e do autocompletar. Sem cota; o autocompletar vai à rede."""
    try:
        return candidatos.gerar()
    except OSError as e:
        log.exception("autocompletar falhou")
        raise HTTPException(502, f"autocompletar do YouTube falhou: {e}") from e


@app.post("/api/candidatos/promover")
def promover(c: Promocao) -> dict[str, str]:
    try:
        return {"categoria": candidatos.promover(c.termo, c.idioma, c.categoria, c.nome_nova)}
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


@app.post("/api/candidatos/recusar", status_code=204)
def recusar(c: Termo) -> Response:
    if not candidatos.recusar(c.termo, c.idioma):
        raise HTTPException(404, "candidato não existe")
    return Response(status_code=204)


@app.post("/api/placar/aposentar", status_code=204)
def aposentar(a: Aposentadoria) -> Response:
    if not placar.aposentar(a.termo, a.idioma, a.valor):
        raise HTTPException(404, "termo nunca buscado")
    return Response(status_code=204)


@app.post("/api/mineracoes")
def criar(pedido: Pedido) -> dict[str, int]:
    id_ = db.criar_mineracao(pedido.model_dump())
    threading.Thread(target=_rodar, args=(id_, pedido), daemon=True).start()
    return {"id": id_}


@app.get("/api/mineracoes")
def listar() -> list[dict[str, Any]]:
    return db.listar_mineracoes()


@app.get("/api/mineracoes/{id_}")
def ler(id_: int) -> dict[str, Any]:
    m = db.ler_mineracao(id_)
    if m is None:
        raise HTTPException(404, "mineração não encontrada")
    return m

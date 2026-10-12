from pathlib import Path
from typing import Any

import pytest
from yt_dlp.utils import DownloadError

import busca
import db
import minerar
from metricas import Filtros


def parametros(termos: list[str]) -> minerar.Parametros:
    return minerar.Parametros(termos, "pt", "BR", "7d_views", 100, Filtros(30, 50_000, 60))


def sem_progresso(fase: str, atual: int, total: int) -> None:
    pass


def test_bloqueio_guarda_o_que_ja_buscou_e_para(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(minerar, "BUSCAS_PARALELAS", 1)  # ordem determinística

    def buscar(termo: str, *_: Any) -> list[dict[str, Any]]:
        if termo == "b":
            raise busca.BuscaBloqueada("403")
        return [{"video_id": f"v-{termo}", "canal_id": "UC1", "views": 10, "duracao": 60}]

    monkeypatch.setattr(busca, "buscar", buscar)
    r = minerar.Resultado()
    itens = minerar._buscar_todos(parametros(["a", "b", "c", "d"]), sem_progresso, r)
    assert [i["termo"] for i in itens] == ["a"]
    assert r.bloqueado and set(r.falhas) == {"b", "c", "d"}
    assert "bloqueou" in (r.aviso() or "")


def test_erro_comum_de_busca_nao_derruba_os_outros(monkeypatch: pytest.MonkeyPatch) -> None:
    def buscar(termo: str, *_: Any) -> list[dict[str, Any]]:
        if termo == "ruim":
            raise DownloadError("vídeo indisponível")
        return [{"video_id": f"v-{termo}", "canal_id": "UC1", "views": 10, "duracao": 60}]

    monkeypatch.setattr(busca, "buscar", buscar)
    r = minerar.Resultado()
    itens = minerar._buscar_todos(parametros(["ok1", "ruim", "ok2"]), sem_progresso, r)
    assert sorted(i["termo"] for i in itens) == ["ok1", "ok2"]
    assert r.falhas == ["ruim"] and not r.bloqueado


def test_sem_falha_nao_ha_aviso() -> None:
    assert minerar.Resultado().aviso() is None


class _YDLFalso:
    """Imita o yt-dlp quando o 403 cai numa página de continuação: loga o erro e devolve o que tinha."""

    def __init__(self, opts: dict[str, Any]) -> None:
        self.logger = opts["logger"]

    def __enter__(self) -> "_YDLFalso":
        return self

    def __exit__(self, *_: Any) -> None:
        pass

    def extract_info(self, url: str, download: bool) -> dict[str, Any]:
        self.logger.error('ERROR: query "x" page 2: HTTP Error 403: Forbidden')
        return {"entries": [{"id": "v1", "channel_id": "UC1"}]}


def test_bloqueio_silencioso_vira_busca_bloqueada(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(busca.yt_dlp, "YoutubeDL", _YDLFalso)
    monkeypatch.setattr(busca, "ESPERAS_BLOQUEIO_S", (0,))
    with pytest.raises(busca.BuscaBloqueada):
        busca._extrair("url", 100, "x")


def test_busca_vazia_nao_vai_pro_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(db, "ARQUIVO", tmp_path / "t.db")
    db.iniciar()
    monkeypatch.setattr(busca, "_extrair", lambda *_: {"entries": []})
    assert busca.buscar("x", "pt", "BR", "7d", 100) == []
    assert db.cache_ler("x|pt|BR|7d|100", busca.VALIDADE_CACHE) is None

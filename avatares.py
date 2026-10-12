"""
Avatares dos canais servidos pelo próprio Minerador, com cache em disco.

O navegador pedindo dezenas de avatares ao yt3 do Google de uma vez recebe erro em quase
todos (um por um, carregam). Aqui cada avatar é baixado uma vez só, em fila, e fica em disco.
"""

from __future__ import annotations

import threading
import urllib.request
from pathlib import Path

PASTA = Path(__file__).parent / "cache_avatares"
_fila = threading.Lock()  # um download por vez: a rajada é o que o Google recusa


def caminho(canal_id: str, url: str) -> Path:
    """Arquivo local do avatar; baixa na primeira vez. Levanta OSError se o Google recusar."""
    if not canal_id.replace("-", "").replace("_", "").isalnum():
        raise ValueError(f"id de canal inválido: {canal_id!r}")  # vira nome de arquivo
    arquivo = PASTA / f"{canal_id}.jpg"
    with _fila:
        if not arquivo.exists():
            PASTA.mkdir(exist_ok=True)
            with urllib.request.urlopen(url, timeout=15) as r:
                dados = r.read()
            arquivo.write_bytes(dados)
    return arquivo

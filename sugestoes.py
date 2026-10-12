"""
Autocompletar do YouTube: o que as pessoas estão digitando agora a partir de um termo. Sem cota,
e por outra rota que não a página de resultados (a busca do yt-dlp, que leva 403 em massa).
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

URL = "https://suggestqueries.google.com/complete/search"
PAUSA_S = 0.5


def ler(resposta: str) -> list[str]:
    """Resposta JSONP: window.google.ac.h(["semente", [["sugestão", 0, [...]], ...], {...}])."""
    dados = json.loads(resposta[resposta.index("(") + 1:resposta.rindex(")")])
    return [s[0] for s in dados[1]]


def sugerir(semente: str, hl: str, gl: str) -> list[str]:
    """Sugestões que refinam a semente (mais palavras que ela), na ordem do YouTube."""
    q = urllib.parse.urlencode({"client": "youtube", "ds": "yt", "oe": "utf-8", "hl": hl, "gl": gl, "q": semente})
    with urllib.request.urlopen(f"{URL}?{q}", timeout=10) as r:
        texto: str = r.read().decode("utf-8")
    time.sleep(PAUSA_S)
    palavras = len(semente.split())
    return [s for s in ler(texto) if len(s.split()) > palavras]

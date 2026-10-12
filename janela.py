"""App desktop: servidor numa thread + janela pywebview. Fechar a janela fecha tudo.

Rodar: .venv\\Scripts\\pythonw janela.py   (pythonw: sem janela de terminal)
Mesmo molde do MultiPerfil (multiperfil/app.py).
"""

from __future__ import annotations

import logging
import os
import socket
import threading
import urllib.request
from pathlib import Path

import uvicorn
import webview

RAIZ = Path(__file__).resolve().parent
PORTA = 8765
log = logging.getLogger("minerador.janela")


def porta_ocupada(porta: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", porta)) == 0


def pedir_para_aparecer() -> bool:
    """Já existe um Minerador aberto? Pede a ele que traga a janela à frente."""
    pedido = urllib.request.Request(f"http://127.0.0.1:{PORTA}/janela/mostrar", method="POST")
    try:
        with urllib.request.urlopen(pedido, timeout=3) as resposta:
            return bool(resposta.status == 204)
    except OSError:
        return False


def trazer_a_frente(janela: webview.Window) -> None:
    janela.restore()
    janela.show()
    janela.on_top = True  # no Windows, alternar on_top é o que tira a janela de trás
    janela.on_top = False


def avisar_porta_em_uso() -> None:
    webview.create_window("Minerador", html="<p style='font:14px sans-serif;padding:24px'>"
                          f"Outro programa está usando a porta {PORTA} (talvez o iniciar.bat). "
                          "Feche-o e abra o Minerador de novo.</p>", width=460, height=170)
    webview.start()


def main() -> None:
    os.chdir(RAIZ)  # o atalho pode abrir com outra pasta de trabalho
    logging.basicConfig(filename=RAIZ / "minerador.log", level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    if porta_ocupada(PORTA):
        if not pedir_para_aparecer():
            avisar_porta_em_uso()
        return

    import app  # importa só aqui: abre o banco, e a segunda instância não precisa dele

    janela = webview.create_window("Minerador", f"http://127.0.0.1:{PORTA}/",
                                   width=1440, height=880, min_size=(1000, 600))
    if janela is None:
        raise RuntimeError("pywebview não criou a janela")
    app.registrar_janela(lambda: trazer_a_frente(janela))
    # access_log desligado: o painel consulta a mineração a cada 1,2 s e encheria o log.
    config = uvicorn.Config(app.app, host="127.0.0.1", port=PORTA, log_config=None, access_log=False)
    servidor = uvicorn.Server(config)
    threading.Thread(target=servidor.run, daemon=True).start()
    janela.events.closed += lambda: setattr(servidor, "should_exit", True)
    webview.start()


if __name__ == "__main__":
    main()

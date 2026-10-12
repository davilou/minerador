"""Cria o atalho "Minerador" na Área de Trabalho: duplo clique abre o app, sem terminal.

Uso: .venv\\Scripts\\python ferramentas\\criar_atalho.py
"""

import os
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Caminhos entram por variável de ambiente: o script PowerShell não precisa de aspas
# escapadas e nada do usuário é interpolado como código.
SCRIPT = r"""
$desktop = [Environment]::GetFolderPath('Desktop')
$atalho = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $desktop 'Minerador.lnk'))
$atalho.TargetPath = $env:MN_ALVO
$atalho.Arguments = '"' + $env:MN_SCRIPT + '"'
$atalho.WorkingDirectory = $env:MN_RAIZ
$atalho.Description = 'Minerador - canais novos do YouTube com muitas views e poucos videos'
$atalho.Save()
Write-Output (Join-Path $desktop 'Minerador.lnk')
"""


def main() -> None:
    alvo = RAIZ / ".venv" / "Scripts" / "pythonw.exe"
    if not alvo.exists():
        raise SystemExit(f"pythonw não encontrado em {alvo}; crie o venv antes")
    ambiente = {**os.environ, "MN_ALVO": str(alvo), "MN_SCRIPT": str(RAIZ / "janela.py"),
                "MN_RAIZ": str(RAIZ)}
    resultado = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", SCRIPT],
        env=ambiente, capture_output=True, text=True, check=True,
    )
    print("atalho criado:", resultado.stdout.strip())


if __name__ == "__main__":
    main()

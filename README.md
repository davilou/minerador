# Minerador

Painel local que acha canais novos do YouTube com muitas views e poucos vídeos — bons para modelar.

A busca usa o yt-dlp (sem gastar cota); a YouTube Data API entra só nas chamadas baratas
(`channels.list`, `playlistItems.list`, `videos.list`, 1 unidade cada). Uma mineração típica gasta ~50
das 10.000 unidades diárias.

## Instalação (Windows, Python 3.13+)

```bash
python -m venv .venv
.venv\Scripts\python -m pip install fastapi uvicorn yt-dlp google-api-python-client pywebview
copy .env.example .env
```

Abra o `.env` e cole sua chave em `YOUTUBE_API_KEY=`.

### Como conseguir a chave

1. Em [console.cloud.google.com](https://console.cloud.google.com), crie um projeto.
2. **APIs e serviços → Biblioteca** → ative a **YouTube Data API v3**.
3. **APIs e serviços → Credenciais → Criar credenciais → Chave de API**.
4. (Recomendado) restrinja a chave à YouTube Data API v3.

A variável de ambiente `YOUTUBE_API_KEY` tem precedência sobre o `.env`.

## Uso

- `iniciar.bat` → abre http://localhost:8765 no navegador.
- Ou janela própria: `.venv\Scripts\python ferramentas\criar_atalho.py` cria o atalho **Minerador** na Área de Trabalho.

Os dados ficam em `minerador.db` (SQLite, criado na primeira execução). Os nichos da varredura estão em
`nichos.json` — edite à vontade.

## Desenvolvimento

```bash
.venv\Scripts\python -m pip install pytest mypy
.venv\Scripts\python -m pytest -q
.venv\Scripts\python -m mypy
```

Arquitetura e regras de cada módulo: `CLAUDE.md`.

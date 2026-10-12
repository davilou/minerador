# Minerador

Painel local que acha canais novos do YouTube com muitas views e poucos vídeos, para modelar.

- **Abrir:** atalho **Minerador** na Área de Trabalho (`janela.py` via `pythonw`: janela própria, instância única,
  fechar a janela para o servidor). Recriar o atalho: `.venv\Scripts\python ferramentas\criar_atalho.py`.
  Modo navegador: `iniciar.bat` → http://localhost:8765. Log do app: `minerador.log`.
- **Venv:** `.venv` próprio (dependências no `pyproject.toml`).
- **Check (rodar depois de cada mudança):** `.venv/Scripts/python -m pytest -q && .venv/Scripts/python -m mypy`

## Como minera

0. `nichos.json` + `nichos.py` — varredura geral: 27 categorias com termos-semente em pt/en/es/de (editável;
   o teste recusa termo repetido entre categorias). `POST /api/varredura` cria uma mineração por idioma,
   status 'na fila', e roda uma depois da outra. A categoria do canal sai dos termos que o acharam.
1. `busca.py` — busca pelo yt-dlp na página de resultados (`hl`/`gl`/`sp`), **sem gastar cota**. Cache de 12 h no SQLite.
   **Sem cota não é sem limite:** busca em massa leva 403 do YouTube por horas, e o 403 em página de continuação
   vem calado (resultado cortado, sem exceção). Por isso: `_Ouvinte` (logger) detecta o 403, busca vazia não
   vai pro cache, 2 buscas em paralelo com pausa, varredura com 40 resultados/termo, e o primeiro bloqueio
   para a mineração (e a fila) aproveitando o que já veio.
2. `youtube_api.py` — só `channels.list`, `playlistItems.list`, `videos.list` (1 unidade/chamada). **Nunca `search.list`** (100 unidades).
3. `minerar.py` — pré-filtro barato (vídeos ≤ máx, views ≥ mín) e só então aprofunda nos que passaram.
4. `base.py` — base acumulada (tabelas `canal`, `video`, `foto`): quem passa na mineração entra uma vez e soma
   termos. "Atualizar números" relê canais e vídeos, busca os uploads novos (~1,5 unidade por canal) e tira
   uma foto nova. Roda sozinho ao abrir o app se a última foto tem 12 h+ (`app.py`).
   **Subida mede `foto.views_videos` (soma das views dos vídeos), não o total do canal:** o `viewCount`
   do canal na API fica parado por horas (0 de 45 mudaram numa hora; a soma dos vídeos subiu em 37).
5. `abas.py` — regras das abas do painel (Explodindo, Subindo, Outliers, Tração, Novos), puras e testadas.
   Os limites ficam no topo do arquivo.
6. `virais.py` — aba "Virais de Pequenos": vídeo 1 mi+ de canal com até 50 mil inscritos, de qualquer idade.
   Sai das buscas (que já trazem views) + vídeos da base; guardado em `viral`, mesmo que o canal reprove
   no filtro da mineração. Buscas antigas foram garimpadas do cache uma vez (`meta.virais_do_cache`).
7. `avatares.py` — avatar baixado pelo servidor, em fila, com cache em `cache_avatares/`: o yt3 do Google
   recusa a rajada de avatares pedida direto pelo navegador.
8. Front em `static/` (módulos ES, sem build): `app.js` abas/filtros, `cards.js` card, `mineracao.js` janela.
9. `metricas.py` — regras do ranking, puras e testadas:
   - idade real = dias desde o **início da fase atual**, não a criação do canal (canal comprado/reaproveitado):
     primeiro vídeo depois do hiato de 180+ dias mais recente, ou o primeiro vídeo se nunca parou.
     Views/mês e "Explodindo" contam só os vídeos da fase;
   - Short = até 180 s; 80%+ de um formato define o canal, senão "misto".
10. Descoberta de nichos (botão 🧭 no painel) — o ciclo que acha nicho fora do `nichos.json`:
    - `placar.py` — por termo e idioma: buscas, canais trazidos, aprovados. Gravado a cada mineração;
      montado uma vez do histórico (`meta.placar_importado`). Termo aposentado sai da varredura.
    - `titulos.py` (puro) — expressão de 2-3 palavras repetida em 3+ canais aprovados vira candidato;
      escolhe com diversidade (mesmo nicho dito de outro jeito sai).
    - `sugestoes.py` — autocompletar do YouTube (`suggestqueries`, sem cota) a partir dos termos que mais rendem.
    - `candidatos.py` — a varredura testa uma fatia (`candidatos`, padrão 15/idioma); 2 buscas sem aprovar
      = descartado; quem aprova espera promoção no painel, que escreve no `nichos.json` (`nichos.adicionar`).

## Chave da API

`YOUTUBE_API_KEY` no ambiente ou no `.env` da raiz (fora do git; modelo em `.env.example`).
Cota padrão de 10.000 unidades/dia; uma mineração típica gasta ~50.
Detalhes da chave local (projeto Google, cota compartilhada) em `CLAUDE.local.md`, fora do git.

// Janela "Nova mineração": modo por termos ou varredura geral, progresso da fila e histórico.
import {criarMineracao, criarVarredura, lerMineracao, listarMineracoes} from "./api.js";
import {esc} from "./cards.js";

const $ = (id) => document.getElementById(id);
const CAMPOS_NUM = ["max_videos", "idade_max_dias", "min_views", "por_termo"];
const FASES = {buscando: "Buscando no YouTube", "lendo canais": "Lendo estatísticas dos canais",
               aprofundando: "Analisando vídeos dos candidatos"};
const IDIOMAS = {pt: "Português", en: "Inglês", es: "Espanhol", de: "Alemão"};
const IDIOMAS_PADRAO = ["pt", "en"];
const SEGUNDOS_POR_TERMO = 7 / 2;  // ~5 s por busca de 40 resultados + 1,5 s de pausa, 2 em paralelo

let aoTerminar = () => {};
let timer = null;
let modo = "termos";
let categorias = [];  // [{id, nome, termos: {pt: n, ...}}]
let pendentes = {};  // idioma -> candidatos esperando teste

function preencher(p) {  // reabrir do histórico deixa pronto para refazer com ajuste
  trocarModo("termos");
  $("termos").value = p.termos.join("\n");
  $("mercado").value = `${p.hl}|${p.gl}`;
  $("periodo").value = p.periodo;
  for (const k of CAMPOS_NUM) $(k).value = p[k];
}

function trocarModo(novo) {
  modo = novo;
  for (const b of document.querySelectorAll("#form .modo")) b.classList.toggle("ativo", b.dataset.modo === modo);
  $("modo-termos").hidden = modo !== "termos";
  $("modo-varredura").hidden = modo !== "varredura";
  $("campo-mercado").hidden = modo !== "termos";
  if (modo === "varredura") {  // padrão que caça canal novo; dá para mudar antes de rodar
    $("periodo").value = "7d_views";
    $("idade_max_dias").value = 60;
    $("min_views").value = 50000;
    $("por_termo").value = 40;  // menos páginas por termo: 100 levou a varredura ao bloqueio (403)
  }
  estimar();
}

const marcados = (id) => [...document.querySelectorAll(`#${id} input:checked`)].map((i) => i.value);

function estimar() {
  const fatia = Math.max(0, +$("vr-candidatos").value || 0);
  const termos = marcados("vr-idiomas").reduce((soma, i) => soma + Math.min(pendentes[i] ?? 0, fatia)
    + categorias.filter((c) => marcados("vr-categorias").includes(c.id)).reduce((s, c) => s + c.termos[i], 0), 0);
  const min = Math.ceil(termos * SEGUNDOS_POR_TERMO / 60);
  $("vr-estimativa").textContent = termos
    ? `${termos} buscas · ~${min} min · a cota só é gasta nos canais aprovados (~3 unidades cada)` : "Marque ao menos um idioma e uma categoria.";
}

export function montarVarredura(lista, candidatosPendentes) {
  categorias = lista;
  pendentes = candidatosPendentes;
  $("vr-idiomas").innerHTML = Object.entries(IDIOMAS).map(([id, nome]) =>
    `<label><input type="checkbox" value="${id}" ${IDIOMAS_PADRAO.includes(id) ? "checked" : ""}>${nome}</label>`).join("");
  $("vr-categorias").innerHTML = lista.map((c) =>
    `<label><input type="checkbox" value="${esc(c.id)}" checked>${esc(c.nome)}</label>`).join("");
  $("modo-varredura").onchange = estimar;
  $("vr-candidatos").oninput = estimar;
  const marcarTodas = (v) => (e) => { e.preventDefault(); document.querySelectorAll("#vr-categorias input").forEach((i) => { i.checked = v; }); estimar(); };
  $("vr-todas").onclick = marcarTodas(true);
  $("vr-nenhuma").onclick = marcarTodas(false);
  estimar();
}

function mostrarProgresso(m, naFila) {
  $("progresso").hidden = false;
  const pct = m.total ? Math.round(100 * m.atual / m.total) : 0;
  const idioma = m.parametros.varredura ? `Varredura ${IDIOMAS[m.parametros.hl] ?? m.parametros.hl} · ` : "";
  const fila = naFila ? ` · mais ${naFila} na fila` : "";
  $("progresso-texto").textContent = `${idioma}${FASES[m.fase] ?? "Começando"}… ${m.atual}/${m.total} · ${m.unidades} unidades${fila}`;
  $("progresso-barra").style.width = `${pct}%`;
}

async function acompanhar(id, naFila = 0) {
  clearTimeout(timer);
  const m = await lerMineracao(id);
  if (m.status === "rodando" || m.status === "na fila") {
    mostrarProgresso(m, naFila);
    timer = setTimeout(() => acompanhar(id, naFila), 1200);
    return;
  }
  timer = null;
  aoTerminar(m);
  await carregarHistorico();  // segue para a próxima da fila, se houver
}

function proximaAtiva(lista) {  // a que está rodando; senão a mais antiga na fila
  const ativas = lista.filter((m) => m.status === "rodando" || m.status === "na fila").sort((a, b) => a.id - b.id);
  return [ativas.find((m) => m.status === "rodando") ?? ativas[0], ativas.length - 1];
}

async function carregarHistorico() {
  const lista = await listarMineracoes();
  $("historico").innerHTML = lista.map((m) => `<div class="item" data-id="${m.id}">
      ${m.parametros.varredura ? "🌐 Varredura · " : ""}${esc(m.parametros.termos.slice(0, 3).join(", "))}${m.parametros.termos.length > 3 ? "…" : ""}
      <small>${esc(m.criado.replace("T", " ").slice(5, 16))} · ${esc(m.parametros.hl)}/${esc(m.parametros.gl)} ·
      <span class="${m.erro ? "erro" : ""}" title="${esc(m.erro ?? "")}">${esc(m.status)}${m.erro && m.status === "pronto" ? " ⚠ incompleta" : ""}</span></small></div>`).join("")
    || `<small style="color:var(--fraco)">Nada ainda.</small>`;
  for (const el of document.querySelectorAll(".item")) {
    el.onclick = () => preencher(lista.find((m) => m.id === +el.dataset.id).parametros);
  }
  const [ativa, naFila] = proximaAtiva(lista);
  $("btn-rodar").disabled = Boolean(ativa);
  if (!ativa) $("progresso").hidden = true;
  else if (!timer) acompanhar(ativa.id, naFila);
}

function corpoComum() {
  const corpo = {periodo: $("periodo").value};
  for (const k of CAMPOS_NUM) corpo[k] = +$(k).value;
  return corpo;
}

async function enviar(e) {
  e.preventDefault();
  $("btn-rodar").disabled = true;
  try {
    if (modo === "varredura") {
      await criarVarredura({...corpoComum(), idiomas: marcados("vr-idiomas"), categorias: marcados("vr-categorias"),
                             candidatos: +$("vr-candidatos").value});
    } else {
      const [hl, gl] = $("mercado").value.split("|");
      await criarMineracao({...corpoComum(), termos: $("termos").value.split("\n"), hl, gl});
    }
    await carregarHistorico();
  } catch (err) {
    $("progresso").hidden = false;
    $("progresso-texto").textContent = `Erro: ${err.message}`;
    $("btn-rodar").disabled = false;
  }
}

export function iniciarMineracao(callback) {
  aoTerminar = callback;
  $("form").onsubmit = enviar;
  for (const b of document.querySelectorAll("#form .modo")) b.onclick = () => trocarModo(b.dataset.modo);
  $("btn-minerar").onclick = () => { $("modal").showModal(); carregarHistorico(); };
  $("modal-fechar").onclick = () => $("modal").close();  // fechar não para a mineração: ela segue no servidor
  carregarHistorico();
}

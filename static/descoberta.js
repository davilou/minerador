// Janela "Descobrir nichos": candidatos a termo (promover ou recusar) e placar dos termos (aposentar).
import {aposentarTermo, gerarCandidatos, lerDescoberta, promoverCandidato, recusarCandidato} from "./api.js";
import {esc, num} from "./cards.js";

const $ = (id) => document.getElementById(id);
const ORIGENS = {titulos: "títulos dos aprovados", autocompletar: "autocompletar"};
const NOVA = "__nova__";

let categorias = [];  // [{id, nome}]
let dados = {candidatos: [], placar: []};
let vista = "candidatos";
let avisar = () => {};
let aoMudarNichos = async () => {};

const nomeCategoria = (id) => categorias.find((c) => c.id === id)?.nome ?? id;
const chave = (t) => `${t.idioma}|${t.termo}`;

function teste(c) {
  if (!c.buscas) return `<span class="fraco">ainda não testado</span>`;
  const linha = `${c.buscas} busca${c.buscas > 1 ? "s" : ""} · ${num(c.canais)} canais · ${c.aprovados} aprovados`;
  return c.aprovados ? `<span class="selo bom">rendeu</span> ${linha}` : linha;
}

function seletorCategoria(c) {
  const opcoes = categorias.map((k) => `<option value="${esc(k.id)}" ${k.id === c.categoria ? "selected" : ""}>${esc(k.nome)}</option>`);
  return `<select data-cat="${esc(chave(c))}">${c.categoria ? "" : `<option value="">Categoria…</option>`}${opcoes.join("")}
    <option value="${NOVA}">＋ nova categoria…</option></select>
    <input data-nova="${esc(chave(c))}" placeholder="Nome da categoria" hidden>`;
}

function linhaCandidato(c) {
  return `<tr>
    <td><b>${esc(c.termo)}</b><small>${esc(ORIGENS[c.origem] ?? c.origem)} · ${esc(c.evidencia)}</small></td>
    <td>${esc(c.idioma)}</td><td>${teste(c)}</td><td>${seletorCategoria(c)}</td>
    <td class="acoes"><button data-promover="${esc(chave(c))}">Promover</button>
      <button class="secundario" data-recusar="${esc(chave(c))}">Recusar</button></td></tr>`;
}

function desenharCandidatos(idioma) {
  const abertos = dados.candidatos.filter((c) => c.status === "novo" && (!idioma || c.idioma === idioma))
    .sort((a, b) => (b.aprovados > 0) - (a.aprovados > 0) || a.buscas - b.buscas);
  const fechados = {};
  for (const c of dados.candidatos) if (c.status !== "novo") fechados[c.status] = (fechados[c.status] ?? 0) + 1;
  const rodape = Object.entries(fechados).map(([s, n]) => `${n} ${s}${n > 1 ? "s" : ""}`).join(" · ");
  return (abertos.length ? `<table class="tabela"><thead><tr><th>Termo</th><th>Idioma</th><th>Teste na varredura</th>
      <th>Categoria</th><th></th></tr></thead><tbody>${abertos.map(linhaCandidato).join("")}</tbody></table>`
    : `<div class="vazio">Nenhum candidato aberto. Clique em <b>Gerar candidatos</b>.</div>`)
    + (rodape ? `<p class="fraco">${esc(rodape)}</p>` : "");
}

function linhaPlacar(t) {
  const taxa = t.buscas ? (t.aprovados / t.buscas).toFixed(1) : "—";
  const selo = t.aposentado ? `<span class="selo">aposentado</span>` : t.nao_rende ? `<span class="selo quente">não rende</span>` : "";
  return `<tr class="${t.aposentado ? "apagado" : ""}">
    <td><b>${esc(t.termo)}</b> ${selo}</td><td>${esc(t.idioma)}</td>
    <td>${esc(t.categorias.map(nomeCategoria).join(", ") || "—")}</td>
    <td class="n">${t.buscas}</td><td class="n">${num(t.canais)}</td><td class="n">${t.aprovados}</td><td class="n">${taxa}</td>
    <td class="acoes"><button class="secundario" data-aposentar="${esc(chave(t))}" data-valor="${t.aposentado ? 0 : 1}">
      ${t.aposentado ? "Reativar" : "Aposentar"}</button></td></tr>`;
}

function desenharPlacar(idioma) {
  const soRuins = $("d-ruins").checked;
  const lista = dados.placar.filter((t) => (!idioma || t.idioma === idioma) && (!soRuins || t.nao_rende));
  if (!lista.length) return `<div class="vazio">${dados.placar.length ? "Nenhum termo com esse filtro." : "O placar enche conforme você minera."}</div>`;
  return `<table class="tabela"><thead><tr><th>Termo</th><th>Idioma</th><th>Categoria</th><th class="n">Buscas</th>
    <th class="n">Canais</th><th class="n">Aprovados</th><th class="n">Aprov./busca</th><th></th></tr></thead>
    <tbody>${lista.map(linhaPlacar).join("")}</tbody></table>`;
}

function desenhar() {
  for (const b of document.querySelectorAll("#d-vistas .modo")) b.classList.toggle("ativo", b.dataset.vista === vista);
  const abertos = dados.candidatos.filter((c) => c.status === "novo").length;
  document.querySelector('#d-vistas [data-vista="candidatos"]').textContent = `Candidatos · ${abertos}`;
  $("d-filtro-ruins").hidden = vista !== "placar";
  const idioma = $("d-idioma").value;
  $("d-lista").innerHTML = vista === "candidatos" ? desenharCandidatos(idioma) : desenharPlacar(idioma);
}

async function recarregar() {
  dados = await lerDescoberta();
  desenhar();
}

const acharTermo = (lista, k) => lista.find((t) => chave(t) === k);

async function agir(acao, mensagem) {
  try {
    await acao();
    if (mensagem) avisar(mensagem);
    await recarregar();
  } catch (err) { avisar(err.message, true); }
}

async function promover(k) {
  const c = acharTermo(dados.candidatos, k);
  const cat = document.querySelector(`[data-cat="${CSS.escape(k)}"]`).value;
  const nova = document.querySelector(`[data-nova="${CSS.escape(k)}"]`).value.trim();
  if (!cat || (cat === NOVA && !nova)) { avisar("Escolha a categoria (ou dê nome à nova) antes de promover.", true); return; }
  await agir(async () => {
    const r = await promoverCandidato({termo: c.termo, idioma: c.idioma, ...(cat === NOVA ? {nome_nova: nova} : {categoria: cat})});
    await aoMudarNichos();
    avisar(`“${c.termo}” agora é semente de ${nomeCategoria(r.categoria)} e entra em toda varredura.`);
  });
}

function aoClicar(e) {
  const alvo = e.target.closest("button");
  if (!alvo) return;
  if (alvo.dataset.promover) promover(alvo.dataset.promover);
  if (alvo.dataset.recusar) {
    const c = acharTermo(dados.candidatos, alvo.dataset.recusar);
    agir(() => recusarCandidato({termo: c.termo, idioma: c.idioma}));
  }
  if (alvo.dataset.aposentar) {
    const t = acharTermo(dados.placar, alvo.dataset.aposentar);
    agir(() => aposentarTermo({termo: t.termo, idioma: t.idioma, valor: alvo.dataset.valor === "1"}));
  }
}

async function gerar() {
  $("btn-gerar").disabled = true;
  $("btn-gerar").textContent = "Gerando…";
  await agir(async () => {
    const r = await gerarCandidatos();
    avisar(`${r.titulos + r.autocompletar} candidatos novos · ${r.titulos} dos títulos · ${r.autocompletar} do autocompletar`);
    await aoMudarNichos();
  });
  $("btn-gerar").disabled = false;
  $("btn-gerar").textContent = "Gerar candidatos";
}

export function definirCategoriasDescoberta(lista) { categorias = lista; }

export function iniciarDescoberta(callbackAviso, callbackNichos) {
  avisar = callbackAviso;
  aoMudarNichos = callbackNichos;
  $("btn-descobrir").onclick = () => { $("modal-desc").showModal(); recarregar().catch((err) => avisar(err.message, true)); };
  $("modal-desc-fechar").onclick = () => $("modal-desc").close();
  for (const b of document.querySelectorAll("#d-vistas .modo")) b.onclick = () => { vista = b.dataset.vista; desenhar(); };
  $("d-idioma").oninput = desenhar;
  $("d-ruins").oninput = desenhar;
  $("btn-gerar").onclick = gerar;
  $("d-lista").onclick = aoClicar;
  $("d-lista").onchange = (e) => {  // "＋ nova categoria…" abre o campo do nome ao lado
    if (!e.target.dataset.cat) return;
    document.querySelector(`[data-nova="${CSS.escape(e.target.dataset.cat)}"]`).hidden = e.target.value !== NOVA;
  };
}

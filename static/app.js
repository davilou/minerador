// Painel de cards: abas, filtros, ordenação e favoritos sobre a base acumulada.
import {atualizarBase, favoritar, listarCanais, listarNichos, listarVirais} from "./api.js";
import {card, cardVideo, definirCategorias, esc, ha} from "./cards.js";
import {definirCategoriasDescoberta, iniciarDescoberta} from "./descoberta.js";
import {iniciarMineracao, montarVarredura} from "./mineracao.js";

const $ = (id) => document.getElementById(id);
const FILTROS = ["f-busca", "f-idioma", "f-categoria", "f-formato", "f-inscritos", "f-views", "f-videos", "f-ordem", "f-ordem-virais"];

const ORDEM_ABAS = ["explodindo", "subindo", "outliers", "tracao", "novos", "favoritos", "todos"];
const estado = {canais: [], virais: [], descricoes: {}, aba: lerAba()};

function lerAba() {
  try { return localStorage.getItem("aba"); } catch { return null; }
}

function abaInicial() {  // sem aba lembrada: a primeira que tem canal, para não abrir numa tela vazia
  return ORDEM_ABAS.find((a) => estado.canais.some((c) => c.abas.includes(a))) ?? "todos";
}

function faixa(valor, filtro) {  // "0-10000", "100000-" ou "" (sem filtro)
  if (!filtro) return true;
  const [min, max] = filtro.split("-");
  return (valor ?? 0) >= +min && (max === "" || (valor ?? 0) <= +max);
}

function casaBusca(c, termo) {
  if (!termo) return true;
  const texto = [c.nome, c.handle, ...c.termos, ...c.top.map((v) => v.titulo)].join(" ").toLowerCase();
  return texto.includes(termo);
}

function chaveOrdem(c, ordem) {
  if (ordem === "views_por_video") return c.views_total / Math.max(c.qtd_videos, 1);
  if (ordem === "dias_postando_asc") return -c.dias_postando;
  if (ordem === "adicionado") return new Date(c.adicionado).getTime();
  return c[ordem] ?? -Infinity;  // subida_dia ainda sem duas fotos vai pro fim
}

function visiveis() {
  const termo = $("f-busca").value.trim().toLowerCase();
  const ordem = $("f-ordem").value;
  return estado.canais
    .filter((c) => c.abas.includes(estado.aba))
    .filter((c) => !$("f-idioma").value || c.idioma === $("f-idioma").value)
    .filter((c) => !$("f-categoria").value || c.categorias.includes($("f-categoria").value))
    .filter((c) => !$("f-formato").value || c.formato === $("f-formato").value)
    .filter((c) => faixa(c.inscritos, $("f-inscritos").value) && faixa(c.views_total, $("f-views").value)
                   && faixa(c.qtd_videos, $("f-videos").value))
    .filter((c) => casaBusca(c, termo))
    .sort((a, b) => chaveOrdem(b, ordem) - chaveOrdem(a, ordem));
}

// Aba Virais lista vídeos, não canais: filtros de canal que não fazem sentido somem.
function viraisVisiveis() {
  const termo = $("f-busca").value.trim().toLowerCase();
  const ordem = $("f-ordem-virais").value;
  const formato = $("f-formato").value;
  const chave = (v) => ordem === "publicado" || ordem === "adicionado" ? new Date(v[ordem]).getTime() : v[ordem];
  return estado.virais
    .filter((v) => !$("f-idioma").value || v.idioma === $("f-idioma").value)
    .filter((v) => !$("f-categoria").value || v.categorias.includes($("f-categoria").value))
    .filter((v) => !formato || (formato === "shorts") === v.short)
    .filter((v) => faixa(v.inscritos, $("f-inscritos").value) && faixa(v.views, $("f-views").value))
    .filter((v) => !termo || [v.titulo, v.canal_nome, v.canal_handle, v.termo].join(" ").toLowerCase().includes(termo))
    .sort((a, b) => chave(b) - chave(a));
}

function desenharAbas() {
  const virais = estado.aba === "virais";
  $("f-ordem").hidden = virais;
  $("f-videos").hidden = virais;
  $("f-ordem-virais").hidden = !virais;
  for (const b of document.querySelectorAll("#abas button")) {
    const n = b.dataset.aba === "virais" ? estado.virais.length
      : estado.canais.filter((c) => c.abas.includes(b.dataset.aba)).length;
    b.classList.toggle("ativa", b.dataset.aba === estado.aba);
    b.querySelector("b")?.remove();
    b.insertAdjacentHTML("beforeend", `<b>${n}</b>`);
  }
  $("regra").textContent = estado.descricoes[estado.aba] ?? "";
}

function desenhar() {
  desenharAbas();
  if (estado.aba === "virais") {
    const lista = viraisVisiveis();
    $("grade").innerHTML = lista.length ? lista.map(cardVideo).join("")
      : `<div class="vazio">Nenhum viral de canal pequeno ainda. Eles aparecem conforme você minera.</div>`;
    return;
  }
  const lista = visiveis();
  $("grade").innerHTML = lista.length ? lista.map(card).join("")
    : `<div class="vazio">${estado.canais.length ? "Nenhum canal nesta aba com esses filtros."
        : "A base está vazia. Clique em <b>+ Nova mineração</b> para começar."}</div>`;
}

function desenharContador() {
  const semana = estado.canais.filter((c) => Date.now() - new Date(c.adicionado) < 7 * 864e5).length;
  $("contador").textContent = `${estado.canais.length} canais · +${semana} esta semana`;
  const idiomas = [...new Set([...estado.canais, ...estado.virais].map((c) => c.idioma))].sort();
  const atual = $("f-idioma").value;
  $("f-idioma").innerHTML = `<option value="">Idioma</option>` + idiomas.map((i) => `<option>${esc(i)}</option>`).join("");
  $("f-idioma").value = idiomas.includes(atual) ? atual : "";
}

async function carregar() {
  const [r, virais] = await Promise.all([listarCanais(), listarVirais()]);
  estado.canais = r.canais;
  estado.virais = virais;
  estado.descricoes = r.descricoes;
  estado.aba ??= abaInicial();
  $("btn-atualizar").textContent = r.ultima_atualizacao ? `↻ Atualizar números · há ${ha(r.ultima_atualizacao)}` : "↻ Atualizar números";
  desenharContador();
  desenhar();
  acompanharAutomatica(r.atualizando);
}

// O servidor relê os números sozinho ao abrir quando a última leitura tem 12 h+ (app.py).
function acompanharAutomatica(atualizando) {
  $("btn-atualizar").disabled = atualizando;
  if (atualizando) {
    estado.esperandoAutomatica = true;
    avisar("Atualizando os números da base (a última leitura tinha mais de 12 h)…");
    setTimeout(() => carregar().catch((err) => avisar(`Não carregou a base: ${err.message}`, true)), 3000);
  } else if (estado.esperandoAutomatica) {
    estado.esperandoAutomatica = false;
    avisar("Números atualizados.");
  }
}

function avisar(texto, erro = false) {
  $("aviso").textContent = texto;
  $("aviso").className = `aviso ${erro ? "erro" : ""}`;
  $("aviso").hidden = false;
  clearTimeout(avisar.timer);
  avisar.timer = setTimeout(() => { $("aviso").hidden = true; }, 6000);
}

async function alternarFavorito(botao) {
  const c = estado.canais.find((x) => x.id === botao.dataset.fav);
  try {
    await favoritar(c.id, !c.favorito);
    c.favorito = !c.favorito;
    c.abas = c.favorito ? [...c.abas, "favoritos"] : c.abas.filter((a) => a !== "favoritos");
    desenhar();
  } catch (err) { avisar(`Não deu para favoritar: ${err.message}`, true); }
}

async function atualizar() {
  $("btn-atualizar").disabled = true;
  try {
    const r = await atualizarBase();
    avisar(`${r.canais} canais atualizados · ${r.videos_novos} vídeos novos · ${r.unidades} unidades de cota`
           + (r.sumiram ? ` · ${r.sumiram} sumiram do YouTube` : ""));
    await carregar();
  } catch (err) { avisar(`Falhou ao atualizar: ${err.message}`, true); }
  $("btn-atualizar").disabled = false;
}

function ligarEventos() {
  for (const b of document.querySelectorAll("#abas button")) {
    b.onclick = () => {
      estado.aba = b.dataset.aba;
      try { localStorage.setItem("aba", estado.aba); } catch { /* sem storage: só não lembra a aba */ }
      desenhar();
    };
  }
  for (const id of FILTROS) $(id).oninput = desenhar;
  $("grade").onclick = (e) => { const b = e.target.closest("[data-fav]"); if (b) alternarFavorito(b); };
  $("btn-atualizar").onclick = atualizar;
}

async function carregarNichos() {
  const {categorias, pendentes} = await listarNichos();
  definirCategorias(Object.fromEntries(categorias.map((c) => [c.id, c.nome])));
  $("f-categoria").innerHTML = `<option value="">Categoria</option>`
    + categorias.map((c) => `<option value="${esc(c.id)}">${esc(c.nome)}</option>`).join("");
  montarVarredura(categorias, pendentes);
  definirCategoriasDescoberta(categorias);
}

ligarEventos();
iniciarDescoberta(avisar, () => carregarNichos().then(carregar));  // promover muda as categorias dos canais
iniciarMineracao(async (m) => {
  if (m.status === "erro") { avisar(`Mineração falhou: ${m.erro}`, true); return; }
  const antes = estado.canais.length, antesVirais = estado.virais.length;
  await carregar();
  avisar(`Mineração pronta: ${m.resultado.length} canais aprovados · ${estado.canais.length - antes} novos na base · `
         + `${estado.virais.length - antesVirais} virais de pequenos · ${m.unidades} unidades`
         + (m.erro ? ` · ⚠ ${m.erro}` : ""), Boolean(m.erro));  // pronto com erro = termos de fora
});
carregarNichos().then(carregar).catch((err) => avisar(`Não carregou a base: ${err.message}`, true));

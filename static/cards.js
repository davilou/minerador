// Monta o card de um canal (HTML). Tudo que vem da base passa por esc().

export const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"}[c]));

const compacto = new Intl.NumberFormat("en-US", {notation: "compact", maximumFractionDigits: 1});
export const num = (n) => n == null ? "—" : compacto.format(n);

export function ha(iso) {
  const min = (Date.now() - new Date(iso)) / 60000;
  if (min < 60) return `${Math.max(1, Math.round(min))} min`;
  if (min < 1440) return `${Math.round(min / 60)}h`;
  const d = Math.round(min / 1440);
  if (d < 7) return `${d} ${d === 1 ? "dia" : "dias"}`;
  if (d < 30) return `${Math.round(d / 7)} sem`;
  return `${Math.round(d / 30)} ${Math.round(d / 30) === 1 ? "mês" : "meses"}`;
}

// Selo do canto: a aba mais forte em que o canal aparece.
const SELOS = [["explodindo", "Explodindo", true], ["subindo", "Subindo", true], ["outliers", "Outlier", false],
               ["tracao", "Tração", false], ["novos", "Novo", false]];
const FORMATOS = {longo: "Longo", shorts: "Shorts", misto: "Misto"};

let nomesCategorias = {};  // id -> nome, vindo de /api/nichos
export const definirCategorias = (mapa) => { nomesCategorias = mapa; };
const chipsCategoria = (ids) => ids.map((c) => `<span class="categoria">${esc(nomesCategorias[c] ?? c)}</span>`).join("");

function bandeira(pais) {
  if (!pais) return "";
  return `<img class="bandeira" src="https://flagcdn.com/w40/${esc(pais.toLowerCase())}.png" alt="${esc(pais)}" title="${esc(pais)}" onerror="this.remove()">`;
}

function miniaturas(top) {
  return top.map((v) => `<a href="https://youtu.be/${esc(v.id)}" target="_blank" title="${esc(v.titulo)}">
      <img src="https://i.ytimg.com/vi/${esc(v.id)}/mqdefault.jpg" loading="lazy" alt="">
      <span>${num(v.views)}${v.short ? " · S" : ""}</span></a>`).join("");
}

const duracao = (dias) => dias >= 365 ? `${(dias / 365).toFixed(1).replace(".0", "")} ${dias >= 730 ? "anos" : "ano"}` : `${Math.round(dias / 30)} meses`;

function aviso_reaproveitado(c) {
  if (c.hiato_dias != null) {  // postou antes, parou 6+ meses e voltou: idade conta da volta
    return `<span class="alerta" title="1º vídeo em ${esc(c.primeiro_video)}; fase atual desde ${esc(c.inicio_fase)}. Idade e views/mês contam só a fase atual.">↺ voltou em ${esc(c.inicio_fase)} após ${duracao(c.hiato_dias)} parado</span>`;
  }
  const antes = (new Date(c.primeiro_video) - new Date(c.criado)) / 864e5;
  return antes > 90 ? `<span class="alerta" title="Canal criado bem antes do primeiro vídeo: pode ser comprado ou reaproveitado">⚠ criado ${Math.round(antes)} d antes do 1º vídeo</span>` : "";
}

export function card(c) {
  const selo = SELOS.find(([aba]) => c.abas.includes(aba));
  const subida = c.subida_dia != null ? ` · <span title="views ganhas por dia entre as duas últimas atualizações">+${num(c.subida_dia)}/dia</span>` : "";
  return `<article class="card ${selo?.[2] ? "destaque" : ""}">
    <div class="cab">
      <div class="avatar"><img class="foto" src="/api/avatar/${encodeURIComponent(c.id)}" loading="lazy" alt="">${bandeira(c.pais)}</div>
      <div class="nome">
        <a href="${esc(c.url)}" target="_blank">${esc(c.nome)}</a>
        <small>${esc(c.handle)} · ${esc(FORMATOS[c.formato] ?? c.formato)}</small>
      </div>
      <div class="lado">
        <button class="coracao ${c.favorito ? "on" : ""}" data-fav="${esc(c.id)}" title="Favorito">${c.favorito ? "♥" : "♡"}</button>
        ${selo ? `<span class="selo ${selo[2] ? "quente" : ""}">${selo[1]}</span>` : ""}
      </div>
    </div>
    <div class="thumbs">${miniaturas(c.top)}</div>
    <div class="numeros">
      <div><b>${num(c.inscritos)}</b><small>inscritos</small></div>
      <div><b>${num(c.views_total)}</b><small>views</small></div>
      <div><b>${c.qtd_videos}</b><small>vídeos</small></div>
      <div class="verde"><b>${num(c.views_total / Math.max(c.qtd_videos, 1))}</b><small>views/vídeo</small></div>
    </div>
    <div class="rodape">
      <span>📅 ${c.dias_postando}d postando · ${c.videos_mes} vid/mês · ${num(c.views_mes)} views/mês${subida}</span>
      <span>🕓 Adicionado há ${ha(c.adicionado)} · atualizado há ${ha(c.atualizado)}</span>
      ${aviso_reaproveitado(c)}
      <span class="termos">${chipsCategoria(c.categorias)}${c.termos.map((t) => `<span class="termo">${esc(t)}</span>`).join("")}</span>
    </div>
  </article>`;
}

// Card de vídeo da aba Virais: o vídeo é o protagonista, o canal é contexto.
export function cardVideo(v) {
  const canal = `https://www.youtube.com/channel/${esc(v.canal_id)}`;
  return `<article class="card-video">
    <a class="capa" href="https://youtu.be/${esc(v.video_id)}" target="_blank">
      <img src="https://i.ytimg.com/vi/${esc(v.video_id)}/mqdefault.jpg" loading="lazy" alt="">
      <span class="razao" title="views ÷ inscritos do canal">${num(v.razao)}× inscritos</span>
      <span class="views">${num(v.views)} views</span>
    </a>
    <div class="corpo">
      <a class="titulo-video" href="https://youtu.be/${esc(v.video_id)}" target="_blank" title="${esc(v.titulo)}">${esc(v.titulo)}</a>
      <div class="dono">
        <img src="/api/avatar/${encodeURIComponent(v.canal_id)}" loading="lazy" alt="">
        <span><a href="${canal}" target="_blank">${esc(v.canal_nome)}</a> · ${num(v.inscritos)} inscritos</span>
      </div>
      <div class="rodape">
        <span>📅 publicado há ${ha(v.publicado)} · ${v.short ? "Short" : "vídeo longo"}${v.canal_pais ? " · " + esc(v.canal_pais) : ""}</span>
        <span class="termos">${chipsCategoria(v.categorias)}<span class="termo">${esc(v.termo)}</span></span>
      </div>
    </div>
  </article>`;
}

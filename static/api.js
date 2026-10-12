// Chamadas ao backend. Erro de HTTP vira exceção com a mensagem do servidor.

async function pedir(url, opcoes) {
  const r = await fetch(url, opcoes);
  if (r.status === 204) return null;
  const corpo = await r.json().catch(() => null);
  if (!r.ok) throw new Error(corpo?.detail?.[0]?.msg ?? corpo?.detail ?? `HTTP ${r.status}`);
  return corpo;
}

const json = (corpo) => ({method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(corpo)});

export const listarCanais = () => pedir("/api/canais");
export const listarVirais = () => pedir("/api/virais");
export const favoritar = (id, valor) => pedir(`/api/canais/${encodeURIComponent(id)}/favorito`, json({valor}));
export const atualizarBase = () => pedir("/api/base/atualizar", {method: "POST"});
export const criarMineracao = (corpo) => pedir("/api/mineracoes", json(corpo));
export const criarVarredura = (corpo) => pedir("/api/varredura", json(corpo));
export const listarNichos = () => pedir("/api/nichos");
export const lerMineracao = (id) => pedir(`/api/mineracoes/${id}`);
export const listarMineracoes = () => pedir("/api/mineracoes");
export const lerDescoberta = () => pedir("/api/descoberta");
export const gerarCandidatos = () => pedir("/api/descoberta/gerar", {method: "POST"});
export const promoverCandidato = (corpo) => pedir("/api/candidatos/promover", json(corpo));
export const recusarCandidato = (corpo) => pedir("/api/candidatos/recusar", json(corpo));
export const aposentarTermo = (corpo) => pedir("/api/placar/aposentar", json(corpo));

"""
Termos novos a partir dos títulos dos canais que já passaram no filtro: a expressão de 2-3 palavras
que se repete em vários canais diferentes é o nome de um nicho ("psicologia feminina",
"história bíblica animada"). Regras puras, sem banco.
"""

from __future__ import annotations

import re

# Palavra que não abre nem fecha um termo. No meio pode ("história da bíblia").
_VAZIAS = set("""
a o as os um uma uns umas de da do das dos em na no nas nos por para pra com sem que se e ou mas
é foi ser são ao aos à às isso isto esse essa este esta ele ela eles elas eu você voce seu sua meu minha
mais muito muita como quando onde porque por que já não nao sim até sobre entre nunca tudo todo toda todos
the an of in on at to for from with by and or but is are was were be been it its this that these those
you your my his her their our we they he she i me how what why who when where which not no yes all
more most very just can will do does did vs about into out up over after before never ever
el la los las un una unos unas del al en con por para que y o pero es son fue ser lo su sus mi tu
como cuando donde porque más muy ya no sí todo toda todos sobre entre nunca
der die das ein eine einen einem einer des dem den und oder aber ist sind war sein zu im am vom zum zur
mit von für auf aus bei nach wie was warum wer wo nicht kein keine alle mehr sehr nur noch über
shorts short video vídeo videos vídeos part parte teil ep episode episódio episodio full official oficial
new novo nova nuevo nueva neu neue live ao vivo en vivo hd 4k
te vai vou pode podem faz fazer fez tem têm ter há vez vezes coisa coisas cosas cosa thing things
estas estes essas esses estos estas esos esas muitas muitos muchas muchos ninguém nadie nobody
if even every only one ones re ll ve don year years old day days ano anos años año dia dias día
watch happens happened whats nº n° wont youre dont cant isnt
english ingles inglés espanol español portugues português deutsch subtitles legendado
""".split())

_SEPARADORES = re.compile(r"[|:;!?.,()\[\]{}\"“”«»#/–—•·]+| - ")
# Só alfabeto latino: os mercados são pt/en/es/de, e escrita com acento combinante (hindi) sai picada.
_PALAVRA = re.compile(r"[a-zß-öø-ÿ]+")


def _trechos(titulo: str) -> list[list[str]]:
    """Palavras do título, por trecho: um termo não atravessa '|' nem ':'."""
    sem_apostrofo = re.sub(r"['’]", "", titulo.lower())  # won't -> wont, não "won" + "t"
    return [_PALAVRA.findall(t) for t in _SEPARADORES.split(sem_apostrofo)]


def _ponta(palavra: str) -> bool:
    """Pode abrir ou fechar um termo: não é vazia nem letra solta ('e', 'y' somem da lista mas contam)."""
    return len(palavra) > 1 and palavra not in _VAZIAS


def ngramas(titulo: str) -> set[str]:
    achados: set[str] = set()
    for palavras in _trechos(titulo):
        for n in (2, 3):
            for i in range(len(palavras) - n + 1):
                g = palavras[i:i + n]
                if _ponta(g[0]) and _ponta(g[-1]):
                    achados.add(" ".join(g))
    return achados


def acrescenta(semente: str, sugestao: str) -> bool:
    """A sugestão traz palavra de verdade além da semente; '2026' ou 'english' sozinhos não contam."""
    da_semente = {p for trecho in _trechos(semente) for p in trecho}
    return any(_ponta(p) and p not in da_semente for trecho in _trechos(sugestao) for p in trecho)


def coberto(termo: str, conhecidos: set[str]) -> bool:
    """Já buscado: igual a um termo conhecido, dentro dele ou contendo ele (palavra inteira)."""
    t = f" {termo.lower()} "
    return any(f" {k} " in t or t in f" {k} " for k in conhecidos)


def frequentes(titulos_por_canal: dict[str, list[str]], conhecidos: set[str],
               min_canais: int) -> list[tuple[str, set[str]]]:
    """
    Expressões que aparecem em min_canais+ canais diferentes e ainda não são termo, da mais
    espalhada para a menos. A de 2 palavras sai quando a de 3 que a contém está nos mesmos canais.
    """
    canais_de: dict[str, set[str]] = {}
    for canal, titulos in titulos_por_canal.items():
        do_canal: set[str] = set()
        for titulo in titulos:
            do_canal |= ngramas(titulo)
        for g in do_canal:
            canais_de.setdefault(g, set()).add(canal)
    conhecidos_min = {k.lower() for k in conhecidos}
    bons = {g: c for g, c in canais_de.items() if len(c) >= min_canais and not coberto(g, conhecidos_min)}
    engolidos = {g for g, c in bons.items() if g.count(" ") == 1
                 and any(f" {g} " in f" {maior} " and c == cm for maior, cm in bons.items() if maior.count(" ") == 2)}
    restantes = [(g, c) for g, c in bons.items() if g not in engolidos]
    return sorted(restantes, key=lambda gc: (-len(gc[1]), -gc[0].count(" "), gc[0]))


# Expressão cujos canais já estão, nessa fração, nos de uma escolhida antes é o mesmo nicho dito
# de outro jeito ("homem mais velho", "velho deveria assistir"): sai para abrir vaga a outro nicho.
SOBREPOSICAO_MAX = 0.5


def diversos(achados: list[tuple[str, set[str]]], limite: int) -> list[tuple[str, set[str]]]:
    """Os primeiros de `achados` (já ordenados) que não repetem o nicho de um escolhido antes."""
    escolhidos: list[tuple[str, set[str]]] = []
    for g, c in achados:
        if all(len(c & ce) / min(len(c), len(ce)) <= SOBREPOSICAO_MAX for _, ce in escolhidos):
            escolhidos.append((g, c))
            if len(escolhidos) == limite:
                break
    return escolhidos

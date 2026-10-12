import titulos


def test_ngramas_nao_abrem_nem_fecham_com_palavra_vazia_e_nao_cruzam_separador() -> None:
    g = titulos.ngramas("A História da Bíblia | Documentário Completo")
    assert {"história da bíblia", "documentário completo"} <= g
    assert "bíblia documentário" not in g  # atravessaria o '|'
    assert not any(x.startswith(("a ", "da ")) or x.endswith(" da") for x in g)


def test_ngramas_ignoram_numero_e_escrita_nao_latina() -> None:
    assert titulos.ngramas("7 Sinais Ocultos 2026 हड सभ") == {"sinais ocultos"}


def test_acrescenta_exige_palavra_nova_de_verdade() -> None:
    assert titulos.acrescenta("true crime documentary", "true crime documentary murders")
    assert not titulos.acrescenta("true crime documentary", "true crime documentary 2026")
    assert not titulos.acrescenta("true crime documentary", "the true crime documentary")


def test_apostrofo_nao_quebra_palavra() -> None:
    assert "believe" not in " ".join(titulos.ngramas("You Won't Believe This"))  # 'wont' e 'this' são vazias


def test_coberto_compara_palavra_inteira() -> None:
    assert titulos.coberto("psicologia feminina", {"psicologia feminina"})
    assert titulos.coberto("segredos da psicologia feminina", {"psicologia feminina"})
    assert titulos.coberto("psicologia", {"psicologia feminina"})
    assert not titulos.coberto("logia feminina", {"psicologia feminina"})


def test_frequentes_conta_canais_distintos_e_tira_o_conhecido() -> None:
    por_canal = {
        "UC1": ["Psicologia Feminina: sinais", "Psicologia Feminina de novo", "carl jung explica"],
        "UC2": ["psicologia feminina hoje", "Carl Jung e a sombra"],
        "UC3": ["Psicologia Feminina!"],
    }
    assert [g for g, _ in titulos.frequentes(por_canal, set(), 3)] == ["psicologia feminina"]
    assert titulos.frequentes(por_canal, {"Psicologia Feminina"}, 3) == []
    assert ("carl jung", {"UC1", "UC2"}) in titulos.frequentes(por_canal, set(), 2)


def test_frequentes_fica_com_a_de_tres_palavras_quando_cobre_os_mesmos_canais() -> None:
    por_canal = {c: ["homem mais velho precisa ouvir"] for c in ("UC1", "UC2", "UC3")}
    nomes = [g for g, _ in titulos.frequentes(por_canal, set(), 3)]
    assert "homem mais velho" in nomes and "mais velho" not in nomes


def test_diversos_pula_o_mesmo_nicho_dito_de_outro_jeito() -> None:
    achados = [("homem mais velho", {"a", "b", "c", "d"}), ("velho deveria", {"a", "b", "c"}),
               ("carl jung", {"e", "f", "a"}), ("linguagem corporal", {"g", "h"})]
    assert [g for g, _ in titulos.diversos(achados, 5)] == ["homem mais velho", "carl jung", "linguagem corporal"]
    assert len(titulos.diversos(achados, 2)) == 2

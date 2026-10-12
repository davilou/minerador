from datetime import date

import pytest

from metricas import (Filtros, Video, duracao_segundos, formato, idade_dias, inicio_fase, passa_prefiltro,
                      resumir)

HOJE = date(2026, 9, 30)
F = Filtros(max_videos=30, min_views=100_000, idade_max_dias=180)


def v(dur: int, views: int = 1000, dia: date = date(2026, 9, 1), vid: str = "x") -> Video:
    return Video(id=vid, titulo=vid, views=views, duracao_s=dur, publicado=dia)


@pytest.mark.parametrize("iso,esperado", [
    ("PT1H2M3S", 3723), ("PT45S", 45), ("PT10M", 600), ("P0D", 0), ("P1DT1S", 86401),
])
def test_duracao_segundos(iso: str, esperado: int) -> None:
    assert duracao_segundos(iso) == esperado


def test_duracao_invalida_falha_alto() -> None:
    with pytest.raises(ValueError):
        duracao_segundos("10 minutos")


def test_short_vai_ate_3_minutos() -> None:
    assert v(180).eh_short and not v(181).eh_short


def test_formato_por_fatia_dominante() -> None:
    assert formato([v(60)] * 8 + [v(600)] * 2) == "shorts"
    assert formato([v(600)] * 8 + [v(60)] * 2) == "longo"
    assert formato([v(600)] * 5 + [v(60)] * 5) == "misto"


def test_formato_ignora_live_agendada() -> None:
    assert formato([v(600), v(0), v(0), v(0)]) == "longo"


def test_formato_sem_video_valido_falha() -> None:
    with pytest.raises(ValueError):
        formato([v(0)])


def test_idade_conta_do_primeiro_video() -> None:
    assert idade_dias([v(600, dia=date(2026, 9, 20)), v(600, dia=date(2026, 7, 2))], HOJE) == 90


def test_fase_sem_hiato_comeca_no_primeiro_video() -> None:
    assert inicio_fase([date(2026, 9, 1), date(2026, 3, 1), date(2026, 6, 1)]) == (date(2026, 3, 1), None)


def test_fase_comeca_depois_do_hiato_mais_recente() -> None:
    datas = [date(2019, 1, 1), date(2019, 2, 1),  # primeira fase
             date(2023, 5, 1),                    # voltou por um mês...
             date(2026, 9, 10), date(2026, 9, 20)]  # ...e agora de novo
    assert inicio_fase(datas) == (date(2026, 9, 10), (date(2026, 9, 10) - date(2023, 5, 1)).days)


def test_hiato_abaixo_do_limite_nao_abre_fase() -> None:
    assert inicio_fase([date(2026, 1, 1), date(2026, 6, 29)]) == (date(2026, 1, 1), None)  # 179 dias
    assert inicio_fase([date(2026, 1, 1), date(2026, 6, 30)])[0] == date(2026, 6, 30)       # 180 dias


def test_inicio_fase_sem_datas_falha() -> None:
    with pytest.raises(ValueError):
        inicio_fase([])


def test_idade_de_canal_que_voltou_conta_da_volta() -> None:
    vids = [v(600, 10_000_000, date(2020, 1, 1)), v(600, 50_000, date(2026, 9, 20))]
    assert idade_dias(vids, HOJE) == 10
    r = resumir(vids, HOJE)
    assert r["inicio_fase"] == "2026-09-20" and r["primeiro_video"] == "2020-01-01"
    assert r["hiato_dias"] == (date(2026, 9, 20) - date(2020, 1, 1)).days


def test_prefiltro_limites() -> None:
    assert passa_prefiltro(30, 100_000, F)
    assert not passa_prefiltro(31, 10_000_000, F)
    assert not passa_prefiltro(5, 99_999, F)
    assert not passa_prefiltro(0, 1_000_000, F)  # canal sem vídeo público


def test_resumir_calcula_medias_e_top() -> None:
    vids = [v(600, 900_000, date(2026, 9, 20), "a"), v(600, 100_000, date(2026, 9, 10), "b"),
            v(60, 50_000, date(2026, 9, 25), "c"), v(600, 10, date(2026, 9, 26), "d")]
    r = resumir(vids, HOJE)
    assert r["idade_dias"] == 20
    assert r["views_por_video"] == 1_050_010 // 4
    assert r["views_por_dia"] == 1_050_010 // 20
    assert [t["id"] for t in r["top"]] == ["a", "b", "c"]  # type: ignore[index]


def test_resumir_canal_de_hoje_nao_divide_por_zero() -> None:
    assert resumir([v(600, 5000, HOJE)], HOJE)["views_por_dia"] == 5000

from datetime import date, datetime

from abas import (EXPLODINDO_VIEWS, OUTLIER_FATOR, Foto, VideoBase, abas_do_canal, dias_postando, fator_outlier, por_mes,
                  subida_por_dia, tracao_recente)

HOJE = date(2026, 9, 30)


def test_dias_postando_nunca_negativo() -> None:
    assert dias_postando(date(2026, 9, 1), HOJE) == 29
    assert dias_postando(date(2026, 10, 1), HOJE) == 0  # fuso: vídeo "de amanhã"


def test_por_mes_extrapola_canal_curto() -> None:
    assert por_mes(10, 15) == 20
    assert por_mes(4, 0) == 120  # canal de hoje conta como 1 dia


def test_tracao_so_conta_ultimos_30_dias() -> None:
    vids = [VideoBase(50_000, date(2026, 9, 29)), VideoBase(60_000, date(2026, 8, 31)),
            VideoBase(999_999, date(2026, 8, 30))]
    assert tracao_recente(vids, HOJE) == 110_000


def test_outlier_compara_maior_com_media_dos_outros() -> None:
    vids = [VideoBase(500_000, HOJE), VideoBase(100_000, HOJE), VideoBase(100_000, HOJE)]
    assert fator_outlier(vids) == 5.0
    assert fator_outlier([VideoBase(10, HOJE)]) is None
    assert fator_outlier([VideoBase(5000, HOJE), VideoBase(0, HOJE)]) == 5000


def test_subida_usa_as_duas_fotos_mais_recentes() -> None:
    fotos = [Foto(datetime(2026, 9, 28), 0), Foto(datetime(2026, 9, 30), 300_000),
             Foto(datetime(2026, 9, 29), 100_000)]
    assert subida_por_dia(fotos) == 200_000


def test_subida_pula_foto_recente_demais_e_usa_a_anterior() -> None:
    fotos = [Foto(datetime(2026, 9, 29, 12), 0), Foto(datetime(2026, 9, 30, 10), 90_000),
             Foto(datetime(2026, 9, 30, 12), 100_000)]  # a das 10h está a só 2 h da última
    assert subida_por_dia(fotos) == 100_000


def test_subida_ignora_fotos_muito_proximas() -> None:
    fotos = [Foto(datetime(2026, 9, 30, 10), 0), Foto(datetime(2026, 9, 30, 12), 50_000)]
    assert subida_por_dia(fotos) is None
    assert subida_por_dia(fotos[:1]) is None


def test_abas_explodindo_exige_as_duas_condicoes() -> None:
    assert "explodindo" in abas_do_canal(EXPLODINDO_VIEWS + 1, 14, 0, None, None, False)
    assert "explodindo" not in abas_do_canal(EXPLODINDO_VIEWS + 1, 15, 0, None, None, False)
    assert "explodindo" not in abas_do_canal(EXPLODINDO_VIEWS, 3, 0, None, None, False)


def test_abas_demais_regras() -> None:
    abas = abas_do_canal(1_000, 60, 100_000, OUTLIER_FATOR, 10, True)
    assert set(abas) == {"todos", "novos", "outliers", "tracao", "subindo", "favoritos"}
    assert abas_do_canal(1_000, 61, 99_999, OUTLIER_FATOR - 0.1, 0, False) == ["todos"]

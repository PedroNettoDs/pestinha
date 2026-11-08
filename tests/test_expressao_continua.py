"""
Rosto contínuo: a forma dos olhos segue (valência, ativação) do cérebro, misturando as predefinidas.

Só lógica pura, sem Qt.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402

from pestinha.core.emotion import ANCHORS, EYE_SHAPES, shape_from_affect  # noqa: E402


@pytest.mark.parametrize("emocao", list(ANCHORS))
def test_no_ponto_de_referencia_a_forma_e_a_predefinida(emocao):
    forma = shape_from_affect(*ANCHORS[emocao])
    for key, valor in EYE_SHAPES[emocao].items():
        assert forma[key] == pytest.approx(valor, rel=0.03, abs=0.05), (emocao, key)


def test_entre_duas_emocoes_a_forma_fica_no_meio():
    meio = shape_from_affect(0.0, 0.35)                 # entre observando e curioso
    lo, hi = EYE_SHAPES["observando"]["h"], EYE_SHAPES["curioso"]["h"]
    assert lo < meio["h"] < hi


def test_mais_triste_e_mais_fundo_que_so_triste():
    leve = shape_from_affect(-0.3, -0.1)["dy"]
    forte = shape_from_affect(-0.9, -0.6)["dy"]
    assert forte > leve > EYE_SHAPES["observando"]["dy"]


def test_forma_sempre_tem_todas_as_chaves():
    for v in (-1.0, -0.2, 0.0, 0.5, 1.0):
        for a in (-1.0, 0.0, 1.0):
            assert set(shape_from_affect(v, a)) == set(EYE_SHAPES["observando"])

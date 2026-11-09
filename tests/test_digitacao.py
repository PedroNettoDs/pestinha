"""
Balanço de digitação: só enquanto ele está sentado no notebook, pequeno e rítmico.
"""

import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.body.pet import TYPING_DEGREES, digitacao_graus  # noqa: E402


def test_parado_quando_nao_esta_sentado():
    assert all(digitacao_graus(False, t / 10) == 0.0 for t in range(50))


def test_balanca_pouco_e_nos_dois_lados_quando_senta():
    valores = [digitacao_graus(True, t / 100) for t in range(200)]
    assert max(valores) <= TYPING_DEGREES + 1e-9
    assert max(valores) > TYPING_DEGREES * 0.9          # chega perto do limite
    assert min(valores) < -TYPING_DEGREES * 0.9         # e vai para o outro lado


def test_e_periodico():
    assert math.isclose(digitacao_graus(True, 0.3), digitacao_graus(True, 0.3 + 1 / 2.4), abs_tol=1e-9)

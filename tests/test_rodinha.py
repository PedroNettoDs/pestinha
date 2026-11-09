"""
Rodinha do mouse: girar rápido deixa o pet tonto; girar devagar não.

Chama o tratador real com um corpo e estado de verdade, sem abrir janela.
"""

import sys
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.body.pet import WHEEL_DIZZY_OMEGA, PetWindow  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402


class _Roda:
    """Evento de rodinha: só o que o tratador lê."""
    def __init__(self, delta):
        self._delta = delta

    def angleDelta(self):
        return SimpleNamespace(y=lambda: self._delta)


def _pet(omega=0.0):
    body = Body(500.0, 500.0, 60.0, 45.0)
    body.omega = omega
    body.grounded = False                              # no ar: não entra no pulo
    return SimpleNamespace(state=PetState(), body=body, _held_angle=0.0)


def test_girar_devagar_nao_deixa_tonto():
    pet = _pet()
    PetWindow.wheelEvent(pet, _Roda(120))              # uma "pancada" de rodinha: 20 * 12 = 240 graus/s
    assert pet.state.dizzy(time.monotonic()) is False


def test_girar_rapido_deixa_tonto_por_um_instante():
    pet = _pet(omega=WHEEL_DIZZY_OMEGA)                # já girando forte: a próxima pancada passa do limite
    PetWindow.wheelEvent(pet, _Roda(120))
    assert pet.state.dizzy(time.monotonic()) is True
    assert pet.state.dizzy(time.monotonic() + 5.0) is False

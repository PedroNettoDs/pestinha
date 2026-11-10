"""
Antecipação do giro: antes de pular girando, ele se inclina para o lado oposto e só então pula.

Usa o corpo e o comportamento reais, sem Qt.
"""

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.body.behavior import SPIN_DEGREES, WINDUP_LEAN, WINDUP_SECONDS, Behavior  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402
from pestinha.core.physics import Body  # noqa: E402

PROF = {"roam_interval": (5.0, 6.0)}
BOUNDS = (0, 0, 1920, 1080)


def _cenario():
    body = Body(500.0, 900.0, 60.0, 45.0)
    body.grounded = True
    st = PetState()
    beh = Behavior(body, st, mischief=SimpleNamespace(things={}))
    return body, st, beh


def _rodar(beh, now, segundos, dt=0.05):
    for _ in range(int(segundos / dt)):
        now += dt
        beh.tick(dt, now, (0, 0), BOUNDS, PROF)
    return now


def test_preparo_inclina_para_o_lado_oposto_sem_pular():
    body, st, beh = _cenario()
    beh.windup = (0.0 + WINDUP_SECONDS, 1, 0.0, -300.0)
    _rodar(beh, 0.0, WINDUP_SECONDS / 2)
    assert beh.windup is not None                       # ainda preparando
    assert body.grounded and body.omega == 0.0          # não saiu do chão nem girou
    assert st.lean_target == -WINDUP_LEAN               # inclina para o lado oposto ao giro


def test_giro_so_sai_depois_do_preparo():
    body, st, beh = _cenario()
    beh.windup = (WINDUP_SECONDS, -1, 0.0, -300.0)
    _rodar(beh, 0.0, WINDUP_SECONDS + 0.2)
    assert beh.windup is None
    assert not body.grounded
    assert body.omega == -SPIN_DEGREES                  # o giro segue o sentido sorteado


def test_mudar_de_emocao_cancela_o_preparo():
    body, st, beh = _cenario()
    beh.windup = (WINDUP_SECONDS, 1, 0.0, -300.0)
    beh.emotion = "assustado"
    _rodar(beh, 0.0, 0.1)
    assert beh.windup is None
    assert body.grounded and body.omega == 0.0


def test_segurar_o_pet_cancela_o_preparo():
    body, st, beh = _cenario()
    beh.windup = (WINDUP_SECONDS, 1, 0.0, -300.0)
    body.held = True
    _rodar(beh, 0.0, 0.1)
    assert beh.windup is None
    assert st.lean_target == 0.0


def test_inclinacao_volta_ao_normal_depois_do_pulo():
    body, st, beh = _cenario()
    st.lean = WINDUP_LEAN
    st.lean_target = 0.0
    _rodar(beh, 0.0, 1.0)
    assert abs(st.lean) < 0.5

"""
Testes dos módulos puros: nada de Qt, nada de Windows.

Rodar (na pasta v7):  python -m pytest tests -q
"""

import math
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from pestinha.core.emotion import EmotionState, classify  # noqa: E402
from pestinha.core.homeostasis import Drives  # noqa: E402
from pestinha.core.motor import MotorTone  # noqa: E402
from pestinha.core.nervous_system import LIFBrain as _LIFBrain  # noqa: E402


def LIFBrain(seed=7, temperament=None):
    """Cérebro com ruído fixo: o teste é determinístico (o app usa ruído de verdade)."""
    brain = _LIFBrain(seed=seed, temperament=temperament)
    brain.rng = np.random.default_rng(123)
    return brain
from pestinha.core.physics import Body  # noqa: E402
from pestinha.body.behavior import Behavior, CROSS_SCREEN_SPEED  # noqa: E402
from pestinha.body.pet_state import PetState  # noqa: E402

PROFILE = {
    "emotion_tau": 1.5, "emotion_dwell": 0.6,
    "energy_span": 300.0, "sleep_recover": 60.0, "stim_decay": 40.0, "contact_span": 120.0,
    "grievance_up": 45.0, "grievance_down": 240.0,
}


# ---------------- emoção ----------------

@pytest.mark.parametrize("valence, arousal, expected", [
    (-0.5, 0.5, "bravo"),
    (-0.5, 0.0, "triste"),
    (0.6, 0.6, "feliz"),
    (0.6, 0.0, "contente"),
    (0.0, 0.6, "curioso"),
    (0.0, 0.0, "observando"),
])
def test_classify_cobre_os_quadrantes(valence, arousal, expected):
    assert classify(valence, arousal) == expected


def test_forcar_emocao_vale_so_pelo_tempo_dado():
    e = EmotionState()
    e.force("assustado", 1.0, now=10.0)
    assert e.update({}, 0.1, PROFILE, now=10.5) == "assustado"
    assert e.update({}, 0.1, PROFILE, now=11.5) != "assustado"


def test_susto_dispara_na_subida_e_nao_repete_sem_esfriar():
    e = EmotionState()
    e.update({"STARTLE": 9.0}, 0.1, PROFILE, now=0.0)
    assert e.override == "assustado"
    e.override = None
    e.update({"STARTLE": 9.0}, 0.1, PROFILE, now=0.2)
    assert e.override is None           # ainda alto: não rearma


# ---------------- motor ----------------

def test_motor_quieto_nao_move():
    t = MotorTone()
    for _ in range(50):
        t.update({}, 0.1)
    assert t.speed() == pytest.approx(20.0, abs=0.5)
    assert t.hop_chance() < 0.1


def test_cheer_e_settle_tambem_movem_o_corpo():
    t = MotorTone()
    for _ in range(50):
        t.update({"CHEER": 8.0}, 0.1)
    fast = t.speed()
    t2 = MotorTone()
    for _ in range(50):
        t2.update({"SETTLE": 4.0}, 0.1)
    assert fast > t2.speed() > 20.0


def test_sono_deixa_tudo_mais_lento():
    awake, asleep = MotorTone(), MotorTone()
    for _ in range(50):
        awake.update({"WANDER": 6.0}, 0.1)
        asleep.update({"WANDER": 6.0, "DROWSE": 8.0}, 0.1)
    assert asleep.speed() < awake.speed()


# ---------------- homeostase ----------------

def test_energia_cai_acordado_e_sobe_dormindo():
    d = Drives()
    for _ in range(100):
        d.update(0.1, PROFILE, asleep=False, moving=0.0, arousal=0.0, user_away=False)
    gasta = d.energy
    assert gasta < 1.0
    for _ in range(100):
        d.update(0.1, PROFILE, asleep=True, moving=0.0, arousal=0.0, user_away=False)
    assert d.energy > gasta


def test_canais_internos_respondem_ao_desequilibrio():
    d = Drives()
    d.stimulation = 0.0
    d.contact = 1.0
    d.energy = 0.1
    ch = d.channels()
    assert ch["BOREDOM"] > 0.9 and ch["LONELY"] > 0.9 and ch["FATIGUE"] > 0.5


def test_sonolento_abaixo_do_limite():
    d = Drives()
    d.energy = 0.1
    assert d.sleepy()


# ---------------- física ----------------

def test_corpo_cai_e_para_no_chao():
    b = Body(300.0, 0.0, 60.0, 45.0)
    for _ in range(600):
        b.step(1 / 60, (0, 0, 1000, 800), [])
    assert b.grounded
    assert b.y + b.extents()[1] == pytest.approx(800.0, abs=1.0)


def test_corpo_pousa_na_barra_de_titulo_de_uma_janela():
    b = Body(300.0, 100.0, 60.0, 45.0)
    platforms = [(42, 100.0, 600.0, 400.0)]
    for _ in range(600):
        b.step(1 / 60, (0, 0, 1000, 800), platforms)
        if b.grounded:
            break
    assert b.grounded and b.platform == 42
    assert b.y + b.extents()[1] == pytest.approx(400.0, abs=1.0)


def test_batida_forte_na_parede_entra_em_impactos():
    b = Body(64.0, 300.0, 60.0, 45.0)     # encostado na parede esquerda
    b.vx = -2000.0
    b.step(1 / 60, (0, 0, 1000, 800), [])
    impacts = b.pop_impacts()
    assert impacts and max(impacts) >= 1500
    assert b.pop_impacts() == []          # lidas uma vez só


def test_corpo_passa_para_monitor_ao_lado():
    areas = [(0, 0, 1000, 800), (1000, 0, 2000, 800)]
    b = Body(930.0, 300.0, 60.0, 45.0)
    b.vx = 800.0
    for _ in range(8):
        atual = areas[0] if b.x < 1000 else areas[1]
        b.step(1 / 30, atual, [], areas)
    assert b.x > 1000 and b.vx > 0


def test_corpo_nao_atravessa_vao_entre_monitores():
    areas = [(0, 0, 1000, 800), (1100, 0, 2100, 800)]
    b = Body(930.0, 300.0, 60.0, 45.0)
    b.vx = 800.0
    b.step(1 / 30, areas[0], [], areas)
    assert b.x <= 940 and b.vx < 0


def test_corpo_cai_para_monitor_abaixo():
    areas = [(0, 0, 1000, 800), (0, 800, 1000, 1600)]
    b = Body(300.0, 730.0, 60.0, 45.0)
    b.vy = 600.0
    for _ in range(8):
        atual = areas[0] if b.y < 800 else areas[1]
        b.step(1 / 30, atual, [], areas)
    assert b.y > 800 and not b.grounded


def test_barra_de_tarefas_nao_esconde_monitor_abaixo():
    areas = [(0, 0, 1000, 750), (0, 800, 1000, 1600)]
    monitores = [(0, 0, 1000, 800), (0, 800, 1000, 1600)]
    b = Body(300.0, 690.0, 60.0, 45.0)
    b.vy = 600.0
    b.step(1 / 30, areas[0], [], areas, monitores)
    assert not b.grounded and b.vy > 0


def test_desalinhamento_vertical_nao_prende_na_divisao():
    areas = [(0, 0, 1920, 1032), (1920, 5, 3840, 1037)]
    monitores = [(0, 0, 1920, 1080), (1920, 5, 3840, 1085)]
    b = Body(1922.0, 987.0, 60.0, 45.0)
    b.angle = 0.2                         # inclinação mínima já aumentava a caixa de colisão
    b.vx = 180.0

    b.step(1 / 60, areas[1], [], areas, monitores)

    assert 1922 < b.x < 1930              # não foi encaixado em left + largura (≈ 1980)
    assert b.vx > 0


def test_passeio_pode_escolher_destino_no_monitor_ao_lado(monkeypatch):
    body = Body(930.0, 700.0, 60.0, 45.0)
    state = SimpleNamespace(tone=SimpleNamespace(drive=lambda: 1.0), protest_stage=0)
    behavior = Behavior(body, state, None)
    behavior.emotion = "feliz"
    behavior.screen_areas = [(0, 0, 1000, 800), (1000, 0, 2000, 800)]
    monkeypatch.setattr("pestinha.body.behavior.random.uniform", lambda _a, b: b)

    assert behavior._pick_target((0, 0), 0, 1000) > 1000


def test_passeio_decide_visitar_monitor_vizinho(monkeypatch):
    body = Body(300.0, 700.0, 60.0, 45.0)
    state = SimpleNamespace(tone=SimpleNamespace(drive=lambda: 1.0), protest_stage=0)
    behavior = Behavior(body, state, None)
    behavior.emotion = "feliz"
    behavior.screen_areas = [(0, 0, 1000, 800), (1000, 0, 2000, 800)]
    monkeypatch.setattr("pestinha.body.behavior.random.random", lambda: 0.0)
    monkeypatch.setattr("pestinha.body.behavior.random.choice", lambda itens: itens[0])
    monkeypatch.setattr("pestinha.body.behavior.random.uniform", lambda a, b: (a + b) / 2)

    assert behavior._pick_target((0, 0), 0, 1000) == 1500


def test_travessia_nao_hesita_nem_troca_de_destino(monkeypatch):
    body = Body(930.0, 700.0, 60.0, 45.0)
    body.grounded = True
    state = PetState()
    state.tone = SimpleNamespace(speed=lambda: 20.0, hesitation=lambda: 1.0, shake=lambda: 0.0)
    behavior = Behavior(body, state, None)
    behavior.target_x = 1500.0
    behavior.crossing_screen = True
    behavior.next_roam = 0.0
    behavior.next_glance = 1e9
    velocidades = []
    monkeypatch.setattr(behavior, "_slide_to", lambda alvo, velocidade: velocidades.append((alvo, velocidade)))
    monkeypatch.setattr("pestinha.body.behavior.random.random", lambda: 0.0)

    behavior.tick(1.0, 100.0, (0, 0), (0, 0, 1000, 800), {})

    assert behavior.target_x == 1500.0
    assert behavior.crossing_screen is True
    assert velocidades == [(1500.0, CROSS_SCREEN_SPEED)]


# ---------------- rede neural ----------------

def test_rede_responde_a_estimulo_e_relaxa():
    brain = LIFBrain(seed=7)
    for _ in range(20):
        brain.stimulate({})
        brain.step(100)
    base = brain.motor_activity()["STARTLE"]
    for _ in range(20):
        brain.stimulate({"MOTION": 1.0})
        brain.step(100)
    assert brain.motor_activity()["STARTLE"] > base


def test_habituacao_enfraquece_a_cutucada():
    """Média de 5 sequências de ruído: uma só pode cair num caso ruim."""
    razoes = []
    for semente in range(1, 6):
        brain = LIFBrain(seed=7)
        brain.rng = np.random.default_rng(semente)
        for _ in range(20):
            brain.stimulate({})
            brain.step(100)
        first = None
        for n in range(12):
            before = brain.motor_activity()["CHEER"]
            for i in range(5):
                brain.stimulate({"POKE": 0.8 * math.exp(-i * 0.1 / 1.5)})
                brain.step(100)
            gain = brain.motor_activity()["CHEER"] - before
            first = gain if first is None else first
            for _ in range(15):
                brain.stimulate({})
                brain.step(100)
        razoes.append(gain / first)
    assert sum(razoes) / len(razoes) < 0.6      # antes da rede de decisões era ~0,4; a cutucada ainda cai pela metade

def test_mesma_semente_mesmo_cerebro(tmp_path):
    a, b = LIFBrain(seed=7), LIFBrain(seed=7)
    assert a.n_synapses == b.n_synapses
    assert (a.W == b.W).all()


def test_aprendizado_persiste_entre_saves(tmp_path):
    path = tmp_path / "estado.json"
    brain = LIFBrain(seed=7)
    for _ in range(60):
        brain.stimulate({"WEB": 1.0, "CARESS": 1.0})
        brain.step(100)
        brain.learn(1.0, 0.1, 0.004)
    brain.save(str(path))
    again = LIFBrain(seed=7)
    assert again.load(str(path))
    assert abs(again.learned - brain.learned).max() < 1e-5


def test_temperamento_muda_a_resposta():
    neutro, curioso = LIFBrain(seed=7), LIFBrain(seed=7, temperament={"CURIOUS": 2.0})
    for brain in (neutro, curioso):
        for _ in range(20):
            brain.stimulate({})
            brain.step(100)
        for _ in range(30):
            brain.stimulate({"NOVELTY": 1.0})
            brain.step(100)
    assert curioso.motor_activity()["WANDER"] > neutro.motor_activity()["WANDER"]

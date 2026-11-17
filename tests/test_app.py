"""
Testes de integração do app, com Qt em modo offscreen e tudo numa pasta temporária.

Nada aqui grava na sua pasta memory/: cada teste usa um Paths apontando para
tmp_path. Rodar (na pasta v7):  python -m pytest tests -q
"""

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402
from main import apagar_memoria  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication([])
    app.setQuitOnLastWindowClosed(False)
    return app


@pytest.fixture
def buddy(qapp, tmp_path):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, travessuras=True))
    app = PestinhaApp(store, paths)
    yield app
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()
    app.mischief.clear()
    app.tray.icon.hide()


def test_permissoes_voltam_como_foram_deixadas(tmp_path):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update({"memes": False, "fotos": True})
    again = SettingsStore(paths)
    assert again["memes"] is False and again["fotos"] is True


def test_panico_fica_desligado_ao_reabrir(tmp_path):
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.panic()
    assert SettingsStore(paths)["ativo"] is False


def test_apagar_memoria_confirma_que_a_pasta_sumiu(tmp_path):
    paths = Paths(root=tmp_path)
    paths.memory.mkdir()
    (paths.memory / "dado.json").write_text("{}", encoding="utf-8")

    sucesso, falhas = apagar_memoria(paths)

    assert sucesso is True
    assert falhas == []
    assert not paths.memory.exists()


def test_apagar_memoria_informa_falha_sem_fingir_sucesso(tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    paths.memory.mkdir()

    def falhar(_path, **callback):
        (avisar,) = callback.values()      # onexc (3.12+) ou onerror (3.11)
        avisar(None, paths.memory / "bloqueado.json", None)

    monkeypatch.setattr("pestinha.store.shutil.rmtree", falhar)
    sucesso, falhas = apagar_memoria(paths)

    assert sucesso is False
    assert falhas == [str(paths.memory / "bloqueado.json")]
    assert paths.memory.exists()


def test_modo_teste_mostra_os_paineis(buddy):
    buddy.apply_perms(dict(buddy.perms, modo_teste=True, ativo=True))
    assert buddy.floats.windows.get("neural") is not None
    assert buddy.floats.windows["neural"].isVisible()
    assert buddy.floats.windows["greve"].isVisible()
    buddy.apply_perms(dict(buddy.perms, modo_teste=False))
    assert not buddy.floats.windows["neural"].isVisible()


def test_painel_arrastado_salva_a_posicao(buddy, tmp_path):
    buddy.apply_perms(dict(buddy.perms, modo_teste=True, ativo=True))
    w = buddy.floats.windows["greve"]
    start = QPointF(w.mapToGlobal(w.rect().center()))
    end = start + QPointF(-120, 80)

    def ev(kind, p):
        return QMouseEvent(kind, p, p, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)

    w.mousePressEvent(ev(QMouseEvent.MouseButtonPress, start))
    w.mouseMoveEvent(ev(QMouseEvent.MouseMove, end))
    w.mouseReleaseEvent(ev(QMouseEvent.MouseButtonRelease, end))
    saved = buddy.paths.panels
    assert saved.exists()
    from pestinha.world.arrastavel import load_positions  # noqa: E402
    assert load_positions(saved)["greve"] == [w.x(), w.y()]


def test_painel_nao_entra_na_lista_de_pouso(buddy):
    buddy.apply_perms(dict(buddy.perms, modo_teste=True, ativo=True))
    buddy.floats.windows["greve"].move(100, 100)
    buddy.floats.windows["neural"].move(100, 500)
    handles = {int(w.winId()) for w in buddy.floats.windows.values()}
    buddy.scan_windows()
    assert not [p for p in buddy.platforms if p[0] in handles]


def test_protesto_sobe_e_o_carinho_leva_ao_acordo(buddy):
    buddy.apply_perms(dict(buddy.perms, modo_teste=True))   # tempos curtos do teste
    pr = buddy.protest
    pr.grievance = 0.8
    t = 0.0
    while pr.stage < 3 and t < 200:                        # um estágio por vez, com tempo em cada um
        change = buddy.protest_ctl.tick(0.1, buddy.pet_state.tone, buddy.prof, False, t)
        if change:
            buddy.protest_ctl.on_stage(*change)
        t += 0.1
    assert pr.stage == 3                                    # greve
    buddy.protest_ctl.carry(pr.respawn_at + 1.0, asleep=False)   # o cartaz sobe no próximo quadro
    assert pr.sign is not None

    pr.last_caress = 1e18
    buddy.protest_ctl.on_stage(3, 0)                       # volta a zero por carinho
    assert pr.sign is not None and pr.sign.text == "ACORDO FECHADO"


def test_repressao_aumenta_a_insatisfacao(buddy):
    pr = buddy.protest
    pr.grievance = 0.3
    pr.stage = 2
    buddy.protest_ctl.on_stage(1, 2)
    sign = pr.sign
    before = pr.grievance
    buddy.protest_ctl.on_sign_clicked(sign)
    assert pr.grievance > before and pr.repressions == 1


def test_dorme_pela_energia_e_nao_acorda_sozinho(buddy):
    body = buddy.pet.body
    body.grounded = True
    body.held = False
    buddy.drives.energy = 0.1
    buddy.sleep.tick(0.0, body, False, 0, None)
    assert buddy.sleep.asleep
    buddy.drives.energy = 1.0
    buddy.sleep.tick(0.0, body, False, 0, None)
    assert buddy.sleep.asleep                               # descansado, continua dormindo
    buddy.sleep.wake(startled=False)                        # o post-it do Alfred (ou a sua mão) acorda
    assert not buddy.sleep.asleep


def test_dormindo_nao_apronta(buddy):
    assert buddy.mischief_ctl.engine.available("dormindo", buddy.perms) == []
    assert buddy.mischief_ctl.engine.available("triste", buddy.perms) == []


def test_cutucada_habitua_na_rede(buddy):
    before = buddy.brain.efficacy()["POKE"]
    for _ in range(5):
        buddy.brain.stimulate({"POKE": 0.8})
        buddy.brain.step(100)
    assert buddy.brain.efficacy()["POKE"] < before


def test_madrugada_sem_trabalho_do_alfred_ele_dorme_descansado(buddy):
    body = buddy.pet.body
    body.grounded, body.held = True, False
    buddy.drives.energy = 1.0
    buddy.sleep.tick(0.0, body, False, 0, None, noite=True)
    assert buddy.sleep.asleep                               # dorme mesmo sem cansaço
    buddy.sleep.tick(1.0, body, False, 0, None, noite=True)
    assert buddy.sleep.asleep                               # e não acorda por estar descansado
    buddy.sleep.tick(2.0, body, False, 0, None, noite=False)
    assert buddy.sleep.asleep                               # amanheceu: continua, até um post-it ou a sua mão


def test_uma_hora_sem_mexer_no_computador_ele_dorme(buddy, monkeypatch):
    from pestinha.ajustes import OCIOSO_PARA_DORMIR
    body = buddy.pet.body
    body.grounded, body.held = True, False
    buddy.drives.energy = 1.0
    monkeypatch.setattr("pestinha.app.noite_de_sono", lambda estado: False)
    monkeypatch.setattr("pestinha.app.senses.get_idle_seconds", lambda: OCIOSO_PARA_DORMIR - 1)
    buddy.think()
    assert not buddy.sleep.asleep
    monkeypatch.setattr("pestinha.app.senses.get_idle_seconds", lambda: OCIOSO_PARA_DORMIR)
    buddy.think()
    assert buddy.sleep.asleep
    monkeypatch.setattr("pestinha.app.senses.get_idle_seconds", lambda: 0.0)
    buddy.think()
    assert buddy.sleep.asleep                               # você voltou: ele não acorda por isso


def test_acordado_no_susto_de_madrugada_fica_um_tempo_de_pe(buddy):
    from pestinha.ajustes import VIGILIA_APOS_SUSTO
    body = buddy.pet.body
    body.grounded, body.held = True, False
    buddy.drives.energy = 1.0
    buddy.sleep.tick(0.0, body, False, 0, None, noite=True)
    buddy.sleep.wake(startled=True)
    buddy.emotion.override = None                           # o susto já passou
    buddy.sleep.tick(1.0, body, False, 0, None, noite=True)
    assert not buddy.sleep.asleep
    buddy.sleep.tick(2.0 + VIGILIA_APOS_SUSTO, body, False, 0, None, noite=True)
    assert buddy.sleep.asleep


def test_madrugada_so_vale_no_horario_e_com_o_alfred_parado():
    from pestinha.mind.sleep import noite_de_sono
    from pestinha.sense.alfred import Estado
    parado, ocupado = Estado(online=True), Estado(online=True, fila=({"id": "f", "tipo": "backup", "rotulo": "B"},))
    assert noite_de_sono(parado, hora=3)
    assert noite_de_sono(Estado(), hora=3)                  # Alfred fora do ar: ninguém chama
    assert not noite_de_sono(parado, hora=14)
    assert not noite_de_sono(ocupado, hora=3)
    assert not noite_de_sono(Estado(online=True, agora=({"id": "a", "tipo": "email"},)), hora=3)


def test_dormindo_a_carencia_e_a_tristeza_nao_crescem(buddy):
    buddy.drives.contact = 0.5
    buddy.drives.update(60.0, buddy.prof, True, 0.0, 0.0, False)
    assert buddy.drives.contact == 0.5
    buddy.sad.grievance = 0.1
    buddy.pet_state.tone.r["SAD"] = 8.0
    buddy.sad_ctl.tick(1.0, buddy.pet_state.tone, buddy.prof, False, 0.0, 1.0, dormindo=True)
    assert buddy.sad.grievance <= 0.1

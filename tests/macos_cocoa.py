"""
MACOS COCOA - roda em outro processo, com o Qt no Cocoa de verdade, para o test_macos_real.py.

    python tests/macos_cocoa.py sem_app | janelas | atalho

Cada modo imprime um JSON na última linha. Fica num processo à parte porque o conftest liga o Qt em
modo offscreen, e um ponteiro errado aqui derrubaria o pytest inteiro em vez de falhar um teste.
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LIMITE = 5.0        # segundos para o macOS trocar o foco ou esconder uma janela


def sem_app():
    """sem_foco_nativo com um id qualquer e sem QApplication: o id não pode virar ponteiro."""
    from pestinha.plataforma import macos
    macos.sem_foco_nativo(12345)
    return {"sobreviveu": True}


def _esperar(app, condicao, limite=LIMITE):
    """Roda o laço de eventos até `condicao()` valer ou o tempo acabar; devolve o último valor."""
    fim = time.monotonic() + limite
    while not condicao() and time.monotonic() < fim:
        app.processEvents()
        time.sleep(0.02)
    return condicao()


def _outro_programa(anterior):
    """O programa que recebe o foco no fim: o que estava na frente antes do teste, ou o Finder."""
    from AppKit import NSRunningApplication
    if anterior is not None and anterior.processIdentifier() != os.getpid():
        return anterior
    finder = NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.apple.finder")
    return finder[0] if finder else None


def janelas():
    """Mostra as janelas do pet e uma Qt.Tool sem o ajuste, tira o foco do programa e vê o que ficou na tela."""
    from AppKit import NSWorkspace
    anterior = NSWorkspace.sharedWorkspace().frontmostApplication()    # antes do Qt trazer este processo para a frente

    from PySide6.QtWidgets import QApplication, QWidget
    app = QApplication([])

    import objc
    import Quartz
    from AppKit import NSApplication, NSPanel
    from pestinha.body.bolinha import Ball
    from pestinha.body.pet import PetWindow, overlay_flags
    from pestinha.body.pet_state import PetState
    from pestinha.plataforma import macos
    from pestinha.world.arrastavel import FloatingWidget
    from pestinha.world.fireworks import Fireworks
    from pestinha.world.objetos import Thing

    painel_app = SimpleNamespace(paths=SimpleNamespace(panels=Path(tempfile.mkdtemp()) / "panels.json"))
    sem_ajuste = QWidget(None, overlay_flags())     # a Qt.Tool pura, sem o set_no_activate do showEvent
    sem_ajuste.resize(40, 40)
    criadas = {
        "sem_ajuste": sem_ajuste,
        "pet": PetWindow(0, 0, PetState()),
        "bolinha": Ball(0, 0),
        "objeto": Thing(60, 40),
        "fogos": Fireworks(),
        "painel": FloatingWidget(painel_app, "teste", "Painel de teste", (160, 100), (80, 60), (0, 0)),
    }
    tela = app.primaryScreen().availableGeometry()
    for ordem, janela in enumerate(criadas.values()):
        janela.move(tela.x() + 10 + ordem * 50, tela.y() + 10 + ordem * 30)
        janela.show()

    nativas = {nome: objc.objc_object(c_void_p=int(janela.winId())).window() for nome, janela in criadas.items()}

    def na_tela():
        """Números das janelas que o servidor de janelas está mostrando agora (o isVisible não muda ao esconder)."""
        lista = Quartz.CGWindowListCopyWindowInfo(Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID)
        return {int(j["kCGWindowNumber"]) for j in lista or []}

    numeros = {nome: int(nativa.windowNumber()) for nome, nativa in nativas.items()}

    # Capture o estado inicial apenas depois de ativar o app e esperar o WindowServer publicar as janelas.
    # Antes disso, o NSPanel sem ajuste pode ainda não aparecer na lista OnScreenOnly, causando um falso
    # negativo em `na_tela_antes` mesmo que a janela apareça corretamente quando o app ganha o foco.
    nsapp = NSApplication.sharedApplication()
    nsapp.activateIgnoringOtherApps_(True)
    ativou = _esperar(app, nsapp.isActive)
    _esperar(app, lambda: set(numeros.values()) <= na_tela())
    antes = na_tela()
    proprias = [j for j, _rect, _max in macos.janelas_visiveis(set()) if j in numeros.values()]

    outro = _outro_programa(anterior)
    if ativou and outro is not None:
        if nsapp.respondsToSelector_("yieldActivationToApplication:"):     # macOS 14+: ativação cooperativa
            nsapp.yieldActivationToApplication_(outro)
        outro.activateWithOptions_(0)
    desativou = ativou and outro is not None and _esperar(app, lambda: not nsapp.isActive())
    if desativou:
        _esperar(app, lambda: numeros["sem_ajuste"] not in na_tela())   # o AppKit esconde logo depois
    depois = na_tela()

    return {
        "ativou": bool(ativou),
        "desativou": bool(desativou),
        "proprias_em_janelas_visiveis": proprias,
        "janelas": {
            nome: {
                "painel": bool(nativa.isKindOfClass_(NSPanel)),
                "some_ao_desativar": bool(nativa.hidesOnDeactivate()),
                "mascara": int(nativa.styleMask()),
                "comportamento": int(nativa.collectionBehavior()),
                "na_tela_antes": numeros[nome] in antes,
                "na_tela_depois": numeros[nome] in depois,
            }
            for nome, nativa in nativas.items()
        },
    }


def atalho():
    """Registra o atalho de pânico de verdade: fora da thread principal recusa, nela registra, e sai limpo."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication
    app = QApplication([])
    from pestinha.plataforma import macos

    fora = []
    thread = threading.Thread(target=lambda: fora.append(macos.iniciar_atalho(lambda: None)))
    thread.start()
    thread.join()
    registrou = macos.iniciar_atalho(lambda: None)
    de_novo = macos.iniciar_atalho(lambda: None)
    QTimer.singleShot(200, app.quit)
    app.exec()                          # ao sair, o aboutToQuit desregistra o atalho
    return {"plataforma": app.platformName(), "fora_da_thread_principal": fora[0],
            "registrou": registrou, "de_novo": de_novo}


MODOS = {"sem_app": sem_app, "janelas": janelas, "atalho": atalho}

if __name__ == "__main__":
    print(json.dumps(MODOS[sys.argv[1]]()), flush=True)

"""
Plataforma: cada sistema expõe as mesmas funções, e as leituras de texto (wmctrl, xdotool, ioreg,
janelas do Quartz) são testadas com saídas de exemplo, em qualquer sistema.

O caminho real do macOS é testado num Mac de verdade em test_macos_real.py. O do Linux ainda precisa
ser testado numa máquina de verdade (ver README).
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha import plataforma  # noqa: E402
from pestinha.plataforma import linux  # noqa: E402
from pestinha.sense.senses import detect_activity  # noqa: E402

# Backends nativos só podem ser importados no seu próprio sistema.
# Isso evita carregar pywin32 no macOS e QuickMacHotKey no Windows/Linux.
macos = None
windows = None
kwin = None
if sys.platform.startswith("linux"):
    from pestinha.plataforma import kwin  # noqa: E402  (QtDBus)
if sys.platform == "darwin":
    from pestinha.plataforma import macos  # noqa: E402
elif sys.platform == "win32":
    from pestinha.plataforma import windows  # noqa: E402

FUNCOES = ["ocioso_segundos", "processo_ativo", "retangulo_ativo", "tela_cheia",
           "janelas_visiveis", "sem_foco_nativo", "iniciar_atalho"]


def test_cada_sistema_expoe_as_mesmas_funcoes():
    modulos = [linux] + ([kwin] if kwin is not None else [])
    if macos is not None:
        modulos.append(macos)
    if windows is not None:
        modulos.append(windows)

    for modulo in modulos:
        for nome in FUNCOES:
            assert callable(getattr(modulo, nome)), (modulo.__name__, nome)


def test_a_plataforma_escolhida_e_a_do_sistema_atual():
    kde_wayland = (os.environ.get("XDG_SESSION_TYPE") == "wayland"
                   and "KDE" in os.environ.get("XDG_CURRENT_DESKTOP", ""))
    esperado = {"win32": windows, "darwin": macos}.get(sys.platform, kwin if kde_wayland else linux)
    assert plataforma._backend is esperado


def test_geometria_do_xdotool():
    texto = "WINDOW=12345\nX=100\nY=50\nWIDTH=800\nHEIGHT=600\nSCREEN=0\n"
    assert linux.parse_geometria(texto) == (100, 50, 900, 650)
    assert linux.parse_geometria("") is None
    assert linux.parse_geometria("X=abc\nY=1\nWIDTH=2\nHEIGHT=3") is None


def test_wmctrl_pula_o_proprio_pet_pequenas_e_excluidas():
    saida = "\n".join([
        "0x01a00003  0 2222  10 20 1280 720 host Tela de um documento privado",
        "0x01b00004  0 4444  0 0 1920 1080 host Pestinha (o próprio pet)",
        "0x01c00005  0 3333  0 0 80 40 host janelinha pequena",
        "0x01d00006  0 5555  30 40 500 300 host Terminal - bash",
        "0x01e00007  0 6666  0 0 900 700 host excluída pelo app",
    ])
    achadas = linux.parse_wmctrl(saida, meu_pid=4444, excluir={0x01e00007})
    assert achadas == [
        (0x01a00003, (10, 20, 1290, 740), False),
        (0x01d00006, (30, 40, 530, 340), False),
    ]


def test_wmctrl_nao_guarda_titulo():
    achadas = linux.parse_wmctrl("0x01a00003  0 2222  10 20 500 300 host Senha do banco", 1, set())
    assert achadas == [(0x01a00003, (10, 20, 510, 320), False)]
    assert "Senha" not in repr(achadas)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_ioreg_converte_nanossegundos():
    texto = '  | |   "HIDIdleTime" = 2500000000\n  | |   "outra" = 5'
    assert macos is not None
    assert macos.ocioso_do_ioreg(texto) == 2.5
    assert macos.ocioso_do_ioreg("sem a chave") == 0.0


def _janela(pid, x, y, w, h, camada=0, janela_id=1):
    return {"kCGWindowOwnerPID": pid, "kCGWindowLayer": camada, "kCGWindowNumber": janela_id,
            "kCGWindowBounds": {"X": x, "Y": y, "Width": w, "Height": h}}


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_quartz_janela_da_frente_e_do_programa_ativo():
    janelas = [
        _janela(10, 0, 0, 30, 20, janela_id=1),          # menu, pequeno: ignorado
        _janela(20, 100, 100, 800, 600, janela_id=2),    # programa ativo, a de cima
        _janela(20, 50, 50, 900, 700, janela_id=3),
    ]
    assert macos is not None
    assert macos.janela_da_frente(janelas, pid=20) == (100, 100, 900, 700)
    assert macos.janela_da_frente(janelas, pid=99) is None


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_quartz_ignora_camadas_e_o_proprio_pet():
    janelas = [
        _janela(7, 0, 0, 1440, 900, janela_id=1),                 # o próprio pet
        _janela(8, 0, 0, 1440, 40, janela_id=2),                  # barra de menu (camada alta)
        _janela(9, 200, 150, 600, 400, janela_id=3),
    ]
    janelas[1]["kCGWindowLayer"] = 25
    assert macos is not None
    achadas = macos.janelas_de(janelas, meu_pid=7, excluir={99}, escala=2.0)
    assert achadas == [(3, (400.0, 300.0, 1600.0, 1100.0), False)]


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_tela_cheia_no_mac_compara_com_a_tela():
    assert macos is not None
    assert macos._cobre((0, 0, 1440, 900), (0, 0, 1440, 900)) is True
    assert macos._cobre((100, 0, 1440, 900), (0, 0, 1440, 900)) is False


@pytest.mark.skipif(sys.platform != "darwin", reason="Requer backend macOS")
def test_atalho_do_mac_usa_control_option_shift(monkeypatch):
    """O atalho registrado deve ser o mesmo Ctrl+Alt/Option+Shift+B mostrado na interface."""
    assert macos is not None
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    assert app is not None
    capturado = {}

    class Atalho:
        def unregister(self):
            pass

    def quick_hot_key(**kwargs):
        capturado.update(kwargs)
        return lambda _callback: Atalho()

    monkeypatch.setattr(macos, "_hotkey", None)
    monkeypatch.setattr(macos, "quickHotKey", quick_hot_key)
    assert macos.iniciar_atalho(lambda: None) is True
    assert capturado == {
        "virtualKey": macos.kVK_ANSI_B,
        "modifierMask": macos.mask(macos.controlKey, macos.optionKey, macos.shiftKey),
    }


def test_atividade_reconhece_nomes_de_todos_os_sistemas():
    assert detect_activity("code.exe", 0.0, 300.0) == "PROGRAMMING"        # Windows
    assert detect_activity("code", 0.0, 300.0) == "PROGRAMMING"            # Linux
    assert detect_activity("Visual Studio Code", 0.0, 300.0) == "PROGRAMMING"   # macOS
    assert detect_activity("Google Chrome", 0.0, 300.0) == "BROWSING"
    assert detect_activity("Discord.exe", 0.0, 300.0) == "SOCIAL"
    assert detect_activity("Spotify", 0.0, 300.0) == "MUSIC"
    assert detect_activity("programa-desconhecido", 0.0, 300.0) == "IDLE"
    assert detect_activity("code", 400.0, 300.0) == "AWAY"


@pytest.mark.skipif(kwin is None, reason="Requer Linux (QtDBus)")
def test_ponte_do_kwin_le_janelas_e_ativa():
    texto = ('{"janelas": [{"id": "{a}", "pid": 10, "x": 0, "y": 0, "w": 800, "h": 600, "max": true,'
             ' "caption": "Senha do banco"}], "ativa": {"id": "{a}", "pid": 10, "x": 0, "y": 0, "w": 800,'
             ' "h": 600, "cheia": true}}')
    janelas, ativa = kwin.parse_estado(texto)
    assert janelas == [{"id": "{a}", "pid": 10, "ret": (0.0, 0.0, 800.0, 600.0), "max": True, "cheia": False}]
    assert ativa["cheia"] is True and ativa["pid"] == 10
    assert "Senha" not in repr(janelas)                 # título nunca é guardado


@pytest.mark.skipif(kwin is None, reason="Requer Linux (QtDBus)")
def test_ponte_do_kwin_descarta_o_que_vier_malformado():
    assert kwin.parse_estado(None) == ([], None)
    assert kwin.parse_estado("não é json") == ([], None)
    assert kwin.parse_estado("[1, 2]") == ([], None)
    ruins = ('{"janelas": [{"pid": 1, "x": NaN, "y": 0, "w": 9, "h": 9}, {"pid": "x"}, 7, "a",'
             ' {"pid": 1, "x": 0, "y": 0, "w": -5, "h": 9}], "ativa": 3}')
    assert kwin.parse_estado(ruins) == ([], None)
    assert kwin.parse_cursor("[10, 20.5]") == (10.0, 20.5)
    assert kwin.parse_cursor("[Infinity, 1]") is None
    assert kwin.parse_cursor('"oi"') is None


@pytest.mark.skipif(kwin is None, reason="Requer Linux (QtDBus)")
def test_tempo_ocioso_do_wayland_soma_o_limiar():
    assert kwin.segundos_ocioso(None, 100.0) == 0.0
    assert kwin.segundos_ocioso(40.0, 100.0) == 60.0 + kwin.LIMIAR_OCIOSO


def test_no_wayland_nativo_o_app_avisa_e_nao_abre(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from PySide6.QtWidgets import QApplication
    from pestinha.paths import Paths
    QApplication.instance() or QApplication([])      # face_icon() precisa de um app de verdade
    import main as main_mod
    avisos, abriu = [], []
    monkeypatch.setattr(main_mod, "QApplication", lambda argv: SimpleNamespace(
        setQuitOnLastWindowClosed=lambda v: None, setWindowIcon=lambda i: None, exec=lambda: 0,
        platformName=lambda: "wayland"))
    monkeypatch.setattr(main_mod, "Paths", lambda: Paths(root=tmp_path))
    monkeypatch.setattr(main_mod.QMessageBox, "critical", lambda *a: avisos.append(a[2]))
    monkeypatch.setattr(main_mod, "PestinhaApp", lambda *a: abriu.append(True))
    monkeypatch.setattr(sys, "argv", ["main.py", "--direto"])
    assert main_mod.main() == 1
    assert abriu == [] and "XWayland" in avisos[0]


def _bruta(janela_id, **campos):
    base = {"id": janela_id, "pid": 2222, "area": 0, "tipo": "_NET_WM_WINDOW_TYPE_NORMAL", "estados": [],
            "x": 100, "y": 200, "largura": 800, "altura": 600, "moldura": (0, 0, 0, 0), "sombra": (0, 0, 0, 0)}
    return {**base, **campos}


def test_x11_so_o_que_esta_na_tela_na_ordem_e_com_a_barra_de_titulo():
    brutas = [
        _bruta(1, moldura=(0, 0, 28, 0)),                                   # barra do gerenciador: o topo sobe 28
        _bruta(2, sombra=(16, 16, 10, 32)),                                 # barra própria (GTK): tira a sombra
        _bruta(3, estados=["_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ"]),
        _bruta(4, estados=["_NET_WM_STATE_HIDDEN"]),                        # minimizada
        _bruta(5, tipo="_NET_WM_WINDOW_TYPE_DESKTOP", area=linux.TODAS_AS_AREAS),
        _bruta(6, tipo="_NET_WM_WINDOW_TYPE_DOCK", area=linux.TODAS_AS_AREAS),
        _bruta(7, area=1),                                                  # outra área de trabalho
        _bruta(8, pid=4444),                                                # o próprio pet
        _bruta(9),                                                          # excluída pelo app
        _bruta(10, largura=80, altura=40),                                  # pequena
        _bruta(11, area=linux.TODAS_AS_AREAS),                              # fixada em todas as áreas
    ]
    assert linux.escolher_janelas(brutas, 0, meu_pid=4444, excluir={9}) == [
        (1, (100, 172, 900, 800), False),
        (2, (116, 210, 884, 768), False),
        (3, (100, 200, 900, 800), True),
        (11, (100, 200, 900, 800), False),
    ]

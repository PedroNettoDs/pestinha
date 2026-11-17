"""
Linux (X11): Xlib (ou wmctrl, sem ele) para a lista de janelas, xdotool para a janela ativa, xprintidle para o tempo ocioso, e pynput para o atalho.

Em Wayland a maior parte dessas leituras não existe: o pet continua andando, mas não enxerga as janelas
nem o tempo ocioso (fica como se você estivesse sempre ativo). Os comandos são opcionais; se faltarem,
a leitura correspondente vira o valor padrão.
"""

import os

import psutil

from ._comum import atalho_pynput, rodar

LARGURA_MINIMA, ALTURA_MINIMA = 120, 60


def parse_geometria(texto):
    """Retângulo (l, t, r, b) a partir de `xdotool getwindowgeometry --shell` (linhas CHAVE=valor)."""
    campos = {}
    for linha in (texto or "").splitlines():
        if "=" in linha:
            chave, valor = linha.split("=", 1)
            campos[chave.strip()] = valor.strip()
    try:
        x, y = int(campos["X"]), int(campos["Y"])
        return (x, y, x + int(campos["WIDTH"]), y + int(campos["HEIGHT"]))
    except (KeyError, ValueError):
        return None


def parse_wmctrl(texto, meu_pid, excluir):
    """[(id, (l, t, r, b), False)] de `wmctrl -lGp`: id desktop pid x y largura altura host título."""
    achadas = []
    for linha in (texto or "").splitlines():
        partes = linha.split(None, 8)
        if len(partes) < 8:
            continue
        try:
            janela_id, pid = int(partes[0], 16), int(partes[2])
            x, y, largura, altura = (int(v) for v in partes[3:7])
        except ValueError:
            continue
        if pid == meu_pid or janela_id in excluir or largura < LARGURA_MINIMA or altura < ALTURA_MINIMA:
            continue
        achadas.append((janela_id, (x, y, x + largura, y + altura), False))
    return achadas


TIPOS_DE_JANELA = {"_NET_WM_WINDOW_TYPE_NORMAL", "_NET_WM_WINDOW_TYPE_DIALOG"}
TODAS_AS_AREAS = 0xFFFFFFFF     # _NET_WM_DESKTOP de janela fixada em todas as áreas de trabalho


def escolher_janelas(brutas, area_atual, meu_pid, excluir):
    """
    [(id, (l, t, r, b), maximizada)] de cima para baixo, só o que está de fato na tela. `brutas` vem de cima
    para baixo: dicionários com id, pid, area, tipo, estados (nomes _NET_WM_*), x, y, largura, altura
    (área cliente), moldura e sombra (esquerda, direita, cima, baixo). Saem a área de trabalho, os painéis,
    as minimizadas, as de outra área de trabalho, as pequenas e as do próprio pet.
    """
    achadas = []
    for j in brutas:
        estados = j["estados"]
        if j["tipo"] not in TIPOS_DE_JANELA or "_NET_WM_STATE_HIDDEN" in estados:
            continue
        if j["area"] not in (area_atual, TODAS_AS_AREAS) or j["pid"] == meu_pid or j["id"] in excluir:
            continue
        me, md, mc, mb = j["moldura"]       # barra de título e bordas do gerenciador: fazem parte da janela
        se, sd, sc, sb = j["sombra"]        # sombra de quem desenha a própria barra (GTK): não faz parte
        l, t = j["x"] - me + se, j["y"] - mc + sc
        r, b = j["x"] + j["largura"] + md - sd, j["y"] + j["altura"] + mb - sb
        if r - l < LARGURA_MINIMA or b - t < ALTURA_MINIMA:
            continue
        maximizada = {"_NET_WM_STATE_MAXIMIZED_VERT", "_NET_WM_STATE_MAXIMIZED_HORZ"} <= set(estados)
        achadas.append((j["id"], (l, t, r, b), maximizada))
    return achadas


class _X11:
    """Conexão própria com o X para listar as janelas (o python-xlib vem com o pynput)."""

    def __init__(self):
        from Xlib import X, display
        self.tudo = X.AnyPropertyType
        self.tela = display.Display()
        self.raiz = self.tela.screen().root
        self._atomos = {}

    def _valor(self, janela, nome):
        if nome not in self._atomos:
            self._atomos[nome] = self.tela.intern_atom(nome)
        prop = janela.get_full_property(self._atomos[nome], self.tudo)
        return list(prop.value) if prop else []

    def _quatro(self, janela, nome):
        valor = self._valor(janela, nome)
        return tuple(valor) if len(valor) == 4 else (0, 0, 0, 0)

    def janelas(self):
        """(janelas de cima para baixo, área de trabalho atual); janela que fechou no meio da leitura é pulada."""
        from Xlib import error
        area = (self._valor(self.raiz, "_NET_CURRENT_DESKTOP") or [0])[0]
        brutas = []
        for janela_id in reversed(self._valor(self.raiz, "_NET_CLIENT_LIST_STACKING")):
            janela = self.tela.create_resource_object("window", janela_id)
            try:
                tipos = self._valor(janela, "_NET_WM_WINDOW_TYPE")
                geo, canto = janela.get_geometry(), janela.translate_coords(self.raiz, 0, 0)
                brutas.append({
                    "id": janela_id,
                    "pid": (self._valor(janela, "_NET_WM_PID") or [0])[0],
                    "area": (self._valor(janela, "_NET_WM_DESKTOP") or [area])[0],
                    "tipo": self.tela.get_atom_name(tipos[0]) if tipos else "_NET_WM_WINDOW_TYPE_NORMAL",
                    "estados": [self.tela.get_atom_name(a) for a in self._valor(janela, "_NET_WM_STATE")],
                    "x": -canto.x, "y": -canto.y, "largura": geo.width, "altura": geo.height,
                    "moldura": self._quatro(janela, "_NET_FRAME_EXTENTS"),
                    "sombra": self._quatro(janela, "_GTK_FRAME_EXTENTS"),
                })
            except error.XError:
                continue
        return brutas, area


_x11 = None         # _X11 ligado; False depois de falhar (sem python-xlib ou sem X): fica o wmctrl


def _janela_ativa():
    """Id da janela ativa no X11 (via xdotool), ou None."""
    return (rodar(["xdotool", "getactivewindow"]) or "").strip() or None


def _tela():
    """Tamanho da tela principal (via xdotool), como (0, 0, largura, altura), ou None."""
    texto = (rodar(["xdotool", "getdisplaygeometry"]) or "").split()
    if len(texto) == 2 and all(v.isdigit() for v in texto):
        return (0, 0, int(texto[0]), int(texto[1]))
    return None


def ocioso_segundos():
    """Tempo ocioso pelo xprintidle (X11). Em Wayland ou sem o comando, devolve 0 (sempre ativo)."""
    texto = (rodar(["xprintidle"]) or "").strip()
    return int(texto) / 1000.0 if texto.isdigit() else 0.0


def processo_ativo():
    """Nome do programa da janela ativa, pegando o pid pelo xdotool e o nome pelo psutil."""
    janela = _janela_ativa()
    pid = (rodar(["xdotool", "getwindowpid", janela]) or "").strip() if janela else ""
    try:
        return psutil.Process(int(pid)).name().lower()
    except (ValueError, psutil.Error):
        return "unknown"


def retangulo_ativo(escala=1.0):
    """Retângulo da janela ativa (pixels), ou None se não houver janela ativa."""
    janela = _janela_ativa()
    if janela is None:
        return None
    return parse_geometria(rodar(["xdotool", "getwindowgeometry", "--shell", janela]))


def tela_cheia():
    """Diz se a janela ativa cobre a tela inteira."""
    rect, tela = retangulo_ativo(), _tela()
    if rect is None or tela is None:
        return False
    return rect[0] <= tela[0] and rect[1] <= tela[1] and rect[2] >= tela[2] and rect[3] >= tela[3]


def janelas_visiveis(excluir, escala=1.0):
    """
    Janelas de outros programas que estão na tela, de cima para baixo. Sem o Xlib, cai no wmctrl, que não
    sabe a ordem nem quais estão minimizadas (o pet quase não acha onde pousar).
    """
    global _x11
    if _x11 is None:
        try:
            _x11 = _X11()
        except Exception:
            _x11 = False
    if _x11:
        try:
            brutas, area = _x11.janelas()
            return escolher_janelas(brutas, area, os.getpid(), excluir)
        except Exception:
            _x11 = None                 # a conexão caiu: tenta de novo na próxima leitura
    return parse_wmctrl(rodar(["wmctrl", "-lGp"]), os.getpid(), excluir)


def programa_em(x, y):
    """Nome e comando (minúsculos) do programa da janela que está na frente no ponto (x, y), ou None. Só com o Xlib."""
    if not _x11:
        return None
    try:
        brutas, area = _x11.janelas()
    except Exception:
        return None
    pids = {j["id"]: j["pid"] for j in brutas}
    for janela_id, (l, t, r, b), _maximizada in escolher_janelas(brutas, area, os.getpid(), set()):
        if l <= x <= r and t <= y <= b:
            try:
                processo = psutil.Process(pids[janela_id])
                # AppImage: o processo se chama "AppRun"; o nome do programa está no primeiro argumento
                comando = os.path.basename((processo.cmdline() or [""])[0])
                return f"{processo.name()} {comando}".lower()
            except psutil.Error:
                return None
    return None


def sem_foco_nativo(janela_id):
    """Tira a janela da barra de tarefas e do pager (o KDE ignora o Qt.Tool); o foco fica com as flags do Qt."""
    rodar(["wmctrl", "-i", "-r", str(janela_id), "-b", "add,skip_taskbar,skip_pager"])


def iniciar_atalho(callback):
    """Registra Ctrl+Alt+Shift+B pelo pynput; devolve True se conseguiu."""
    return atalho_pynput(callback)

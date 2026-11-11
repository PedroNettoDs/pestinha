"""
FLOATS - os painéis flutuantes (monitor neural e painel de protesto).

Modo teste: ficam sempre na tela, arrastáveis. Fora dele, só aparecem quando você
abre pelo menu ou pela bandeja, e ficam até você fechar de novo (ou esconder o pet).
A bandeja pode esconder ou mostrar; o tamanho e a posição ficam salvos (paths.panels).
"""

from PySide6.QtGui import QGuiApplication

from .fila_alfred import FilaAlfred
from .monitor import NeuralMonitor
from .panel import StrikePanel

KEYS = ("neural", "greve", "alfred")
AUTOMATICOS = ("neural", "greve")       # os que o modo teste deixa sempre na tela


class FloatManager:
    """Guarda os painéis abertos (monitor neural, painel de protesto) e decide quando eles podem aparecer."""
    def __init__(self, app):
        """Começa sem painéis abertos."""
        self.app = app
        self.windows = {}
        self.opened = set()             # painéis que você abriu à mão (menu ou bandeja)
        self.hidden_by_tray = False

    def window(self, key):
        """Devolve o painel `key`, criando-o na primeira vez (com a posição salva ou a padrão)."""
        if key not in self.windows:
            screen = QGuiApplication.primaryScreen().availableGeometry()
            if key == "neural":
                self.windows[key] = NeuralMonitor(self.app, (screen.x() + 20, screen.y() + 20))
            elif key == "alfred":
                self.windows[key] = FilaAlfred(self.app, (screen.x() + 20, screen.y() + 20))
            else:
                self.windows[key] = StrikePanel(self.app, (screen.right() - 600, screen.y() + 40))
        return self.windows[key]

    def sync(self, automatic, base):
        """
        automatic: modo teste ligado (os painéis ficam sempre na tela).
        base: o pet está ativo, não escondido e a tela cheia não atrapalha.
        """
        for key in KEYS:
            # abertos à mão aparecem sempre; os automáticos (modo teste) obedecem à bandeja
            shown = base and (key in self.opened
                              or (automatic and key in AUTOMATICOS and not self.hidden_by_tray))
            if shown:
                self.window(key).show()
            elif key in self.windows:
                self.windows[key].hide()

    def open(self, key):
        """Abre um painel, se o pet estiver ativo, visível e a tela não estiver cheia."""
        if not self.app.floats_base():          # desligado, escondido ou tela cheia: não abre
            return
        self.opened.add(key)
        w = self.window(key)
        w.show()
        w.raise_()

    def close(self, key):
        """Fecha um painel e o esquece da lista de abertos."""
        self.opened.discard(key)
        if key in self.windows:
            self.windows[key].hide()

    def toggle(self, key):
        """Abre o painel se estiver fechado; fecha se estiver aberto."""
        if key in self.opened:
            self.close(key)
        else:
            self.open(key)

    def toggle_tray(self, automatic, base):
        """Esconde ou mostra todos os painéis de uma vez (pelo ícone da bandeja)."""
        self.hidden_by_tray = not self.hidden_by_tray
        if self.hidden_by_tray:
            self.opened.clear()                  # "esconder painéis" fecha também os abertos à mão
        self.sync(automatic, base)

    def visible_handles(self):
        """Identificadores das janelas dos painéis visíveis (o pet não deve contá-los como janelas de outros programas)."""
        return {int(w.winId()) for w in self.windows.values() if w.isVisible()}

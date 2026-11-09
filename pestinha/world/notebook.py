"""
NOTEBOOK - o notebook do pet (só o desenho e o arrastar).

Fica sempre na tela, junto com o pet, e pode ser arrastado com o botão esquerdo.
A posição é lembrada em memory/panels.json. A decisão de trabalhar fica em
pestinha/mind/mesa.py; aqui só mostramos se ele está trabalhando (borda acesa).
"""

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QGuiApplication, QLinearGradient, QPainter, QPen, QPixmap
from .arrastavel import FloatingWidget

NOTEBOOK_W, NOTEBOOK_H = 110, 70     # tamanho do desenho de reserva
SPRITE_W = 150                       # largura da foto notebook.png (do pet ou de assets/comum/), se existir
MARGEM_TELA = 24                     # px da borda da tela no primeiro uso


def _default_position(size):
    """Canto inferior direito da tela, onde o notebook começa."""
    screen = QGuiApplication.primaryScreen().availableGeometry()
    return (screen.right() - size[0] - MARGEM_TELA, screen.bottom() - size[1] - MARGEM_TELA)


def load_notebook_sprite(path):
    """Foto do notebook já no tamanho do jogo. None se o arquivo não existir."""
    if not path.exists():
        return None
    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None
    return pixmap.scaledToWidth(SPRITE_W, Qt.SmoothTransformation)


class Notebook(FloatingWidget):
    """Notebook do pet: a foto se existir, senão o desenho de reserva."""

    def __init__(self, app):
        """Carrega a imagem do notebook (ou usa o desenho de reserva) e o põe na tela."""
        self.sprite = load_notebook_sprite(app.conteudo.notebook)
        size = (self.sprite.width(), self.sprite.height()) if self.sprite else (NOTEBOOK_W, NOTEBOOK_H)
        super().__init__(app, "notebook", f"Notebook do {app.nome}", size, size, _default_position(size))
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.working = False

    def set_working(self, working):
        """Acende a borda quando você está trabalhando (o pet sentado)."""
        if working != self.working:
            self.working = working
            self.update()

    def paintEvent(self, _event):
        """Desenha o notebook (a imagem, se houver, senão o desenho de reserva)."""
        if self.sprite is not None:
            self._paint_sprite()
        else:
            self._paint_desenho()

    def _paint_sprite(self):
        """Desenha a imagem do notebook suavizada."""
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.drawPixmap(0, 0, self.sprite)
        p.end()

    def _paint_desenho(self):
        """Verso da tampa, como na foto de referência: cinza fosco, sem logo, base prateada embaixo."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        tampa = QRectF(4, 3, NOTEBOOK_W - 8, NOTEBOOK_H - 14)
        gradiente = QLinearGradient(tampa.topLeft(), tampa.bottomLeft())
        gradiente.setColorAt(0.0, QColor("#5d6165"))
        gradiente.setColorAt(1.0, QColor("#3b3e41"))
        borda = QColor("#63e56f") if self.working else QColor("#24272a")
        p.setPen(QPen(borda, 2.5 if self.working else 1.2))
        p.setBrush(gradiente)
        p.drawRoundedRect(tampa, 6, 6)
        base = QRectF(2, NOTEBOOK_H - 13, NOTEBOOK_W - 4, 9)
        prata = QLinearGradient(base.topLeft(), base.bottomLeft())
        prata.setColorAt(0.0, QColor("#d9dcdf"))
        prata.setColorAt(1.0, QColor("#959a9f"))
        p.setPen(QPen(QColor("#5a5e62"), 1))
        p.setBrush(prata)
        p.drawRoundedRect(base, 3, 3)
        p.end()

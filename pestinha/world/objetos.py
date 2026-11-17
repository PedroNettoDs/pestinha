"""
OBJETOS - os post-its, memes e fotos que o pet traz, como janelas na tela.

Só desenho e clique. Quem decide criar, largar e remover fica em mischief.py.
"""

import random
import time

from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from ..body.pet import overlay_flags, set_no_activate
from ..ajustes import GRAVIDADE as GRAVITY

NOTE_SIZE = (180, 150)


class Thing(QWidget):
    """Objeto genérico na tela (post-it, meme ou foto): uma janela sem moldura que pode ser clicada, arrastada e cai."""
    clicked = Signal(object)

    def __init__(self, w, h):
        """Cria a janela do objeto com o tamanho `w` x `h`, transparente e sem foco."""
        super().__init__(None, overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(w, h)
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip("clique para fechar")
        self.born = time.monotonic()
        self.x = self.y = 0.0     # centro
        self.vy = 0.0
        self.carried = False
        self.resting = True
        self.tilt = random.uniform(-6.0, 6.0)

    def showEvent(self, event):
        """Ao aparecer, o objeto não rouba o foco do programa que você está usando."""
        super().showEvent(event)
        set_no_activate(self)

    def place(self, x, y):
        """Põe o objeto com o centro em (x, y)."""
        self.x, self.y = x, y
        self.move(int(x - self.width() / 2), int(y - self.height() / 2))

    def mousePressEvent(self, event):
        """Clique no objeto: avisa o app (ele conta como 'você viu')."""
        if event.button() == Qt.LeftButton:
            self.clicked.emit(self)

    def fall(self, dt, floor):
        """Física simples: o objeto cai até `floor` (o chão do pet), se não estiver sendo carregado."""
        if self.carried or self.resting:
            return
        self.vy += GRAVITY * dt
        y = self.y + self.vy * dt
        if y + self.height() / 2 >= floor:
            y = floor - self.height() / 2
            self.vy = -self.vy * 0.25 if self.vy > 300 else 0.0
            self.resting = self.vy == 0.0
        self.place(self.x, y)


class ImageThing(Thing):
    """Objeto com uma imagem (meme ou foto), reduzida para caber no tamanho máximo."""
    def __init__(self, path, max_side):
        """Carrega a imagem; se o arquivo estiver corrompido, `valida` fica falso e ele não aparece."""
        pix = QPixmap(str(path))
        self.valida = not pix.isNull()           # arquivo corrompido ou formato não suportado
        if pix.isNull():
            pix = QPixmap(10, 10)
            pix.fill(Qt.transparent)
        self.pix = pix.scaled(max_side, max_side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        pad = 16
        super().__init__(self.pix.width() + pad, self.pix.height() + pad)

    def paintEvent(self, _event):
        """Desenha a imagem suavizada."""
        p = QPainter(self)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(self.tilt * 0.5)
        p.drawPixmap(-self.pix.width() // 2, -self.pix.height() // 2, self.pix)
        p.end()


class NoteThing(Thing):
    """Post-it com uma frase, num papel amarelo."""
    def __init__(self, text, small=False):
        """Monta o post-it com o texto; `small` é o tamanho de canto (bilhete de revolta)."""
        w, h = NOTE_SIZE
        if small:
            w, h = int(w * 0.75), int(h * 0.75)
        super().__init__(w + 20, h + 20)
        self.text = text
        self.small = small
        self.note_w, self.note_h = w, h
        self.carimbo = ""           # texto miúdo na faixa de cima (o Alfred põe a hora em que o post-it nasceu)

    def paintEvent(self, _event):
        """Desenha o papel e o texto do post-it."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(self.tilt)
        rect = QRectF(-self.note_w / 2, -self.note_h / 2, self.note_w, self.note_h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRect(rect.translated(3, 4))
        p.setBrush(QColor("#ffe97a"))
        p.drawRect(rect)
        p.setBrush(QColor("#f5d84f"))
        p.drawRect(QRectF(rect.left(), rect.top(), rect.width(), 14))
        p.setPen(QColor("#3a3320"))
        if self.carimbo:
            p.setFont(QFont("Segoe Print", 7))
            p.drawText(QRectF(rect.left(), rect.top(), rect.width() - 6, 14), Qt.AlignRight | Qt.AlignVCenter, self.carimbo)
        p.setFont(QFont("Segoe Print", 9 if self.small else 11))
        p.drawText(rect.adjusted(10, 18, -10, -8), Qt.AlignCenter | Qt.TextWordWrap, self.text)
        p.end()

"""
ALFRED (objetos) - o que aparece na tela quando o pet encena o trabalho do Alfred. Só desenho.

O balão em cima dele (a atividade e o andamento, ou uma fala) e o objeto que ele carrega (carta, livros,
caixa). Nenhum dos dois recebe cliques: o que está embaixo continua clicável.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF

from .objetos import Thing

ICONES = {
    "email": "✉️", "briefing_matinal": "📰", "briefing_vespertino": "📰", "rag": "📚", "vigia": "🔦",
    "backup": "📦", "podcast": "🎙️", "conversas": "🗂️", "pendencia": "📌",
}
ICONE_PADRAO = "⚙️"

BALAO_LARGURA_MAX = 250
BALAO_MARGEM = 10
BALAO_BICO = 8              # px do bico que aponta para o pet
BALAO_BARRA = 5             # px de altura da barra de andamento


def icone_de(tipo):
    """Emoji de um tipo de atividade ou aviso do Alfred (engrenagem para os desconhecidos)."""
    return ICONES.get(tipo, ICONE_PADRAO)


def _sem_cliques(widget):
    """O clique atravessa a janela: ela é só desenho."""
    widget.setWindowFlag(Qt.WindowTransparentForInput, True)
    widget.setAttribute(Qt.WA_TransparentForMouseEvents)
    widget.setToolTip("")


class PropThing(Thing):
    """Objeto que o pet carrega enquanto o Alfred trabalha: um emoji grande."""

    def __init__(self, icone, lado=46):
        """Cria o objeto com o emoji `icone`."""
        super().__init__(lado, lado)
        self.icone = icone
        self.tilt = 0.0
        _sem_cliques(self)

    def paintEvent(self, _event):
        """Desenha o emoji no centro."""
        p = QPainter(self)
        fonte = QFont()
        fonte.setPixelSize(int(self.height() * 0.68))
        p.setFont(fonte)
        p.drawText(self.rect(), Qt.AlignCenter, self.icone)
        p.end()


class BalaoThing(Thing):
    """Balão em cima do pet: o que o Alfred está fazendo (com barra de andamento) ou uma fala."""

    def __init__(self):
        """Começa vazio; `definir` ajusta o tamanho ao texto."""
        super().__init__(60, 40)
        self.texto = ""
        self.fracao = None
        self.tilt = 0.0
        self.fonte = QFont()
        self.fonte.setPixelSize(13)
        _sem_cliques(self)

    def definir(self, texto, fracao=None):
        """Troca o texto e o andamento (0..1, ou None para sem barra); redimensiona se o texto mudou."""
        if (texto, fracao) == (self.texto, self.fracao):
            return
        if texto != self.texto:
            caixa = QFontMetrics(self.fonte).boundingRect(
                0, 0, BALAO_LARGURA_MAX, 400, Qt.AlignCenter | Qt.TextWordWrap, texto)
            self.setFixedSize(caixa.width() + 2 * BALAO_MARGEM + 4,
                              caixa.height() + 2 * BALAO_MARGEM + BALAO_BARRA + BALAO_BICO)
        self.texto, self.fracao = texto, fracao
        self.update()

    def paintEvent(self, _event):
        """Desenha o balão, o texto e a barra de andamento."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        corpo = QRectF(1, 1, self.width() - 2, self.height() - BALAO_BICO - 2)
        p.setPen(QPen(QColor("#24332a"), 1.5))
        p.setBrush(QColor(20, 27, 22, 235))
        p.drawRoundedRect(corpo, 9, 9)
        meio = self.width() / 2
        p.setPen(Qt.NoPen)
        p.drawPolygon(QPolygonF([QPointF(meio - 6, corpo.bottom() - 1), QPointF(meio + 6, corpo.bottom() - 1),
                                 QPointF(meio, corpo.bottom() + BALAO_BICO)]))
        p.setPen(QColor("#dcebe0"))
        p.setFont(self.fonte)
        p.drawText(corpo.adjusted(BALAO_MARGEM, BALAO_MARGEM - 2, -BALAO_MARGEM, -BALAO_MARGEM - BALAO_BARRA + 2),
                   Qt.AlignCenter | Qt.TextWordWrap, self.texto)
        if self.fracao is not None:
            trilho = QRectF(corpo.left() + BALAO_MARGEM, corpo.bottom() - BALAO_BARRA - 5,
                            corpo.width() - 2 * BALAO_MARGEM, BALAO_BARRA)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#24332a"))
            p.drawRoundedRect(trilho, 2.5, 2.5)
            p.setBrush(QColor("#5fe07a"))
            p.drawRoundedRect(QRectF(trilho.left(), trilho.top(), trilho.width() * self.fracao, BALAO_BARRA), 2.5, 2.5)
        p.end()

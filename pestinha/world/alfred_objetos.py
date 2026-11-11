"""
ALFRED (objetos) - o que aparece na tela quando o pet encena o trabalho do Alfred. Só desenho.

O balão em cima dele (a atividade e o andamento, ou uma fala) e o objeto que ele carrega (carta, livros,
caixa). Nenhum dos dois recebe cliques: o que está embaixo continua clicável. A anotação (post-it de aviso ou
de recado) recebe: arrastar move, clicar abre o detalhe e o botão do meio fecha. Ela fica atrás das outras
janelas, para não atrapalhar.
"""

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen, QPolygonF

from .objetos import NOTE_SIZE, NoteThing, Thing

ICONES = {
    "email": "✉️", "briefing_matinal": "📰", "briefing_vespertino": "📰", "rag": "📚", "vigia": "🔦",
    "backup": "📦", "podcast": "🎙️", "conversas": "🗂️", "pendencia": "📌",
}
ICONE_PADRAO = "⚙️"

BALAO_LARGURA_MAX = 250
BALAO_MARGEM = 10
BALAO_BICO = 8              # px do bico que aponta para o pet
BALAO_BARRA = 5             # px de altura da barra de andamento
ANOTACAO_ABERTA = (300, 260)    # px do papel com o detalhe aberto
ANOTACAO_BORDA = 10         # px entre a janela e o papel (a sombra e a inclinação cabem aí)
ANOTACAO_BOTAO = 30         # px de altura dos botões Feito e Voltar
ARRASTE_MIN = 6             # px: menos que isso é clique, não arraste
PERGUNTA = ("Encerrar também no Alfred?\n\nSim: a pendência é fechada lá, sem resposta ao contato.\n"
            "Não: só o post-it sai; ela continua no Painel.")


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


class AnotacaoThing(NoteThing):
    """Post-it do Alfred, atrás das outras janelas: arrastar move, clicar abre o detalhe (com Feito e Voltar) e
    o botão do meio fecha."""
    feito = Signal(object, bool)    # você clicou em Feito; o segundo valor diz se é para encerrar também no Alfred
    fechada = Signal(object)    # você clicou com o botão do meio
    movida = Signal(object)     # você soltou depois de arrastar

    def __init__(self, texto, detalhe="", pergunta=False):
        """Monta o post-it fechado; `detalhe` é o texto a mais que aparece ao clicar. Com `pergunta`, o Feito
        pergunta antes se é para encerrar também no Alfred."""
        super().__init__(texto)
        self.setWindowFlag(Qt.WindowStaysOnTopHint, False)
        self.setWindowFlag(Qt.WindowStaysOnBottomHint, True)
        self.detalhe = detalhe
        self.pergunta = pergunta
        self.perguntando = False    # o Feito já foi clicado e os botões agora são Sim e Não
        self.aberta = False
        self._pego = None           # (onde o mouse apertou, centro do post-it naquela hora)
        self._arrastou = False
        self.setToolTip("arraste para mover · clique para ver mais · botão do meio fecha")

    def canto(self):
        """Canto de cima à esquerda, que não muda ao abrir e fechar o detalhe (é o que se guarda)."""
        return self.x - self.width() / 2, self.y - self.height() / 2

    def por_canto(self, cx, cy):
        """Põe o post-it com o canto em (cx, cy), sem deixar sair da tela."""
        tela = self.screen().availableGeometry()
        cx = min(max(cx, tela.left()), tela.right() - self.width())
        cy = min(max(cy, tela.top()), tela.bottom() - self.height())
        self.place(cx + self.width() / 2, cy + self.height() / 2)

    def abrir(self, aberta):
        """Abre o detalhe (papel maior, com os botões) ou volta ao post-it pequeno, no mesmo canto."""
        cx, cy = self.canto()
        self.aberta = aberta
        self.perguntando = False
        self.note_w, self.note_h = ANOTACAO_ABERTA if aberta else NOTE_SIZE
        self.setFixedSize(self.note_w + 2 * ANOTACAO_BORDA, self.note_h + 2 * ANOTACAO_BORDA)
        self.por_canto(cx, cy)
        self.update()

    def botoes(self):
        """Onde ficam os botões do detalhe: {"feito": QRectF, "voltar": QRectF}."""
        y = ANOTACAO_BORDA + self.note_h - ANOTACAO_BOTAO - 10
        largura = (self.note_w - 30) / 2
        return {"feito": QRectF(ANOTACAO_BORDA + 10, y, largura, ANOTACAO_BOTAO),
                "voltar": QRectF(ANOTACAO_BORDA + 20 + largura, y, largura, ANOTACAO_BOTAO)}

    def mousePressEvent(self, event):
        """Botão do meio fecha; o esquerdo começa um clique ou um arraste."""
        if event.button() == Qt.MiddleButton:
            self.fechada.emit(self)
        elif event.button() == Qt.LeftButton:
            self._pego = (event.globalPosition(), self.canto())
            self._arrastou = False

    def mouseMoveEvent(self, event):
        """Com o botão apertado, o post-it segue o mouse."""
        if self._pego is None:
            return
        delta = event.globalPosition() - self._pego[0]
        if self._arrastou or delta.manhattanLength() >= ARRASTE_MIN:
            self._arrastou = True
            self.por_canto(self._pego[1][0] + delta.x(), self._pego[1][1] + delta.y())

    def mouseReleaseEvent(self, event):
        """Soltou: se arrastou, ficou onde está; se foi só um clique, abre o detalhe ou aciona o botão."""
        if event.button() != Qt.LeftButton or self._pego is None:
            return
        self._pego = None
        if self._arrastou:
            self.movida.emit(self)
        elif not self.aberta:
            self.abrir(True)
        elif self.botoes()["feito"].contains(event.position()):
            if self.pergunta and not self.perguntando:
                self.perguntando = True             # os botões viram Sim e Não
                self.update()
            else:
                self.feito.emit(self, self.perguntando)     # Sim: encerra também no Alfred
        elif self.botoes()["voltar"].contains(event.position()):
            if self.perguntando:
                self.feito.emit(self, False)        # Não: só tira o post-it
            else:
                self.abrir(False)

    def paintEvent(self, event):
        """Fechado, é o post-it de sempre; aberto, o papel maior com o texto, o detalhe e os botões."""
        if not self.aberta:
            super().paintEvent(event)
            return
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        papel = QRectF(ANOTACAO_BORDA, ANOTACAO_BORDA, self.note_w, self.note_h)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 50))
        p.drawRect(papel.translated(3, 4))
        p.setBrush(QColor("#ffe97a"))
        p.drawRect(papel)
        p.setBrush(QColor("#f5d84f"))
        p.drawRect(QRectF(papel.left(), papel.top(), papel.width(), 14))
        botoes = self.botoes()
        miolo = papel.adjusted(12, 22, -12, -(ANOTACAO_BOTAO + 18))
        titulo = QFont("Segoe Print", 11)
        titulo.setBold(True)
        p.setPen(QColor("#3a3320"))
        p.setFont(titulo)
        usado = p.boundingRect(miolo, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.text)
        p.drawText(miolo, Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap, self.text)
        p.setFont(QFont("Segoe Print", 9))
        p.drawText(miolo.adjusted(0, usado.height() + 8, 0, 0), Qt.AlignLeft | Qt.AlignTop | Qt.TextWordWrap,
                   PERGUNTA if self.perguntando else self.detalhe or "Sem mais detalhes.")
        rotulos = ("Sim", "Não") if self.perguntando else ("Feito", "Voltar")
        for nome, rotulo, cor in (("feito", rotulos[0], "#8fd694"), ("voltar", rotulos[1], "#f5d84f")):
            p.setPen(QPen(QColor("#3a3320"), 1))
            p.setBrush(QColor(cor))
            p.drawRoundedRect(botoes[nome], 5, 5)
            p.setFont(titulo)
            p.drawText(botoes[nome], Qt.AlignCenter, rotulo)
        p.end()

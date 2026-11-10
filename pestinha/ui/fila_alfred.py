"""
FILA DO ALFRED - a fila de ações do Alfred na tela, como a de um jogo: o que ele faz agora e o que vem depois.

Da esquerda para a direita: o que está em andamento (borda verde, com o andamento), o que você pediu (na
ordem em que vai rodar), as próximas rotinas agendadas (apagadas, com a hora) e o "+", que abre a lista do
que dá para pedir. No fim, dois atalhos: conversar com o Alfred e abrir o Painel dele no navegador. Clique num item da fila para passar para a frente ou tirar; numa agendada, para adiantar.
Arrasta-se como os outros painéis.
"""

import time

from PySide6.QtCore import QEvent, QRectF, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import QMenu, QToolTip

from ..world.alfred_objetos import icone_de
from ..world.arrastavel import FloatingWidget
from .panel import GOOD, GRID, MUTED, PANEL, RED, TEXT

LADO, VAO, BORDA = 50, 6, 10    # px: lado de cada bloco, vão entre eles e margem do painel
TOPO = 28                       # faixa de cima, com o texto de estado
RODAPE = 18                     # faixa de baixo, com a hora das agendadas
ALTURA = TOPO + LADO + RODAPE
LARGURA_MINIMA = 240
MAX_FILA, MAX_AGENDADAS = 6, 3
ARRASTE_PX = 4                  # o botão soltou a menos disso de onde apertou: foi clique, não arraste


def fonte(px, negrito=False):
    """Fonte padrão do sistema num tamanho em pixels."""
    f = QFont()
    f.setPixelSize(px)
    f.setBold(negrito)
    return f


def hora(quando, agora=None):
    """Hora de uma rotina agendada: "07:00" nas próximas 24 h, senão o dia ("15/11")."""
    agora = time.time() if agora is None else agora
    return time.strftime("%H:%M" if quando - agora < 86400 else "%d/%m", time.localtime(quando))


def texto_do_andamento(atividade):
    """"Classificando e-mails 3/12": o passo (ou o nome da rotina) e o andamento, se houver."""
    texto = atividade["passo"] or atividade["rotulo"]
    if atividade["total"]:
        texto += f" {int(atividade['feito'] or 0)}/{int(atividade['total'])}"
    return texto


def preencher_menu(menu, alfred):
    """Lista do que dá para pedir ao Alfred: clicar põe na frente da fila; o submenu põe no fim."""
    catalogo = alfred.estado.catalogo
    if not catalogo:
        menu.addAction("Alfred fora do ar").setEnabled(False)
        return
    menu.addAction("Fazer em seguida:").setEnabled(False)
    fim = QMenu("Pôr no fim da fila", menu)
    for item in catalogo:
        texto = f"{icone_de(item['tipo'])}  {item['rotulo']}"
        menu.addAction(texto).triggered.connect(lambda _=False, t=item["tipo"]: alfred.enfileirar(t, frente=True))
        fim.addAction(texto).triggered.connect(lambda _=False, t=item["tipo"]: alfred.enfileirar(t, frente=False))
    menu.addSeparator()
    menu.addMenu(fim)


class FilaAlfred(FloatingWidget):
    """Painel com a fila do Alfred: blocos clicáveis para o que roda agora, a fila e as agendadas."""

    def __init__(self, app, default_pos):
        """Cria o painel e um relógio que o atualiza duas vezes por segundo."""
        super().__init__(app, "alfred", f"{app.nome} · Fila", (LARGURA_MINIMA, ALTURA), (LARGURA_MINIMA, ALTURA),
                         default_pos)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.blocos = []            # [(QRectF, grupo, item)]: o que está desenhado e onde os cliques caem
        self._apertou = None
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.atualizar)
        self.timer.start(500)
        self.atualizar()

    def atualizar(self):
        """Refaz os blocos a partir do retrato do Alfred e ajusta a largura do painel."""
        estado = self.app.alfred.estado
        agora = time.time()
        grupos = [("agora", a) for a in estado.agora] or [("livre", None)]
        grupos += [("fila", i) for i in estado.fila[:MAX_FILA]]
        grupos += [("agendada", a) for a in estado.agendadas if a["quando"] > agora][:MAX_AGENDADAS]
        grupos.append(("mais", None))
        grupos += [(nome, None) for nome in ("conversa", "painel") if nome in estado.links]
        self.blocos = [(QRectF(BORDA + n * (LADO + VAO), TOPO, LADO, LADO), grupo, item)
                       for n, (grupo, item) in enumerate(grupos)]
        largura = max(LARGURA_MINIMA, 2 * BORDA + len(grupos) * (LADO + VAO) - VAO)
        if largura != self.width():
            self.resize(largura, ALTURA)
        self.update()

    # ---------------- desenho ----------------

    def paintEvent(self, _event):
        """Desenha o fundo, o texto de estado e um bloco por item."""
        alfred = self.app.alfred
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(QPen(GRID, 1))
        p.setBrush(QColor(13, 17, 15, 235))
        p.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 10, 10)

        atividade = alfred.atividade()
        if not alfred.estado.online:
            texto, cor = "fora do ar", RED
        elif atividade is None:
            texto, cor = "livre", MUTED
        else:
            texto, cor = texto_do_andamento(atividade), TEXT
        p.setPen(MUTED)
        p.setFont(fonte(10, negrito=True))
        p.drawText(QRectF(BORDA, 0, 60, TOPO), Qt.AlignLeft | Qt.AlignVCenter, "ALFRED")
        p.setPen(cor)
        p.setFont(fonte(12))
        espaco = QRectF(BORDA + 56, 0, self.width() - 2 * BORDA - 56, TOPO)
        p.drawText(espaco, Qt.AlignLeft | Qt.AlignVCenter,
                   QFontMetrics(p.font()).elidedText(texto, Qt.ElideRight, int(espaco.width())))

        posicao = 0
        for rect, grupo, item in self.blocos:
            if grupo == "fila":
                posicao += 1
            self._bloco(p, rect, grupo, item, posicao)
        p.end()

    def _bloco(self, p, rect, grupo, item, posicao):
        """Um bloco: a borda diz o grupo; dentro, o emoji; embaixo, a hora (agendadas)."""
        borda = {"agora": QPen(GOOD, 2), "fila": QPen(MUTED, 1.3), "conversa": QPen(MUTED, 1.3),
                 "painel": QPen(MUTED, 1.3)}.get(grupo, QPen(GRID, 1.3, Qt.DashLine))
        p.setPen(borda)
        p.setBrush(PANEL)
        p.drawRoundedRect(rect, 8, 8)
        p.setOpacity(0.45 if grupo in ("agendada", "livre") else 1.0)
        p.setPen(MUTED)
        p.setFont(fonte(24))
        simbolo = {"mais": "+", "livre": "💤", "conversa": "💬", "painel": "🖥️"}.get(grupo) or icone_de(item["tipo"])
        p.drawText(rect, Qt.AlignCenter, simbolo)
        p.setOpacity(1.0)
        if grupo == "agora" and item["total"]:
            fracao = max(0.0, min(1.0, (item["feito"] or 0.0) / item["total"]))
            p.setPen(Qt.NoPen)
            p.setBrush(GOOD)
            p.drawRoundedRect(QRectF(rect.left() + 5, rect.bottom() - 7, (rect.width() - 10) * fracao, 3), 1.5, 1.5)
        p.setFont(fonte(10))
        if grupo == "fila":
            p.setPen(TEXT)
            p.drawText(rect.adjusted(5, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop, str(posicao))
        elif grupo == "agendada":
            p.setPen(MUTED)
            p.drawText(QRectF(rect.left() - VAO / 2, rect.bottom(), rect.width() + VAO, RODAPE),
                       Qt.AlignCenter, hora(item["quando"]))

    # ---------------- mouse ----------------

    def bloco_em(self, pos):
        """(grupo, item) do bloco que contém o ponto, ou (None, None)."""
        return next(((grupo, item) for rect, grupo, item in self.blocos if rect.contains(pos)), (None, None))

    def abrir(self, grupo):
        """Os blocos de atalho: a conversa numa janela ao lado do pet e o Painel no navegador. False nos outros."""
        if grupo == "conversa":
            self.app.alfred.abrir_conversa()
        elif grupo == "painel":
            self.app.alfred.abrir_painel()
        else:
            return False
        return True

    def menu_de(self, grupo, item):
        """O menu de um bloco: pedir (no "+"), reordenar ou tirar (na fila), adiantar (nas agendadas)."""
        alfred = self.app.alfred
        menu = QMenu()
        if grupo == "mais":
            preencher_menu(menu, alfred)
        elif grupo == "fila":
            frente = menu.addAction("Passar para a frente")
            frente.setEnabled(alfred.estado.fila[0]["id"] != item["id"])
            frente.triggered.connect(lambda: alfred.passar_para_frente(item["id"]))
            menu.addAction("Tirar da fila").triggered.connect(lambda: alfred.cancelar(item["id"]))
        elif grupo == "agendada":
            menu.addAction(f"Fazer agora: {item['rotulo']}").triggered.connect(
                lambda: alfred.enfileirar(item["tipo"], frente=True))
        else:
            return None
        return menu

    def dica(self, grupo, item):
        """Texto que aparece ao parar o mouse num bloco."""
        if grupo == "agora":
            return f"Agora: {item['rotulo']}" + (f" ({texto_do_andamento(item)})" if item["passo"] else "")
        if grupo == "fila":
            return f"Na fila: {item['rotulo']}. Clique para passar para a frente ou tirar."
        if grupo == "agendada":
            return f"{item['rotulo']}, agendada para {hora(item['quando'])}. Clique para adiantar."
        return {"mais": "Pedir uma rotina ao Alfred", "livre": "Nada em andamento",
                "conversa": "Conversar com o Alfred (texto ou microfone)",
                "painel": "Abrir o terminal do Alfred: o Painel, no navegador"}.get(grupo, "")

    def mousePressEvent(self, event):
        """Guarda onde o botão apertou, para separar clique de arraste."""
        super().mousePressEvent(event)
        self._apertou = event.globalPosition().toPoint() if event.button() == Qt.LeftButton else None

    def mouseReleaseEvent(self, event):
        """Soltou sem arrastar em cima de um bloco: abre o menu dele."""
        super().mouseReleaseEvent(event)
        apertou, self._apertou = self._apertou, None
        solto = event.globalPosition().toPoint()
        if apertou is None or (solto - apertou).manhattanLength() > ARRASTE_PX:
            return
        grupo, item = self.bloco_em(event.position())
        if not self.abrir(grupo):
            menu = self.menu_de(grupo, item)
            if menu is not None:
                menu.exec(solto)

    def event(self, event):
        """Dica de cada bloco."""
        if event.type() == QEvent.ToolTip:
            QToolTip.showText(event.globalPos(), self.dica(*self.bloco_em(event.pos())), self)
            return True
        return super().event(event)

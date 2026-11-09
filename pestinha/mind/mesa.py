"""
MESA - o computadorzinho do pet: sentar e levantar do notebook.

Quem decide é o neurônio motor SENTAR da rede: ele dispara quando há vontade de
trabalhar (foco, pedido seu) e para quando há vontade de brincar, tristeza ou
frustração. Não há limiar de foco nem temporizador aqui: só o limiar de disparo
do próprio neurônio (com histerese, para não ficar trocando de estado).

Pedir para trabalhar é um sinal que entra na rede por um tempo. Se ele não senta
até o pedido acabar, ele recusa, e a recusa entra na rede como frustração.

DeskController é a decisão pura. MesaController liga a decisão ao notebook.
"""

from ..ajustes import (
    ALCANCE_NOTEBOOK,
    FOCO_MAXIMO_HZ,
    LIMIAR_LEVANTAR_HZ,
    JANELA_PEDIDOS_S,
    LIMIAR_SENTAR_HZ,
    PEDIDO_VALIDADE_S,
    FRACAO_ESCONDIDA_NOTEBOOK,
    DESLOCAMENTO_NOTEBOOK_X,
)
from ..log import log
from ..mathutil import clamp
from ..world.notebook import Notebook

INTERVALO_TOPO = 0.25      # s entre um "trazer para frente" e outro


def focus_level(pool_rates):
    """0..1: quão concentrado ele está agora (população FOCUS)."""
    return clamp(pool_rates.get("FOCUS", 0.0) / FOCO_MAXIMO_HZ)


def distraction_level(pool_rates):
    """0..1: quão distraído ele está (brincalhão ou curioso)."""
    return clamp(max(pool_rates.get("PLAYFUL", 0.0), pool_rates.get("CURIOUS", 0.0)) / FOCO_MAXIMO_HZ)


def pull(pool_rates):
    """0..1: quanto a rede quer brincar agora (distração acima do foco). Trabalhando, é zero."""
    return clamp(distraction_level(pool_rates) - focus_level(pool_rates))


class DeskController:
    """Sentar quando o disparo de SENTAR passa do limiar; levantar quando cai abaixo do outro."""

    def __init__(self):
        """Guarda se o pet está sentado no notebook e quando se levantou."""
        self.at_desk = False
        self.left_at = 0.0

    def tick(self, now, sentar_hz, pode):
        """Devolve (antes, depois) quando o estado muda, senão None."""
        before = self.at_desk
        if self.at_desk:
            if not pode or sentar_hz < LIMIAR_LEVANTAR_HZ:
                self.at_desk = False
                self.left_at = now
        elif pode and sentar_hz >= LIMIAR_SENTAR_HZ:
            self.at_desk = True
        return (before, self.at_desk) if before != self.at_desk else None


class MesaController:
    """Liga a decisão ao notebook: sentar, levantar e mostrar o notebook (arrastável)."""

    def __init__(self, debug, app):
        """Controla o notebook: sentar, levantar, pedidos de trabalho e a janela do notebook."""
        self.decisao = DeskController()
        self.caderno = Notebook(app)            # sempre na tela junto com o pet, arrastável
        self.debug = debug
        self.ancora = None                      # onde o notebook estava quando ele sentou
        self.ancora_corpo = None                # onde ele estava quando sentou (o corpo não sobe para o notebook)
        self.ultimo_topo = -1e9                 # quando o notebook foi trazido para frente pela última vez
        self.pedido_ate = 0.0                   # até quando um pedido para trabalhar ainda vale
        self.em_pedido = False                  # um pedido está em aberto (ainda não sentou nem recusou)
        self.pode_no_pedido = False             # durante o pedido, houve momento em que ele podia sentar
        self.pedidos = []                       # quando você pediu (para a frustração crescer com a insistência)
        self.recusou = False                    # ele recusou o último pedido
        self.visivel = False                    # o pet está na tela
        self.escondido = False                  # você escondeu o notebook pelo menu

    @property
    def sentado(self):
        """Diz se o pet está sentado no notebook agora."""
        return self.decisao.at_desk

    # ---------------- pedidos ----------------

    def pedir(self, now):
        """Você pede para ele trabalhar: entra na rede como um sinal que vai decaindo."""
        self.pedido_ate = now + PEDIDO_VALIDADE_S
        self.em_pedido = True
        self.pode_no_pedido = False             # só é recusa se ele pôde sentar em algum momento
        self.pedidos = [t for t in self.pedidos if now - t < JANELA_PEDIDOS_S] + [now]

    def deslocar(self, segundos):
        """A pausa não conta: o prazo do pedido anda junto com ela."""
        if self.em_pedido:
            self.pedido_ate += segundos

    def pedidos_recentes(self):
        """Quantos pedidos de trabalho foram feitos há pouco (eles pesam na decisão da rede)."""
        return len(self.pedidos)

    def intensidade_pedido(self, now):
        """0..1 para a rede: forte logo depois do pedido, some quando ele acaba."""
        restante = self.pedido_ate - now
        return clamp(restante / PEDIDO_VALIDADE_S) if restante > 0 else 0.0

    def pop_recusa(self):
        """Devolve True uma vez quando ele recusou um pedido."""
        recusou, self.recusou = self.recusou, False
        return recusou

    # ---------------- decisão ----------------

    def tick(self, now, rates, sentar_hz, pode_sentar, brincadeira):
        """Atualiza a decisão a partir do disparo de SENTAR. Devolve a mudança (antes, depois) ou None."""
        pode = pode_sentar and not self.escondido
        mudanca = self.decisao.tick(now, sentar_hz, pode)
        if self.em_pedido:
            self.pode_no_pedido = self.pode_no_pedido or pode
            if self.sentado:
                self.em_pedido = False          # pediram e ele quis
            elif now >= self.pedido_ate:
                self.em_pedido = False
                self.recusou = self.pode_no_pedido   # pediram, ele podia e não quis
        self.caderno.set_working(self.sentado)
        if mudanca and mudanca[1]:
            self.ancora = (self.caderno.x(), self.caderno.y())
            self.caderno.raise_()                # o notebook fica na frente: ele aparece atrás dele
        if mudanca and mudanca[1] is False:
            self.ancora = None
            self.ancora_corpo = None
            brincadeira.next_at = 0.0            # levantou: a bolinha fica mais provável agora
        if mudanca and self.debug():
            log(f"[notebook] {'sentou' if mudanca[1] else 'levantou'} "
                f"(SENTAR {sentar_hz:.1f} Hz, foco {focus_level(rates):.2f}, "
                f"distração {distraction_level(rates):.2f})")
        return mudanca

    def pin(self, body, now):
        """Fixa o pet atrás do notebook. Devolve "arrancado" se o notebook foi levado longe demais."""
        if not self.sentado:
            return None
        _ex, ey = body.extents()
        if self.ancora_corpo is None:                  # primeiro quadro sentado: o notebook vai para debaixo dele
            self.ancora_corpo = (body.x, body.y)
            self.caderno.move(int(body.x - self.caderno.width() * (0.5 + DESLOCAMENTO_NOTEBOOK_X)),
                              int(body.y - (2 * FRACAO_ESCONDIDA_NOTEBOOK - 1) * ey))
            self.ancora = (self.caderno.x(), self.caderno.y())
        dx = self.caderno.x() - self.ancora[0]
        dy = self.caderno.y() - self.ancora[1]
        if (dx * dx + dy * dy) ** 0.5 > ALCANCE_NOTEBOOK:
            return "arrancado"
        body.x = self.ancora_corpo[0] + dx             # ele fica no lugar; só anda se você arrastar o notebook
        body.y = self.ancora_corpo[1] + dy
        body.vx = body.vy = 0.0
        body.grounded = True
        if now - self.ultimo_topo >= INTERVALO_TOPO:       # o pet não pode ficar por cima do notebook
            self.caderno.raise_()
            self.ultimo_topo = now
        return None

    def levantar_arrancado(self, now):
        """Ele levanta à força. A frustração vem pela rede (o app manda o sinal de dispensa)."""
        self.decisao.at_desk = False
        self.decisao.left_at = now
        self.ancora = None

    # ---------------- janela ----------------

    def set_visible(self, visivel):
        """Mostra ou esconde o notebook junto com o pet."""
        self.visivel = visivel                  # o pet está na tela (e o app quer o notebook)
        self._aplicar_visibilidade()

    def alternar_notebook(self):
        """Esconde ou mostra o notebook pelo menu. Escondido, ele não senta."""
        self.escondido = not self.escondido
        if self.escondido and self.sentado:          # sem notebook não dá para trabalhar: levanta na hora
            self.decisao.at_desk = False
            self.ancora = None
            self.caderno.set_working(False)
        self._aplicar_visibilidade()

    def _aplicar_visibilidade(self):
        """Aplica a visibilidade do notebook (ele só aparece se o pet estiver visível e o notebook não estiver escondido)."""
        self.caderno.setVisible(self.visivel and not self.escondido)

    def fechar(self):
        """Fecha a janela do notebook ao sair."""
        self.caderno.close()

"""
PET - a telinha com olhinhos: janela transparente, desenho e mouse.

A janela é um quadrado transparente maior que o corpo, para caber o corpo
girado. Pixels transparentes deixam o clique passar para o que está embaixo.
A janela nunca pega o foco (o teclado continua no seu programa).
"""

import math
import random
import time

from PySide6.QtCore import QRect, QRectF, Qt, Signal
from PySide6.QtGui import QCursor, QFont, QPainter
from PySide6.QtWidgets import QWidget

from ..config import EMOTION_NAMES
from ..core.emotion import EYE_SHAPES, shape_from_affect
from ..core.physics import Body
from .. import plataforma
from ..ajustes import (
    LADO_JANELA_PET as WIN,
    TEMPO_MAX_CUTUCADA_MS as POKE_MAX_MS,
    DISTANCIA_INICIO_ARRASTE as DRAG_START_PX,
    VELOCIDADE_ARREMESSO as THROW_MIN_SPEED,
    JANELA_CARINHO as RUB_WINDOW,
    TROCAS_CARINHO as RUB_REVERSALS,
    DESLOCAMENTO_CARINHO as RUB_MIN_TRAVEL,
)

from .desenho_rosto import BODY_H, BODY_W, PADRAO, draw_face, draw_zzz, lerp_shape

CX, CY = WIN / 2, WIN / 2 - 6   # centro do corpo dentro da janela



# carinho = passar o mouse para lá e para cá em cima dele, sem clicar


def set_no_activate(widget):
    """Garante que clicar/mostrar a janela não rouba o foco do programa atual (onde o sistema permite)."""
    try:
        plataforma.sem_foco_nativo(int(widget.winId()))
    except Exception:
        pass    # sem janela nativa (ex.: teste offscreen)


def overlay_flags():
    """Janela sem moldura, sempre por cima, que não aparece na barra de tarefas nem recebe foco ao aparecer."""
    return (
        Qt.FramelessWindowHint
        | Qt.Tool
        | Qt.WindowStaysOnTopHint
        | Qt.WindowDoesNotAcceptFocus
    )


class PetWindow(QWidget):
    """Janela do pet: desenha o PetState e traduz o mouse em gestos (sinais)."""

    poked = Signal()
    drag_started = Signal()
    drag_ended = Signal()
    thrown = Signal(float)          # velocidade do arremesso (px/s)
    menu_requested = Signal(object) # botão direito: posição global do clique

    def __init__(self, x, y, state):
        """Janela transparente do pet: o rosto é desenhado aqui e o mouse vira gestos (cutucar, arrastar, arremessar)."""
        super().__init__(None, overlay_flags())
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(WIN, WIN)

        self.body = Body(x, y, BODY_W / 2, BODY_H / 2)
        self.state = state
        self.aparencia = PADRAO      # cores e acessórios do pet (pets/<pet>.json)
        self.next_blink = time.monotonic() + random.uniform(2.0, 5.0)

        self._press = None          # (pos global, tempo)
        self._grab = (0.0, 0.0)
        self._dragging = False
        self._samples = []          # (t, x, y) para a velocidade do arremesso
        self._held_angle = 0.0
        self._rub = []              # (t, x) do mouse passando sem clicar
        self.setMouseTracking(True)

    def _track_rub(self, x):
        """Detecta carinho: o mouse passando de um lado para o outro várias vezes, sem clicar, em cima do pet."""
        now = time.monotonic()
        self._rub.append((now, x))
        self._rub = [r for r in self._rub if now - r[0] < RUB_WINDOW]
        reversals, travel, last_dir = 0, 0.0, 0
        for (_, x0), (_, x1) in zip(self._rub, self._rub[1:]):
            step = x1 - x0
            if abs(step) < 2:
                continue
            direction = 1 if step > 0 else -1
            if last_dir and direction != last_dir:
                reversals += 1
            last_dir = direction
            travel += abs(step)
        if reversals >= RUB_REVERSALS and travel >= RUB_MIN_TRAVEL:
            self.state.mark_caress(now)

    def showEvent(self, event):
        """Ao aparecer, a janela já é marcada para não roubar o foco do programa que você está usando."""
        super().showEvent(event)
        set_no_activate(self)

    # ---------------- animação ----------------

    def animate(self, now):
        """Um quadro da animação: suaviza a forma dos olhos, pisca de tempos em tempos e reposiciona a janela."""
        st = self.state
        if st.forced or st.emotion not in EYE_SHAPES:
            target = dict(EYE_SHAPES.get(st.emotion, EYE_SHAPES["observando"]))
        else:
            target = shape_from_affect(*st.affect)
        if st.emotion != "dormindo":
            droop = st.tone.lid_droop()             # DROWSE pesa as pálpebras, em qualquer emoção
            target["inner"] = min(0.8, target["inner"] + droop)
            target["outer"] = min(0.8, target["outer"] + droop)
        st.shape = lerp_shape(st.shape, target, 0.22)
        if now >= self.next_blink:
            st.blink_until = now + 0.13
            self.next_blink = now + random.uniform(2.5, 6.0)

        if self.body.held:
            vx = self._velocity()[0]
            sway = max(-35.0, min(35.0, -vx * 0.03))
            self.body.angle += (self._held_angle + sway - self.body.angle) * 0.25

        self.move(int(self.body.x - CX), int(self.body.y - CY))
        self.update()

    def paintEvent(self, _event):
        """Desenha o pet: corpo, olhos, acessórios e balanço; some atrás da tampa do notebook quando está sentado."""
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        st = self.state
        if st.desk_top is not None:
            # sentado: o corpo some atrás da tampa do notebook (corta no nível dela, não depende da ordem das janelas)
            corte = int(st.desk_top - self.y())
            p.setClipRect(QRect(0, 0, self.width(), max(0, min(self.height(), corte))))
        shake = st.shake
        jitter_x = random.uniform(-shake, shake) if shake else 0.0
        jitter_y = random.uniform(-shake, shake) if shake else 0.0

        # SETTLE: balança devagarinho, de boa; a amplitude é a atividade da população
        sway = 0.0
        if self.body.grounded and st.emotion != "dormindo":
            sway = st.tone.sway() * math.sin(time.monotonic() * 2.2)
        if st.emotion == "dormindo":
            jitter_y += 1.5 * math.sin(time.monotonic() * 1.6)     # respirando devagar

        p.save()
        p.translate(CX + jitter_x, CY + jitter_y)
        p.rotate(self.body.angle + sway)
        blink = 0.08 if time.monotonic() < st.blink_until else 1.0
        draw_face(p, st.shape, st.gaze, blink, st.emotion, carinho=st.feliz_fechado(), aparencia=self.aparencia)
        p.restore()

        if st.emotion == "dormindo":
            draw_zzz(p, CX + jitter_x, CY + jitter_y, time.monotonic(), self.aparencia.olho)

        if st.show_label:
            p.setPen(self.aparencia.olho)
            p.setFont(QFont("Consolas", 9, QFont.Bold))
            p.drawText(QRectF(0, WIN - 22, WIN, 20), Qt.AlignCenter, EMOTION_NAMES.get(st.emotion, st.emotion))
        p.end()

    # ---------------- mouse ----------------

    def mousePressEvent(self, event):
        """Início de um gesto: guarda onde o botão foi apertado (clique esquerdo)."""
        if event.button() != Qt.LeftButton:
            return
        pos = event.globalPosition()
        self.state.pressing = math.hypot(pos.x() - self.body.x, pos.y() - self.body.y) < 90
        self._press = (pos, time.monotonic())
        self._grab = (pos.x() - self.body.x, pos.y() - self.body.y)
        self._samples = [(time.monotonic(), pos.x(), pos.y())]

    def mouseMoveEvent(self, event):
        """Enquanto o botão está apertado, arrasta o pet; sem botão, só registra o carinho do mouse."""
        pos = event.globalPosition()
        if self._press is None:
            self._track_rub(pos.x())
            return
        if not self.state.allow_drag:
            return
        start = self._press[0]
        if not self._dragging:
            if math.hypot(pos.x() - start.x(), pos.y() - start.y()) < DRAG_START_PX:
                return
            self._dragging = True
            self._held_angle = self.body.angle
            self.body.held = True
            self.body.grounded = False
            self.body.platform = None
            self.drag_started.emit()

        self.body.x = pos.x() - self._grab[0]
        self.body.y = pos.y() - self._grab[1]
        now = time.monotonic()
        self._samples.append((now, pos.x(), pos.y()))
        self._samples = [s for s in self._samples if now - s[0] < 0.12]

    def cancel_interaction(self):
        """Cancela um toque ou arraste em andamento (pânico, esconder): o corpo volta a cair."""
        self._press = None
        self._samples = []
        self.state.pressing = False
        if self._dragging:
            self._dragging = False
            self.body.held = False
            self.body.vx = self.body.vy = 0.0
            self.body.grounded = False
            self.body.platform = None

    def mouseReleaseEvent(self, event):
        """Fim do gesto: se foi um clique, é cutucada; se foi um arremesso, a velocidade vira força do lance."""
        if event.button() != Qt.LeftButton or self._press is None:
            return
        self.state.pressing = False
        held_ms = (time.monotonic() - self._press[1]) * 1000.0
        if self._dragging:
            vx, vy = self._velocity()
            self.body.held = False
            self.body.vx = max(-2500.0, min(2500.0, vx))
            self.body.vy = max(-2500.0, min(2500.0, vy))
            self.body.omega += self.body.vx * 0.35
            self.drag_ended.emit()
            speed = math.hypot(self.body.vx, self.body.vy)
            if speed >= THROW_MIN_SPEED:
                self.thrown.emit(speed)
        elif held_ms <= POKE_MAX_MS and self.state.allow_poke:
            self.poked.emit()
        self._press = None
        self._dragging = False

    def contextMenuEvent(self, event):
        """Botão direito: pede ao app para abrir o menu do pet."""
        self.menu_requested.emit(event.globalPos())

    def wheelEvent(self, event):
        """Rodinha do mouse gira o pet (segurando ou no ar)."""
        if not self.state.allow_drag:
            return
        step = event.angleDelta().y() / 120.0 * 20.0
        if self.body.held:
            self._held_angle += step
        else:
            self.body.omega += step * 12.0
            if self.body.grounded:
                self.body.jump(0.0, -250.0)

    def _velocity(self):
        """Velocidade média do mouse nas últimas amostras (para o arremesso e o balanço)."""
        if len(self._samples) < 2:
            return 0.0, 0.0
        t0, x0, y0 = self._samples[0]
        t1, x1, y1 = self._samples[-1]
        dt = max(t1 - t0, 1e-3)
        return (x1 - x0) / dt, (y1 - y0) / dt

    @property
    def dragging(self):
        """Verdadeiro enquanto você está arrastando o pet."""
        return self._dragging


def cursor_pos():
    """Posição atual do cursor em pixels (x, y)."""
    p = QCursor.pos()
    return p.x(), p.y()

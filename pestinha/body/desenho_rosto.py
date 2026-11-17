"""
DESENHO DO ROSTO - só o que se desenha do pet: moldura, olhos, brilho, acessórios, a roupa de dormir e os Zzz.

Não tem estado nem decisão: recebe a forma dos olhos, a direção do olhar e a aparência do pet
(cores e acessórios, de pets/<pet>.json) e pinta. Os acessórios são uma camada por cima do rosto:
não mudam os olhos nem as expressões.
"""

import math
import re
from dataclasses import dataclass, field

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainterPath, QPen, QPolygonF

from ..ajustes import ZZZ_PERIODO as ZZZ_PERIOD, ZZZ_QUANTIDADE as ZZZ_COUNT

BODY_W, BODY_H = 120, 90
FRAME = QColor("#63e56f")
SHELL = QColor("#101512")
SCREEN = QColor("#171e19")
EYE = QColor("#3ee877")
SHINE = QColor("#c8ffd8")

ACESSORIOS = ("oculos", "gravata")
COR_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
COR_PADRAO_ACESSORIO = {"oculos": "#e8e8e8", "gravata": "#b3261e"}
PIJAMA = QColor("#3f7fe0")         # gorro e pijama de dormir
PIJAMA_CLARO = QColor("#cfe2ff")   # listras, barra e pompom


@dataclass(frozen=True)
class Aparencia:
    """Cores do corpo e acessórios de um pet. O padrão é o visual original (o do pet)."""
    moldura: QColor = field(default_factory=lambda: QColor(FRAME))
    casca: QColor = field(default_factory=lambda: QColor(SHELL))
    tela: QColor = field(default_factory=lambda: QColor(SCREEN))
    olho: QColor = field(default_factory=lambda: QColor(EYE))
    brilho: QColor = field(default_factory=lambda: QColor(SHINE))
    acessorios: tuple = ()             # ((nome, QColor), ...) na ordem em que são desenhados


CAMPOS_DE_COR = ("moldura", "casca", "tela", "olho", "brilho")


def aparencia_de(dados):
    """
    Monta a Aparencia a partir do "aparencia" do pet.json. Cor fora do formato #rrggbb e
    acessório desconhecido são ignorados (ficam com o padrão), como os outros campos do pet.
    """
    if not isinstance(dados, dict):
        return Aparencia()
    cores = {k: QColor(dados[k]) for k in CAMPOS_DE_COR
             if isinstance(dados.get(k), str) and COR_HEX.match(dados[k])}
    pedidos = dados.get("acessorios")
    acessorios = []
    if isinstance(pedidos, dict):
        for nome in ACESSORIOS:                         # ordem fixa: a gravata não cobre os óculos
            if nome in pedidos:
                cor = pedidos[nome]
                cor = cor if isinstance(cor, str) and COR_HEX.match(cor) else COR_PADRAO_ACESSORIO[nome]
                acessorios.append((nome, QColor(cor)))
    return Aparencia(**cores, acessorios=tuple(acessorios))


PADRAO = Aparencia()


def lerp_shape(current, target, k):
    """Interpola duas formas de olho: `k` entre 0 (atual) e 1 (alvo), para a transição ser suave."""
    return {key: current[key] + (target[key] - current[key]) * k for key in target}


def draw_face(p, shape, gaze=(0.0, 0.0), blink=1.0, emotion="observando", carinho=False, aparencia=PADRAO):
    """Desenha moldura + tela + olhos (+ acessórios) com centro na origem do painter."""
    a = aparencia
    p.setPen(QPen(a.moldura, 5))
    p.setBrush(a.casca)
    p.drawRoundedRect(QRectF(-BODY_W / 2, -BODY_H / 2, BODY_W, BODY_H), 20, 20)
    p.setPen(Qt.NoPen)
    p.setBrush(a.tela)
    p.drawRoundedRect(QRectF(-BODY_W / 2 + 11, -BODY_H / 2 + 11, BODY_W - 22, BODY_H - 22), 12, 12)
    dormindo = emotion == "dormindo"
    if dormindo:
        _pijama(p)
    for nome, cor in a.acessorios:
        if nome == "gravata":                          # por cima da tela, sempre dentro do contorno do corpo
            _gravata(p, cor)

    if carinho:
        # carinho: olhinhos fechados de felicidade, em arco para cima (^ ^)
        p.setPen(QPen(a.olho, 5, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for side in (-1, 1):
            cx, cy = side * 24, shape["dy"]
            p.drawArc(QRectF(cx - 15, cy - 8, 30, 22), 0, 180 * 16)
        p.setPen(Qt.NoPen)
    else:
        _olhos(p, shape, gaze, blink, emotion, a)
    for nome, cor in a.acessorios:
        if nome == "oculos":
            _oculos(p, cor)
    if dormindo:
        _gorro(p)


def _olhos(p, shape, gaze, blink, emotion, a):
    """Desenha os dois olhos: forma, piscada, brilho e direção do olhar."""
    gx, gy = gaze
    for side in (-1, 1):
        w = shape["w"]
        h = shape["h"] * blink
        if emotion == "curioso" and side == 1:
            h *= 1.15
        h = max(h, 3.0)
        cx = side * 24 + gx * 4
        cy = shape["dy"] + gy * 3
        top = cy - h / 2

        eye = QPainterPath()
        eye.addRoundedRect(QRectF(cx - w / 2, top, w, h), min(w, h) * 0.38, min(w, h) * 0.38)

        if blink > 0.5:
            outer_x = cx + side * w / 2
            inner_x = cx - side * w / 2
            lid = QPainterPath()
            lid.addPolygon(QPolygonF([
                QPointF(outer_x + side * 4, top - 40),
                QPointF(inner_x - side * 4, top - 40),
                QPointF(inner_x - side * 4, top + shape["inner"] * h),
                QPointF(outer_x + side * 4, top + shape["outer"] * h),
            ]))
            eye = eye.subtracted(lid)
            if shape["smile"] > 0.02:
                cut = QPainterPath()
                ch = h * shape["smile"] * 1.6
                cut.addEllipse(QRectF(cx - w * 0.75, top + h - ch * 0.45, w * 1.5, ch))
                eye = eye.subtracted(cut)

        p.setBrush(a.olho)
        p.drawPath(eye)

        if blink > 0.5 and h >= 8:                 # olho fechado não tem brilho
            p.save()
            p.setClipPath(eye)
            p.setBrush(a.brilho)
            sx = cx - w * 0.18 + gx * 3
            sy = top + h * (0.24 + max(shape["inner"], shape["outer"]) * 0.6) + gy * 2
            p.drawEllipse(QPointF(sx, sy), 3.6, 3.6)
            p.restore()



def _oculos(p, cor):
    """Armação por cima dos olhos: aro grosso em cima, fino embaixo, e a ponte no meio."""
    p.save()
    p.setBrush(Qt.NoBrush)
    for side in (-1, 1):
        lente = QRectF(side * 24 - 21, -25, 42, 52)
        vidro = QColor(cor)
        vidro.setAlpha(22)                              # um reflexo leve: o olho continua aparecendo
        p.setPen(Qt.NoPen)
        p.setBrush(vidro)
        p.drawRoundedRect(lente, 10, 10)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(cor, 2))
        p.drawRoundedRect(lente, 10, 10)
        p.setPen(QPen(cor, 5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(lente.left() + 4, lente.top()), QPointF(lente.right() - 4, lente.top()))
    p.setPen(QPen(cor, 3, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(-3, -18), QPointF(3, -18))       # ponte
    p.restore()


def _gravata(p, cor):
    """
    Gravata na frente do peito, dentro do contorno do corpo. Termina antes da borda de baixo para
    não cair na barra de tarefas quando ele anda sobre ela.
    """
    p.save()
    topo = BODY_H / 2 - 24                              # nó logo abaixo da tela, cola no contorno
    escura = cor.darker(140)
    p.setPen(QPen(escura, 1.2))
    p.setBrush(cor)
    p.drawPolygon(QPolygonF([QPointF(-4, topo), QPointF(4, topo), QPointF(3.5, topo + 6),
                             QPointF(-3.5, topo + 6)]))          # nó
    p.drawPolygon(QPolygonF([QPointF(-3, topo + 5), QPointF(3, topo + 5), QPointF(5.5, topo + 17),
                             QPointF(0, topo + 21), QPointF(-5.5, topo + 17)]))   # ponta
    p.setPen(QPen(escura, 1.5))
    p.drawLine(QPointF(-4, topo + 10), QPointF(4, topo + 8))                   # listra
    p.restore()


def _pijama(p):
    """Pijama listrado por cima do corpo (moldura e casca); a tela, com os olhos, fica de fora."""
    corpo = QPainterPath()
    corpo.addRoundedRect(QRectF(-BODY_W / 2 - 2.5, -BODY_H / 2 - 2.5, BODY_W + 5, BODY_H + 5), 22, 22)
    tela = QPainterPath()
    tela.addRoundedRect(QRectF(-BODY_W / 2 + 11, -BODY_H / 2 + 11, BODY_W - 22, BODY_H - 22), 12, 12)
    p.save()
    p.setClipPath(corpo.subtracted(tela))
    p.fillRect(QRectF(-BODY_W / 2 - 3, -BODY_H / 2 - 3, BODY_W + 6, BODY_H + 6), PIJAMA)
    p.setPen(QPen(PIJAMA_CLARO, 2))
    for x in range(-BODY_W // 2 + 4, BODY_W // 2, 12):
        p.drawLine(QPointF(x, -BODY_H / 2 - 3), QPointF(x, BODY_H / 2 + 3))
    p.restore()


def _gorro(p):
    """Gorro de dormir no topo da cabeça, com a ponta caída para a esquerda (os Zzz sobem pela direita)."""
    topo = -BODY_H / 2
    gorro = QPainterPath()
    gorro.moveTo(32, topo - 3)
    gorro.cubicTo(30, topo - 22, 12, topo - 37, -8, topo - 35)
    gorro.cubicTo(-28, topo - 33, -46, topo - 26, -54, topo - 10)
    gorro.cubicTo(-42, topo - 19, -35, topo - 17, -32, topo - 3)
    gorro.closeSubpath()
    p.save()
    p.setPen(QPen(PIJAMA.darker(130), 1.5))
    p.setBrush(PIJAMA)
    p.drawPath(gorro)
    p.setPen(Qt.NoPen)
    p.setBrush(PIJAMA_CLARO)
    p.drawRoundedRect(QRectF(-36, topo - 8, 72, 10), 5, 5)      # barra
    p.drawEllipse(QPointF(-55, topo - 7), 6, 6)                 # pompom
    p.restore()


def draw_zzz(p, cx, cy, now, cor=EYE):
    """Zs subindo do canto de cima do corpo, crescendo, balançando e sumindo."""
    for i in range(ZZZ_COUNT):
        t = ((now / ZZZ_PERIOD) + i / ZZZ_COUNT) % 1.0     # 0 nasce ... 1 some
        x = cx + BODY_W * 0.32 + 34 * t + 5 * math.sin(t * math.tau * 1.5)
        y = cy - BODY_H * 0.42 - 44 * t       # sobe até ~12 px do topo da janela
        size = 8 + 9 * t
        alpha = int(255 * min(1.0, t * 5) * (1.0 - t) ** 0.6)
        color = QColor(cor)
        color.setAlpha(alpha)
        p.save()
        p.translate(x, y)
        p.rotate(-12 + 10 * math.sin(t * math.tau))
        p.setPen(color)
        p.setFont(QFont("Consolas", int(size), QFont.Bold))
        p.drawText(QRectF(-20, -20, 40, 40), Qt.AlignCenter, "Z")
        p.restore()

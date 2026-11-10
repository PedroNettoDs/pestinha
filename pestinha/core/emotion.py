"""
EMOTION - da atividade dos neurônios motores para UMA emoção.

Cada motor empurra duas variáveis contínuas:
    valência  (-1 triste/bravo ... +1 feliz)
    ativação  (-1 calmo        ... +1 agitado)
Elas seguem o cérebro com atraso (emotion_tau) e a emoção é lida do
quadrante. Susto e drama são sobreposições curtas, disparadas por eventos.
"""

import math
import time

# motor -> (valência, ativação)
MOTOR_VECTORS = {
    "STARTLE": (-0.2, 1.0),
    "WATCH": (0.0, 0.3),
    "WANDER": (0.25, 0.55),
    "CHEER": (0.9, 0.8),
    "SETTLE": (0.6, -0.45),
    "DROWSE": (0.0, -0.8),
    "ANGRY": (-0.9, 0.9),
    "SAD": (-0.9, -0.6),
}

BASELINE_HZ = 0.5          # abaixo disso o motor não conta (ruído); em regime os motores ficam em 2-7 Hz
NEUTRAL_WEIGHT = 2.0       # "massa" do neutro: pouca atividade = observando
STARTLE_HZ = 7.0           # acima disso o susto passa na frente (troca de janela chega a ~13)
STARTLE_SECONDS = 1.2

# Forma dos olhos por emoção (unidades em px no corpo de 120x90).
#   w, h        tamanho do olho
#   inner/outer quanto da pálpebra desce no lado de dentro/fora (fração de h)
#   smile       olho "sorrindo" (corta a parte de baixo em arco)
#   dy          desloca os olhos para baixo
EYE_SHAPES = {
    "observando": dict(w=30, h=40, inner=0.14, outer=0.0, smile=0.0, dy=0.0),
    "contente":   dict(w=32, h=34, inner=0.0, outer=0.0, smile=0.36, dy=1.0),
    "feliz":      dict(w=34, h=36, inner=0.0, outer=0.0, smile=0.55, dy=-2.0),
    "curioso":    dict(w=30, h=46, inner=0.0, outer=0.08, smile=0.0, dy=-2.0),
    "bravo":      dict(w=34, h=36, inner=0.55, outer=0.0, smile=0.0, dy=2.0),
    "triste":     dict(w=28, h=34, inner=0.0, outer=0.5, smile=0.0, dy=7.0),
    "assustado":  dict(w=26, h=50, inner=0.0, outer=0.0, smile=0.0, dy=-3.0),
    "dramatico":  dict(w=38, h=52, inner=0.0, outer=0.22, smile=0.0, dy=0.0),
    "dormindo":   dict(w=32, h=4, inner=0.0, outer=0.0, smile=0.0, dy=8.0),     # olhinhos fechados
}

# Onde cada emoção cai no plano (valência, ativação). O rosto mistura as formas pela proximidade.
ANCHORS = {
    "observando": (0.0, 0.0),
    "contente": (0.55, -0.25),
    "feliz": (0.85, 0.6),
    "curioso": (0.0, 0.7),
    "bravo": (-0.8, 0.7),
    "triste": (-0.8, -0.5),
}


def shape_from_affect(valence, arousal):
    """Forma dos olhos como mistura das predefinidas, pela distância de (valência, ativação) a cada uma."""
    weights = {name: math.exp(-((valence - v) ** 2 + (arousal - a) ** 2) / 0.08)
               for name, (v, a) in ANCHORS.items()}
    total = sum(weights.values())
    return {key: sum(EYE_SHAPES[name][key] * w for name, w in weights.items()) / total
            for key in EYE_SHAPES["observando"]}


def classify(valence, arousal):
    """Dá nome à emoção a partir de valência (agradável ou não) e excitação (calmo ou agitado)."""
    if valence < -0.2:
        return "bravo" if arousal > 0.15 else "triste"
    if valence > 0.18:
        return "feliz" if arousal > 0.3 else "contente"
    if arousal > 0.22:
        return "curioso"
    return "observando"


# Árbitro: quando duas causas querem a cara ao mesmo tempo, vence a de maior prioridade.
# Uma causa de prioridade menor não interrompe uma maior enquanto a maior durar.
PRIORITY = {
    "dormindo": 50,     # sono: ninguém acorda o rosto no meio
    "assustado": 40,    # susto e acordar assustado
    "dramatico": 35,    # três dispensas seguidas
    "voo": 30,          # reflexo no ar depois de um arremesso
    "protesto": 20,     # manifestação, greve, revolução
    "carinho": 15,      # carinho fecha os olhinhos em contente
}
DEFAULT_PRIORITY = 20


class EmotionState:
    """Emoção atual do pet, suavizada no tempo: valência (humor) e excitação (energia)."""
    def __init__(self):
        """Começa neutro (valência e excitação zeradas)."""
        self.valence = 0.0
        self.arousal = 0.0
        self.current = "observando"
        self.since = time.monotonic()
        self.override = None
        self.override_until = 0.0
        self.override_priority = 0
        self._startled = False

    def force(self, emotion, seconds, now=None, priority=DEFAULT_PRIORITY):
        """Sobreposição curta. Devolve False se outra causa de prioridade maior está valendo."""
        now = time.monotonic() if now is None else now
        if self.override and now < self.override_until and priority < self.override_priority:
            return False
        self.override = emotion
        self.override_until = now + seconds
        self.override_priority = priority
        return True

    def update(self, motor_activity, dt, prof, now=None):
        """Atualiza valência e excitação a partir da atividade dos motores, suavemente."""
        total_v = total_a = 0.0
        weight = NEUTRAL_WEIGHT
        for motor, hz in motor_activity.items():
            w = max(0.0, hz - BASELINE_HZ)
            v, a = MOTOR_VECTORS.get(motor, (0.0, 0.0))
            total_v += w * v
            total_a += w * a
            weight += w
        target_v = total_v / weight
        target_a = total_a / weight

        k = 1.0 - math.exp(-dt / prof["emotion_tau"])
        self.valence += (target_v - self.valence) * k
        self.arousal += (target_a - self.arousal) * k

        now = time.monotonic() if now is None else now
        # susto é reflexo curto, na subida; só rearma quando o motor esfria (histerese)
        startle = motor_activity.get("STARTLE", 0.0)
        if startle >= STARTLE_HZ and not self._startled:
            self.force("assustado", STARTLE_SECONDS, now, PRIORITY["assustado"])
            self._startled = True
        elif startle < STARTLE_HZ * 0.3:
            self._startled = False

        if self.override and now < self.override_until:
            wanted = self.override
        else:
            self.override = None
            wanted = classify(self.valence, self.arousal)

        if wanted != self.current and (
            now - self.since >= prof["emotion_dwell"] or wanted in ("assustado", "dramatico")
        ):
            self.current = wanted
            self.since = now
        return self.current

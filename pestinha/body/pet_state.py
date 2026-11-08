"""
PET STATE - o que o pet está sentindo e mostrando, num lugar só.

Quem escreve aqui:
    app         emoção, tom motor, protesto, modo de rótulo
    behavior    olhar (gaze), tremor (shake), tontura, quando fica parado
    pet (input) carinho (esfregar o mouse), e o rosto em animação

Quem lê:
    pet (view)  desenha o rosto a partir deste estado
    behavior    decide o movimento a partir deste estado

Assim nenhum dos três precisa conhecer os outros atributos da janela.
"""

import time

from ..core.emotion import EYE_SHAPES
from ..core.motor import MotorTone
from ..ajustes import DURACAO_CARINHO as CARESS_HOLD, FELIZ_APOS_CARINHO



class PetState:
    """O que o pet está sentindo e mostrando agora: emoção, forma dos olhos, olhar, carinho, tontura e se está sentado."""
    def __init__(self):
        """Começa observando, com olhos normais e sem carinho."""
        self.emotion = "observando"
        self.affect = (0.0, 0.0)        # (valência, ativação) do cérebro: o rosto segue isso quando não está forçado
        self.forced = False             # sobreposição (sono, susto, drama, protesto): usa a forma fixa da emoção
        self.shape = dict(EYE_SHAPES["observando"])
        self.gaze = (0.0, 0.0)
        self.shake = 0.0
        self.tone = MotorTone()
        self.protest_stage = 0
        self.show_label = False
        self.allow_drag = True
        self.allow_poke = True
        self.blink_until = 0.0
        self.caress_until = 0.0
        self.feliz_ate = 0.0            # olhinhos fechados de felicidade, um pouco depois do carinho
        self.dizzy_until = 0.0
        self.pressing = False       # botão apertado em cima dele: início de um gesto
        self.at_desk = False
        self.desk_top = None        # y (na tela) da tampa do notebook quando ele está sentado: o corpo para ali
        self.castigo = False        # no cantinho do castigo: parado, sem passear

    def mark_caress(self, now=None):
        """Marca que ele está recebendo carinho agora (dura um instante)."""
        now = time.monotonic() if now is None else now
        self.caress_until = now + CARESS_HOLD
        self.feliz_ate = now + FELIZ_APOS_CARINHO

    def feliz_fechado(self, now=None):
        """Diz se ele está com os olhos fechados de felicidade (^ ^)."""
        return (time.monotonic() if now is None else now) < self.feliz_ate

    def caressing(self, now=None):
        """Diz se ele está recebendo carinho neste instante."""
        return (time.monotonic() if now is None else now) < self.caress_until

    def dizzy(self, now=None):
        """Diz se ele está tonto (depois de uma batida forte)."""
        return (time.monotonic() if now is None else now) < self.dizzy_until

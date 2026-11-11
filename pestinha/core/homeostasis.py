"""
HOMEOSTASIS - variáveis internas que o pet tenta manter em equilíbrio.

    energia      1 = descansado ... 0 = exausto. Gasta acordado (mais quando se
                 mexe ou está agitado), recupera dormindo.
    estimulação  1 = muita coisa acontecendo ... 0 = nada. Decai sozinha;
                 sobe com eventos, interação e travessuras.
    contato      necessidade de interação: 0 = satisfeito ... 1 = carente.
                 Cresce com o tempo; cutucar, arrastar e carinho satisfazem.

Os desequilíbrios entram na rede como sentidos internos (interocepção):
    pouca estimulação -> BOREDOM  (explora, fica curioso/brincalhão)
    muito carente     -> LONELY   (fica triste)
    pouca energia     -> FATIGUE  (fica sonolento; abaixo do limite, dorme)
Ou seja: nenhum timer manda ele explorar ou ficar triste; ele tenta
recuperar o equilíbrio.
"""

import time

from ..mathutil import clamp, valor_real
from ..store import read_json, write_json

SLEEP_BELOW = 0.18          # energia abaixo disso: dorme (se puder)
WAKE_ABOVE = 0.6            # energia acima disso: acorda sozinho (antes 0,95: dormia quase até o fim)
BORED_BELOW = 0.35          # estimulação abaixo disso: tédio
LONELY_ABOVE = 0.5          # contato acima disso: carência
TIRED_BELOW = 0.5           # energia abaixo disso: cansaço
TEDIO_PRESO = 3.0           # preso no canto, a estimulação cai 3x mais rápido
CARENCIA_PRESO = 2.0        # preso e ignorado, a carência cresce 2x mais rápido
ENGAGED_LEVEL = 0.6         # trabalhando de verdade, a estimulação sobe até aqui (não há tédio)
ENGAGED_RISE_S = 20.0       # tempo para chegar a esse nível

# quanto cada acontecimento estimula (+) e satisfaz o contato (-)
STIMULUS = {"app": 0.08, "novelty": 0.2, "poke": 0.15, "drag": 0.2, "throw": 0.35,
            "mischief": 0.25, "caress": 0.05}
CONTACT = {"poke": 0.15, "drag": 0.1, "throw": 0.1, "caress": 0.25, "dismiss": 0.05,
           "alfred": 0.5}      # você usou o Alfred (Painel, conversa, WhatsApp): ele foi notado


class Drives:
    """Necessidades internas do pet: energia (cansaço), estimulação (tédio) e contato (carência). Elas sobem e descem com o tempo e com o que você faz."""
    def __init__(self):
        """Começa com energia cheia, estimulação média e contato alto."""
        self.energy = 1.0
        self.stimulation = 0.6
        self.contact = 0.0

    # ---------------- acontecimentos ----------------

    def stimulate(self, kind, scale=1.0):
        """Uma travessura ou novidade aumenta a estimulação (o tédio diminui)."""
        self.stimulation = clamp(self.stimulation + STIMULUS.get(kind, 0.0) * scale)

    def touched(self, kind, scale=1.0):
        """Você deu atenção (carinho, cutucada): o contato sobe e a carência diminui."""
        self.contact = clamp(self.contact - CONTACT.get(kind, 0.0) * scale)

    # ---------------- tempo ----------------

    def update(self, dt, prof, asleep, moving, arousal, user_away, engaged=False, preso=False, visitado=False):
        """Um passo do tempo: cansa quando acordado e parado, recupera dormindo, e o tédio e a carência crescem sem atenção."""
        if asleep:
            self.energy = clamp(self.energy + dt / prof["sleep_recover"])
        else:
            effort = 1.0 + 1.5 * moving + max(0.0, arousal)
            self.energy = clamp(self.energy - dt * effort / prof["energy_span"])
        if engaged and not asleep:
            # trabalhar já é estímulo: sem eventos novos, a estimulação não cai e não vira tédio
            self.stimulation += (ENGAGED_LEVEL - self.stimulation) * min(1.0, dt / ENGAGED_RISE_S)
        else:
            tedio = TEDIO_PRESO if preso else 1.0          # no canto não acontece nada: o tédio vem rápido
            self.stimulation = clamp(self.stimulation - dt * tedio / prof["stim_decay"])
        # você longe: a falta é mais lenta (ele não "espera" você no banheiro); preso e sem visita, mais rápida
        falta = 0.3 if user_away else (CARENCIA_PRESO if preso and not visitado else 1.0)
        self.contact = clamp(self.contact + dt / prof["contact_span"] * falta)

    def channels(self):
        """Os três níveis (tédio, cansaço, carência) como intensidades de 0 a 1, para a rede."""
        return {
            "BOREDOM": clamp((BORED_BELOW - self.stimulation) / BORED_BELOW),
            "LONELY": clamp((self.contact - LONELY_ABOVE) / (1.0 - LONELY_ABOVE)),
            "FATIGUE": clamp((TIRED_BELOW - self.energy) / TIRED_BELOW),
        }

    def sleepy(self):
        """Diz se a energia está baixa o bastante para ele querer dormir."""
        return self.energy < SLEEP_BELOW

    def rested(self):
        """Diz se a energia já está alta o bastante para acordar."""
        return self.energy >= WAKE_ABOVE

    def describe(self):
        """Texto curto com os três níveis (para o log)."""
        return f"energia {self.energy:.2f}  estimulação {self.stimulation:.2f}  contato {self.contact:.2f}"

    # ---------------- persistência ----------------

    def save(self, path):
        """Grava energia, estimulação e contato em drives.json."""
        data = {"energy": self.energy, "stimulation": self.stimulation,
                "contact": self.contact, "saved_at": time.time()}
        write_json(path, data)

    def load(self, path, prof):
        """O tempo fechado conta como sono: volta descansado, um pouco carente."""
        data = read_json(path, default=None)
        if not isinstance(data, dict):
            return False
        try:
            elapsed = max(0.0, time.time() - valor_real(data.get("saved_at", time.time()), 0.0, 1e13))
            energy = valor_real(data.get("energy", 1.0), 0.0, 1.0)
            stimulation = valor_real(data.get("stimulation", 0.6), 0.0, 1.0)
            contact = valor_real(data.get("contact", 0.0), 0.0, 1.0)
        except (TypeError, ValueError):
            return False                        # arquivo com tipos errados: fica com os valores iniciais
        self.energy = clamp(energy + elapsed / prof["sleep_recover"])
        self.stimulation = clamp(stimulation - elapsed / prof["stim_decay"])
        self.contact = clamp(contact + 0.3 * elapsed / prof["contact_span"])
        return True

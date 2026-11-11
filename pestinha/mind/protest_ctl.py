"""
PROTEST CONTROLLER - liga o protesto (core/protesto.py) à cena: cartaz, estágio, repressão.

O core/protesto.py decide a insatisfação e o estágio. Este controlador cuida do que
aparece na tela: o cartaz preso no pet, a bandeja da revolução, o cartaz
que volta maior depois de arrancado e o cartaz de acordo ou desistência.
"""

from ..log import log
import math
import time

from ..ajustes import TEMPO_CARTAZ_FIM as END_SIGN_SECONDS
from ..ajustes import INSATISFACAO_MAXIMA
from ..core.protesto import STAGE_NAMES
from ..world.cartazes import FlagThing, criar_cartaz


DEVER_VOLTA_S = 120.0        # s até o cartaz do dever voltar depois que você o fecha


class ProtestController:
    """Liga o protesto à cena: mostra o cartaz preso no pet, a bandeja da revolução e as bolinhas de papel."""
    def __init__(self, protest, body, behavior, senses, drives, state, debug):
        """Guarda o estado do protesto e o que ele precisa mexer (corpo, comportamento, sentidos, necessidades)."""
        self.protest = protest
        self.body = body
        self.behavior = behavior
        self.senses = senses
        self.drives = drives
        self.state = state          # PetState: protest_stage é espelhado aqui
        self.debug = debug
        self.visivel = True         # o cartaz novo nasce com a visibilidade da sessão

    @property
    def stage(self):
        """Estágio atual do protesto (0 em paz, 4 revolução)."""
        return self.protest.stage

    def sign_windows(self):
        """Janelas de cartaz abertas agora (para o app não contar essas janelas como 'de outros programas')."""
        return [self.protest.sign] if self.protest.sign is not None else []

    # ---------------- estágios ----------------

    def tick(self, dt, tone, prof, caressing, now, lonely=0.0, negligencia=None):
        """Integra a intensidade do sentimento. Devolve (antigo, novo) quando o estágio muda."""
        if self.protest.kind == "dever":                 # segue o que o Alfred informa; sem Alfred, passa
            self.protest.motivo = negligencia["texto"] if negligencia else ""
            return self.protest.update(dt, 0.0, prof, False, now, alvo=negligencia["nivel"] if negligencia else 0.0)
        if self.protest.kind == "tristeza":
            rate = tone.r["SAD"] + 0.5 * lonely          # triste + sozinho por muito tempo
            prof = dict(prof, grievance_up=prof["sad_up"], grievance_down=prof["sad_down"],
                        stage_up=prof["sad_stage_up"])
        else:
            rate = tone.r["ANGRY"] + 0.5 * tone.r["SAD"]  # raiva
        return self.protest.update(dt, rate, prof, caressing, now)

    def provoke(self, amount):
        """Algo que o deixa mais insatisfeito (ex.: arrancaram o notebook dele)."""
        self.protest.grievance = min(INSATISFACAO_MAXIMA, self.protest.grievance + amount)

    def on_stage(self, old, new):
        """Mudou de estágio: tira o cartaz antigo. Voltando à calma, mostra um cartaz de fim; senão, solta o que ele carregava e prepara o cartaz do novo estágio."""
        self.drop_sign()
        now = time.monotonic()
        if new == 0:
            by_caress = now - self.protest.last_caress < 5.0
            self.protest.end_until = now + END_SIGN_SECONDS      # antes de mostrar: senão some na hora
            self.show(criar_cartaz(self.protest.escolher_cartaz(fim_por_carinho=by_caress)))
        else:
            self.protest.respawn_at = now           # o cartaz do estágio novo sobe no próximo quadro
            self.behavior.drop_carried()
        if self.debug():
            extra = f" (revolução nº {self.protest.revolutions})" if new == 4 else ""
            log(f"[protesto] {STAGE_NAMES[old]} -> {STAGE_NAMES[new]}{extra}  "
                  f"insatisfação {self.protest.grievance:.2f}")

    def on_sign_clicked(self, sign):
        """Fechar o cartaz é repressão: ele fica mais bravo e volta maior."""
        if sign is not self.protest.sign:
            return
        self.drop_sign()
        if self.protest.kind == "dever":
            if self.protest.stage:                  # "como queira": sai sem reprimir e volta depois
                self.protest.respawn_at = time.monotonic() + DEVER_VOLTA_S
            return
        if self.protest.stage == 0 or self.protest.kind == "tristeza":
            return                                  # cartaz de fim, ou tristeza: só fecha, não reprime
        self.protest.repressed()
        self.senses.dismissed()
        self.drives.touched("dismiss")
        self.protest.respawn_at = time.monotonic() + 3.0
        if self.debug():
            log(f"[protesto] cartaz arrancado! insatisfação {self.protest.grievance:.2f}")

    # ---------------- cena ----------------

    def show(self, sign):
        """Mostra um cartaz novo, preso no pet."""
        sign.clicked.connect(self.on_sign_clicked)
        self.protest.sign = sign
        self.carry(time.monotonic(), asleep=False)
        sign.setVisible(self.visivel)

    def drop_sign(self):
        """Tira o cartaz que está sendo mostrado."""
        sign = self.protest.sign
        self.protest.sign = None
        if sign is not None:
            sign.close()
            sign.deleteLater()

    def carry(self, now, asleep):
        """O cartaz vai preso em cima dele; a bandeja, ao lado. Some ao dormir."""
        pr = self.protest
        if pr.sign is None and pr.stage and pr.respawn_at and now >= pr.respawn_at and not asleep:
            pr.respawn_at = None
            self.show(criar_cartaz(pr.escolher_cartaz()))
        if pr.stage == 0 and pr.sign is not None and now > pr.end_until:
            self.drop_sign()
            return
        sign = pr.sign
        if sign is None:
            return
        if asleep:
            self.drop_sign()
            pr.respawn_at = now
            return
        body = self.body
        _ex, ey = body.extents()
        top = body.y - ey
        if isinstance(sign, FlagThing):
            sign.place(body.x + 30 - 10 + sign.width() / 2, top + 24 - sign.height() / 2)
        else:
            sign.tilt = 7.0 * math.sin(now * 6.0) if pr.stage == 2 else 0.0
            sign.place(body.x, top + 8 - sign.height() / 2)
        sign.update()

    def set_visible(self, visible, asleep):
        """Mostra ou esconde o cartaz junto com o pet (não aparece se ele estiver dormindo)."""
        self.visivel = visible and not asleep
        if self.protest.sign is not None:
            self.protest.sign.setVisible(self.visivel)

    def save(self):
        """Grava o estado do protesto no arquivo do pet."""
        self.protest.save()

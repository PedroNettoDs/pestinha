"""
SLEEP - quando ele dorme, quando acorda, e o que acontece ao adormecer.

Dormir é decisão da energia (homeostase). As exceções: de madrugada, sem nada do
Alfred em andamento nem na fila, e depois de uma hora sem você mexer no computador,
ele dorme mesmo descansado. Ele só adormece
apoiado, sem ser segurado, sem voar, sem missão e fora de protesto ativo
(indignado não dorme). Ao adormecer, consolida a memória episódica.

Não acorda sozinho: só quando o Alfred cola um post-it (recado, dose ou aviso) ou
quando você o cutuca, arrasta ou arremessa. Acordado, fica um tempo de pé antes de
poder dormir de novo.
"""

from datetime import datetime

from ..ajustes import MADRUGADA, VIGILIA_APOS_SUSTO
from ..log import log
from ..core.emotion import PRIORITY


def noite_de_sono(estado, hora=None):
    """Diz se é madrugada e o Alfred não tem nada em andamento nem na fila (`estado` é o retrato dele)."""
    hora = datetime.now().hour if hora is None else hora
    return MADRUGADA[0] <= hora < MADRUGADA[1] and not estado.agora and not estado.fila


class SleepController:
    """Quando ele dorme e acorda: dorme se estiver cansado, no chão e sem estar em protesto ou em missão."""
    def __init__(self, emotion, drives, memory, debug):
        """Guarda a emoção, as necessidades e a memória."""
        self.emotion = emotion
        self.drives = drives
        self.memory = memory
        self.debug = debug          # função -> bool: imprime no terminal só no modo teste
        self.asleep = False
        self._acordou = False       # acabou de acordar: o próximo passo marca a vigília
        self.vigilia_ate = 0.0      # até quando ele não volta a dormir (acabou de ser acordado)

    def can_sleep(self, body, in_flight, protest_stage, mission, noite=False):
        """Diz se ele pode dormir agora (cansado, no chão, sem ser segurado, sem protesto forte e sem missão)."""
        return ((self.drives.sleepy() or noite) and body.grounded and not body.held and not in_flight
                and protest_stage < 2 and not mission
                and self.emotion.current not in ("assustado", "dramatico"))

    def tick(self, now, body, in_flight, protest_stage, mission, noite=False):
        """Um passo: dorme quando pode e continua dormindo até alguém acordá-lo (`wake`). `noite` (madrugada sem
        trabalho, ou você longe do computador) o faz dormir mesmo descansado."""
        if self._acordou:
            self._acordou = False
            self.vigilia_ate = now + VIGILIA_APOS_SUSTO
        if self.asleep:
            self.emotion.force("dormindo", 0.3, now, PRIORITY["dormindo"])
        elif now >= self.vigilia_ate and self.can_sleep(body, in_flight, protest_stage, mission, noite):
            self.fall_asleep()

    def fall_asleep(self):
        """Adormece e consolida: refaz as preferências a partir dos episódios."""
        self.asleep = True
        prefs = self.memory.consolidate()
        if self.debug():
            log(f"[sono] dormiu ({self.drives.describe()})")
            for ctx, action, mean, n in prefs:
                log(f"[sono]   {ctx} -> {action}: {mean:+.2f} ({n:.0f} episódios)")

    def wake(self, startled):
        """Acorda: se foi um susto, ele fica assustado; senão (post-it do Alfred), acorda calmo."""
        self.asleep = False
        self._acordou = True
        if startled:
            self.emotion.force("assustado", 1.2, priority=PRIORITY["assustado"])    # acordou no susto
        if self.debug():
            how = "no susto" if startled else "com um post-it"
            log(f"[sono] acordou {how} ({self.drives.describe()})")

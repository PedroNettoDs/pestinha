"""
INTERAÇÃO - o que você faz com o pet: cutucar, arrastar, arremessar, dispensar travessuras,
os comandos do menu do botão direito e o notebook.

Cada interação vira sinal para a rede (sentidos), homeostase, condicionamento e memória.
Pausado ou desligado, as interações não mexem no estado (ver SessaoMixin._congelado).
Mixin de PestinhaApp: usa os atributos criados em PestinhaApp.__init__.
"""

from ..log import log
import time
from PySide6.QtWidgets import QMenu
from ..body.pet import cursor_pos
from ..ui.fila_alfred import preencher_menu
from ..ajustes import (
    INSATISFACAO_NOTEBOOK,
    COOLDOWN_CUTUCADA as POKE_COOLDOWN,
    ESPERA_MEDIDA_CUTUCADA as POKE_PROBE,
    HZ_RESPOSTA_CHEIA as POKE_FULL_HZ,
    RESPOSTA_MINIMA as POKE_MIN_RESPONSE,
)


class InteracaoMixin:
    """Ações do usuário sobre o pet: cutucar, arrastar, arremessar, dispensar travessuras e o menu do botão direito. Vira atributo de PestinhaApp."""
    def on_poke(self):
        """Você cutucou o pet: ele reage e a rede recebe o toque (ignorado na pausa)."""
        if self._congelado():
            return
        now = time.monotonic()
        if now - self.last_poke < POKE_COOLDOWN:
            return
        self.sad.grievance = max(0.0, self.sad.grievance - 0.25)     # cutucar alegra um pouco
        self.last_poke = now
        self.conditioning.outcome(now)
        self.senses.poke()
        self.timeline.note_interaction()
        self.drives.stimulate("poke")
        self.drives.touched("poke")
        self.memory.on_interaction()
        if self.asleep:
            self.sleep.wake(startled=True)
        # a reação NÃO é fixa: mede-se o que a rede fez com a cutucada (ver poke_reflex)
        self.poke_probe = (now + POKE_PROBE, self.brain.motor_activity()["CHEER"])

    def poke_reflex(self, delta_hz):
        """
        Tamanho da reação = aumento real de CHEER causado pela cutucada.
        Com cutucadas repetidas a sinapse de POKE habitua e a resposta encolhe:
        pulo grande, pulo menor, só os olhos, quase nada. Volta depois de minutos.
        """
        self.poke_probe = None
        response = max(0.0, min(1.0, delta_hz / POKE_FULL_HZ))
        if self.protest.stage == 3:
            response *= 0.2                         # em greve: mal responde
        self.last_poke_response = response
        body = self.pet.body
        if response >= POKE_MIN_RESPONSE and body.grounded:
            body.jump(0.0, -(150.0 + 650.0 * response))
        else:
            self.pet_state.blink_until = time.monotonic() + 0.13       # só pisca e olha
            cx, cy = cursor_pos()
            self.behavior.look_at(cx, cy, time.monotonic())
        if self.debugging():
            eff = self.brain.efficacy()["POKE"]
            log(f"[cutucada] resposta da rede {response:.2f} "
                  f"(+{delta_hz:.1f} Hz em CHEER, eficácia POKE {eff:.2f})")

    def on_drag_started(self):
        """Você pegou o pet: ele sente o arraste e a insatisfação baixa um pouco (você está interagindo)."""
        if self._congelado():
            return
        self.sad.grievance = max(0.0, self.sad.grievance - 0.1)
        self.conditioning.outcome(time.monotonic())
        self.senses.set_dragging(True)
        self.timeline.note_interaction()
        self.drives.stimulate("drag")
        self.drives.touched("drag")
        self.memory.on_interaction()
        if self.asleep:
            self.sleep.wake(startled=True)

    def on_thrown(self, speed):
        """Você arremessou o pet: a velocidade vira intensidade do arremesso; ele não aprende com isso na pausa."""
        if self._congelado():
            return
        self.conditioning.outcome(time.monotonic())
        self.senses.thrown(min(1.0, speed / 2000.0))
        self.timeline.note_interaction()
        self.drives.stimulate("throw")
        self.drives.touched("throw")
        self.in_flight = True

    def on_dismissed(self, thing, elapsed):
        """Você dispensou uma travessura: ela some, e o tempo até você fechar vira aprendizado (fechar rápido é pior)."""
        if self._congelado():
            return                                   # o objeto some, mas não vira aprendizado na pausa
        self.mischief_ctl.on_dismissed(thing, elapsed, self.prof, time.monotonic())

    def arrancar_notebook(self, now):
        """Arrancaram o notebook dele: ele levanta e fica bravo ou triste, conforme o pet."""
        self.mesa.levantar_arrancado(now)
        self.senses.dismissed()                    # a dispensa entra na rede como frustração
        alvo = self.sad_ctl if self.reacao_notebook == "triste" else self.protest_ctl
        alvo.provoke(INSATISFACAO_NOTEBOOK)
        if self.debugging():
            log(f"[notebook] arrancado: reação {self.reacao_notebook}")

    def show_pet_menu(self, pos):
        """Mostra o menu do botão direito no pet; cada item fica desativado se não fizer sentido agora."""
        menu = QMenu()
        perms = self.perms

        def item(text, fn, enabled=True):
            """Cria um item do menu; `enabled=False` deixa o item visível mas sem ação."""
            act = menu.addAction(text)
            act.setEnabled(enabled)
            act.triggered.connect(fn)

        item("Cutucar", self.menu_poke, perms["cutucar"])
        item("Dar carinho", self.menu_caress, perms["carinho"])
        menu.addSeparator()
        item("Jogar a bolinha perto dele", self.menu_place_ball, perms["bolinha"])
        item("Guardar a bolinha", self.menu_store_ball, perms["bolinha"] and not self.ball_stored)
        menu.addSeparator()
        item("Pedir para dormir", self.menu_sleep, not self.asleep)
        item("Pedir para trabalhar", self.menu_pedir_trabalho)
        item("Mostrar o notebook" if self.mesa.escondido else "Esconder o notebook",
             self.menu_alternar_notebook)
        item("Fazer uma travessura agora", self.menu_mischief, perms["travessuras"])
        if self.alfred.ligado:
            menu.addSeparator()
            preencher_menu(menu.addMenu("Alfred: trabalhar em"), self.alfred)
            item("Fila do Alfred", lambda: self.floats.toggle("alfred"))
        menu.addSeparator()
        item("Cantinho do castigo", lambda: self.castigo.toggle(self.bounds()))
        item("Painel de protesto", lambda: self.floats.toggle("greve"))
        item("Monitor neural", lambda: self.floats.toggle("neural"))
        item("Configurações...", self.open_settings)
        menu.addSeparator()
        item("Esconder (volta pela bandeja)", self.toggle_hidden)
        item("Fechar", self.menu_close)
        menu.exec(pos)

    def menu_poke(self):
        """Menu: 'Cutucar' (ignora o intervalo mínimo entre cutucadas)."""
        self.last_poke = 0.0
        self.on_poke()

    def menu_caress(self):
        """Menu: 'Fazer carinho' (conta como carinho na rede, se não estiver pausado)."""
        if self._congelado():
            return
        self.pet_state.mark_caress()
        self.drives.touched("caress")
        self.memory.on_interaction()
        self.timeline.note_interaction()

    def menu_place_ball(self):
        """Menu: 'Pôr a bolinha' (coloca a bolinha perto do pet, no chão)."""
        self.ball_stored = False
        self.ball.body.x = self.pet.body.x + 130
        self.ball.body.y = self.bounds()[3] - 40
        self.ball.body.vx = self.ball.body.vy = 0.0
        self.update_visibility()

    def menu_store_ball(self):
        """Menu: 'Guardar a bolinha' (some com a bolinha até você pedir de novo)."""
        self.ball_stored = True
        self.update_visibility()

    def menu_sleep(self):
        """Menu: 'Dormir' (baixa a energia: ele cochila em vez de ficar acordado)."""
        if self._congelado():
            return
        self.drives.energy = min(self.drives.energy, 0.1)

    def menu_mischief(self):
        """Menu: 'Aprontar' (pede uma travessura agora)."""
        self.mischief_ctl.pedir(time.monotonic())

    def menu_alternar_notebook(self):
        """Menu: mostra ou esconde o notebook; sem o notebook, ele não pode sentar nele."""
        self.mesa.alternar_notebook()
        self.pet_state.at_desk = self.mesa.sentado
        if not self.mesa.sentado:
            self.pet_state.desk_top = None

    def menu_pedir_trabalho(self):
        """Menu: 'Pedir para trabalhar' (ele pode aceitar, ou recusar com frustração)."""
        self.mesa.pedir(time.monotonic())

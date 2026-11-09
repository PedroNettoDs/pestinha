"""
BEHAVIOR - como a rede e a emoção viram movimento.

Divisão de trabalho (v7.1):
    emoção          ALTO nível: para onde ir (cursor, cantinho, longe), missões
    tom motor       COMO: velocidade, pulinhos, giros, tremor, olhar, hesitação
                    (motor.py lê direto as populações motoras da rede)

Ele não tem pernas: "andar" é deslizar, "pular" é um impulso.
Estados de missão (entregar meme, atravessar a tela) passam na frente do
passeio normal; cair, ser segurado ou estar tombado passam na frente de tudo.
"""

import math
import random

from ..core.physics import CLOSE_BUTTONS, GRAVITY, wrap_angle

STILL = ("assustado", "dramatico", "dormindo")     # emoções que não passeiam
GLANCE_EVERY = 1.2          # s: a cada olhada, decide se fixa o cursor ou olha em volta

LOOK_SECONDS = 2.5          # quanto tempo ele encara a janela que você acabou de abrir
MAX_CLIMB = 800             # px: altura máxima de um pulo até uma janela

CURIOUS_DISTANCE = 170      # o curioso chega perto do cursor, mas não em cima
DELIVER_TIMEOUT = 14.0
CARRY_GAP = 14
CROSS_SCREEN_CHANCE = 0.3  # em parte dos passeios, visita deliberadamente um monitor lateral
CROSS_SCREEN_SPEED = 180.0
WINDUP_SECONDS = 0.35       # antes de um pulo com giro, ele se prepara: inclina para o lado oposto
WINDUP_LEAN = 22.0          # graus dessa inclinação
LEAN_SPEED = 10.0           # 1/s: quão rápido a inclinação segue o alvo
SPIN_DEGREES = 720.0        # giro do pulo: duas voltas, no sentido escolhido


class Behavior:
    """Comportamento do corpo: para onde olha, para onde anda, quando pega ou entrega objetos. Ele só executa; quem decide é a rede."""
    def __init__(self, body, state, mischief):
        """Guarda o corpo, o estado do pet e a lista de objetos de travessura."""
        self.body = body
        self.state = state          # PetState: gaze, shake, tontura, carinho, tom motor
        self.mischief = mischief
        self.target_x = None
        self.next_roam = 0.0
        self.crossing_screen = False
        self.emotion = "observando"
        self.tipped_since = None
        self.mission = None         # ("deliver", thing, x, prazo) | ("cross", x, prazo)
        self.look = None            # (x, y, até) ponto que ele encara
        self.tone = state.tone      # o app atualiza com a rede a cada 100 ms
        self.glance = None          # ponto qualquer quando não está fixando o cursor
        self.state.protest_stage = 0      # 0 em paz; 1 reclamação; 2 manifestação; 3 greve; 4 revolução
        self.toy = None             # (x, y) da bolinha, quando ela está na tela
        self.ball = None            # a bolinha (toy.Ball), ligada pelo app
        self.play = None            # Play: estilo de brincadeira do pet, ligado pelo app
        self.play_pull = 0.0        # 0..1, da rede: quanto ele quer brincar agora (ver mesa.pull)
        self.canto = False          # o neurônio CANTO está disparando: ele vai para o cantinho
        self.fuga_alvo = None       # x para onde ele está fugindo do cantinho (None: não está fugindo)
        self.march_dir = 1
        self.next_glance = 0.0
        self.screen_areas = []      # áreas de todos os monitores, atualizadas pelo app
        self.windup = None          # (até, sentido, vx, vy): preparo de um pulo com giro, em andamento

    def look_at(self, x, y, now):
        """Olha para um ponto da tela por alguns segundos."""
        self.look = (x, y, now + LOOK_SECONDS)

    def on_emotion(self, emotion, now):
        """Troca de emoção: ajusta o olhar e os gestos de cada emoção."""
        if emotion == self.emotion:
            return
        self.emotion = emotion
        self.next_roam = now     # reage na hora
        if emotion == "assustado" and self.body.grounded:
            power = self.tone.startle_power()       # pulo do tamanho do disparo de STARTLE
            self.body.jump(random.uniform(-150, 150), -power, random.uniform(-200, 200))
        elif emotion == "dramatico" and self.body.grounded:
            self.body.jump(0.0, -500.0, random.choice((-1, 1)) * 540.0)

    def start_mission(self, plan, bounds, cursor, now):
        """Começa uma missão (levar um objeto para algum lugar), conforme o plano que a rede escolheu."""
        kind, thing = plan
        left, _top, right, _bottom = bounds
        margin = 140
        far_x = right - margin if self.body.x < (left + right) / 2 else left + margin
        if kind == "cross":
            self.mission = ("cross", far_x, now + DELIVER_TIMEOUT)
        elif kind == "deliver":
            # leva o objeto até um ponto longe do cursor
            options = [random.uniform(left + margin, right - margin) for _ in range(6)]
            x = max(options, key=lambda ox: abs(ox - cursor[0]))
            direction = 1 if x > self.body.x else -1
            ex, ey = self.body.extents()
            thing.carried = True
            self.mischief.attach(
                thing,
                self.body.x - direction * (ex + thing.width() / 2 + CARRY_GAP),
                self.body.y + ey - thing.height() / 2,
            )
            self.mission = ("deliver", thing, x, now + DELIVER_TIMEOUT)

    def drop_carried(self):
        """Solta o objeto que ele estava carregando (se houver)."""
        if self.mission and self.mission[0] == "deliver":
            thing = self.mission[1]
            if thing in self.mischief.things:
                self.mischief.release(thing)
        self.mission = None

    def tick(self, dt, now, cursor, bounds, prof, platforms=()):
        """Um passo do comportamento: anda, mexe na bolinha e reage ao cursor, respeitando as plataformas."""
        body = self.body
        st = self.state

        # olhar: janela recém-aberta > cursor; virado, olha para "cima" do mundo (indignado)
        if self.look and now > self.look[2]:
            self.look = None
        dizzy = st.dizzy(now)
        if dizzy:
            gaze = (math.cos(now * 14.0), math.sin(now * 14.0))     # olhinhos rodando
        elif body.upright() and self.state.protest_stage == 3 and self.emotion == "triste":
            gaze = (0.0, 0.9)                           # abandonado: olha para o chão
        elif body.upright() and self.state.protest_stage == 3:
            side = 1 if cursor[0] < body.x else -1          # greve: vira o rosto para longe de você
            gaze = (side * 0.9, 0.4)
        elif body.upright() and self.state.protest_stage in (1, 4):
            dx, dy = cursor[0] - body.x, cursor[1] - body.y  # reclamação/revolução: encara você
            dist = math.hypot(dx, dy) or 1.0
            gaze = (dx / dist, dy / dist)
        elif body.upright():
            if now >= self.next_glance:                 # WATCH alto: fixa o cursor; baixo: olha em volta
                self.next_glance = now + GLANCE_EVERY
                self.glance = None if random.random() < self.tone.watch() else (
                    body.x + random.uniform(-600, 600), body.y + random.uniform(-400, 150))
            point = self.look[:2] if self.look else (self.glance or cursor)
            dx, dy = point[0] - body.x, point[1] - body.y
            dist = math.hypot(dx, dy) or 1.0
            gaze = (dx / dist, dy / dist)
            if self.emotion == "triste":
                gaze = (gaze[0] * 0.3, 0.8)
        else:
            a = math.radians(body.angle)
            gaze = (-math.sin(a), -math.cos(a))
        st.gaze = gaze
        st.shake = self.tone.shake()

        if body.held:
            self.drop_carried()
            self.tipped_since = None
            self.windup = None
            st.lean_target = 0.0
            return

        # objeto carregado acompanha (e solta se o pet cair/voar)
        if self.mission and self.mission[0] == "deliver":
            thing = self.mission[1]
            if thing not in self.mischief.things:
                self.mission = None
            elif not body.grounded and abs(body.vy) > 600:
                self.drop_carried()
            else:
                direction = 1 if self.mission[2] > body.x else -1
                ex, ey = body.extents()
                self.mischief.follow(
                    thing,
                    body.x - direction * (ex + thing.width() / 2 + CARRY_GAP),
                    body.y + ey - thing.height() / 2,
                    dt,
                )

        if not body.grounded:
            return

        # fugindo do cantinho: o destino da fuga vale até ele chegar (nada sobrescreve a direção)
        if self.fuga_alvo is not None:
            if abs(body.x - self.fuga_alvo) < 20:
                self.fuga_alvo = None
            else:
                self._slide_to(self.fuga_alvo, 160.0)
                return

        # no cantinho do castigo: parado; missões pendentes são canceladas e protesto não move
        if st.castigo:
            self.drop_carried()
            body.vx = 0.0
            self.next_roam = now + 1.0
            return

        # tonto, dormindo ou ganhando carinho: fica paradinho
        if st.at_desk:                                  # sentado no notebook: trabalha, sem passear
            body.vx = 0.0
            st.gaze = (0.0, 0.9)
            self.next_roam = now + 1.0
            return
        if dizzy or self.emotion == "dormindo" or (st.caressing(now) and not self.mission):
            body.vx = 0.0
            self.next_roam = now + 1.0
            return

        # tombado: tenta se endireitar (triste prefere ficar caído)
        if not body.upright():
            if self.tipped_since is None:
                self.tipped_since = now
            if self.emotion != "triste" and now - self.tipped_since > prof["righting_after"]:
                turn = -wrap_angle(body.angle)
                body.jump(0.0, -650.0, turn * 1.6)
                self.tipped_since = None
            return
        self.tipped_since = None

        left, _top, right, _bottom = bounds

        # neurônio CANTO disparando (tristeza): vai para o cantinho e fica lá
        if self.canto:
            corner = left + 90 if body.x - left < right - body.x else right - 90
            if abs(body.x - corner) > 12:
                self._slide_to(corner, 110.0)
            else:
                body.vx = 0.0
            return

        # missões
        if self.mission:
            if self.mission[0] == "deliver":
                target, deadline = self.mission[2], self.mission[3]
                if abs(body.x - target) < 20 or now > deadline:
                    self.drop_carried()
                    self.next_roam = now + 2.0
                else:
                    self._slide_to(target, 190.0 * max(0.5, self.tone.vigor()))
                    return
            elif self.mission[0] == "cross":
                target, deadline = self.mission[1], self.mission[2]
                if abs(body.x - target) < 20 or now > deadline:
                    self.mission = None
                    self.next_roam = now + 2.0
                else:
                    self._slide_to(target, 260.0)
                    return

        if self.state.protest_stage:
            self._protest_move(dt, now, left, right)
            return

        # brincar com a bolinha (chutar ou arremessar, conforme o estilo do pet)
        if self.play is not None and self.ball is not None and self.emotion not in STILL and not st.at_desk:
            if self.play.tick(now, body, self.ball, cursor, self.emotion, self.play_pull):
                body.jump(0.0, -180.0)              # pulinho de quem acabou de chutar

        # antecipação: antes de girar, ele se inclina para o lado oposto e só então pula
        st.lean += (st.lean_target - st.lean) * min(1.0, dt * LEAN_SPEED)
        if self.windup is not None:
            fim, sentido, vx, vy = self.windup
            if self.emotion in STILL or not body.grounded:
                self.windup = None                  # o preparo cancela se a cabeça muda ou ele sai do chão
                st.lean_target = 0.0
            elif now < fim:
                st.lean_target = -sentido * WINDUP_LEAN
                return
            else:
                self.windup = None
                st.lean_target = 0.0
                body.jump(vx, vy, sentido * SPIN_DEGREES)
                return

        # passeio: a emoção escolhe o destino, o tom motor escolhe o jeito
        tone = self.tone
        if self.emotion in STILL:
            return
        if now >= self.next_roam and not self.crossing_screen:
            self.next_roam = now + random.uniform(*prof["roam_interval"]) * tone.roam_scale()
            self.target_x = self._pick_target(cursor, left, right)
            self.crossing_screen = bool(
                self.target_x is not None and not (left + 80 <= self.target_x <= right - 80)
            )
            if platforms and random.random() < tone.climb_chance() and self._jump_to_window(platforms):
                return
            if random.random() < tone.hop_chance():
                vy = -tone.hop_power() * random.uniform(0.85, 1.15)
                if random.random() < tone.spin_chance():
                    self.windup = (now + WINDUP_SECONDS, random.choice((-1, 1)), body.vx, vy)
                else:
                    body.jump(body.vx, vy)
                return

        if self.target_x is not None:
            chegou = abs(body.x - self.target_x) < 12
            hesitou = not self.crossing_screen and random.random() < tone.hesitation() * dt
            if chegou or hesitou:
                self.target_x = None            # chegou, ou hesitou no meio (curioso com sono)
                self.crossing_screen = False
            else:
                speed = max(CROSS_SCREEN_SPEED, tone.speed()) if self.crossing_screen else tone.speed()
                self._slide_to(self.target_x, speed)

    def walk_to(self, x, speed):
        """Anda até x (usado por quem decide para onde ele vai, como a fuga do cantinho)."""
        self._slide_to(x, speed)

    def _protest_move(self, dt, now, left, right):
        """Marcha (2 e 4), greve no cantinho (3), ou parado encarando (1)."""
        body = self.body
        stage = self.state.protest_stage
        if stage == 1:
            body.vx = 0.0
            return
        if stage == 3:
            corner = left + 90 if body.x - left < right - body.x else right - 90
            if abs(body.x - corner) > 12:
                self._slide_to(corner, 130.0)
            else:
                body.vx = 0.0                       # sentado, em greve
            return
        # marcha de um lado ao outro, pulando de indignação
        edge = right - 120 if self.march_dir > 0 else left + 120
        if (self.march_dir > 0 and body.x >= edge) or (self.march_dir < 0 and body.x <= edge):
            self.march_dir *= -1
        self._slide_to(right if self.march_dir > 0 else left, 150.0 if stage == 2 else 105.0)
        if random.random() < dt * (1.4 if stage == 2 else 0.6):
            body.jump(body.vx, -330.0 if stage == 2 else -220.0)

    def _pick_target(self, cursor, left, right):
        """Escolhe um ponto de destino no chão: perto da bolinha se ele está brincando, senão ao acaso."""
        x = self.body.x
        walk_left, walk_right = self._movement_limits(left, right)
        if self.toy and self.emotion in ("feliz", "curioso", "contente") and random.random() < 0.75:
            if abs(self.toy[0] - x) > 40:                  # brincando: vai atrás da bolinha
                return min(walk_right - 80, max(walk_left + 80, self.toy[0]))
        if self.emotion == "curioso":
            side = 1 if x > cursor[0] else -1
            return min(walk_right - 80, max(walk_left + 80, cursor[0] + side * CURIOUS_DISTANCE))
        if self.canto:
            return left + 80 if x - left < right - x else right - 80   # cantinho mais perto
        if self.emotion == "observando" and random.random() < 1.0 - self.tone.drive():
            return None                         # às vezes só fica olhando mesmo
        vizinhos = self._lateral_neighbors(left, right)
        if vizinhos and random.random() < CROSS_SCREEN_CHANCE:
            v_left, v_right = random.choice(vizinhos)
            return random.uniform(v_left + 100, v_right - 100)
        reach = 120 + 450 * self.tone.drive()
        return min(walk_right - 80, max(walk_left + 80, x + random.uniform(-reach, reach)))

    def _movement_limits(self, left, right):
        """Amplia o passeio para monitores encostados à esquerda ou à direita do atual."""
        walk_left, walk_right = left, right
        for a_left, a_right in self._lateral_neighbors(left, right):
            walk_left = min(walk_left, a_left)
            walk_right = max(walk_right, a_right)
        return walk_left, walk_right

    def _lateral_neighbors(self, left, right):
        """Faixas horizontais dos monitores laterais alcançáveis na altura atual do pet."""
        vizinhos = []
        y = self.body.y
        for a_left, a_top, a_right, a_bottom in self.screen_areas:
            if not (a_top <= y < a_bottom):
                continue
            if abs(a_right - left) <= 1 or abs(a_left - right) <= 1:
                vizinhos.append((a_left, a_right))
        return vizinhos

    def _jump_to_window(self, platforms):
        """Pulo balístico até a barra de título de uma janela próxima."""
        body = self.body
        ex, ey = body.extents()
        bottom = body.y + ey
        options = []
        for hwnd, p_left, p_right, p_top in platforms:
            if hwnd == body.platform:
                continue
            lo, hi = p_left + ex, p_right - CLOSE_BUTTONS - ex
            if hi - lo < 20 or not (-MAX_CLIMB < bottom - p_top < MAX_CLIMB):
                continue
            tx = min(hi, max(lo, body.x + random.uniform(-200, 200)))
            if abs(tx - body.x) < 1400:
                options.append((tx, p_top))
        if not options:
            return False
        tx, p_top = random.choice(options)
        apex = min(bottom, p_top) - 70
        t_up = math.sqrt(2 * (bottom - apex) / GRAVITY)
        t_down = math.sqrt(2 * (p_top - apex) / GRAVITY)
        body.jump((tx - body.x) / (t_up + t_down), -GRAVITY * t_up, random.uniform(-90, 90))
        return True

    def _slide_to(self, target, speed):
        """Anda devagar até `target` com a velocidade dada."""
        direction = 1 if target > self.body.x else -1
        self.body.vx = direction * speed

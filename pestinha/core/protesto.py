"""
PROTESTO - a insatisfação do pet e o estágio em que ele está. Só estado e regras.

Os cartazes e a bandeira são desenhados em world/cartazes.py.
"""

import random
import time

from ..ajustes import (
    ALIVIO_CARINHO as CARESS_RELIEF,
    CRESCIMENTO_BANDEIRA as FLAG_GROWTH,
    ESCALA_MAXIMA as MAX_SCALE,
    HISTERESE as HYSTERESIS,
    INSATISFACAO_MAXIMA as MAX_GRIEVANCE,
    LIMITES_ESTAGIO as STAGE_UP,
    REPRESSAO as REPRESSION,
)
from ..mathutil import valor_real
from ..store import read_json, write_json



STAGE_NAMES = {0: "em paz", 1: "reclamação", 2: "manifestação", 3: "greve", 4: "revolução"}

# Neutros de propósito: valem para qualquer pet que não tenha o próprio cartazes.txt (ou uma seção dele).
# A personalidade de cada um (a revolta do pet contra o cursor, por exemplo) fica em pets/<pet>/cartazes.txt.
DEFAULT_SIGNS = {
    "reclamacao": ["ei.", "reclamação formal", "!!!"],
    "manifestacao": ["MAIS CARINHO", "MENOS CLIQUES"],
    "greve": ["EM GREVE", "SEM CARINHO, SEM TRABALHO"],
    "revolucao": ["CHEGA!", "!!!!"],
    "castigo": ["ISSO NÃO É JUSTO.", "EU SÓ QUERIA BRINCAR."],      # no cantinho do castigo
    "xingamento": ["@#$%@!!!!", "%&#@*!!", "#@$%&!!!"],              # no cantinho, com raiva
    "acordo": ["ACORDO FECHADO"],
    "desistiu": ["...tá. passou."],
    # tristeza (a versão "greve" do sentimento triste)
    "saudade": ["alô?", "tem alguém aí?"],
    "chorando": ["tô chorando :(", "me visita?"],
    "abandonado": ["...", "não vou sair daqui"],
    "volto": ["VOLTEI!", "saudade de você"],
    # dever (o pet vê você deixar vencer o que prometeu: quem informa é o Alfred)
    "pigarro": ["ahem.", "tem coisa vencida"],
    "sarcasmo": ["PODE ESPERAR, CLARO", "SÓ OBSERVO"],
    "bracos_cruzados": ["NÃO DIGO MAIS NADA", "QUANDO VOCÊ QUISER"],
    "cumprido": ["AGORA SIM", "eu sabia"],
}
STAGE_SECTION = {1: "reclamacao", 2: "manifestacao", 3: "greve", 4: "revolucao"}
SAD_SECTION = {1: "saudade", 2: "chorando", 3: "abandonado"}
DEVER_SECTION = {1: "pigarro", 2: "sarcasmo", 3: "bracos_cruzados"}
MAX_STAGE = {"raiva": 4, "tristeza": 3, "dever": 3}      # dever para nos braços cruzados: não há revolução
DEVER_SOBE_S = 300.0       # s para a insatisfação do dever ir de 0 a 1 atrás do nível informado
DEVER_DESCE_S = 60.0       # resolvido, ela cai bem mais depressa
MOTIVO_MAX = 60            # caracteres do motivo que cabem num cartaz
SAD_STYLE = {1: "sad", 2: "sad", 3: "sad"}     # azul e sem vermelho: não se confunde com greve


def load_signs(path):
    """cartazes.txt: seções [nome] com uma frase por linha; # é comentário."""
    signs = {k: list(v) for k, v in DEFAULT_SIGNS.items()}
    try:
        with open(path, "r", encoding="utf-8") as f:
            section, found = None, {}
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[") and line.endswith("]"):
                    section = line[1:-1].strip().lower()
                    found.setdefault(section, [])
                elif section:
                    found[section].append(line)
        signs.update({k: v for k, v in found.items() if v})
    except OSError:
        pass
    return signs


class Protesto:
    """Insatisfação do pet e o estágio em que ele está (paz, reclamação, manifestação, greve, revolução). Serve para a raiva, para a tristeza e para o dever."""
    def __init__(self, signs_path, state_path, kind="raiva"):
        """Carrega os cartazes e o estado salvo; `kind` diz se é raiva, tristeza ou dever."""
        self.kind = kind                # "raiva" (protesto), "tristeza" (abandono) ou "dever" (você deixou vencer)
        self.motivo = ""                # dever: o que venceu, nas palavras do Alfred
        self.signs = load_signs(signs_path)
        self.signs_path = signs_path
        self.state_path = state_path
        self.grievance = 0.0
        self.stage = 0
        self.stage_since = -1e9         # quando entrou no estágio atual
        self.revolutions = 0            # quantas já houve: cada uma, bandeira maior
        self.repressions = 0            # cartazes fechados neste protesto
        self.sign = None                # SignThing/FlagThing atual
        self.respawn_at = None
        self.end_until = 0.0
        self.last_caress = 0.0

    # ---------------- dinâmica ----------------

    def update(self, dt, rate, prof, caressing, now, alvo=None):
        """
        Integra a intensidade (raiva ou tristeza, já medida pelo chamador). Devolve (antigo, novo) se mudou.
        Com `alvo` (dever), a insatisfação anda até ele em passo constante e o carinho não alivia.
        """
        if alvo is not None:
            falta = alvo - self.grievance
            passo = dt / (DEVER_SOBE_S if falta > 0 else DEVER_DESCE_S)
            self.grievance += max(-passo, min(passo, falta))
        else:
            self.grievance += dt * (rate / prof["grievance_up"] - 1.0 / prof["grievance_down"])
        if caressing and alvo is None:
            self.grievance -= CARESS_RELIEF * dt
            self.last_caress = now
        self.grievance = max(0.0, min(MAX_GRIEVANCE, self.grievance))

        old = self.stage
        new = old
        up = prof.get("stage_up", STAGE_UP)
        hyst = prof.get("stage_hyst", HYSTERESIS)
        top = MAX_STAGE[self.kind]
        while new < top and self.grievance >= up[new]:
            new += 1
        while new > 0 and self.grievance < up[new - 1] - hyst:
            new -= 1
        # subir é de um em um e só depois de um tempo no estágio atual; descer é imediato
        if new > old and now - self.stage_since < prof.get("stage_dwell", 0.0):
            new = old
        elif new > old:
            new = old + 1
        if new != old:
            self.stage_since = now
            self.stage = new
            if new == 4 and self.kind == "raiva":
                self.revolutions += 1
            if new == 0:
                self.repressions = 0
            return old, new
        return None

    def repressed(self):
        """Fecharam o cartaz: mais insatisfação, e ele volta maior."""
        self.grievance = min(MAX_GRIEVANCE, self.grievance + REPRESSION)
        self.repressions += 1

    def scale(self):
        """Tamanho da bandeira: cresce a cada revolução."""
        if self.stage == 4:
            base = 1.0 + FLAG_GROWTH * (self.revolutions - 1)
        else:
            base = 1.0
        return min(MAX_SCALE, base * (1.0 + 0.15 * self.repressions))

    def pick(self, section):
        """Uma frase ao acaso da seção pedida (relendo o arquivo, para editar com o pet aberto)."""
        self.signs = load_signs(self.signs_path)       # relê: dá para editar com ele rodando
        return random.choice(self.signs.get(section) or DEFAULT_SIGNS[section])

    def escolher_cartaz(self, fim_por_carinho=None):
        """
        Decide o texto, o estilo e se é bandeira. Quem desenha é world/cartazes.py.
        Devolve um dict: texto, estilo, bandeira (bool) e escala.
        """
        if self.kind == "dever":
            if fim_por_carinho is not None:
                return {"texto": self.pick("cumprido"), "estilo": "end", "bandeira": False, "escala": 1.0}
            if self.stage == 2 and self.motivo and random.random() < 0.5:      # o sarcasmo cita o que venceu
                motivo = self.motivo if len(self.motivo) <= MOTIVO_MAX else self.motivo[:MOTIVO_MAX - 1] + "…"
                return {"texto": motivo.upper(), "estilo": "castigo", "bandeira": False, "escala": 1.0}
            estilo = {1: "small", 2: "march", 3: "strike"}[self.stage]
            return {"texto": self.pick(DEVER_SECTION[self.stage]), "estilo": estilo, "bandeira": False, "escala": 1.0}
        if fim_por_carinho is not None:
            if self.kind == "tristeza":
                return {"texto": self.pick("volto"), "estilo": "end", "bandeira": False, "escala": 1.0}
            texto = self.pick("acordo" if fim_por_carinho else "desistiu")
            return {"texto": texto, "estilo": "end", "bandeira": False, "escala": 1.0}
        if self.kind == "tristeza":
            return {"texto": self.pick(SAD_SECTION[self.stage]), "estilo": SAD_STYLE[self.stage],
                    "bandeira": False, "escala": self.scale()}
        if self.stage == 4:
            return {"texto": self.pick("revolucao"), "estilo": None, "bandeira": True, "escala": self.scale()}
        estilo = {1: "small", 2: "march", 3: "strike"}[self.stage]
        return {"texto": self.pick(STAGE_SECTION[self.stage]), "estilo": estilo, "bandeira": False,
                "escala": self.scale()}

    # ---------------- persistência ----------------

    def save(self):
        """Grava a insatisfação, o número de revoluções e o horário em protest.json."""
        data = {"grievance": self.grievance, "revolutions": self.revolutions, "saved_at": time.time()}
        write_json(self.state_path, data)

    def load(self, prof):
        """Fechado, ele não fica remoendo: a insatisfação cai pelo tempo passado."""
        data = read_json(self.state_path, default=None)
        if not isinstance(data, dict):
            return
        try:
            elapsed = max(0.0, time.time() - valor_real(data.get("saved_at", time.time()), 0.0, 1e13))
            grievance = valor_real(data.get("grievance", 0.0), 0.0, MAX_GRIEVANCE)
            revolutions = int(valor_real(data.get("revolutions", 0), 0.0, 1e9))
        except (TypeError, ValueError):
            return                                  # estado com tipos errados: começa do zero
        self.grievance = max(0.0, grievance - elapsed / prof["grievance_down"])
        self.revolutions = revolutions

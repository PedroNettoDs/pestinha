"""
ALFRED CONTROLLER - o pet encena o que o Alfred está fazendo e deixa você mexer na fila dele.

É regra explícita, não decisão da rede: enquanto o Alfred trabalha, um balão em cima do pet mostra a
atividade e o andamento, e ele se mexe conforme o tipo. Carrega objetos de um lado ao outro da tela
(e-mails, notas, caixas), faz a ronda, ou vai até o notebook; aí quem decide sentar é o neurônio SENTAR,
pelo sinal PEDIDO. Dormindo, de castigo, em protesto, de braços cruzados (dever) ou na sua mão, ele não encena. Um aviso do Alfred
(pendência nova) vira uma fala no balão e um post-it; um recado também fica num post-it. Esses post-its se
arrastam, ficam atrás das outras janelas, o clique abre o detalhe (com Feito e Voltar), só o botão do meio fecha, e eles voltam ao mesmo lugar
quando o pet reabre (memory/alfred_notas.json). Usar o Alfred (Painel, conversa, WhatsApp, fila) conta como atenção: a carência
dele diminui (`notado` no retrato). Solto com a mão em cima de um programa conhecido (PROGRAMAS), ele age:
no WordCraft abre a Escrita, no Thunderbird manda ler os e-mails. Também abre no navegador os endereços locais que o Alfred
publica: o Painel e a conversa com ele.
"""

import math
import time

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices

from .. import plataforma
from ..ajustes import EXCLAMACAO_SEGUNDOS
from ..log import log
from ..sense.alfred import FORA_DO_AR, Leitor, pasta_do_alfred
from ..store import read_json, write_json
from ..world.alfred_objetos import AnotacaoThing, BalaoThing, PropThing, icone_de

LER_A_CADA = 1.0        # s entre leituras do retrato do Alfred
MARGEM = 140            # px da borda da tela até os pontos de carga e de entrega
PRAZO = 20.0            # s: uma travessia que não chega é abandonada
FALA_SEGUNDOS = 8.0     # quanto tempo um aviso fica no balão
MAX_NO_CHAO = 3         # objetos entregues que ficam no chão; os mais antigos somem
MAX_NOTAS = 12          # post-its de aviso na tela; passando disso, o mais antigo sai
NOTADO_VALE_S = 60.0    # uso do Alfred mais antigo que isso (pet aberto depois) não conta como atenção
CENAS = {"email": "carregar", "rag": "carregar", "backup": "carregar", "vigia": "ronda"}   # o resto: "mesa"
# Solto em cima da janela de um programa (pedaço do nome do processo) -> o que ele faz.
PROGRAMAS = (("wordcraft", "escrita"), ("thunderbird", "email"))
SOLTO_ESPERA = 20.0     # s até a mesma ação poder disparar de novo
JANELA_CONVERSA = (440, 680)    # px: a caixinha de conversa, estreita o bastante para o Painel mostrar só o chat


class AlfredController:
    """Lê o retrato do Alfred, encena a atividade em andamento e manda os pedidos da fila."""

    def __init__(self, app, debug):
        """Liga-se ao Alfred se memory/alfred.json apontar a pasta dele; senão fica inerte (`ligado` falso)."""
        self.app = app
        self.debug = debug
        pasta = pasta_do_alfred(app.paths)
        self.leitor = Leitor(pasta) if pasta else None
        self.estado = FORA_DO_AR
        self.balao = BalaoThing()
        self.carga = None           # objeto que ele está levando
        self.objetos = []           # objetos já entregues, no chão
        self.notas = []             # post-its dos avisos
        self.recados = {}           # id do recado -> post-it colado
        self.recados_abertos = set()    # recados que você fechou ou marcou como feitos: não voltam para a tela
        self.fala = None            # (texto, até quando)
        self.vistos = None          # ids de avisos já mostrados; None até a primeira leitura
        self._notado = None         # o último uso do Alfred já contado como atenção
        self._solto = {}            # ação -> quando disparou pela última vez
        self.visivel = False
        self._lido_em = -1e9
        self._missao = None         # a travessia que este controlador pediu ao comportamento
        self._cena = None
        if self.ligado:
            self._restaurar()

    @property
    def ligado(self):
        """Diz se há uma pasta do Alfred configurada."""
        return self.leitor is not None

    def atividade(self):
        """A atividade que ele encena: a primeira que informa o passo, senão a primeira em andamento."""
        agora = self.estado.agora
        return next((a for a in agora if a["passo"]), agora[0] if agora else None)

    # ---------------- leitura (ciclo de 100 ms) ----------------

    def tick(self, now):
        """Relê o retrato uma vez por segundo; avisos novos viram fala e o fim do trabalho, um pulinho."""
        if not self.ligado or now - self._lido_em < LER_A_CADA:
            return
        self._lido_em = now
        trabalhava = self.atividade() is not None
        self.estado = self.leitor.ler()
        novos = [e for e in self.estado.eventos if self.vistos is not None and e["id"] not in self.vistos]
        self.vistos = (self.vistos or set()) | {e["id"] for e in self.estado.eventos}
        for evento in novos:
            self._avisar(evento, now)
        self._colar_recados()
        self._sentir_notado()
        if trabalhava and self.atividade() is None:
            body = self.app.pet.body
            if body.grounded and not self.app.asleep:
                body.jump(0.0, -260.0)              # terminou: um pulinho
            if self.debug():
                log("[alfred] terminou o trabalho")

    def _sentir_notado(self):
        """Você usou o Alfred agora há pouco: para o pet é atenção, e a carência (solidão) diminui."""
        quando = self.estado.notado
        if quando is None or quando == self._notado:
            return
        self._notado = quando
        if abs(self.leitor.relogio() - quando) > NOTADO_VALE_S or self.app._congelado():
            return
        self.app.drives.touched("alfred")
        self.app.timeline.note_interaction()
        if self.debug():
            log(f"[alfred] notado: {self.app.drives.describe()}")

    def pedido(self):
        """0..1 para o canal PEDIDO da rede: o Alfred está num trabalho de mesa e o pet pode encenar."""
        return 1.0 if self._cena == "mesa" else 0.0

    def _avisar(self, evento, now):
        """Aviso do Alfred: "!" em cima dele, novidade para a rede, fala no balão e um post-it."""
        self.app.pet_state.exclamacao_until = now + EXCLAMACAO_SEGUNDOS
        self.app.senses.kick("NOVELTY", 0.8)
        self.fala = (f"{icone_de(evento['tipo'])} {evento['texto']}".strip(), now + FALA_SEGUNDOS)
        e_recado = any(r["texto"] == evento["texto"] for r in self.estado.recados)   # o recado já tem o post-it dele
        if evento["texto"] and self.app.perms["bilhetes"] and not e_recado:
            quando = time.strftime("%d/%m às %H:%M", time.localtime(evento["quando"])) if evento["quando"] else ""
            detalhe = f"{icone_de(evento['tipo'])} Aviso do Alfred" + (f", {quando}" if quando else "")
            self.notas.append(self._nova_nota(evento["texto"], detalhe, len(self.notas)))
            for velha in self.notas[:-MAX_NOTAS]:
                self._fechar_nota(velha)
            self._guardar()

    def _nova_nota(self, texto, detalhe, deslocamento, rid=None, canto=None):
        """Um post-it ao lado do pet, do lado com mais espaço (ou no `canto` guardado); `rid` é o recado dele."""
        nota = AnotacaoThing(texto, detalhe, pergunta=rid is not None)
        if canto is None:
            body = self.app.pet.body
            left, top, right, _bottom = self.app.bounds()
            lado = -1 if body.x > (left + right) / 2 else 1
            nota.place(body.x + lado * (150 + 30 * deslocamento), max(top + nota.height() / 2, body.y - 120))
        else:
            nota.por_canto(*canto)
        if rid is None:
            nota.feito.connect(lambda nota, _encerrar: self._fechar_nota(nota))
            nota.fechada.connect(self._fechar_nota)
        else:
            nota.feito.connect(lambda _nota, encerrar, rid=rid: self._dispensar_recado(rid, encerrar))
            nota.fechada.connect(lambda _nota, rid=rid: self._dispensar_recado(rid))
        nota.movida.connect(lambda _nota: self._guardar())
        nota.setVisible(self.visivel)
        return nota

    # ---------------- post-its guardados ----------------

    def _guardar(self):
        """Grava os post-its que estão na tela e os recados já dispensados, para a próxima abertura."""
        def item(nota, **mais):
            cx, cy = nota.canto()
            return dict(texto=nota.text, detalhe=nota.detalhe, x=round(cx), y=round(cy), **mais)
        try:
            write_json(self.app.paths.alfred_notas, {
                "notas": [item(n) for n in self.notas],
                "recados": [item(n, id=rid) for rid, n in self.recados.items()],
                "dispensados": sorted(self.recados_abertos)})
        except (OSError, ValueError) as e:
            log(f"[alfred] post-its não gravados ({e})")

    def _restaurar(self):
        """Recoloca na tela os post-its da última vez, cada um onde estava."""
        dados = read_json(self.app.paths.alfred_notas, default=None)
        if not isinstance(dados, dict):
            return
        def itens(nome):
            lista = dados.get(nome) if isinstance(dados.get(nome), list) else []
            return [d for d in lista if isinstance(d, dict) and isinstance(d.get("texto"), str) and d["texto"]
                    and all(isinstance(d.get(k), (int, float)) for k in ("x", "y"))]
        for d in itens("notas")[-MAX_NOTAS:]:
            self.notas.append(self._nova_nota(d["texto"], str(d.get("detalhe") or ""), 0, canto=(d["x"], d["y"])))
        for d in itens("recados"):
            if isinstance(d.get("id"), str) and d["id"] and d["id"] not in self.recados:
                self.recados[d["id"]] = self._nova_nota(d["texto"], str(d.get("detalhe") or ""), 0,
                                                        rid=d["id"], canto=(d["x"], d["y"]))
        dispensados = dados.get("dispensados") if isinstance(dados.get("dispensados"), list) else []
        self.recados_abertos = {r for r in dispensados if isinstance(r, str)}

    def _colar_recados(self):
        """Um post-it por recado que espera você; some quando o Alfred tira o recado da lista ou você o dispensa."""
        if not self.estado.online:
            return                                  # Alfred fora do ar: o que está colado fica
        atuais = {r["id"]: r for r in self.estado.recados}
        antes = (set(self.recados), len(self.notas), set(self.recados_abertos))
        for rid in [rid for rid in self.recados if rid not in atuais]:
            self._tirar_recado(rid)
        self.recados_abertos &= set(atuais)
        for rid, recado in atuais.items() if self.app.perms["bilhetes"] else ():
            if rid in self.recados or rid in self.recados_abertos:
                continue
            for nota in [n for n in self.notas if n.text == recado["texto"]]:
                self._fechar_nota(nota)             # o aviso do mesmo recado chegou antes: fica só um post-it
            self.recados[rid] = self._nova_nota(recado["texto"], recado["detalhe"],
                                                len(self.notas) + len(self.recados), rid=rid)
        if antes != (set(self.recados), len(self.notas), set(self.recados_abertos)):
            self._guardar()

    def _dispensar_recado(self, rid, encerrar=False):
        """Você marcou o recado como feito ou fechou o post-it (botão do meio): ele sai e não volta para a tela.
        Com `encerrar` (o Sim do Feito), pede ao Alfred que feche a pendência também."""
        if encerrar:
            self.leitor.pedir("recado_feito", id=rid)
        self.recados_abertos.add(rid)
        self._tirar_recado(rid)
        self._guardar()

    def _tirar_recado(self, rid):
        nota = self.recados.pop(rid, None)
        if nota:
            nota.close()
            nota.deleteLater()

    def _fechar_nota(self, nota):
        """Você marcou o aviso como feito ou fechou o post-it: ele some (não é travessura, não conta como dispensa)."""
        if nota in self.notas:
            self.notas.remove(nota)
        nota.close()
        nota.deleteLater()
        self._guardar()

    # ---------------- cena (a cada quadro) ----------------

    def _pode_encenar(self):
        """Só encena quando o corpo está livre: visível, acordado, fora do cantinho, sem protesto e solto."""
        app = self.app
        return (self.visivel and not app.asleep and not app.castigo.dentro and app.castigo.fuga is None
                and not app.pet.body.held and not app.in_flight
                and app.protest.stage == 0 and app.sad.stage < 2 and app.dever.stage < 3)

    def act(self, now, dt, bounds):
        """Um quadro: escolhe a cena pela atividade, move o pet e os objetos e posiciona o balão."""
        if not self.ligado:
            return
        atividade = self.atividade()
        cena = CENAS.get(atividade["tipo"], "mesa") if atividade and self._pode_encenar() else None
        if cena != self._cena:
            self._trocar_cena(cena)
        if cena == "carregar":
            self._carregar(atividade, now, dt, bounds)
        elif cena == "ronda":
            self._ronda(now, bounds)
        elif cena == "mesa":
            self._ir_ao_notebook(now)
        for objeto in self.objetos:
            objeto.fall(dt, bounds[3])
        self._atualizar_balao(atividade, now, bounds)

    def _trocar_cena(self, cena):
        """Mudou a cena: larga o que carregava, desiste da travessia e, sem trabalho, limpa o chão."""
        beh = self.app.behavior
        if beh.mission is not None and beh.mission is self._missao:
            beh.mission = None
        self._missao = None
        self._soltar_carga()
        if self.atividade() is None:
            self._limpar_objetos()
        if self.debug():
            log(f"[alfred] cena: {self._cena} -> {cena}")
        self._cena = cena

    def _ir(self, x, now):
        """Pede ao comportamento uma travessia até x (a mesma missão das travessuras)."""
        self._missao = ("cross", x, now + PRAZO)
        self.app.behavior.mission = self._missao

    def _livre(self):
        """O corpo está no chão, em pé, e o comportamento não está em outra missão."""
        body = self.app.pet.body
        return self.app.behavior.mission is None and body.grounded and body.upright()

    def _carregar(self, atividade, now, dt, bounds):
        """Busca um objeto de um lado da tela, leva até o outro, larga e volta para buscar mais."""
        body = self.app.pet.body
        left, _top, right, _bottom = bounds
        origem, entrega = left + MARGEM, right - MARGEM
        if self.carga is not None:
            ex, ey = body.extents()
            k = 1.0 - math.exp(-dt / 0.12)                      # segue com atraso, como quem tem peso
            alvo_x = body.x - (ex + self.carga.width() / 2 + 8)   # vai atrás dele (a entrega é à direita)
            alvo_y = body.y + ey - self.carga.height() / 2
            self.carga.place(self.carga.x + (alvo_x - self.carga.x) * k,
                             self.carga.y + (alvo_y - self.carga.y) * k)
            if self.app.behavior.mission is not self._missao:   # chegou, o prazo venceu ou outra coisa tomou a vez
                self._soltar_carga()
            return
        if not self._livre():
            return
        if abs(body.x - origem) > 30:
            self._ir(origem, now)
            return
        ex, ey = body.extents()
        self.carga = PropThing(icone_de(atividade["tipo"]))
        self.carga.carried = True
        self.carga.place(body.x - ex - self.carga.width() / 2, body.y + ey - self.carga.height() / 2)
        self.carga.setVisible(self.visivel)
        self._ir(entrega, now)

    def _soltar_carga(self):
        """Larga o objeto onde está: ele cai e fica no chão com os outros entregues."""
        if self.carga is None:
            return
        self.carga.carried = False
        self.carga.resting = False
        self.objetos.append(self.carga)
        self.carga = None
        for velho in self.objetos[:-MAX_NO_CHAO]:
            self.objetos.remove(velho)
            velho.close()
            velho.deleteLater()

    def _limpar_objetos(self):
        """Tira da tela os objetos entregues."""
        for objeto in self.objetos:
            objeto.close()
            objeto.deleteLater()
        self.objetos = []

    def _ronda(self, now, bounds):
        """Atravessa a tela de um lado ao outro, sem parar, enquanto a ronda durar."""
        if not self._livre():
            return
        left, _top, right, _bottom = bounds
        self._ir(right - MARGEM if self.app.pet.body.x < (left + right) / 2 else left + MARGEM, now)

    def _ir_ao_notebook(self, now):
        """Trabalho de mesa: chega perto do notebook; sentar é com a rede (sinal PEDIDO)."""
        mesa = self.app.mesa
        if mesa.sentado or mesa.escondido or not self._livre():
            return
        centro = mesa.caderno.x() + mesa.caderno.width() / 2
        if abs(self.app.pet.body.x - centro) > 40:
            self._ir(centro, now)

    def _atualizar_balao(self, atividade, now, bounds):
        """Fala recente tem prioridade; senão, a atividade e o andamento. Some dormindo ou com cartaz."""
        app = self.app
        texto = fracao = None
        if self.fala and now < self.fala[1]:
            texto = self.fala[0]
        elif atividade is not None:
            texto = f"{icone_de(atividade['tipo'])} {atividade['passo'] or atividade['rotulo']}"
            if atividade["total"]:
                feito = atividade["feito"] or 0.0
                texto += f" {int(feito)}/{int(atividade['total'])}"
                fracao = max(0.0, min(1.0, feito / atividade["total"]))
        if (texto is None or not self.visivel or app.asleep
                or app.protest.sign is not None or app.sad.sign is not None or app.dever.sign is not None):
            self.balao.hide()
            return
        self.balao.definir(texto, fracao)
        body = app.pet.body
        left, top, right, _bottom = bounds
        meia = self.balao.width() / 2
        self.balao.place(min(right - meia, max(left + meia, body.x)),
                         max(top + self.balao.height() / 2, body.y - body.extents()[1] - self.balao.height() / 2 - 2))
        if not self.balao.isVisible():
            self.balao.show()

    # ---------------- fila ----------------

    def enfileirar(self, tipo, frente=True):
        """Pede uma rotina ao Alfred: na frente da fila (roda em seguida) ou no fim."""
        return self.ligado and self.leitor.pedir("enfileirar", tipo=tipo, frente=frente)

    def passar_para_frente(self, item_id):
        """Passa um item da fila para a frente."""
        return self.ligado and self.leitor.pedir("frente", id=item_id)

    def cancelar(self, item_id):
        """Tira um item da fila."""
        return self.ligado and self.leitor.pedir("cancelar", id=item_id)

    # ---------------- navegador ----------------

    def abrir_painel(self):
        """Abre o Painel do Alfred (o "terminal" dele) no navegador padrão. Devolve False se ele não publicou o endereço."""
        url = self.estado.links.get("painel")
        return bool(url) and QDesktopServices.openUrl(QUrl(url))

    def solto_em(self, x, y, now):
        """Você soltou o pet no ponto (x, y): conforme o programa da janela ali, ele age. Devolve a ação, ou None."""
        if not self.estado.online:
            return None
        programa = plataforma.programa_em(x, y) or ""
        acao = next((a for trecho, a in PROGRAMAS if trecho in programa), None)
        if acao is None or now - self._solto.get(acao, -1e9) < SOLTO_ESPERA:
            return None
        if acao == "escrita":
            feito = self._abrir_ao_lado("escrita")
            fala = "✍️ Abrindo a Escrita"
        else:
            ocupado = any(i["tipo"] == acao for i in (*self.estado.agora, *self.estado.fila))
            feito = ocupado or (any(c["tipo"] == acao for c in self.estado.catalogo) and self.enfileirar(acao))
            fala = f"{icone_de(acao)} " + ("Já estou nos e-mails" if ocupado else "Vou olhar os e-mails e a agenda")
        if not feito:
            return None
        self._solto[acao] = now
        self.fala = (fala, now + FALA_SEGUNDOS)
        if self.debug():
            log(f"[alfred] solto em {programa}: {acao}")
        return acao

    def abrir_conversa(self):
        """Abre a conversa com o Alfred numa janela pequena ao lado do pet (ou no navegador padrão, sem um Chromium)."""
        return self._abrir_ao_lado("conversa")

    def _abrir_ao_lado(self, nome):
        """Abre o endereço `nome` dos links do Alfred numa janela pequena ao lado do pet."""
        url = self.estado.links.get(nome)
        if not url:
            return False
        largura, altura = JANELA_CONVERSA
        left, top, right, bottom = self.app.bounds()
        body = self.app.pet.body
        x = body.x + 90 if body.x + 90 + largura <= right else body.x - 90 - largura     # do lado que couber
        x = int(min(right - largura, max(left, x)))
        y = int(max(top, bottom - altura - 12))
        return plataforma.abrir_janela_web(url, x, y, largura, altura) or QDesktopServices.openUrl(QUrl(url))

    # ---------------- sessão ----------------

    def janelas(self):
        """Janelas deste controlador que estão na tela (o pet não deve tentar pousar nelas)."""
        todas = [self.balao, *self.objetos, *self.notas, *self.recados.values()] + ([self.carga] if self.carga else [])
        return [w for w in todas if w.isVisible()]

    def set_visible(self, visivel):
        """Mostra ou esconde tudo junto com o pet (o balão volta no próximo quadro, se couber)."""
        self.visivel = visivel
        for w in [*self.objetos, *self.notas, *self.recados.values()] + ([self.carga] if self.carga else []):
            w.setVisible(visivel)
        if not visivel:
            self.balao.hide()

    def fechar(self):
        """Fecha tudo ao sair. Os post-its continuam guardados: voltam na próxima abertura."""
        self._soltar_carga()
        self._limpar_objetos()
        for nota in [*self.notas, *self.recados.values()]:
            nota.close()
            nota.deleteLater()
        self.notas, self.recados = [], {}
        self.balao.close()

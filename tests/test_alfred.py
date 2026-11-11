"""
Ligação com o Alfred: o leitor do retrato, o controlador que encena a atividade e o painel da fila.

Tudo em pasta temporária: o "Alfred" aqui é um estado.json escrito pelo teste.
"""
import json
import os
import sys
import time
from pathlib import Path

ROOT =Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtCore import QEvent, QPointF, Qt  # noqa: E402
from PySide6.QtGui import QMouseEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.app import PestinhaApp  # noqa: E402
from pestinha.mind.alfred_ctl import MARGEM  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.sense.alfred import FORA_DO_AR, TEXTO_MAX, VALIDADE_S, Leitor, pasta_do_alfred  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

EMAIL = {"id": "a1", "tipo": "email", "rotulo": "Ler e classificar os e-mails",
         "passo": "Classificando e-mails", "feito": 3, "total": 12}
CATALOGO = [{"tipo": "email", "rotulo": "Ler e classificar os e-mails"}, {"tipo": "backup", "rotulo": "Backup"}]


def publicar(pasta, atualizado=None, **listas):
    """Escreve o retrato como o Alfred escreveria."""
    pasta.mkdir(parents=True, exist_ok=True)
    estado = {"versao": 1, "atualizado": time.time() if atualizado is None else atualizado,
              "agora": [], "fila": [], "agendadas": [], "catalogo": CATALOGO, "eventos": []}
    estado.update(listas)
    (pasta / "estado.json").write_text(json.dumps(estado), encoding="utf-8")
    # o leitor só relê quando a data do arquivo muda: garante datas diferentes entre publicações seguidas
    publicar.n = getattr(publicar, "n", 0) + 1
    os.utime(pasta / "estado.json", ns=(publicar.n * 10 ** 9, publicar.n * 10 ** 9))


def pedidos(pasta):
    """Os pedidos deixados, em ordem estável (no mesmo milissegundo o nome do arquivo não dá a ordem)."""
    lidos = [json.loads(f.read_text(encoding="utf-8")) for f in (pasta / "pedidos").glob("*.json")]
    return sorted(lidos, key=lambda p: json.dumps(p, sort_keys=True))


# ---------------- leitor ----------------

def test_retrato_valido_e_itens_ruins_descartados(tmp_path):
    publicar(tmp_path, agora=[EMAIL, "lixo", {"sem": "tipo"}, {"tipo": "rag", "rotulo": "x" * 500, "total": "doze"}],
             fila=[{"id": "f1", "tipo": "backup", "rotulo": "Backup"}],
             agendadas=[{"tipo": "email", "rotulo": "e", "quando": 123.0}, {"tipo": "rag", "rotulo": "sem hora"}])
    estado = Leitor(tmp_path).ler()
    assert estado.online
    assert estado.agora[0] == dict(EMAIL, feito=3.0, total=12.0)
    assert [a["tipo"] for a in estado.agora] == ["email", "rag"]
    assert len(estado.agora[1]["rotulo"]) == TEXTO_MAX and estado.agora[1]["total"] is None
    assert [i["id"] for i in estado.fila] == ["f1"]
    assert [a["tipo"] for a in estado.agendadas] == ["email"]


def test_ausente_velho_ou_ilegivel_e_fora_do_ar(tmp_path):
    leitor = Leitor(tmp_path)
    assert leitor.ler() is FORA_DO_AR
    publicar(tmp_path, atualizado=time.time() - VALIDADE_S - 5, agora=[EMAIL])
    assert leitor.ler() is FORA_DO_AR
    publicar(tmp_path, agora=[EMAIL])
    assert leitor.ler().online
    (tmp_path / "estado.json").write_text("{ pela metade", encoding="utf-8")
    assert Leitor(tmp_path).ler() is FORA_DO_AR
    assert [f.name for f in tmp_path.iterdir()] == ["estado.json"]      # o arquivo do Alfred não é renomeado


def test_links_so_enderecos_desta_maquina(tmp_path):
    publicar(tmp_path, links={"painel": "http://127.0.0.1:7073/painel", "conversa": "http://localhost:7073/painel/conversa",
                              "fora": "http://exemplo.com/painel", "https": "https://127.0.0.1/painel",
                              "arquivo": "file:///etc/passwd", "disfarce": "http://127.0.0.1.exemplo.com/x",
                              "com_query": "http://127.0.0.1:7073/painel?x=1", "numero": 7073})
    assert Leitor(tmp_path).ler().links == {"painel": "http://127.0.0.1:7073/painel",
                                            "conversa": "http://localhost:7073/painel/conversa"}
    publicar(tmp_path, links=["http://127.0.0.1/"])
    assert Leitor(tmp_path).ler().links == {}
    assert FORA_DO_AR.links == {}


def test_pedir_deixa_um_arquivo_na_pasta_do_alfred(tmp_path):
    assert Leitor(tmp_path).pedir("enfileirar", tipo="email", frente=True) is True
    assert pedidos(tmp_path) == [{"acao": "enfileirar", "tipo": "email", "frente": True}]


def test_pasta_vem_de_memory_alfred_json(tmp_path):
    paths = Paths(root=tmp_path)
    assert pasta_do_alfred(paths) is None
    for ruim in ("[]", '{"pasta": 3}', '{"pasta": "relativa/aqui"}'):
        paths.memory.mkdir(exist_ok=True)
        paths.alfred.write_text(ruim, encoding="utf-8")
        assert pasta_do_alfred(paths) is None
    paths.alfred.write_text(json.dumps({"pasta": str(tmp_path / "atividade")}), encoding="utf-8")
    assert pasta_do_alfred(paths) == tmp_path / "atividade"


# ---------------- app ----------------

def _montar(tmp_path, ligado=True):
    qt = QApplication.instance() or QApplication([])
    qt.setQuitOnLastWindowClosed(False)
    paths = Paths(root=tmp_path)
    if ligado:
        paths.memory.mkdir(parents=True, exist_ok=True)
        paths.alfred.write_text(json.dumps({"pasta": str(tmp_path / "atividade")}), encoding="utf-8")
        publicar(tmp_path / "atividade")
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS))
    return PestinhaApp(store, paths)


def _fechar(app):
    app.floats.hidden_by_tray = True
    for w in list(app.floats.windows.values()):
        w.close()
    app.alfred.fechar()
    app.tray.icon.hide()


@pytest.fixture
def app(tmp_path):
    app = _montar(tmp_path)
    body = app.pet.body
    body.grounded, body.angle, body.held = True, 0.0, False     # em pé no chão, pronto para encenar
    yield app
    _fechar(app)


def quadro(app, now, **listas):
    """Publica um retrato, lê e roda um quadro da cena."""
    publicar(app.alfred.leitor.pasta, **listas)
    app.alfred._lido_em = -1e9
    app.alfred.tick(now)
    app.alfred.act(now, 0.016, app.bounds())


def test_sem_alfred_json_o_pet_fica_como_antes(tmp_path):
    app = _montar(tmp_path, ligado=False)
    try:
        assert not app.alfred.ligado and "alfred" not in app.floats.opened
        app.alfred.tick(1.0)
        app.alfred.act(1.0, 0.016, app.bounds())
        assert app.alfred.pedido() == 0.0 and app.behavior.mission is None
        assert app.alfred.enfileirar("email") is False
    finally:
        _fechar(app)


def test_email_busca_carrega_e_entrega(app):
    left, _top, right, _bottom = app.bounds()
    body, alfred = app.pet.body, app.alfred
    body.x = (left + right) / 2
    quadro(app, 10.0, agora=[EMAIL])
    assert app.behavior.mission[:2] == ("cross", left + MARGEM)          # vai buscar
    assert alfred.balao.texto == "✉️ Classificando e-mails 3/12" and alfred.balao.fracao == 0.25
    assert alfred.balao.isVisible()

    body.x, app.behavior.mission = left + MARGEM, None                    # chegou ao ponto de carga
    alfred.act(10.1, 0.016, app.bounds())
    assert alfred.carga is not None and app.behavior.mission[:2] == ("cross", right - MARGEM)

    body.x, app.behavior.mission = right - MARGEM, None                   # chegou à entrega
    alfred.act(10.2, 0.016, app.bounds())
    assert alfred.carga is None and len(alfred.objetos) == 1
    assert {int(w.winId()) for w in alfred.janelas()} >= {int(alfred.objetos[0].winId())}

    quadro(app, 12.0, agora=[])                                           # o Alfred terminou
    assert alfred.objetos == [] and not alfred.balao.isVisible() and alfred.atividade() is None


def test_na_mao_ou_dormindo_ele_nao_encena(app):
    app.pet.body.held = True
    quadro(app, 10.0, agora=[EMAIL])
    assert app.behavior.mission is None and app.alfred.carga is None
    assert app.alfred.balao.isVisible()                                   # o balão continua dizendo o que acontece
    app.pet.body.held = False
    app.sleep.asleep = True
    app.alfred.act(10.1, 0.016, app.bounds())
    assert app.behavior.mission is None and not app.alfred.balao.isVisible()


def test_carga_cai_se_ele_deixa_de_poder_encenar(app):
    app.pet.body.x = app.bounds()[0] + MARGEM
    quadro(app, 10.0, agora=[EMAIL])
    assert app.alfred.carga is not None
    app.pet.body.held = True
    app.alfred.act(10.1, 0.016, app.bounds())
    assert app.alfred.carga is None and len(app.alfred.objetos) == 1 and app.behavior.mission is None


def test_ronda_atravessa_e_mesa_pede_o_notebook(app):
    left, _top, right, _bottom = app.bounds()
    app.pet.body.x = left + 200
    quadro(app, 10.0, agora=[{"id": "v", "tipo": "vigia", "rotulo": "Ronda dos serviços"}])
    assert app.behavior.mission[:2] == ("cross", right - MARGEM) and app.alfred.pedido() == 0.0

    app.mesa.caderno.move(int(left + 900), app.mesa.caderno.y())
    quadro(app, 12.0, agora=[{"id": "b", "tipo": "briefing_matinal", "rotulo": "Briefing da manhã"}])
    assert app.alfred.pedido() == 1.0
    assert app.behavior.mission[:2] == ("cross", left + 900 + app.mesa.caderno.width() / 2)
    assert app.alfred.balao.texto == "📰 Briefing da manhã" and app.alfred.balao.fracao is None


def test_aviso_novo_vira_fala_e_postit(app):
    antigo = {"id": "e0", "tipo": "pendencia", "texto": "já estava lá", "quando": 1.0}
    novo = {"id": "e1", "tipo": "pendencia", "texto": "Convite da Fatec", "quando": 2.0}
    quadro(app, 10.0, eventos=[antigo])
    assert app.alfred.fala is None and app.alfred.notas == []             # o que já existia ao abrir não é novidade
    quadro(app, 12.0, eventos=[antigo, novo])
    assert app.alfred.balao.texto == "📌 Convite da Fatec"
    assert app.pet_state.exclamacao_until > 12.0
    assert [n.text for n in app.alfred.notas] == ["Convite da Fatec"]
    quadro(app, 14.0, eventos=[antigo, novo])
    assert len(app.alfred.notas) == 1                                     # o mesmo aviso não repete
    app.alfred.notas[0].fechada.emit(app.alfred.notas[0])
    assert app.alfred.notas == []


def _mouse(nota, tipo, botao, local, global_):
    """Entrega um evento de mouse ao post-it, com a posição dentro dele e a posição na tela."""
    apertados = Qt.NoButton if tipo == QEvent.MouseButtonRelease else botao
    QApplication.sendEvent(nota, QMouseEvent(tipo, QPointF(*local), QPointF(*global_), botao, apertados, Qt.NoModifier))


def test_postit_arrasta_abre_o_detalhe_e_so_o_botao_do_meio_fecha(app):
    quadro(app, 10.0)
    quadro(app, 12.0, eventos=[{"id": "e1", "tipo": "pendencia", "texto": "Convite da Fatec", "quando": 2.0}])
    nota = app.alfred.notas[0]
    assert nota.windowFlags() & Qt.WindowStaysOnBottomHint and not nota.windowFlags() & Qt.WindowStaysOnTopHint
    nota.por_canto(300, 200)
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (50, 50), (350, 250))
    _mouse(nota, QEvent.MouseMove, Qt.LeftButton, (50, 50), (470, 310))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (50, 50), (470, 310))
    assert nota.canto() == (420, 260) and not nota.aberta                 # arrastar move e não abre
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (50, 50), (470, 310))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (50, 50), (470, 310))
    assert nota.aberta and nota.canto() == (420, 260) and "Aviso do Alfred" in nota.detalhe   # o clique abre o detalhe
    voltar = nota.botoes()["voltar"].center()
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (voltar.x(), voltar.y()), (500, 400))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (voltar.x(), voltar.y()), (500, 400))
    assert not nota.aberta and app.alfred.notas == [nota]                 # Voltar fecha só o detalhe
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (50, 50), (470, 310))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (50, 50), (470, 310))
    feito = nota.botoes()["feito"].center()
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (feito.x(), feito.y()), (500, 400))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (feito.x(), feito.y()), (500, 400))
    assert app.alfred.notas == []                                         # Feito tira o post-it
    quadro(app, 14.0, eventos=[{"id": "e2", "tipo": "pendencia", "texto": "Outro", "quando": 3.0}])
    outra = app.alfred.notas[0]
    _mouse(outra, QEvent.MouseButtonPress, Qt.MiddleButton, (50, 50), (0, 0))
    assert app.alfred.notas == []                                         # o botão do meio fecha


def _clicar(nota, botao):
    centro = nota.botoes()[botao].center()
    _mouse(nota, QEvent.MouseButtonPress, Qt.LeftButton, (centro.x(), centro.y()), (500, 400))
    _mouse(nota, QEvent.MouseButtonRelease, Qt.LeftButton, (centro.x(), centro.y()), (500, 400))


def test_feito_no_recado_so_encerra_no_alfred_com_sim(app):
    recados = [{"id": rid, "tipo": "recado", "texto": f"Recado {rid}", "link": ""} for rid in ("r1", "r2")]
    quadro(app, 10.0, recados=recados)
    pasta = app.alfred.leitor.pasta
    for rid, resposta in (("r1", "voltar"), ("r2", "feito")):             # os botões viram Não e Sim
        nota = app.alfred.recados[rid]
        nota.abrir(True)
        _clicar(nota, "feito")
        assert nota.perguntando and rid in app.alfred.recados             # o Feito só pergunta
        _clicar(nota, resposta)
        assert rid not in app.alfred.recados
    assert pedidos(pasta) == [{"acao": "recado_feito", "id": "r2"}]       # só o Sim chega ao Alfred


def test_postits_voltam_no_mesmo_lugar_ao_reabrir(tmp_path):
    recado = {"id": "r1", "tipo": "recado", "texto": "Marina: pede orçamento", "link": "", "detalhe": "Marina\nQuer preço"}
    feito = {"id": "r2", "tipo": "recado", "texto": "Já resolvido", "link": ""}
    app = _montar(tmp_path)
    quadro(app, 10.0, recados=[recado, feito])
    quadro(app, 12.0, recados=[recado, feito], eventos=[{"id": "e1", "tipo": "pendencia", "texto": "Convite", "quando": 2.0}])
    app.alfred.notas[0].por_canto(300, 200)
    app.alfred.notas[0].movida.emit(app.alfred.notas[0])
    app.alfred.recados["r1"].por_canto(520, 240)
    app.alfred.recados["r1"].movida.emit(app.alfred.recados["r1"])
    app.alfred.recados["r2"].feito.emit(app.alfred.recados["r2"], False)
    _fechar(app)
    app = _montar(tmp_path)                                               # o pet reabre: nada foi lido do Alfred ainda
    try:
        assert [(n.text, n.canto()) for n in app.alfred.notas] == [("Convite", (300, 200))]
        nota = app.alfred.recados["r1"]
        assert list(app.alfred.recados) == ["r1"] and nota.canto() == (520, 240) and nota.detalhe == "Marina\nQuer preço"
        quadro(app, 10.0, recados=[recado, feito])
        assert app.alfred.recados == {"r1": nota} and len(app.alfred.notas) == 1   # nem duplica, nem volta o que foi feito
    finally:
        _fechar(app)


def test_recado_fica_colado_ate_ser_dispensado(app):
    link = "http://127.0.0.1:7073/painel/pendencias/20261110-marina"
    recado = {"id": "20261110-marina", "tipo": "recado", "texto": "Marina: pede orçamento", "link": link}
    quadro(app, 10.0, recados=[recado, {"id": "x", "tipo": "recado", "texto": "fora", "link": "http://golpe.test/x"}])
    assert [n.text for n in app.alfred.recados.values()] == ["Marina: pede orçamento", "fora"]   # já existia ao abrir: cola
    assert app.alfred.estado.recados[1]["link"] == ""                      # endereço de fora desta máquina não entra
    aviso = {"id": "e1", "tipo": "pendencia", "texto": "Marina: pede orçamento", "quando": 2.0}
    quadro(app, 12.0, recados=[recado], eventos=[aviso])
    assert app.alfred.notas == [] and list(app.alfred.recados) == ["20261110-marina"]   # um post-it só; "fora" saiu
    nota = app.alfred.recados["20261110-marina"]
    nota.fechada.emit(nota)
    assert app.alfred.recados == {}
    quadro(app, 14.0, recados=[recado])
    assert app.alfred.recados == {}                                        # fechado não volta
    quadro(app, 16.0, recados=[])
    assert app.alfred.recados_abertos == set()


def test_painel_da_fila_blocos_e_menus(app):
    fila = [{"id": "f1", "tipo": "backup", "rotulo": "Backup"}, {"id": "f2", "tipo": "email", "rotulo": "E-mails"}]
    quadro(app, 10.0, agora=[EMAIL], fila=fila,
           agendadas=[{"tipo": "rag", "rotulo": "Indexar", "quando": time.time() + 600},
                      {"tipo": "vigia", "rotulo": "Ronda", "quando": time.time() - 5}])
    app.floats.sync(app.floats_allowed(), app.floats_base())
    painel = app.floats.window("alfred")
    assert painel.isVisible()                                             # ligado: a fila abre sozinha
    painel.atualizar()
    assert [grupo for _r, grupo, _i in painel.blocos] == ["agora", "fila", "fila", "agendada", "mais"]
    assert not painel.grab().isNull()                                     # desenha sem erro
    centro = painel.blocos[2][0].center()
    assert painel.bloco_em(centro) == ("fila", app.alfred.estado.fila[1])
    assert "Classificando e-mails 3/12" in painel.dica("agora", app.alfred.estado.agora[0])

    pasta = app.alfred.leitor.pasta
    mais = painel.menu_de("mais", None)                                   # os menus ficam em variáveis: sem dono, o Qt os apaga
    mais.actions()[1].trigger()                                           # 1º do catálogo: na frente
    primeiro, segundo = (painel.menu_de("fila", item) for item in app.alfred.estado.fila)
    assert segundo.actions()[0].isEnabled() and not primeiro.actions()[0].isEnabled()
    segundo.actions()[0].trigger()
    segundo.actions()[1].trigger()
    agendada = painel.menu_de("agendada", app.alfred.estado.agendadas[0])
    agendada.actions()[0].trigger()
    assert painel.menu_de("agora", EMAIL) is None
    assert pedidos(pasta) == [
        {"acao": "cancelar", "id": "f2"},
        {"acao": "enfileirar", "frente": True, "tipo": "email"},
        {"acao": "enfileirar", "frente": True, "tipo": "rag"},
        {"acao": "frente", "id": "f2"},
    ]


LINKS = {"painel": "http://127.0.0.1:7073/painel", "conversa": "http://127.0.0.1:7073/painel/conversa"}


def test_atalhos_abrem_a_conversa_ao_lado_do_pet_e_o_painel_no_navegador(app, monkeypatch):
    from pestinha import plataforma
    from pestinha.mind import alfred_ctl
    janelas, abertos = [], []
    monkeypatch.setattr(plataforma, "abrir_janela_web", lambda *a: janelas.append(a) or True)
    monkeypatch.setattr(alfred_ctl.QDesktopServices, "openUrl", lambda url: abertos.append(url.toString()) or True)

    quadro(app, 10.0)                                                     # o Alfred ainda não publicou os endereços
    assert app.alfred.abrir_conversa() is False and app.alfred.abrir_painel() is False
    painel = app.floats.window("alfred")
    painel.atualizar()
    assert [grupo for _r, grupo, _i in painel.blocos] == ["livre", "mais"]

    quadro(app, 12.0, links=LINKS)
    painel.atualizar()
    assert [grupo for _r, grupo, _i in painel.blocos] == ["livre", "mais", "conversa", "painel"]
    assert "microfone" in painel.dica("conversa", None) and "Painel" in painel.dica("painel", None)
    assert not painel.grab().isNull()

    left, top, right, bottom = app.bounds()
    app.pet.body.x = right - 60                                           # colado na borda direita: a janela vai para a esquerda
    assert painel.abrir("conversa") is True and painel.abrir("painel") is True and painel.abrir("mais") is False
    url, x, y, largura, altura = janelas[0]
    assert url == LINKS["conversa"] and (largura, altura) == alfred_ctl.JANELA_CONVERSA
    assert left <= x and x + largura <= right and top <= y and y + altura <= bottom
    assert abertos == [LINKS["painel"]]                                   # o Painel vai para o navegador padrão

    monkeypatch.setattr(plataforma, "abrir_janela_web", lambda *a: False) # sem Chromium: a conversa também vai para o padrão
    assert app.alfred.abrir_conversa() is True
    assert abertos == [LINKS["painel"], LINKS["conversa"]]


def test_janela_web_usa_o_modo_app_e_nao_segura_o_pet(monkeypatch):
    from pestinha.plataforma import _comum
    chamadas = []
    monkeypatch.setattr(_comum.shutil, "which", lambda nome: "/usr/bin/brave-browser" if nome == "brave-browser" else None)
    monkeypatch.setattr(_comum.subprocess, "Popen", lambda cmd, **kw: chamadas.append((cmd, kw)))
    assert _comum.abrir_janela_web(LINKS["conversa"], 10, 20, 440, 680) is True
    cmd, kw = chamadas[0]
    assert cmd == ["/usr/bin/brave-browser", "--app=" + LINKS["conversa"], "--window-size=440,680", "--window-position=10,20"]
    assert kw["start_new_session"] is True
    monkeypatch.setattr(_comum.shutil, "which", lambda nome: None)
    assert _comum.abrir_janela_web(LINKS["conversa"], 0, 0, 1, 1) is False and len(chamadas) == 1


def test_alfred_fora_do_ar_no_painel(app):
    publicar(app.alfred.leitor.pasta, atualizado=time.time() - VALIDADE_S - 5, agora=[EMAIL])
    app.alfred._lido_em = -1e9
    app.alfred.tick(10.0)
    painel = app.floats.window("alfred")
    painel.atualizar()
    assert [grupo for _r, grupo, _i in painel.blocos] == ["livre", "mais"]
    menu = painel.menu_de("mais", None)
    assert [a.text() for a in menu.actions()] == ["Alfred fora do ar"]
    assert not painel.grab().isNull()


def test_usar_o_alfred_conta_como_atencao(app):
    app.drives.contact = 0.9                                  # carente
    quadro(app, 1.0)                                          # retrato sem `notado`: nada muda
    assert app.drives.contact == 0.9
    agora = time.time()
    quadro(app, 2.0, notado=agora)                            # você usou o Alfred: a carência cai
    assert app.drives.contact == pytest.approx(0.4)
    quadro(app, 3.0, notado=agora)                            # o mesmo uso não conta duas vezes
    assert app.drives.contact == pytest.approx(0.4)
    quadro(app, 4.0, notado=agora - 3600)                     # uso antigo: não conta
    assert app.drives.contact == pytest.approx(0.4)
    app.paused = True
    quadro(app, 5.0, notado=agora + 1)                        # pausado: nada mexe no estado
    assert app.drives.contact == pytest.approx(0.4)


def test_em_cima_da_janela_passeia_na_barra_e_prefere_a_da_frente(app, monkeypatch):
    from pestinha.body import behavior
    beh, body = app.behavior, app.pet.body
    plataformas = [(7, 500.0, 900.0, 300.0), (8, 100.0, 400.0, 500.0)]      # de cima para baixo: a 7 é a da frente
    ex = body.extents()[0]

    body.platform, beh.target_x = 7, 5000.0
    monkeypatch.setattr(behavior.random, "random", lambda: 0.99)             # não é hora de descer
    beh._ficar_na_janela(plataformas)
    assert beh.target_x == 900.0 - behavior.CLOSE_BUTTONS - ex              # o passeio para antes da beirada
    beh.target_x = 5000.0
    monkeypatch.setattr(behavior.random, "random", lambda: 0.0)              # às vezes sai pela beirada e desce
    beh._ficar_na_janela(plataformas)
    assert beh.target_x == 5000.0

    body.platform, body.x, body.y = None, 450.0, 800.0
    monkeypatch.setattr(behavior.random, "choice", lambda opcoes: opcoes[-1])
    assert beh._jump_to_window(plataformas) and body.vx > 0                  # só a da frente entra no sorteio


def test_solto_em_cima_de_um_programa_ele_age(app, monkeypatch):
    from pestinha import plataforma
    janelas, programa = [], ["firefox"]
    monkeypatch.setattr(plataforma, "abrir_janela_web", lambda *a: janelas.append(a) or True)
    monkeypatch.setattr(plataforma, "programa_em", lambda x, y: programa[0])
    links = {**LINKS, "escrita": "http://127.0.0.1:7073/painel/escrita"}
    quadro(app, 1.0, links=links)

    assert app.alfred.solto_em(0, 0, 10.0) is None                         # programa que ele não conhece
    programa[0] = "wordcraft-0.17.0-linux-x86_64.appimage"
    assert app.alfred.solto_em(0, 0, 11.0) == "escrita" and janelas[0][0] == links["escrita"]
    assert app.alfred.solto_em(0, 0, 12.0) is None and len(janelas) == 1   # solto de novo em seguida: não repete

    programa[0] = "thunderbird-bin"
    assert app.alfred.solto_em(0, 0, 13.0) == "email"
    assert [(p["acao"], p["tipo"], p["frente"]) for p in pedidos(app.alfred.leitor.pasta)] == [("enfileirar", "email", True)]

    body = app.pet.body                                                     # o sinal do corpo: soltar age, arremessar não
    app.alfred._solto.clear()
    body.vx, body.vy = 2000.0, 0.0
    app.pet.drag_ended.emit()
    assert not app.alfred._solto
    body.vx = 0.0
    app.pet.drag_ended.emit()
    assert "email" in app.alfred._solto


# ---------------- dever: você deixou vencer o que prometeu ----------------

NEGLIGENCIA = {"nivel": 0.6, "motivo": "promessa", "texto": "Mandar o orçamento (Carlos), vencida há 2 dias",
               "link": "http://127.0.0.1:7073/painel/agenda"}
PROF_DEVER = {"stage_up": [0.25, 0.5, 0.75, 1.0], "stage_hyst": 0.12}


def test_negligencia_do_retrato_e_validada(tmp_path):
    publicar(tmp_path)
    assert Leitor(tmp_path).ler().negligencia is None                      # retrato antigo, sem o campo
    publicar(tmp_path, negligencia=dict(NEGLIGENCIA, nivel=7, link="http://exemplo.com/x", texto="x" * 500))
    lido = Leitor(tmp_path).ler().negligencia
    assert lido["nivel"] == 1.0 and lido["link"] == "" and len(lido["texto"]) == TEXTO_MAX
    for ruim in (None, "muito", {"nivel": "alto"}, {"nivel": 0}, {"nivel": -1}):
        publicar(tmp_path, negligencia=ruim)
        assert Leitor(tmp_path).ler().negligencia is None


def _dever(tmp_path):
    from pestinha.core.protesto import Protesto
    return Protesto(Paths(root=tmp_path).conteudo("alfred").signs, None, kind="dever")


def _andar(p, alvo, segundos, carinho=False):
    """Roda o dever por `segundos` atrás de `alvo`; devolve os estágios por que passou."""
    estagios = []
    for i in range(int(segundos * 10)):
        mudou = p.update(0.1, 0.0, PROF_DEVER, carinho, i * 0.1, alvo=alvo)
        if mudou:
            estagios.append(mudou[1])
    return estagios


def test_dever_segue_o_nivel_e_para_nos_bracos_cruzados(tmp_path):
    p = _dever(tmp_path)
    assert _andar(p, 0.3, 600) == [1] and abs(p.grievance - 0.3) < 1e-6    # uma tarefa vencida: só o pigarro
    assert _andar(p, 0.6, 600) == [2]                                      # promessa atrasada: sarcasmo
    assert _andar(p, 1.0, 600) == [3] and p.grievance <= 1.0               # nunca revolução
    assert _andar(p, 1.0, 600, carinho=True) == [] and p.stage == 3        # carinho não resolve pendência
    assert _andar(p, 0.0, 120)[-1] == 0 and p.grievance == 0.0             # resolveu: passa depressa


def test_cartazes_do_dever(tmp_path, monkeypatch):
    from pestinha.core import protesto
    p = _dever(tmp_path)
    p.motivo = "x" * 200
    secoes = protesto.load_signs(p.signs_path)
    for estagio, secao in protesto.DEVER_SECTION.items():
        p.stage = estagio
        monkeypatch.setattr(protesto.random, "random", lambda: 0.9)        # sem citar o motivo
        info = p.escolher_cartaz()
        assert info["texto"] in secoes[secao] and not info["bandeira"]
    p.stage = 2
    monkeypatch.setattr(protesto.random, "random", lambda: 0.1)            # o sarcasmo cita o que venceu
    assert len(p.escolher_cartaz()["texto"]) == protesto.MOTIVO_MAX
    assert p.escolher_cartaz(fim_por_carinho=False)["texto"] in secoes["cumprido"]


def test_pet_cobra_o_que_venceu_e_cruza_os_bracos(app):
    from pestinha.mind import protest_ctl
    quadro(app, 1.0, negligencia=dict(NEGLIGENCIA, nivel=1.0))
    assert app.alfred.estado.negligencia["nivel"] == 1.0
    prof = dict(app.prof, stage_dwell=0.0)
    for i in range(4000):                                                  # 400 s: chega ao nível 1
        mudou = app.dever_ctl.tick(0.1, app.pet_state.tone, prof, True, i * 0.1,
                                   negligencia=app.alfred.estado.negligencia)
        if mudou:
            app.dever_ctl.on_stage(*mudou)
    assert app.dever.stage == 3 and app.dever.motivo == NEGLIGENCIA["texto"]
    assert not app.alfred._pode_encenar()                                  # de braços cruzados, não encena
    app.dever_ctl.carry(time.monotonic() + 1, asleep=False)
    cartaz = app.dever.sign
    assert cartaz is not None
    antes = app.dever.grievance
    app.dever_ctl.on_sign_clicked(cartaz)                                  # fechar não reprime: ele só volta depois
    assert app.dever.sign is None and app.dever.grievance == antes and app.dever.repressions == 0
    assert app.dever.respawn_at >= time.monotonic() + protest_ctl.DEVER_VOLTA_S - 5

    # Alfred fora do ar (ou tudo resolvido): a cobrança passa e ele mostra o cartaz de fim
    for i in range(700):
        mudou = app.dever_ctl.tick(0.1, app.pet_state.tone, prof, False, 400 + i * 0.1, negligencia=None)
        if mudou:
            app.dever_ctl.on_stage(*mudou)
    assert app.dever.stage == 0 and app.dever.sign is not None
    app.dever_ctl.drop_sign()

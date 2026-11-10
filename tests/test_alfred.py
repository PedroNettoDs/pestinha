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
    app.alfred.notas[0].clicked.emit(app.alfred.notas[0])
    assert app.alfred.notas == []


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

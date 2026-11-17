"""
Etapa 4 do multipet: o Jorge, segundo personagem, feito só de configuração e conteúdo.

Mesma rede e mesmos estágios do Bryan; muda a semente, o temperamento (pets/jorge.json) e o
conteúdo (pets/jorge/). Nada do Bryan aparece nele, e nada dele no Bryan.
"""
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.core.nervous_system import CONNECTIONS, MOTOR_SPEC, SENSORY_SPEC, LIFBrain  # noqa: E402
from pestinha.core.protesto import DEFAULT_SIGNS, load_signs  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

PATHS = Paths(root=ROOT)
POOLS = {post for _pre, post, _w, _d in CONNECTIONS}


def frases(pet_id):
    """Tudo que o pet escreve: cartazes (todas as seções), recadinhos e bilhetes tristes."""
    c = PATHS.conteudo(pet_id)
    textos = {t for lista in load_signs(c.signs).values() for t in lista}
    for arquivo in (c.notes, c.notes_sad):
        textos |= {linha.strip() for linha in arquivo.read_text(encoding="utf-8").splitlines()
                   if linha.strip() and not linha.lstrip().startswith("#")}
    return textos


def test_jorge_existe_e_e_selecionavel():
    assert config.list_pets(PATHS) == ["alfred", "bryan", "jorge"]
    jorge = config.load_pet(PATHS, "jorge")
    assert jorge["nome"] == "Jorge" and jorge["seed"] != config.load_pet(PATHS, "bryan")["seed"]
    assert len(jorge["temperamento"]) >= 8                   # nenhum campo descartado por tipo errado


def test_todo_temperamento_mexe_em_uma_ligacao_que_existe():
    """Uma chave com erro de digitação seria ignorada em silêncio; aqui ela falha."""
    validas = {f"{pre}->{post}" for pre, post, _w, _d in CONNECTIONS if pre in SENSORY_SPEC} | POOLS
    for pet in ("alfred", "bryan", "jorge"):
        chaves = set(config.load_pet(PATHS, pet)["temperamento"])
        assert chaves <= validas, (pet, chaves - validas)


def test_mesmo_cerebro_outro_temperamento():
    jorge = config.load_pet(PATHS, "jorge")
    com = LIFBrain(seed=jorge["seed"], temperament=jorge["temperamento"])
    sem = LIFBrain(seed=jorge["seed"])
    pet_app = LIFBrain(seed=7, temperament=config.load_pet(PATHS, "bryan")["temperamento"])
    assert com.W.shape == pet_app.W.shape and com.N == pet_app.N   # mesma estrutura
    assert all(com.pool(m[0]) == pet_app.pool(m[0]) for m in MOTOR_SPEC)

    def bloco(cerebro, pre, post):
        a, b = cerebro.pool(pre), cerebro.pool(post)
        return cerebro.W[a["start"]:a["start"] + a["n"], b["start"]:b["start"] + b["n"]].sum()

    for chave, ganho in jorge["temperamento"].items():           # cada ganho chega na ligação certa
        pre, post = chave.split("->")
        assert np.isclose(bloco(com, pre, post), ganho * bloco(sem, pre, post)), chave
    assert np.isclose(bloco(com, "PRESO", "FRUSTRATION"), bloco(sem, "PRESO", "FRUSTRATION"))  # o resto igual


def test_jorge_tem_conteudo_proprio_completo():
    c = PATHS.conteudo("jorge")
    placas = load_signs(c.signs)
    with open(c.signs, encoding="utf-8") as f:
        secoes = set(re.findall(r"^\[(\w+)\]", f.read(), re.M))
    assert secoes == set(DEFAULT_SIGNS)                          # não cai no neutro em nenhuma seção
    assert all(placas[s] for s in DEFAULT_SIGNS)
    assert config.Notes(c.notes).pick() and config.Notes(c.notes_sad).pick()
    assert c.bolinha_papel == PATHS.pets / "jorge" / "bolinha_papel.png"    # o panfleto dele
    assert c.bolinha_tenis.parent == PATHS.comum and c.notebook.parent == PATHS.comum


def test_nada_exclusivo_de_um_aparece_no_outro():
    neutras = {t for lista in DEFAULT_SIGNS.values() for t in lista}
    em_comum = frases("jorge") & frases("bryan")
    assert em_comum <= neutras, em_comum - neutras
    textos = " ".join(frases("jorge")).upper()
    for marca in ("BRYAN", "ABAIXO O CURSOR", "A RAM É DE QUEM USA", "ABAIXO O GERENCIADOR", "ABAIXO O ALT+F4",
                  "CURSOR, RESPEITA", "470 NEURÔNIOS"):
        assert marca not in textos, marca
    textos_bryan = " ".join(frases("bryan")).upper()
    for marca in ("JORGE", "MENTORIA", "MINDSET", "JORGECOIN"):
        assert marca not in textos_bryan, marca


def test_satira_sem_nada_de_verdade():
    """Nada de link, chave de PIX, e-mail ou valor para pagar: é só piada."""
    for texto in frases("jorge"):
        assert not re.search(r"https?://|www\.|\.com\b|R\$\s*\d|chave pix|@\w+\.\w+", texto, re.I), texto


def test_jorge_no_app(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import shutil
    import pestinha.app as app_mod
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    shutil.copytree(PATHS.comum, tmp_path / "assets" / "comum")
    paths = Paths(root=tmp_path)
    SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet="jorge"))
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    app = app_mod.PestinhaApp(SettingsStore(paths), paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    jorge = frases("jorge")
    assert app.nome == "Jorge" and app.pet_paths == paths.pet("jorge")
    assert app.tray.icon.toolTip().startswith("Pestinha · Jorge")
    assert app.revolucao.sprite is not None                     # atira panfletos
    assert app.mischief.notes.pick() in jorge
    assert set(app.castigo.cartazes) <= jorge and set(app.castigo.xingamentos) <= jorge
    for secao in DEFAULT_SIGNS:
        assert app.protest.pick(secao) in jorge
    assert "meme" in app.mischief.available("feliz", dict(app.perms, travessuras=True, memes=True))   # tem memes felizes

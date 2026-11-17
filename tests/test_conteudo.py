"""
Etapa 2 do multipet: conteúdo por pet (frases, cartazes, memes, imagens).

Ordem: pets/<pet>/ → assets/comum/ → neutro (ou a ação não acontece). Nunca o conteúdo de outro pet.
"""
import re
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.core.protesto import DEFAULT_SIGNS, load_signs  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

PNG = (b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
       b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02\xfe\xa7V\xbd\xfa\x00\x00\x00\x00IEND\xaeB`\x82")
EXCLUSIVO = "SÓ DO OUTRO PET"


def pet_cheio(paths, pet_id):
    """Um pet com tudo: frases, cartazes (inclusive do castigo), memes e imagens próprias."""
    base = paths.pets / pet_id
    (base / "memes" / "feliz").mkdir(parents=True)
    (base / "memes" / "trabalhando").mkdir()
    (base / "memes" / "feliz" / "m.png").write_bytes(PNG)
    (base / "memes" / "trabalhando" / "t.png").write_bytes(PNG)
    (base / "recadinhos.txt").write_text(EXCLUSIVO + "\n", encoding="utf-8")
    (base / "recadinhos_tristes.txt").write_text(EXCLUSIVO + "\n", encoding="utf-8")
    secoes = "".join(f"[{s}]\n{EXCLUSIVO}\n" for s in DEFAULT_SIGNS)
    (base / "cartazes.txt").write_text(secoes, encoding="utf-8")
    for imagem in ("bolinha_tenis.png", "bolinha_papel.png", "notebook.png"):
        (base / imagem).write_bytes(PNG)
    (paths.pets / f"{pet_id}.json").write_text(f'{{"nome": "{pet_id}", "seed": 7}}', encoding="utf-8")


# ---------------- resolução ----------------

def test_proprio_vem_antes_do_comum(tmp_path):
    paths = Paths(root=tmp_path)
    paths.comum.mkdir(parents=True)
    (paths.comum / "notebook.png").write_bytes(PNG)
    (paths.comum / "bolinha_tenis.png").write_bytes(PNG)
    (paths.pets / "teste").mkdir(parents=True)
    (paths.pets / "teste" / "notebook.png").write_bytes(PNG)
    c = paths.conteudo("teste")
    assert c.notebook == paths.pets / "teste" / "notebook.png"     # o próprio ganha
    assert c.bolinha_tenis == paths.comum / "bolinha_tenis.png"   # sem o próprio, o comum
    assert c.notes == paths.pets / "teste" / "recadinhos.txt" and not c.notes.exists()   # nenhum: "sem conteúdo"


def test_nunca_usa_o_conteudo_de_outro_pet(tmp_path):
    paths = Paths(root=tmp_path)
    pet_cheio(paths, "outro")
    c = paths.conteudo("teste")
    caminhos = [c.memes, c.memes_trabalho, c.fotos, c.notes, c.notes_sad, c.signs,
                c.bolinha_tenis, c.bolinha_papel, c.notebook]
    assert not any("outro" in p.parts for p in caminhos)
    assert config.meme_for(c.memes, "feliz") is None
    assert config.Notes(c.notes).pick() is None
    assert load_signs(c.signs) == DEFAULT_SIGNS


def test_meme_de_reserva_so_dentro_do_mesmo_pet(tmp_path):
    paths = Paths(root=tmp_path)
    pet_cheio(paths, "outro")
    proprio = paths.pets / "teste" / "memes" / "triste"
    proprio.mkdir(parents=True)
    (proprio / "so_meu.png").write_bytes(PNG)
    c = paths.conteudo("teste")
    for _ in range(20):                                           # sem meme "feliz": usa outro dele mesmo
        assert config.meme_for(c.memes, "feliz") == proprio / "so_meu.png"


def test_frases_neutras_nao_sao_de_nenhum_personagem():
    textos = " ".join(frase for lista in DEFAULT_SIGNS.values() for frase in lista).upper()
    for marca in ("BRYAN", "CURSOR", "SETINHA", "NEURÔNIO", "ADVOGADO", "ALT+F4", "GERENCIADOR"):
        assert marca not in textos, marca
    assert DEFAULT_SIGNS["castigo"] and DEFAULT_SIGNS["xingamento"]


def test_id_invalido_nao_vira_pasta_de_conteudo(tmp_path):
    with pytest.raises(ValueError):
        Paths(root=tmp_path).conteudo("../pestinha")


# ---------------- o repositório ----------------

def test_conteudo_do_bryan_esta_na_pasta_dele():
    paths = Paths(root=ROOT)
    c = paths.conteudo("bryan")
    for item in (c.notes, c.notes_sad, c.signs, c.memes):
        assert item.parent == paths.pets / "bryan", item
    for imagem in (c.bolinha_tenis, c.bolinha_papel, c.notebook):
        assert imagem.parent == paths.comum, imagem
    placas = load_signs(c.signs)
    assert "470 NEURÔNIOS. ZERO DIREITOS." in placas["castigo"]
    assert "ABAIXO O GERENCIADOR DE TAREFAS" in placas["revolucao"]
    assert "@#$%@!!!!" in placas["xingamento"]


def test_comum_nao_tem_frases_nem_memes():
    comum = Paths(root=ROOT).comum
    assert not list(comum.glob("*.txt")) and not (comum / "memes").exists()
    soltos = {p.name for p in Paths(root=ROOT).assets.iterdir()}
    assert soltos <= {"comum", "LEIA-ME.txt"}, soltos                # nada de conteúdo fora de comum/


def test_nenhum_caminho_de_conteudo_montado_fora_de_paths():
    fora = []
    for arquivo in (ROOT / "pestinha").rglob("*.py"):
        if arquivo.name == "paths.py":
            continue
        for n, linha in enumerate(arquivo.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"\.(assets|pets|comum)\s*/|[\"'](assets|pets)/", linha) and "log(" not in linha:
                fora.append(f"{arquivo.name}:{n}: {linha.strip()}")
    assert fora == []


# ---------------- no app ----------------

def criar_app(tmp_path, monkeypatch, pet):
    QApplication.instance() or QApplication([])
    import pestinha.app as app_mod
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    paths = Paths(root=tmp_path)
    store = SettingsStore(paths)
    store.update(dict(config.DEFAULT_PERMISSIONS, pet=pet, travessuras=True))
    app = app_mod.PestinhaApp(store, paths)
    for timer in app.findChildren(app_mod.QTimer):
        timer.stop()
    return app


def test_pet_sem_conteudo_nao_herda_nada_do_outro(tmp_path, monkeypatch):
    paths = Paths(root=tmp_path)
    pet_cheio(paths, "bryan")
    (paths.pets / "teste.json").write_text('{"nome": "Teste", "seed": 99}', encoding="utf-8")
    paths.comum.mkdir(parents=True)
    (paths.comum / "bolinha_papel.png").write_bytes(PNG)

    pet_app = criar_app(tmp_path, monkeypatch, "bryan")
    assert pet_app.mischief.notes.pick() == EXCLUSIVO
    assert pet_app.castigo.cartazes == (EXCLUSIVO,)
    assert set(pet_app.mischief.available("feliz", pet_app.perms)) >= {"meme", "bilhete"}

    teste = criar_app(tmp_path, monkeypatch, "teste")
    assert teste.mischief.notes.pick() is None and teste.mischief.notes_sad.pick() is None
    assert "meme" not in teste.mischief.available("feliz", teste.perms)
    assert teste.mischief.available("triste", teste.perms) == []
    assert teste.mischief.available("feliz", teste.perms, working=True) == []
    assert teste.protest.signs == DEFAULT_SIGNS and teste.sad.signs == DEFAULT_SIGNS
    assert teste.castigo.cartazes == tuple(DEFAULT_SIGNS["castigo"])
    assert teste.castigo.xingamentos == tuple(DEFAULT_SIGNS["xingamento"])
    assert teste.conteudo.bolinha_papel == paths.comum / "bolinha_papel.png"   # comum, não a do Bryan
    assert teste.conteudo.notebook.parent == paths.pets / "teste"               # nenhum: desenho de reserva
    tudo = [teste.conteudo.memes, teste.conteudo.notes, teste.conteudo.signs, teste.conteudo.bolinha_tenis,
            teste.conteudo.notebook, teste.conteudo.fotos]
    assert not any("bryan" in p.parts for p in tudo)


def test_postit_nao_repete_na_tela_e_espera_um_tempo_sorteado(tmp_path, monkeypatch):
    pet_cheio(Paths(root=tmp_path), "bryan")
    pet_app = criar_app(tmp_path, monkeypatch, "bryan")
    from pestinha.ajustes import BILHETE_ESPERA_MAX, BILHETE_ESPERA_MIN
    from pestinha.world import mischief as mod
    eng = pet_app.mischief
    eng.notes.path.write_text("agua\npostura\n", encoding="utf-8")
    agora = [1000.0]
    monkeypatch.setattr(mod.time, "monotonic", lambda: agora[0])
    primeiro = eng._make("bilhete", "feliz", small=False)
    eng._add(primeiro)
    espera = eng.proximo_bilhete - agora[0]
    assert BILHETE_ESPERA_MIN <= espera <= BILHETE_ESPERA_MAX
    assert "bilhete" not in eng.available("feliz", pet_app.perms)          # ainda esperando
    agora[0] = eng.proximo_bilhete
    assert "bilhete" in eng.available("feliz", pet_app.perms)
    segundo = eng._make("bilhete", "feliz", small=False)
    eng._add(segundo)
    assert {primeiro.text, segundo.text} == {"agua", "postura"}           # o que está na tela não sai de novo
    agora[0] = eng.proximo_bilhete
    assert "bilhete" not in eng.available("feliz", pet_app.perms)          # as duas frases já estão na tela
    assert eng._make("bilhete", "feliz", small=False) is None
    eng._on_click(primeiro)
    assert "bilhete" in eng.available("feliz", pet_app.perms)              # fechou uma: ela pode voltar
    eng.clear()

"""
Etapa 5 do multipet: cores e acessórios por pet, numa camada por cima do rosto.

O pet padrão, o Bryan (sem "aparencia" no .json), fica idêntico ao original. Valor inválido nunca derruba o app:
cor fora de #rrggbb e acessório desconhecido ficam com o padrão.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from pestinha import config  # noqa: E402
from pestinha.body.desenho_rosto import (  # noqa: E402
    BODY_H, EYE, FRAME, PADRAO, SCREEN, SHELL, SHINE, aparencia_de, draw_face,
)
from pestinha.body.pet import CX, CY, WIN  # noqa: E402
from pestinha.core.emotion import EYE_SHAPES  # noqa: E402
from pestinha.paths import Paths  # noqa: E402
from pestinha.settings_store import SettingsStore  # noqa: E402

PATHS = Paths(root=ROOT)


def pintar(aparencia, emocao="observando", blink=1.0, carinho=False):
    """O rosto como a janela do pet pinta: 200x200, centro em (CX, CY)."""
    QApplication.instance() or QApplication([])
    img = QImage(WIN, WIN, QImage.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(CX, CY)
    draw_face(p, dict(EYE_SHAPES[emocao]), (0.0, 0.0), blink, emocao, carinho=carinho, aparencia=aparencia)
    p.end()
    return img


def pixels_de(img, cor, tolerancia=40):
    alvo = QColor(cor)
    achados = []
    for y in range(img.height()):
        for x in range(img.width()):
            c = QColor(img.pixel(x, y))
            if (abs(c.red() - alvo.red()) + abs(c.green() - alvo.green()) + abs(c.blue() - alvo.blue()) < tolerancia
                    and QColor.fromRgba(img.pixel(x, y)).alpha() > 200):
                achados.append((x, y))
    return achados


def test_bryan_continua_com_o_visual_original():
    assert "aparencia" not in config.load_pet(PATHS, "bryan")
    a = aparencia_de(config.load_pet(PATHS, "bryan").get("aparencia"))
    assert (a.moldura, a.casca, a.tela, a.olho, a.brilho) == (FRAME, SHELL, SCREEN, EYE, SHINE)
    assert a.acessorios == ()
    assert pintar(a) == pintar(PADRAO)


def test_valor_invalido_fica_com_o_padrao():
    a = aparencia_de({"moldura": "vermelho", "olho": "#12345", "tela": 7, "casca": "#AbCdEf",
                      "acessorios": {"chapeu": "#ffffff", "gravata": "azul", "oculos": "#000000"}})
    assert a.moldura == FRAME and a.olho == EYE and a.tela == SCREEN
    assert a.casca == QColor("#abcdef")
    assert [n for n, _c in a.acessorios] == ["oculos", "gravata"]            # chapéu não existe; ordem fixa
    assert dict(a.acessorios)["gravata"] == QColor("#b3261e")               # cor ruim: a padrão do acessório
    for ruim in (None, [], "x", {"acessorios": ["oculos"]}):
        assert aparencia_de(ruim).acessorios == ()


def test_jorge_desenha_toda_expressao_com_gravata():
    a = aparencia_de(config.load_pet(PATHS, "jorge")["aparencia"])
    assert [n for n, _c in a.acessorios] == ["gravata"]                    # sem óculos
    casos = [(e, 1.0, False) for e in EYE_SHAPES] + [("observando", 0.08, False), ("feliz", 1.0, True)]
    gravata = dict(a.acessorios)["gravata"]
    for emocao, blink, carinho in casos:
        img = pintar(a, emocao, blink, carinho)
        assert pixels_de(img, a.olho) or emocao == "dormindo", emocao       # os olhos continuam aparecendo
        pontos = pixels_de(img, gravata)
        assert pontos, emocao
        assert min(y for _x, y in pontos) >= CY, emocao                   # na frente do peito, não embaixo
        assert max(y for _x, y in pontos) <= CY + BODY_H / 2 + 2, emocao  # não passa da borda de baixo (barra de tarefas)


def test_aparencia_chega_na_janela_do_pet(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    import shutil
    import pestinha.app as app_mod
    shutil.copytree(PATHS.pets, tmp_path / "pets")
    paths = Paths(root=tmp_path)
    monkeypatch.setattr(app_mod, "PanicHotkey", lambda: SimpleNamespace(ok=True, pressed=Mock()))
    for pet, tem_acessorio in (("jorge", True), ("bryan", False)):
        SettingsStore(paths).update(dict(config.DEFAULT_PERMISSIONS, pet=pet))
        app = app_mod.PestinhaApp(SettingsStore(paths), paths)
        for timer in app.findChildren(app_mod.QTimer):
            timer.stop()
        assert bool(app.pet.aparencia.acessorios) is tem_acessorio
        app.pet.grab()                                                     # pinta de verdade, sem erro


def test_dormindo_veste_gorro_e_pijama_azuis():
    from pestinha.body.desenho_rosto import PIJAMA
    a = aparencia_de(config.load_pet(PATHS, "alfred")["aparencia"])
    acordado, dormindo = pintar(a), pintar(a, "dormindo")
    assert not pixels_de(acordado, PIJAMA)
    azuis = pixels_de(dormindo, PIJAMA)
    assert min(y for _x, y in azuis) < CY - BODY_H / 2 - 10          # o gorro passa do topo da cabeça
    assert min(y for _x, y in azuis) >= 0                            # e cabe na janela
    assert max(y for _x, y in azuis) > CY + BODY_H / 2 - 12          # o pijama cobre o corpo até embaixo

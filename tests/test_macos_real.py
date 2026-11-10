"""
MACOS DE VERDADE - janelas, atalho e leituras do sistema num Mac real, sem imitar o AppKit.

Só roda no macOS (num Mac comum e no macos-latest do CI); o que precisa de tela pula sem sessão
gráfica. As partes com janela rodam em outro processo (tests/macos_cocoa.py), com o Qt no Cocoa.
Abre janelinhas por uns segundos e devolve o foco ao programa que estava na frente.
Para pular: python -m pytest -m "not macos_real".
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

if sys.platform != "darwin":
    pytest.skip("só no macOS", allow_module_level=True)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pestinha.plataforma import macos  # noqa: E402
from pestinha.plataforma._comum import rodar  # noqa: E402

JANELAS_DO_PET = ["pet", "bolinha", "objeto", "fogos", "painel"]


def _sessao_grafica():
    """Há um usuário logado com tela (sem isso, o Cocoa não abre janela)."""
    try:
        import Quartz
        return Quartz.CGSessionCopyCurrentDictionary() is not None
    except Exception:
        return False


pytestmark = pytest.mark.macos_real
requer_tela = pytest.mark.skipif(not _sessao_grafica(), reason="sem sessão gráfica no macOS")


def _rodar(modo):
    """Roda um modo de tests/macos_cocoa.py com o Qt no Cocoa e devolve o JSON que ele imprimiu."""
    processo = subprocess.run(
        [sys.executable, str(ROOT / "tests" / "macos_cocoa.py"), modo],
        cwd=ROOT, env=dict(os.environ, QT_QPA_PLATFORM="cocoa"),
        capture_output=True, text=True, timeout=120,
    )
    assert processo.returncode == 0, f"'{modo}' terminou com {processo.returncode}:\n{processo.stderr[-3000:]}"
    return json.loads(processo.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def reais():
    """Uma rodada só de janelas de verdade para todos os testes de janela (abre e troca o foco uma vez)."""
    return _rodar("janelas")


def _exige_troca_de_foco(reais):
    if not (reais["ativou"] and reais["desativou"]):
        pytest.skip("o macOS não deixou trocar o foco entre programas nesta sessão")


# ---------------- a janela do id ----------------

def test_sem_qapplication_um_id_qualquer_nao_derruba_o_processo():
    """Sem app, o platformName() do Qt responde "cocoa", e o id virava ponteiro: o processo caía (SIGSEGV)."""
    assert _rodar("sem_app") == {"sobreviveu": True}


# ---------------- janelas na frente de tudo ----------------

@requer_tela
@pytest.mark.parametrize("nome", JANELAS_DO_PET)
def test_janela_do_pet_vira_painel_que_nao_some_nem_ativa(reais, nome):
    janela = reais["janelas"][nome]
    assert janela["painel"], "o Qt.Tool deveria virar NSPanel"
    assert janela["some_ao_desativar"] is False
    assert janela["mascara"] & macos.PAINEL_SEM_ATIVAR
    assert janela["comportamento"] == macos.EM_TODOS_OS_ESPACOS
    assert janela["na_tela_antes"]


@requer_tela
def test_sem_o_ajuste_o_qt_cria_um_painel_que_some(reais):
    """A premissa do ajuste: se uma versão nova do Qt mudar isto, o ajuste pode não ser mais preciso."""
    janela = reais["janelas"]["sem_ajuste"]
    assert janela["painel"]
    assert janela["some_ao_desativar"] is True
    assert not janela["mascara"] & macos.PAINEL_SEM_ATIVAR


@requer_tela
@pytest.mark.parametrize("nome", JANELAS_DO_PET)
def test_janela_do_pet_continua_na_tela_quando_outro_programa_ganha_o_foco(reais, nome):
    _exige_troca_de_foco(reais)
    assert reais["janelas"][nome]["na_tela_depois"]


@requer_tela
def test_sem_o_ajuste_a_janela_sai_da_tela_quando_outro_programa_ganha_o_foco(reais):
    """Confirma que a janela sem ajuste some se essa versão do Qt/macOS reproduzir o comportamento."""
    _exige_troca_de_foco(reais)
    janela = reais["janelas"]["sem_ajuste"]
    if not janela["some_ao_desativar"]:
        pytest.skip("neste macOS/Qt a janela não some sem o ajuste; a regressão não se reproduz")
    assert janela["na_tela_antes"]
    assert not janela["na_tela_depois"]


@requer_tela
def test_o_pet_nao_enxerga_as_proprias_janelas_para_pousar(reais):
    assert reais["proprias_em_janelas_visiveis"] == []


# ---------------- atalho de pânico ----------------

@requer_tela
def test_atalho_registra_na_thread_principal_e_recusa_fora_dela():
    """Fora da thread principal o HIToolbox derrubava o processo (SIGTRAP): lá ele só recusa."""
    resultado = _rodar("atalho")
    assert resultado["plataforma"] == "cocoa"
    assert resultado["fora_da_thread_principal"] is False
    assert resultado["registrou"] is True
    assert resultado["de_novo"] is True


# ---------------- leituras do sistema ----------------

@requer_tela
def test_leituras_reais_tem_o_formato_que_o_resto_do_app_espera():
    ocioso = macos.ocioso_segundos()
    assert isinstance(ocioso, float) and ocioso >= 0
    nome = macos.processo_ativo()
    assert isinstance(nome, str) and nome and nome == nome.lower()
    assert isinstance(macos.tela_cheia(), bool)
    rect = macos.retangulo_ativo(1.0)
    assert rect is None or (len(rect) == 4 and rect[2] > rect[0] and rect[3] > rect[1])


@requer_tela
def test_quartz_de_verdade_tem_os_campos_que_o_app_le():
    import Quartz
    janelas = macos._listar(Quartz)
    assert janelas, "o Quartz não listou nenhuma janela (nem a barra de menus)"
    for janela in janelas:
        assert {"kCGWindowOwnerPID", "kCGWindowLayer", "kCGWindowNumber", "kCGWindowBounds"} <= set(janela.keys())
        assert {"X", "Y", "Width", "Height"} <= set(janela["kCGWindowBounds"].keys())


@requer_tela
def test_janelas_visiveis_devolvem_so_numero_e_geometria():
    """Privacidade: das janelas dos outros programas, só o número e o retângulo; nunca título nem nome."""
    for janela_id, rect, maximizada in macos.janelas_visiveis(set()):
        assert isinstance(janela_id, int)
        assert len(rect) == 4 and all(isinstance(valor, (int, float)) for valor in rect)
        assert rect[2] - rect[0] >= macos.LARGURA_MINIMA and rect[3] - rect[1] >= macos.ALTURA_MINIMA
        assert maximizada is False


def test_ioreg_de_verdade_tem_o_campo_que_o_parser_le():
    """O tempo ocioso sem pyobjc sai do ioreg: a saída real precisa ter o HIDIdleTime."""
    texto = rodar(["ioreg", "-c", "IOHIDSystem", "-d", "4"], tempo=10.0) or ""
    assert '"HIDIdleTime"' in texto
    assert macos.ocioso_do_ioreg(texto) >= 0

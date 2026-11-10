"""Partes que os três sistemas compartilham: rodar comandos do sistema, abrir uma janela de navegador e o atalho global via pynput."""

import shutil
import subprocess

from ..log import log

NAVEGADORES_APP = ("brave-browser", "chromium", "chromium-browser", "google-chrome", "microsoft-edge")


def rodar(comando, tempo=1.0):
    """Saída do comando (texto) ou None se ele não existe, falhou ou demorou demais."""
    try:
        resultado = subprocess.run(comando, capture_output=True, text=True, timeout=tempo, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return resultado.stdout if resultado.returncode == 0 else None


def abrir_janela_web(url, x, y, largura, altura):
    """
    Abre `url` numa janela própria (o modo app dos navegadores Chromium), na posição e no tamanho pedidos, sem
    esperar por ela. Devolve False se não houver um navegador desses: quem chama abre no navegador padrão.
    """
    for nome in NAVEGADORES_APP:
        caminho = shutil.which(nome)
        if not caminho:
            continue
        try:
            subprocess.Popen([caminho, f"--app={url}", f"--window-size={largura},{altura}",
                              f"--window-position={x},{y}"],
                             stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             start_new_session=True)       # o navegador não fecha junto com o pet
        except OSError:
            return False
        return True
    return False


def atalho_pynput(callback):
    """Ctrl + Alt + Shift + B em qualquer lugar do sistema. Precisa de pynput instalado."""
    try:
        from pynput import keyboard
    except Exception:
        log("[pânico] pynput não está instalado: o atalho global fica desligado (o menu da bandeja funciona)")
        return False
    try:
        listener = keyboard.GlobalHotKeys({"<ctrl>+<alt>+<shift>+b": callback})
        listener.daemon = True
        listener.start()
    except Exception as error:
        log(f"[pânico] não deu para registrar o atalho: {error}")
        return False
    return True

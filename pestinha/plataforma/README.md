# `pestinha/plataforma/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Tudo que depende do sistema operacional: programa em primeiro plano, tempo ocioso, janelas, tela cheia, foco e o atalho de pânico. Um módulo por sistema (Windows, macOS, Linux). Só nome de programa e geometria; nunca conteúdo nem título de janela.

**Pode importar de:** nada (só o sistema) (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `_comum.py` | Partes que os três sistemas compartilham: rodar comandos do sistema, abrir uma janela de navegador e o atalho global via pynput. |
| `kwin.py` | KDE Plasma 6 no Wayland: as janelas do pet rodam pelo XWayland (main.py) e os sentidos vêm do KWin. |
| `linux.py` | Linux (X11): xdotool e wmctrl para as janelas, xprintidle para o tempo ocioso, e pynput para o atalho. |
| `macos.py` | MacOS: Quartz (pyobjc) para as janelas e o tempo ocioso; AppKit para o programa em primeiro plano. |
| `windows.py` | Windows: a API do sistema (user32, dwmapi) via ctypes e pywin32. |

# `pestinha/sense/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Sentidos: o que as leituras da plataforma significam (atividade, tela cheia, janela para pousar) e registro da rotina. Nunca conteúdo nem título de janela.

**Pode importar de:** core, plataforma (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `alfred.py` | O que o Alfred (assistente que roda neste computador) está fazendo, lido dos arquivos que ele publica. |
| `senses.py` | O computador como mundo sensorial. |
| `timeline.py` | Uma linha por minuto da sua rotina, para o futuro LSTM. |

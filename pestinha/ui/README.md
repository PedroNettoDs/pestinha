# `pestinha/ui/`

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Janelas de interface: tela de permissões, bandeja, passo a passo, monitor neural e painel de protesto.

**Pode importar de:** core, sense, body, world, mind (e dos módulos compartilhados). A regra é verificada por `tests/test_arquitetura.py`.

| Arquivo | O que faz |
|---|---|
| `fila_alfred.py` | A fila de ações do Alfred na tela, como a de um jogo: o que ele faz agora e o que vem depois. |
| `float_manager.py` | Os painéis flutuantes (monitor neural e painel de protesto). |
| `monitor.py` | O que a rede está fazendo agora, sincronizado com o corpo. |
| `onboarding.py` | Passo a passo da primeira vez, com aviso de projeto em desenvolvimento. |
| `panel.py` | Medidor de protesto: quanto falta para ele entrar em greve. |
| `rotulos.py` | Os nomes que aparecem na tela, em português. |
| `ui.py` | Tela inicial de permissões, ícone na bandeja e atalho de pânico. |

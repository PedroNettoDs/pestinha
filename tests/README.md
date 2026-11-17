# `tests/` — testes automáticos

> Gerado por `ferramentas/gerar_readmes.py` a partir das docstrings. Não edite à mão: rode o script.

Rodam sem abrir janelas (o `conftest.py` da raiz liga o Qt em modo offscreen) e sempre numa pasta
temporária: nada aqui toca na `memory/` de verdade.

```bash
python -m pytest -q
```

O `python -m pytest` na raiz roda `tests/` (ver `pyproject.toml`). Testes que montam o
app inteiro usam um relógio virtual: avançam o tempo sem esperar.

A exceção é `test_macos_real.py`: no macOS, abre janelinhas de verdade por alguns segundos (num processo
à parte, `macos_cocoa.py`) e devolve o foco ao programa que estava na frente. Para pular:
`python -m pytest -m "not macos_real"`.

| Arquivo | O que faz |
|---|---|
| `macos_cocoa.py` | Roda em outro processo, com o Qt no Cocoa de verdade, para o test_macos_real.py. |
| `test_30_bugs.py` | Regressão dos 30 bugs encontrados na rodada de fuzzing e revisão (docs/auditorias/BUGS_30_RODADA.md). |
| `test_alfred.py` | Ligação com o Alfred: o leitor do retrato, o controlador que encena a atividade e o painel da fila. |
| `test_aparencia.py` | Etapa 5 do multipet: cores e acessórios por pet, numa camada por cima do rosto. |
| `test_app.py` | Testes de integração do app, com Qt em modo offscreen e tudo numa pasta temporária. |
| `test_arquitetura.py` | Regra de camadas do pacote `pestinha`: cada camada só importa das que estão abaixo dela. |
| `test_atividade.py` | Programas de trabalho: VS Code, Claude e Codex contam como programação. |
| `test_auditoria_30.py` | Contratos dos 30 bugs da auditoria (docs/auditorias/AUDITORIA_30_BUGS.md). |
| `test_bolinha.py` | Testes da bolinha e da tristeza (abandono). |
| `test_brincadeira.py` | Bolinha: colisão com post-its e estilos de brincadeira por pet. |
| `test_cantinho_cenarios.py` | 100 cenários explícitos do cantinho. |
| `test_cantinho_rede.py` | As 10 funções do cantinho que mexem na rede neural: entrada, aprendizado e efeito nos motores. |
| `test_carinho.py` | Carinho: olhinhos fechados de felicidade enquanto ele recebe carinho, e voltam ao normal depois. |
| `test_castigo.py` | Cantinho do castigo: soltar o Bryan na frente da placa prende ele, e a fuga bem-sucedida fica salva. |
| `test_castigo_bugs_rede.py` | Reproduções diagnósticas: asserções descrevem o comportamento esperado. |
| `test_castigo_integracao.py` | Cantinho do castigo dentro do app: o castigo vence a mesa e as travessuras, e o pânico encerra a fuga. |
| `test_castigo_real.py` | Cantinho no app inteiro, com relógio virtual: soltar no ar, pousar, ficar preso e reagir pela rede. |
| `test_condicionamento.py` | Testes do condicionamento: aprender a reagir antes, extinguir, e persistir. |
| `test_conteudo.py` | Etapa 2 do multipet: conteúdo por pet (frases, cartazes, memes, imagens). |
| `test_digitacao.py` | Balanço de digitação: só enquanto ele está sentado no notebook, pequeno e rítmico. |
| `test_escolha_pet.py` | Etapa 3 do multipet: escolha do personagem nas configurações e o nome certo em cada texto. |
| `test_expressao_continua.py` | Rosto contínuo: a forma dos olhos segue (valência, ativação) do cérebro, misturando as predefinidas. |
| `test_festa.py` | Fogos de artifício ligados à rede e brincadeira mais animada quando feliz. |
| `test_giro_antecipacao.py` | Antecipação do giro: antes de pular girando, ele se inclina para o lado oposto e só então pula. |
| `test_homeostase.py` | Homeostase: trabalhar é estímulo, então o tédio não sobe enquanto ele programa. |
| `test_janela_na_frente.py` | No macOS o pet não some ao trocar de programa; as Configurações pedem o foco. |
| `test_jorge.py` | Etapa 4 do multipet: o Jorge, segundo personagem, feito só de configuração e conteúdo. |
| `test_macos_real.py` | Janelas, atalho e leituras do sistema num Mac real, sem imitar o AppKit. |
| `test_melhorias_windows.py` | Melhorias para o Windows: tela cheia, vários monitores, pasta de dados, uma cópia só, início automático e fechamento seguro. |
| `test_mesa.py` | Notebook: sentar e levantar pelo disparo do neurônio SENTAR. |
| `test_migracao.py` | Etapa 1 do multipet: memória por pet (memory/pets/<pet>/) e a migração da versão antiga. |
| `test_nucleo.py` | Testes dos módulos puros: nada de Qt, nada de Windows. |
| `test_paineis.py` | Painéis do menu (monitor neural e painel de protesto): abrir à mão deve manter o painel na tela. |
| `test_pedido.py` | Pedir para trabalhar: o neurônio SENTAR decide. |
| `test_plataforma.py` | Plataforma: cada sistema expõe as mesmas funções, e as leituras de texto (wmctrl, xdotool, ioreg, janelas do Quartz) são testadas com saídas de exemplo, em qualquer sistema. |
| `test_robustez.py` | Robustez: arquivo corrompido, assets faltando, log em arquivo. |
| `test_robustez_v2.py` | Falhas do relatório técnico (docs/auditorias/ANALISE_TECNICA.md): cada caso tem um teste que reproduz o problema. |
| `test_rodinha.py` | Rodinha do mouse: girar rápido deixa o pet tonto; girar devagar não. |

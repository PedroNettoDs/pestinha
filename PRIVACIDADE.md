# Privacidade do Pestinha

O Pestinha roda só no seu computador. Ele não envia nada para a internet.

## O que ele lê

- O **nome** do programa em primeiro plano (por exemplo `code.exe`). Nunca o título nem o conteúdo da janela.
- Quanto tempo você está sem usar teclado ou mouse, e se o teclado ou o mouse foram usados agora.
- A posição do cursor, para saber se ele encostou na bolinha, se você está em cima do pet (carinho,
  cutucar) ou perto dele no cantinho do castigo.
- Se uma janela cobre a tela inteira (para não aparecer em jogos ou apresentações).
- A posição e o tamanho das janelas abertas, para ele poder pousar nas barras de título.
- No KDE Plasma com Wayland, essas leituras vêm de um script do KWin (`pestinha/plataforma/kwin_ponte.js`)
  que só existe enquanto o pet está aberto e manda geometria, pid e estado das janelas, nunca títulos.
- Só se você criar `memory/alfred.json`: o arquivo `estado.json` da pasta indicada ali, onde o assistente
  Alfred (outro programa deste computador) publica o que está fazendo, a fila e os avisos dele. O título de
  um aviso aparece na tela, num balão e num post-it. Os pedidos que você faz pela fila são gravados em
  `pedidos/`, nessa mesma pasta. Nada disso passa pela rede. Quando você clica em "Conversar" ou "Abrir
  terminal", o pet abre no navegador um endereço que o Alfred publicou; só endereços deste computador
  (`127.0.0.1` ou `localhost`) são aceitos. Veja [docs/ALFRED.md](docs/ALFRED.md).

Ele **não** lê o conteúdo nem o título de nenhuma janela, página, documento ou conversa.

## O que ele grava

Tudo fica na pasta de dados, mostrada na tela de configurações. Ela é `memory/` ao lado do programa ou, no
executável do Windows, `%LOCALAPPDATA%\Pestinha` (a menos que já exista uma `memory/` ao lado dele). Abaixo,
`memory/` significa essa pasta. Desinstalar o programa não apaga esses dados.

Do app e seu, direto em `memory/`:

| Arquivo | Conteúdo |
|---|---|
| `permissions.json` | As opções que você escolheu |
| `timeline.csv` | Uma linha por minuto: hora, categoria de programa, trocas de janela, ocioso. Só com "Registrar minha rotina" ligado, que vem desligado. O pet ainda não usa esse histórico |
| `panels.json` | Posição dos painéis, do notebook e da placa |
| `alfred.json` | Só se você criar: a pasta de atividade do Alfred (`{"pasta": "..."}`) |
| `logs/pestinha.log` | Mensagens do programa e erros inesperados (sem conteúdo de janelas) |

De cada personagem, em `memory/pets/<pet>/` (um personagem não lê a memória do outro):

| Arquivo | Conteúdo |
|---|---|
| `nervous.json` | Estado da rede neural (habituação e aprendizado) |
| `episodes.jsonl`, `preferences.json` | Resultado de cada travessura e preferências aprendidas |
| `conditioning.json` | O que ele aprendeu a antecipar |
| `drives.json` | Energia, estimulação e carência |
| `protest.json`, `sad_protest.json` | Insatisfação e tristeza |
| `castigo.json` | Fugas do cantinho, rancor e receio |
| `.migrado` | Só existe se a memória veio da versão antiga: quando migrou e o hash de cada arquivo |

Quem usou uma versão antiga (arquivos soltos em `memory/`) tem a memória migrada sozinha na primeira
abertura. Os originais não são apagados: ficam em `memory/legado/<pet>/`. Se a migração não puder ser
concluída (por exemplo, um arquivo já existe com outro conteúdo), nada é sobrescrito, ele continua usando
os arquivos antigos e avisa no ícone da bandeja.

## Como apagar

- Na tela de configurações, **Apagar histórico** apaga a rotina (`timeline.csv`), inclusive o minuto que
  ainda estava na memória.
- **Apagar todos os dados do Pestinha** apaga a pasta `memory/` inteira, com a memória de todos os personagens (pede confirmação, desliga o início com o Windows e fecha o programa). Se algum arquivo não puder ser apagado, ele avisa quais foram antes de fechar.
- Você também pode apagar a pasta `memory/` manualmente, com o programa fechado.

## Fora da pasta de dados

- **Abrir ao entrar no Windows** (desligado por padrão) grava uma entrada em
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`, só para o seu usuário.
- Um arquivo de trava na pasta temporária do sistema impede abrir duas cópias. Não contém dados seus além do
  número do processo e do nome do computador.

## Controle

- Cada permissão pode ser desligada na tela de configurações; desligar uma permissão também recolhe o que
  já estava na tela.
- O atalho **Ctrl + Alt + Shift + B** desliga tudo na hora, e ele continua desligado até você religar.

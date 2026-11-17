# Ligação com o Alfred

Esta ramificação (`alfred`) faz o pet acompanhar o **Alfred**, um assistente que roda no mesmo computador
(repositório `Alfred-Pennyworth`, fora daqui). O pet mostra o que o Alfred está fazendo, encena o trabalho e
deixa você mexer na fila de rotinas dele. Sem `memory/alfred.json`, nada disto liga e o pet é o de sempre.

## Ligar

1. Crie `memory/alfred.json` com a pasta de atividade do Alfred:

   ```json
   {"pasta": "/home/voce/dev/Alfred-Pennyworth/logs/atividade"}
   ```

2. Em **Configurações**, escolha o personagem **Alfred** (`pets/alfred.json`). Qualquer personagem acompanha o
   Alfred; este só tem a cara e as frases de mordomo.

## O que aparece

| | |
|---|---|
| **Fila** | Painel arrastável, da esquerda para a direita: o que roda agora (borda verde, com o andamento), o que você pediu (numerado), as próximas rotinas agendadas (apagadas, com a hora) e o `+`. |
| **Pedir** | `+` no painel, ou botão direito no pet, **Alfred: trabalhar em**. Clicar põe **na frente** da fila (roda em seguida); o submenu põe no fim. |
| **Reordenar** | Clique num item da fila: passar para a frente ou tirar. Clique numa agendada: fazer agora. |
| **Conversar** | Bloco 💬 no fim da fila, ou botão direito no pet. Abre a conversa do Alfred numa janela pequena de navegador ao lado do pet (modo app do Brave/Chromium; sem um deles, no navegador padrão). Lá dá para escrever ou falar pelo microfone. |
| **Terminal** | Bloco 🖥️, ou botão direito. Abre o Painel do Alfred no navegador padrão. |
| **Balão** | Em cima do pet: a atividade e o passo ("Classificando e-mails 3/12"), com barra de andamento. |
| **Cena** | E-mail, índice e backup: ele busca um objeto de um lado da tela e leva ao outro. Ronda: atravessa a tela. O resto: vai até o notebook e senta (quem decide sentar é o neurônio `SENTAR`, pelo sinal `PEDIDO`). |
| **Avisos** | Pendência nova: "!" em cima dele, o título no balão por alguns segundos e um post-it (com "Deixar bilhetes" ligado). Fechar o post-it não conta como dispensa. |

| **Recados** | O que o Alfred lista em `recados` (hoje: quem deixou recado no número de WhatsApp dele) fica num post-it. Ele também some quando o Alfred tira o recado da lista. |
| **Post-its** | Os de aviso e de recado: arrastar move, também de um monitor para outro; clicar abre o detalhe, com **Mais detalhes**, **Feito** e **Voltar**; só o botão do meio do mouse fecha. Ficam guardados em `memory/alfred_notas.json` e voltam ao mesmo lugar quando o pet reabre. Ficam atrás das outras janelas. **Mais detalhes** abre o item no Painel do Alfred (o `link`; sem ele, o Painel). **Feito** deixa o pedido `recado_feito` e a pendência é fechada também no Alfred, sem resposta ao contato; pelo botão do meio, só o post-it sai. A pendência resolvida no Alfred (Painel, WhatsApp, aplicativo) sai da lista `pendentes` e o post-it dela some sozinho. Passando de 12 avisos, o mais antigo sai. A faixa de cima de cada post-it mostra dia e hora em que o Alfred o criou (`quando`), para distinguir dois iguais. |
| **Remédio** | Recado de tipo `remedio` (dose vencida de um lembrete do Alfred): "!" e o nome no balão (💊), e um post-it "Tomar X" com os cuidados no detalhe. O botão é **Tomei**: deixa o pedido `recado_feito` e o Alfred recomeça a contagem das horas. Pelo botão do meio só o post-it sai; a dose segue aberta no Alfred, que pergunta pelo WhatsApp. |
| **Dever** | O Alfred informa em `negligencia` o que você deixou vencer (promessas e tarefas com prazo passado), com um nível de 0 a 1. A insatisfação do pet anda até esse nível (0 a 1 em 5 minutos) e ele levanta cartazes em três estágios: pigarro, sarcasmo (metade das vezes cita o que venceu) e braços cruzados (senta e para de encenar). Não há revolução. Carinho não alivia e fechar o cartaz não reprime: ele volta em 2 minutos. O clique no cartaz de cobrança também abre no navegador o item cobrado (o `link` da negligência; sem ele, o Painel). Só resolver a pendência faz passar (cai em 1 minuto e sai um cartaz de fim). A raiva passa na frente do dever, e o dever, da tristeza. Frases em `[pigarro]`, `[sarcasmo]`, `[bracos_cruzados]` e `[cumprido]` do `cartazes.txt` do pet. |
| **Atenção** | Usar o Alfred (Painel, conversa, WhatsApp, fila) conta como atenção: o campo `notado` do retrato (horário do último uso) baixa a carência dele, como um carinho. Uso com mais de 60 s não conta; pausado, também não. |
| **Solto num programa** | Solte o pet com a mão em cima da janela de um programa (arremesso não conta; só Linux X11). No **WordCraft** ele abre a Escrita do Alfred ao lado; no **Thunderbird** põe "Ler e classificar os e-mails" na frente da fila (a rotina também anota a agenda). A tabela é `PROGRAMAS` em `pestinha/mind/alfred_ctl.py`; a mesma ação só repete depois de 20 s. |
| **Janelas** | Com "Pousar em janelas" ligado, ele sobe nas barras de título das janelas não maximizadas, prefere a da frente e passeia em cima dela. |

Dormindo, de castigo, em protesto ou na sua mão, ele não encena; o balão e a fila continuam informando.

De madrugada (0h às 6h, `MADRUGADA` em `ajustes.py`), sem nada do Alfred em andamento nem na fila, ele dorme mesmo descansado, de gorro e pijama azuis. Também dorme depois de 1 h sem teclado nem mouse (`OCIOSO_PARA_DORMIR`). Dormindo, a carência não cresce e a tristeza só passa. Não acorda sozinho: só quando o Alfred cola um post-it (recado, dose de remédio ou aviso) ou quando você o acorda (cutucar, arrastar, arremessar). Acordado, fica 10 min de pé antes de voltar a dormir. Só o pet dorme: o balão, a fila e os post-its continuam.

## Contrato (arquivos, sem rede)

O Alfred grava `estado.json` na pasta de atividade; o pet só lê esse arquivo e só grava em `pedidos/`.

```json
{"versao": 1, "atualizado": 1794281596.4,
 "agora":     [{"id": "…", "tipo": "email", "rotulo": "Ler e classificar os e-mails",
                "passo": "Classificando e-mails", "feito": 3, "total": 12}],
 "fila":      [{"id": "…", "tipo": "backup", "rotulo": "Backup"}],
 "agendadas": [{"tipo": "rag", "rotulo": "Indexar os cofres", "quando": 1794281749.5}],
 "catalogo":  [{"tipo": "email", "rotulo": "Ler e classificar os e-mails"}],
 "eventos":   [{"id": "…", "tipo": "pendencia", "texto": "Convite …", "quando": 1794281600.0,
                "ref": "20261110-convite", "link": "http://127.0.0.1:7073/painel/pendencias/20261110-convite"}],
 "pendentes": [{"id": "20261110-convite", "texto": "Convite …",
                "link": "http://127.0.0.1:7073/painel/pendencias/20261110-convite"}],
 "recados":   [{"id": "20261110-marina", "tipo": "recado", "texto": "Marina: pede orçamento",
                "link": "http://127.0.0.1:7073/painel/pendencias/20261110-marina",
                "detalhe": "Marina\n2026-11-10 14:32\nPede o orçamento do site até sexta."}],
 "negligencia": {"nivel": 0.5, "motivo": "promessa", "texto": "Mandar o orçamento (Carlos), vencida há 1 dia",
                 "link": "http://127.0.0.1:7073/painel/agenda"},
 "links":     {"painel": "http://127.0.0.1:7073/painel", "conversa": "http://127.0.0.1:7073/painel/conversa"}}
```

- `atualizado` com mais de 20 s: o pet mostra "fora do ar".
- Pedidos, um arquivo JSON por pedido em `pedidos/`: `{"acao": "enfileirar", "tipo": "email", "frente": true}`,
  `{"acao": "frente", "id": "…"}`, `{"acao": "cancelar", "id": "…"}`.
- Itens malformados são descartados; textos são cortados em 120 caracteres.
- `recados`: no máximo 6; `link` segue a mesma regra de `links` (fora dela, fica vazio); `detalhe` (opcional, até 600 caracteres) é o texto que o post-it mostra ao clicar; `quando` (opcional, epoch) é a hora em que o Alfred criou o recado. `tipo` `"remedio"` é a dose de um remédio a tomar.
- `eventos`: `ref` (opcional) é a pendência do aviso; `link` segue a regra de `links`.
- `pendentes`: as pendências ainda abertas no Alfred, até 100. O post-it de aviso com `ref` fora da lista some; o
  aviso sem `ref` ganha o da pendente de mesmo `texto`. Lista ausente, ou com 100 itens (pode estar cortada): nada some.
- `negligencia`: `null` ou ausente quando nada venceu. `nivel` fora de 0 a 1 é cortado; zero, negativo ou não numérico vale como ausente. `link` segue a regra de `links`; o pet o abre quando você clica no cartaz de cobrança.
- `links`: o pet só aceita `http://127.0.0.1` ou `http://localhost` (com porta e caminho simples) e só os
  abre quando você clica. O navegador é aberto pelo pet; nenhum comando vem do arquivo.

## Onde está no código

| Arquivo | Papel |
|---|---|
| `pestinha/sense/alfred.py` | Lê e valida o retrato; grava pedidos. Sem Qt. |
| `pestinha/mind/alfred_ctl.py` | Cena, balão, avisos, pedidos da fila e os atalhos do navegador. |
| `pestinha/plataforma/_comum.py` | `abrir_janela_web`: a janela própria de navegador. |
| `pestinha/world/alfred_objetos.py` | Balão, objeto carregado e os emojis de cada tipo. |
| `pestinha/ui/fila_alfred.py` | Painel da fila e o menu de pedidos. |
| `pets/alfred.json`, `pets/alfred/` | O personagem. |
| `tests/test_alfred.py` | Testes. |

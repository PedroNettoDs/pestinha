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
| **Balão** | Em cima do pet: a atividade e o passo ("Classificando e-mails 3/12"), com barra de andamento. |
| **Cena** | E-mail, índice e backup: ele busca um objeto de um lado da tela e leva ao outro. Ronda: atravessa a tela. O resto: vai até o notebook e senta (quem decide sentar é o neurônio `SENTAR`, pelo sinal `PEDIDO`). |
| **Avisos** | Pendência nova: "!" em cima dele, o título no balão por alguns segundos e um post-it (com "Deixar bilhetes" ligado). Clicar no post-it fecha, sem contar como dispensa. |

Dormindo, de castigo, em protesto ou na sua mão, ele não encena; o balão e a fila continuam informando.

## Contrato (arquivos, sem rede)

O Alfred grava `estado.json` na pasta de atividade; o pet só lê esse arquivo e só grava em `pedidos/`.

```json
{"versao": 1, "atualizado": 1794281596.4,
 "agora":     [{"id": "…", "tipo": "email", "rotulo": "Ler e classificar os e-mails",
                "passo": "Classificando e-mails", "feito": 3, "total": 12}],
 "fila":      [{"id": "…", "tipo": "backup", "rotulo": "Backup"}],
 "agendadas": [{"tipo": "rag", "rotulo": "Indexar os cofres", "quando": 1794281749.5}],
 "catalogo":  [{"tipo": "email", "rotulo": "Ler e classificar os e-mails"}],
 "eventos":   [{"id": "…", "tipo": "pendencia", "texto": "Convite …", "quando": 1794281600.0}]}
```

- `atualizado` com mais de 20 s: o pet mostra "fora do ar".
- Pedidos, um arquivo JSON por pedido em `pedidos/`: `{"acao": "enfileirar", "tipo": "email", "frente": true}`,
  `{"acao": "frente", "id": "…"}`, `{"acao": "cancelar", "id": "…"}`.
- Itens malformados são descartados; textos são cortados em 120 caracteres.

## Onde está no código

| Arquivo | Papel |
|---|---|
| `pestinha/sense/alfred.py` | Lê e valida o retrato; grava pedidos. Sem Qt. |
| `pestinha/mind/alfred_ctl.py` | Cena, balão, avisos e pedidos da fila. |
| `pestinha/world/alfred_objetos.py` | Balão, objeto carregado e os emojis de cada tipo. |
| `pestinha/ui/fila_alfred.py` | Painel da fila e o menu de pedidos. |
| `pets/alfred.json`, `pets/alfred/` | O personagem. |
| `tests/test_alfred.py` | Testes. |

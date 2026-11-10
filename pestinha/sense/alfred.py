"""
ALFRED - o que o Alfred (assistente que roda neste computador) está fazendo, lido dos arquivos que ele publica.

O Alfred grava um retrato em <pasta>/estado.json (atividade em andamento, fila, rotinas agendadas e
avisos) e aceita pedidos em <pasta>/pedidos/. Aqui só se lê esse retrato e se deixam pedidos: nada de
rede, e nada é lido fora dessa pasta. A pasta vem de memory/alfred.json; sem esse arquivo, o pet não
acompanha o Alfred.
"""

import json
import math
import secrets
import time
from dataclasses import dataclass
from pathlib import Path

from ..store import read_json, read_lines, write_json

VERSAO = 1
VALIDADE_S = 20.0       # retrato mais velho que isso: o Alfred está fora do ar
TEXTO_MAX = 120
LIMITES = {"agora": 4, "fila": 20, "agendadas": 12, "catalogo": 30, "eventos": 10}


@dataclass(frozen=True)
class Estado:
    """Retrato do Alfred: cada lista tem dicionários já validados (textos curtos, números finitos ou None)."""
    online: bool = False
    agora: tuple = ()           # {id, tipo, rotulo, passo, feito, total}
    fila: tuple = ()            # {id, tipo, rotulo}
    agendadas: tuple = ()       # {tipo, rotulo, quando}
    catalogo: tuple = ()        # {tipo, rotulo}
    eventos: tuple = ()         # {id, tipo, texto, quando}


FORA_DO_AR = Estado()


def pasta_do_alfred(paths):
    """Pasta de atividade do Alfred escrita em memory/alfred.json ({"pasta": "/caminho"}), ou None."""
    dados = read_json(paths.alfred, default=None)
    pasta = dados.get("pasta") if isinstance(dados, dict) else None
    if not isinstance(pasta, str) or not Path(pasta).is_absolute():
        return None
    return Path(pasta)


def _texto(valor):
    return valor.strip()[:TEXTO_MAX] if isinstance(valor, str) else ""


def _numero(valor):
    ok = isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
    return float(valor) if ok else None


def _itens(bruto, nome, textos, numeros=()):
    """Só os itens bem formados (dicionário com `tipo`), com os campos pedidos e no máximo LIMITES[nome]."""
    itens = []
    for d in bruto.get(nome) if isinstance(bruto.get(nome), list) else []:
        if not isinstance(d, dict):
            continue
        item = {campo: _texto(d.get(campo)) for campo in textos}
        item.update({campo: _numero(d.get(campo)) for campo in numeros})
        if item["tipo"]:
            itens.append(item)
    return tuple(itens[:LIMITES[nome]])


def interpretar(texto):
    """(atualizado, Estado) a partir do texto de estado.json, ou None se não for um retrato válido."""
    try:
        bruto = json.loads(texto)
    except ValueError:
        return None
    if not isinstance(bruto, dict) or bruto.get("versao") != VERSAO:
        return None
    atualizado = _numero(bruto.get("atualizado"))
    if atualizado is None:
        return None
    return atualizado, Estado(
        online=True,
        agora=_itens(bruto, "agora", ("id", "tipo", "rotulo", "passo"), ("feito", "total")),
        fila=_itens(bruto, "fila", ("id", "tipo", "rotulo")),
        agendadas=tuple(a for a in _itens(bruto, "agendadas", ("tipo", "rotulo"), ("quando",))
                        if a["quando"] is not None),
        catalogo=_itens(bruto, "catalogo", ("tipo", "rotulo")),
        eventos=_itens(bruto, "eventos", ("id", "tipo", "texto"), ("quando",)),
    )


class Leitor:
    """Lê o retrato do Alfred (só relê o arquivo quando ele muda) e deixa pedidos para ele."""

    def __init__(self, pasta, relogio=time.time):
        """`pasta` é a de atividade do Alfred; `relogio` existe para os testes."""
        self.pasta = Path(pasta)
        self.relogio = relogio
        self._mtime = None
        self._lido = None           # (atualizado, Estado) do arquivo atual, ou None se ilegível

    def ler(self):
        """O retrato atual, ou FORA_DO_AR se o arquivo não existe, é inválido ou está velho."""
        arquivo = self.pasta / "estado.json"
        try:
            mtime = arquivo.stat().st_mtime_ns
        except OSError:
            return FORA_DO_AR
        if mtime != self._mtime:
            # read_lines e não read_json: um arquivo ilegível do Alfred não é nosso para renomear
            self._mtime = mtime
            self._lido = interpretar("\n".join(read_lines(arquivo)))
        if self._lido is None or abs(self.relogio() - self._lido[0]) > VALIDADE_S:
            return FORA_DO_AR
        return self._lido[1]

    def pedir(self, acao, **campos):
        """Deixa um pedido (enfileirar, frente, cancelar) na pasta do Alfred; devolve True se gravou."""
        nome = f"{int(self.relogio() * 1000)}-{secrets.token_hex(3)}.json"
        try:
            write_json(self.pasta / "pedidos" / nome, {"acao": acao, **campos})
        except (OSError, ValueError):
            return False
        return True

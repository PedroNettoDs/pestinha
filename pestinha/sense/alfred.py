"""
ALFRED - o que o Alfred (assistente que roda neste computador) está fazendo, lido dos arquivos que ele publica.

O Alfred grava um retrato em <pasta>/estado.json (atividade em andamento, fila, rotinas agendadas, avisos
e os endereços locais do Painel dele) e aceita pedidos em <pasta>/pedidos/. Aqui só se lê esse retrato e se deixam pedidos: nada de
rede, e nada é lido fora dessa pasta. A pasta vem de memory/alfred.json; sem esse arquivo, o pet não
acompanha o Alfred.
"""

import json
import math
import re
import secrets
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..store import read_json, read_lines, write_json

VERSAO = 1
VALIDADE_S = 20.0       # retrato mais velho que isso: o Alfred está fora do ar
TEXTO_MAX = 120
DETALHE_MAX = 600       # o detalhe de um recado (o que o post-it mostra ao clicar)
LIMITES = {"agora": 4, "fila": 20, "agendadas": 12, "catalogo": 30, "eventos": 10, "recados": 6}
# Só endereços desta máquina: é o que o pet aceita abrir no navegador.
URL_LOCAL = re.compile(r"^http://(127\.0\.0\.1|localhost)(:\d{1,5})?(/[\w\-./]*)?$")


@dataclass(frozen=True)
class Estado:
    """Retrato do Alfred: cada lista tem dicionários já validados (textos curtos, números finitos ou None)."""
    online: bool = False
    agora: tuple = ()           # {id, tipo, rotulo, passo, feito, total}
    fila: tuple = ()            # {id, tipo, rotulo}
    agendadas: tuple = ()       # {tipo, rotulo, quando}
    catalogo: tuple = ()        # {tipo, rotulo}
    eventos: tuple = ()         # {id, tipo, texto, quando}
    recados: tuple = ()         # {id, tipo, texto, link, detalhe}: o que espera você; link local, ou ""
    links: dict = field(default_factory=dict)   # nome -> URL local (painel, conversa)
    notado: float | None = None     # quando você usou o Alfred pela última vez (epoch), ou None
    negligencia: dict | None = None     # {nivel 0..1, motivo, texto, link}: o que você deixou vencer, ou None


FORA_DO_AR = Estado()


def pasta_do_alfred(paths):
    """Pasta de atividade do Alfred escrita em memory/alfred.json ({"pasta": "/caminho"}), ou None."""
    dados = read_json(paths.alfred, default=None)
    pasta = dados.get("pasta") if isinstance(dados, dict) else None
    if not isinstance(pasta, str) or not Path(pasta).is_absolute():
        return None
    return Path(pasta)


def _texto(valor, maximo=TEXTO_MAX):
    return valor.strip()[:maximo] if isinstance(valor, str) else ""


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


def _recados(bruto):
    """Os recados bem formados, cada um com o `detalhe` (texto mais longo) que veio junto, ou ""."""
    brutos = [d for d in bruto.get("recados") or [] if isinstance(d, dict) and _texto(d.get("tipo"))] \
        if isinstance(bruto.get("recados"), list) else []
    itens = _itens(bruto, "recados", ("id", "tipo", "texto", "link"))
    return tuple(dict(item, detalhe=_texto(d.get("detalhe"), DETALHE_MAX)) for item, d in zip(itens, brutos))


def _links(bruto):
    """Só os links com nome e endereço local bem formados (http://127.0.0.1 ou localhost)."""
    links = bruto.get("links")
    return {nome: url for nome, url in (links.items() if isinstance(links, dict) else ())
            if isinstance(nome, str) and isinstance(url, str) and len(url) <= 200 and URL_LOCAL.match(url)}


def _negligencia(bruto):
    """O que você deixou vencer, já validado: nível entre 0 e 1, textos curtos e link só local. Sem nada, None."""
    d = bruto.get("negligencia")
    nivel = _numero(d.get("nivel")) if isinstance(d, dict) else None
    if not nivel or nivel < 0:
        return None
    link = _texto(d.get("link"))
    return {"nivel": min(1.0, nivel), "motivo": _texto(d.get("motivo")), "texto": _texto(d.get("texto")),
            "link": link if URL_LOCAL.match(link) else ""}


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
        recados=tuple(dict(r, link=r["link"] if URL_LOCAL.match(r["link"]) else "")
                      for r in _recados(bruto) if r["id"] and r["texto"]),
        links=_links(bruto),
        notado=_numero(bruto.get("notado")),
        negligencia=_negligencia(bruto),
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
        """Deixa um pedido (enfileirar, frente, cancelar, recado_feito) na pasta do Alfred; devolve True se gravou."""
        nome = f"{int(self.relogio() * 1000)}-{secrets.token_hex(3)}.json"
        try:
            write_json(self.pasta / "pedidos" / nome, {"acao": acao, **campos})
        except (OSError, ValueError):
            return False
        return True

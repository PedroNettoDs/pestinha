"""
PATHS - onde ficam as coisas. Um objeto, criado uma vez e passado adiante.

Nada no resto do código monta caminho sozinho: quem precisa de um arquivo
pergunta ao Paths. Assim os testes passam uma pasta temporária e nada encosta
na sua pasta memory/ de verdade.

O conteúdo (frases, cartazes, memes, imagens) vem de pets/<pet>/ e depois de assets/comum/
(ConteudoPaths); um personagem nunca usa o conteúdo de outro.

A memória tem duas partes:
    memory/                 o que é do app e de você: permissões, rotina, painéis, log
    memory/pets/<pet>/      o que é de cada personagem (PetPaths): rede, memória, homeostase...
Arquivos da versão antiga (tudo solto em memory/) são migrados por pestinha/migracao.py e os
originais ficam guardados em memory/legado/<pet>/.
"""

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# Rodando como executável (PyInstaller): assets, pets e memory ficam ao lado do .exe,
# para você poder editar as pastas sem reempacotar.
ROOT = (Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent)

ID_DE_PET = re.compile(r"^[a-z0-9][a-z0-9_-]{0,39}$")    # vira nome de pasta: nada de "..", "/" ou espaços


def pet_id_valido(pet_id):
    """Diz se o id pode virar nome de pasta: só minúsculas, números, '-' e '_', até 40 caracteres."""
    return isinstance(pet_id, str) and bool(ID_DE_PET.match(pet_id))


def pasta_de_dados(root, congelado=None, sistema=sys.platform, ambiente=os.environ):
    """
    Onde gravar a memória. O padrão é memory/ ao lado do programa, mas o executável do Windows pode estar
    numa pasta sem permissão de escrita (Program Files): sem uma memory/ já existente, usa %LOCALAPPDATA%.
    """
    if congelado is None:
        congelado = getattr(sys, "frozen", False)
    ao_lado = Path(root) / "memory"
    local = ambiente.get("LOCALAPPDATA")
    if congelado and sistema == "win32" and local and not ao_lado.exists():
        return Path(local) / "Pestinha"
    return ao_lado


@dataclass(frozen=True)
class PetPaths:
    """Arquivos de um personagem. `base` é a pasta dele; `nome_rede` muda no modo compatível."""
    base: Path
    nome_rede: str = "nervous.json"

    @property
    def nervous(self):
        """Estado da rede neural do pet (pesos e habituação)."""
        return self.base / self.nome_rede

    @property
    def episodes(self):
        """Histórico de travessuras e o resultado de cada uma (uma linha por episódio)."""
        return self.base / "episodes.jsonl"

    @property
    def preferences(self):
        """Preferências aprendidas: quais travessuras ele mais gosta."""
        return self.base / "preferences.json"

    @property
    def drives(self):
        """Homeostase: energia, estimulação e carência."""
        return self.base / "drives.json"

    @property
    def protest(self):
        """Insatisfação acumulada e o estágio do protesto (raiva)."""
        return self.base / "protest.json"

    @property
    def sad_protest(self):
        """Estado da tristeza (o protesto de abandono)."""
        return self.base / "sad_protest.json"

    @property
    def conditioning(self):
        """O que ele aprendeu a antecipar (condicionamento)."""
        return self.base / "conditioning.json"

    @property
    def castigo(self):
        """Cantinho do castigo: fugas, rancor e receio."""
        return self.base / "castigo.json"

    @property
    def marcador(self):
        """Existe só depois que a migração deste pet foi validada e concluída."""
        return self.base / ".migrado"

    def todos(self):
        """Os oito arquivos de estado do pet: a rede e os sete de memória."""
        return [self.nervous, self.episodes, self.preferences, self.drives, self.protest,
                self.sad_protest, self.conditioning, self.castigo]


@dataclass(frozen=True)
class ConteudoPaths:
    """
    Conteúdo de um personagem. Cada item é procurado em `proprio` (pets/<pet>/) e depois em
    `comum` (assets/comum/). Se não existir em nenhum, o caminho devolvido é o do próprio pet,
    que não existe: quem lê trata como "sem conteúdo". Nunca procura na pasta de outro pet.
    """
    proprio: Path
    comum: Path

    def resolver(self, nome):
        """Caminho do item `nome`: primeiro no pet, depois no comum; se nenhum tiver, o do pet (inexistente)."""
        for base in (self.proprio, self.comum):
            if (base / nome).exists():
                return base / nome
        return self.proprio / nome

    @property
    def memes(self):
        """Pasta de memes por emoção (feliz/, bravo/...)."""
        return self.resolver("memes")

    @property
    def memes_trabalho(self):
        """Memes de quando você programa e ele não está sentado no notebook."""
        return self.resolver("memes/trabalhando")

    @property
    def fotos(self):
        """Fotos que ele pode trazer (só com 'Trazer fotos' ligado)."""
        return self.resolver("fotos")

    @property
    def notes(self):
        """Recadinhos (post-its) de todo dia."""
        return self.resolver("recadinhos.txt")

    @property
    def notes_sad(self):
        """Bilhetes que ele cola quando está triste."""
        return self.resolver("recadinhos_tristes.txt")

    @property
    def signs(self):
        """cartazes.txt: frases dos cartazes de protesto, por seção."""
        return self.resolver("cartazes.txt")

    @property
    def bolinha_tenis(self):
        """Imagem da bolinha que ele chuta."""
        return self.resolver("bolinha_tenis.png")

    @property
    def bolinha_papel(self):
        """Imagem da bolinha de papel (ou panfleto) que ele atira na revolução."""
        return self.resolver("bolinha_papel.png")

    @property
    def notebook(self):
        """Imagem do notebook."""
        return self.resolver("notebook.png")


@dataclass(frozen=True)
class Paths:
    """Todos os caminhos do app. `root` é a pasta do programa (ou a do .exe); `dados`, a da memória."""
    root: Path = ROOT
    dados: Path = None

    def __post_init__(self):
        """Sem `dados` explícito, escolhe a pasta da memória pela regra de pasta_de_dados."""
        if self.dados is None:
            object.__setattr__(self, "dados", pasta_de_dados(self.root))

    # ----- conteúdo que você edita -----

    @property
    def assets(self):
        """Pasta de assets (conteúdo neutro e comum)."""
        return self.root / "assets"

    @property
    def comum(self):
        """Conteúdo neutro, de qualquer personagem: imagens da bolinha e do notebook, suas fotos."""
        return self.assets / "comum"

    @property
    def programas(self):
        """Programas extras que contam como trabalho, jogo, música etc. (lista que você edita)."""
        return self.comum / "programas.json"

    @property
    def pets(self):
        """`<pet>.json` (quem ele é) e a pasta `<pet>/` (as frases, cartazes e memes dele)."""
        return self.root / "pets"

    def definicao(self, pet_id):
        """pets/<pet>.json: nome, semente da rede, temperamento. É o que faz um pet existir."""
        if not pet_id_valido(pet_id):
            raise ValueError(f"id de pet inválido: {pet_id!r}")
        return self.pets / f"{pet_id}.json"

    def conteudo(self, pet_id):
        """Conteúdo de um pet (ConteudoPaths): pasta do pet, com fallback para assets/comum/."""
        if not pet_id_valido(pet_id):
            raise ValueError(f"id de pet inválido: {pet_id!r}")
        return ConteudoPaths(self.pets / pet_id, self.comum)

    # ----- estado do app e seu (global) -----

    @property
    def memory(self):
        """Pasta da memória (memory/ ou %LOCALAPPDATA%\\Pestinha): tudo que é seu e do app, fora do código."""
        return self.dados

    @property
    def permissions(self):
        """Suas permissões (o que o pet pode fazer)."""
        return self.memory / "permissions.json"

    @property
    def timeline(self):
        """Sua rotina, um minuto por linha (só com 'Aprender minha rotina' ligado)."""
        return self.memory / "timeline.csv"

    @property
    def panels(self):
        """Posição dos painéis e do notebook na tela."""
        return self.memory / "panels.json"

    @property
    def alfred(self):
        """Ligação com o Alfred: {"pasta": "..."} com a pasta de atividade dele. Sem o arquivo, não há ligação."""
        return self.memory / "alfred.json"

    @property
    def log(self):
        """Log do programa (sem conteúdo de janelas)."""
        return self.memory / "logs" / "pestinha.log"

    # ----- estado de cada personagem -----

    @property
    def memoria_dos_pets(self):
        """Pasta com a memória de cada personagem: memory/pets/<pet>/."""
        return self.memory / "pets"

    @property
    def legado(self):
        """Originais da versão antiga, guardados pela migração (nunca apagados automaticamente)."""
        return self.memory / "legado"

    def pet(self, pet_id):
        """Arquivos de estado do personagem `pet_id` (memory/pets/<pet_id>/)."""
        if not pet_id_valido(pet_id):
            raise ValueError(f"id de pet inválido: {pet_id!r}")
        return PetPaths(self.memoria_dos_pets / pet_id)

    def pet_legado(self, pet_id):
        """Modo compatível: os arquivos soltos em memory/, como na versão antiga."""
        if not pet_id_valido(pet_id):
            raise ValueError(f"id de pet inválido: {pet_id!r}")
        return PetPaths(self.memory, nome_rede=f"{pet_id}_nervous.json")

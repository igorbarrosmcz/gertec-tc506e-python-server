import socket
import threading
import os
import time
import unicodedata

from pathlib import Path
from datetime import datetime
from connection_manager import ConnectionManager

connection_manager = ConnectionManager()



# ============================================================
# CONFIGURACAO
# ============================================================

HOST = "0.0.0.0"
PORTA = 6502

# Caminho do arquivo gerado pelo sistema
ARQUIVO_PRODUTOS = Path(__file__).parent / "Produto.txt"

# Encodings comuns em arquivos gerados no Windows
ENCODINGS = (
    "utf-8-sig",
    "cp1252",
    "latin-1",
)


# ============================================================
# ESTADO DO CATALOGO
# ============================================================

produtos = {}

arquivo_mtime = None

lock_produtos = threading.Lock()


# ============================================================
# LOG
# ============================================================

def log(mensagem):
    agora = datetime.now().strftime(
        "%d/%m/%Y %H:%M:%S"
    )

    print(
        f"[{agora}] {mensagem}",
        flush=True
    )


# ============================================================
# LEITURA DO ARQUIVO
# ============================================================

def ler_arquivo_produtos():
    """
    Tenta abrir Produto.txt utilizando diferentes
    codificacoes comuns no Windows.
    """

    ultimo_erro = None

    for encoding in ENCODINGS:
        try:
            with open(
                ARQUIVO_PRODUTOS,
                "r",
                encoding=encoding
            ) as arquivo:

                return arquivo.readlines()

        except UnicodeDecodeError as erro:
            ultimo_erro = erro

    if ultimo_erro:
        raise ultimo_erro

    return []


def carregar_produtos(forcar=False):
    """
    Carrega o Produto.txt em memoria.

    Formato esperado:

    CODIGO|DESCRICAO|PRECO
    """

    global produtos
    global arquivo_mtime

    try:
        mtime_atual = os.path.getmtime(
            ARQUIVO_PRODUTOS
        )

        # Se o arquivo nao mudou, nao reler
        if (
            not forcar
            and arquivo_mtime == mtime_atual
        ):
            return

        linhas = ler_arquivo_produtos()

        novo_catalogo = {}

        linhas_invalidas = 0

        duplicados = 0

        for numero_linha, linha in enumerate(
            linhas,
            start=1
        ):
            linha = linha.strip()

            if not linha:
                continue

            partes = linha.split("|", 2)

            if len(partes) != 3:
                linhas_invalidas += 1

                log(
                    f"Linha invalida "
                    f"{numero_linha}: "
                    f"{linha[:80]}"
                )

                continue

            codigo = partes[0].strip()
            descricao = partes[1].strip()
            preco = partes[2].strip()

            if not codigo:
                linhas_invalidas += 1
                continue

            if codigo in novo_catalogo:
                duplicados += 1

            novo_catalogo[codigo] = {
                "descricao": descricao,
                "preco": preco
            }

        with lock_produtos:
            produtos = novo_catalogo

            arquivo_mtime = mtime_atual

        log(
            f"Catalogo atualizado: "
            f"{len(novo_catalogo)} produtos."
        )

        if linhas_invalidas:
            log(
                f"Linhas invalidas ignoradas: "
                f"{linhas_invalidas}"
            )

        if duplicados:
            log(
                f"Codigos duplicados encontrados: "
                f"{duplicados}"
            )

    except FileNotFoundError:
        log(
            f"ERRO: arquivo nao encontrado: "
            f"{ARQUIVO_PRODUTOS}"
        )

    except PermissionError:
        log(
            f"ERRO: sem permissao para ler: "
            f"{ARQUIVO_PRODUTOS}"
        )

    except Exception as erro:
        log(
            f"ERRO ao carregar catalogo: "
            f"{erro}"
        )


def buscar_produto(codigo):
    """
    Atualiza o cache se o TXT tiver sido modificado
    e procura o produto pelo codigo.
    """

    carregar_produtos()

    with lock_produtos:
        return produtos.get(codigo)


# ============================================================
# TRATAMENTO DE TEXTO
# ============================================================

def normalizar_texto(texto):
    """
    Remove acentos e caracteres que podem causar
    problemas no display do terminal.
    """

    texto = unicodedata.normalize(
        "NFKD",
        texto
    )

    texto = texto.encode(
        "ascii",
        "ignore"
    ).decode("ascii")

    texto = texto.replace("|", " ")

    texto = " ".join(
        texto.split()
    )

    return texto


def formatar_descricao(descricao):
    """
    Limita a descricao para evitar textos excessivamente
    longos no display do terminal.

    Pode ser ajustado posteriormente conforme necessario.
    """

    descricao = normalizar_texto(
        descricao
    )

    # Limite inicial conservador
    return descricao[:40]


# ============================================================
# PROTOCOLO TC506E
# ============================================================

def remover_null(dados):
    return dados.replace(
        b"\x00",
        b""
    )


def interpretar_pacote(dados):
    """
    Exemplos observados:

    b'#tc506e|4.4.4 S\\x00'
    b'#7891000102626\\x00'
    """

    texto = dados.decode(
        "latin-1",
        errors="ignore"
    )

    texto = texto.replace(
        "\x00",
        ""
    )

    return texto.strip()


def extrair_codigo(texto):
    """
    Recebe:

    #7891000102626

    Retorna:

    7891000102626
    """

    if texto.startswith("#"):
        texto = texto[1:]

    return texto.strip()


def montar_resposta_produto(produto):
    """
    Formato validado no TC506E:

    #DESCRICAO|PRECO\\x00
    """

    descricao = formatar_descricao(
        produto["descricao"]
    )

    preco = produto["preco"]

    resposta = (
        f"#{descricao}|{preco}\x00"
    )

    return resposta.encode(
        "latin-1",
        errors="replace"
    )


def montar_resposta_nao_encontrado():
    """
    Resposta enviada quando o codigo nao existe.
    """

    resposta = (
        "#PRODUTO NAO CADASTRADO|0,00\x00"
    )

    return resposta.encode(
        "latin-1"
    )


# ============================================================
# ATENDIMENTO DO TERMINAL
# ============================================================

def atender_terminal(
    cliente,
    endereco
):
    ip = endereco[0]

    conexao_anterior = connection_manager.register(
        ip,
        cliente
    )

    if conexao_anterior:

        log(
            f"Nova sessao assumiu o terminal: {ip}"
        )

    porta_remota = endereco[1]

    log(
        f"TC506E conectado: "
        f"{ip}:{porta_remota}"
    )

    try:
        cliente.settimeout(60)

        # ----------------------------------------------------
        # HANDSHAKE
        # ----------------------------------------------------

        cliente.sendall(
            b"#ok"
        )

        log(
            f"{ip} <- #ok"
        )

        buffer = b""

        while True:
            try:
                dados = cliente.recv(4096)

            except socket.timeout:
                # Terminal pode ficar minutos sem leitura.
                continue

            if not dados:
                log(
                    f"{ip} encerrou a conexao."
                )
                break

            buffer += dados

            # O TC506E termina as mensagens em 0x00.
            while b"\x00" in buffer:
                pacote, buffer = buffer.split(
                    b"\x00",
                    1
                )

                if not pacote:
                    continue

                # Recolocamos apenas para facilitar o log
                pacote_completo = (
                    pacote + b"\x00"
                )

                log(
                    f"{ip} -> "
                    f"{repr(pacote_completo)}"
                )

                texto = interpretar_pacote(
                    pacote_completo
                )

                # --------------------------------------------
                # IDENTIFICACAO DO TERMINAL
                # --------------------------------------------

                if texto.lower().startswith(
                    "#tc506e|"
                ):
                    log(
                        f"Terminal identificado: "
                        f"{texto}"
                    )

                    continue

                # --------------------------------------------
                # CONSULTA
                # --------------------------------------------

                codigo = extrair_codigo(
                    texto
                )

                if not codigo:
                    continue

                log(
                    f"Consulta: {codigo}"
                )

                produto = buscar_produto(
                    codigo
                )

                if produto is None:
                    log(
                        f"Produto nao encontrado: "
                        f"{codigo}"
                    )

                    resposta = (
                        montar_resposta_nao_encontrado()
                    )

                else:
                    log(
                        f"Produto encontrado: "
                        f"{produto['descricao']} "
                        f"| R$ {produto['preco']}"
                    )

                    resposta = (
                        montar_resposta_produto(
                            produto
                        )
                    )

                log(
                    f"{ip} <- "
                    f"{repr(resposta)}"
                )

                cliente.sendall(
                    resposta
                )

    except ConnectionResetError:
        log(
            f"{ip} resetou a conexao."
        )

    except ConnectionAbortedError:
        log(
            f"{ip} abortou a conexao."
        )

    except OSError as erro:

        if getattr(erro, "winerror", None) == 10038:

            log(
                f"Sessao antiga encerrada: {ip}"
            )

        else:

            log(
                f"ERRO no terminal {ip}: "
                f"{erro}"
            )


    except Exception as erro:

        log(
            f"ERRO no terminal {ip}: "
            f"{erro}"
        )

    finally:

        conexao = connection_manager.remove(
            ip,
            cliente
        )

        try:
            cliente.close()

        except Exception:
            pass


        if conexao:

            log(
                f"Conexao encerrada: {ip} "
                f"| Tempo conectado: "
                f"{conexao['duration']}"
            )

        else:

            log(
                f"Conexao ignorada (sessao substituida): {ip}"
            )

# ============================================================
# MONITOR DO TXT
# ============================================================

def monitorar_catalogo():
    """
    Verifica periodicamente se Produto.txt mudou.

    A busca individual tambem verifica a alteracao,
    mas este monitor permite atualizar o cache mesmo
    sem ocorrer nenhuma consulta.
    """

    while True:
        try:
            carregar_produtos()

        except OSError as erro:

            if getattr(erro, "winerror", None) == 10038:

                log(
                    f"Conexao substituida por nova sessao: {ip}"
                )

            else:

                log(
                    f"ERRO no terminal {ip}: "
                    f"{erro}"
                )


        except Exception as erro:

            log(
                f"ERRO no terminal {ip}: "
                f"{erro}"
            )

        time.sleep(2)


# ============================================================
# SERVIDOR
# ============================================================

def iniciar_servidor():
    print()
    print("=" * 60)
    print(
        " GERTEC TC506E - SERVIDOR DE PRECOS"
    )
    print("=" * 60)

    print(
        f"Arquivo Python : "
        f"{os.path.abspath(__file__)}"
    )

    print(
        f"Catalogo       : "
        f"{ARQUIVO_PRODUTOS}"
    )

    print(
        f"Endereco       : "
        f"{HOST}:{PORTA}"
    )

    print("=" * 60)
    print()

    carregar_produtos(
        forcar=True
    )

    # Monitor automatico do Produto.txt
    thread_monitor = threading.Thread(
        target=monitorar_catalogo,
        daemon=True
    )

    thread_monitor.start()

    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    servidor.bind(
        (
            HOST,
            PORTA
        )
    )

    servidor.listen(20)

    log(
        f"Servidor ativo em "
        f"{HOST}:{PORTA}"
    )

    log(
        "Aguardando terminais TC506E..."
    )

    try:
        while True:
            cliente, endereco = (
                servidor.accept()
            )

            thread = threading.Thread(
                target=atender_terminal,
                args=(
                    cliente,
                    endereco
                ),
                daemon=True
            )

            thread.start()

    except KeyboardInterrupt:
        log(
            "Servidor encerrado "
            "pelo usuario."
        )

    finally:
        servidor.close()


if __name__ == "__main__":
    iniciar_servidor()
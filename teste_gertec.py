import socket
import os

HOST = "0.0.0.0"
PORTA = 6502


def imprimir_pacote(dados: bytes):
    print()
    print("========== PACOTE RECEBIDO ==========")
    print("Bytes :", len(dados))
    print("RAW   :", repr(dados))
    print("HEX   :", dados.hex(" "))

    try:
        print("ASCII :", repr(dados.decode("ascii")))
    except UnicodeDecodeError:
        pass

    try:
        print("TEXTO :", repr(dados.decode("latin-1")))
    except Exception as erro:
        print("Erro ao decodificar:", erro)

    print("=====================================")


def main():
    print("======================================")
    print("TESTE GERTEC TC506E")
    print("Arquivo:", os.path.abspath(__file__))
    print("======================================")

    servidor = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    servidor.setsockopt(
        socket.SOL_SOCKET,
        socket.SO_REUSEADDR,
        1
    )

    servidor.bind((HOST, PORTA))
    servidor.listen(5)

    print(f"Escutando em {HOST}:{PORTA}")
    print("Aguardando conexao do TC506E...")

    try:
        while True:
            cliente, endereco = servidor.accept()

            print()
            print("======================================")
            print("TC506E CONECTOU")
            print("Endereco:", endereco)
            print("======================================")

            try:
                cliente.settimeout(30)

                # Handshake validado no TC506E
                handshake = b"#ok"

                print(
                    "Enviando handshake:",
                    repr(handshake)
                )

                print(
                    "HEX:",
                    handshake.hex(" ")
                )

                cliente.sendall(handshake)

                while True:
                    try:
                        dados = cliente.recv(4096)

                    except socket.timeout:
                        print(
                            "[TIMEOUT] Nenhum dado "
                            "recebido em 30 segundos."
                        )
                        continue

                    if not dados:
                        print(
                            "[DESCONECTOU] Terminal "
                            "encerrou a conexao."
                        )
                        break

                    imprimir_pacote(dados)

            except ConnectionResetError:
                print(
                    "[RESET] Conexao resetada "
                    "pelo TC506E."
                )

            except Exception as erro:
                print("[ERRO]", erro)

            finally:
                cliente.close()

                print(
                    "Aguardando nova conexao..."
                )

    except KeyboardInterrupt:
        print()
        print("Servidor encerrado pelo usuario.")

    finally:
        servidor.close()


if __name__ == "__main__":
    main()
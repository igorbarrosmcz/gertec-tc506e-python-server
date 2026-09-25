import socket

HOST = "127.0.0.1"
PORTA = 6502

CODIGO = "7891000102626"


def main():
    cliente = socket.socket(
        socket.AF_INET,
        socket.SOCK_STREAM
    )

    cliente.settimeout(5)

    try:
        print(f"Conectando em {HOST}:{PORTA}...")

        cliente.connect(
            (HOST, PORTA)
        )

        handshake = cliente.recv(1024)

        print(
            "Handshake recebido:",
            repr(handshake)
        )

        identificacao = (
            b"#tc506e|4.4.4 S\x00"
        )

        print(
            "Enviando identificacao:",
            repr(identificacao)
        )

        cliente.sendall(
            identificacao
        )

        consulta = (
            f"#{CODIGO}\x00"
        ).encode("latin-1")

        print(
            "Enviando consulta:",
            repr(consulta)
        )

        cliente.sendall(
            consulta
        )

        resposta = cliente.recv(
            4096
        )

        print(
            "Resposta recebida:",
            repr(resposta)
        )

        print(
            "Texto:",
            resposta.decode(
                "latin-1",
                errors="replace"
            )
        )

    finally:
        cliente.close()


if __name__ == "__main__":
    main()
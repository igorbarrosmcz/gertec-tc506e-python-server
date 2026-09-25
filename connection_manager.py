import socket
from datetime import datetime
import threading



class ConnectionManager:

    def __init__(self):
        self.connections = {}
        self.lock = threading.Lock()


    def register(self, ip, client_socket):
        """
        Registra nova conexao.

        Caso exista uma conexao ativa para o mesmo IP,
        encerra a anterior.

        Retorna a conexao antiga.
        """

        old_connection = None

        with self.lock:

            if ip in self.connections:

                old_connection = self.connections[ip]

                try:
                    endereco_remoto = old_connection["socket"].getpeername()

                    old_connection["remote_ip"] = endereco_remoto[0]
                    old_connection["remote_port"] = endereco_remoto[1]

                except OSError:
                    pass

                try:
                    old_connection["socket"].shutdown(
                        socket.SHUT_RDWR
                    )

                except Exception:
                    pass

                try:
                    old_connection["socket"].close()

                except Exception:
                    pass

            self.connections[ip] = {
                "socket": client_socket,
                "connected_at": datetime.now()
            }

        return old_connection



    def remove(self, ip, client_socket=None):
        """
        Remove uma conexão.

        Só remove se for a conexão atualmente registrada.
        """

        with self.lock:

            if ip not in self.connections:
                return None


            current = self.connections[ip]


            if (
                client_socket is None
                or current["socket"] == client_socket
            ):

                connection = self.connections.pop(ip)

                connection["disconnected_at"] = datetime.now()

                connection["duration"] = (
                    connection["disconnected_at"]
                    -
                    connection["connected_at"]
                )

                return connection


        return None



    def get_connection(self, ip):
        """
        Retorna conexão ativa de um IP.
        """

        with self.lock:
            return self.connections.get(ip)



    def count(self):
        """
        Retorna quantidade de conexões ativas.
        """

        with self.lock:
            return len(self.connections)



    def list_connections(self):
        """
        Lista conexões ativas.
        """

        with self.lock:
            return self.connections.copy()
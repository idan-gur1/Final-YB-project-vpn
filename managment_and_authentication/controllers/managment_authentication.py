import socket

from .base_server import Server
from .database import Database

SERVICE_SECRET_CODE = b"code123-123"  # temp


class AuthenticationManagement(Server):
    def __init__(self, database: Database, ip="0.0.0.0", port=55555):
        """
        setting up the handler server
        :param ip: str
        :param port: int
        """

        super().__init__(ip, port)

        self.database = database
        self.waiting_dual_auth = []
        self.waiting_ip = []
        self.connected_client_ips = {}
        self.services = {}

    def _handle_data(self, client_sock: socket.socket, msg: bytes):
        if msg.startswith(SERVICE_SECRET_CODE):
            name = msg.decode()[len(SERVICE_SECRET_CODE):]
            self.services[name] = client_sock

        elif msg.startswith(b"out_auth||"):
            if len(msg.split(b"||")) != 3:
                self.send_message(client_sock, b"bad")
                return

            email, password = msg.decode().split("||")[1:]
            if self.database.check_user_exists(email, password):
                self.send_message(client_sock, b"auth_ok")
                self.waiting_dual_auth.append(email)

            else:
                self.send_message(client_sock, b"auth_bad")

        elif msg.startswith(b"out_dual_auth||"):
            if len(msg.split(b"||")) != 3:
                self.send_message(client_sock, b"bad")
                return

            email, otp = msg.decode().split("||")[1:]

            if email not in self.waiting_dual_auth:
                self.send_message(client_sock, b"bad")
                return

            if self.database.check_user_otp(email, otp):
                self.waiting_dual_auth.remove(email)

                services_msg = "|".join(f"{name},{service_sock.getpeername()[0]}" for name, service_sock in self.services.items() if name != "outer_user_manager")

                self.send_message(client_sock, b"dual_auth_ok||"+services_msg.encode())
                self.waiting_ip.append(client_sock)

            else:
                self.send_message(client_sock, b"dual_auth_bad")
        elif msg.startswith(b"out_new_ip||"):
            if client_sock not in self.waiting_ip:
                # not the user
                return

            if len(msg.split(b"||")) != 2:
                self.send_message(client_sock, b"bad")
                return

            ip = msg.decode().split("||")[1]

            self.connected_client_ips[client_sock] = ip

            for name, service in self.services.items():
                if name != "outer_user_manager":
                    self.send_message(service, b"new" + ip.encode())

            self.waiting_ip.remove(client_sock)
            self.send_message(client_sock, b"ok")

        elif msg == b"client_disconnected":
            host = self.connected_client_ips[client_sock]

            self.connected_client_ips.pop(client_sock)

            for name, service in self.services.items():
                if name != "outer_user_manager":
                    self.send_message(service, b"left" + host.encode())

        elif msg.startswith(b"login||"):
            if len(msg.split(b"||")) != 3:
                self.send_message(client_sock, b"bad")
                return

            email, password = msg.decode().split("||")[1:]
            if self.database.check_user_exists(email, password):
                self.send_message(client_sock, b"auth_ok")
                self.waiting_dual_auth.append(email)

            else:
                self.send_message(client_sock, b"auth_bad")

        elif msg.startswith(b"dual_auth||"):
            if len(msg.split(b"||")) != 3:
                self.send_message(client_sock, b"bad")
                return

            email, otp = msg.decode().split("||")[1:]

            if email not in self.waiting_dual_auth:
                self.send_message(client_sock, b"bad")
                return

            if self.database.check_user_otp(email, otp):
                self.waiting_dual_auth.remove(email)

                services_msg = "|".join(f"{name},{service_sock.getpeername()[0]}" for name, service_sock in self.services.items() if name != "outer_user_manager")
                self.send_message(client_sock, b"dual_auth_ok||" + services_msg.encode())

                host, _ = client_sock.getpeername()

                self.connected_client_ips[client_sock] = host

                for name, service in self.services.items():
                    if name != "outer_user_manager":
                        self.send_message(service, b"new" + host.encode())

            else:
                self.send_message(client_sock, b"dual_auth_bad")


# >>> import socket
# >>> socket.inet_aton('115.255.8.97')
# b's\xff\x08a'
# >>> _
# b's\xff\x08a'
# >>> _
# b's\xff\x08a'
# >>> binascii.hexlify(_).upper()
# b'73FF0861'
# >>> binascii.unhexlify(b'73FF0861')
# b's\xff\x08a'
# >>> socket.inet_ntoa(b's\xff\x08a')
# '115.255.8.97'
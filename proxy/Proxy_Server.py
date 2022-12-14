import socket
from _thread import start_new_thread
from logger import Logger


class Proxy:
    def __init__(self, ip="0.0.0.0", port=8080):
        self.addr = ip, port

        self.web_servers = []
        self.__base_buffer = 4096

        self.logger = Logger("proxy", "proxy server started")

        self.__setup_socket()

    def __setup_socket(self):
        """
        setting up the server socket object
        :return: None
        """
        self.__server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.__server_socket.bind(("0.0.0.0", 8080))

    def start(self):
        """
        starting the server's socket and mainloop
        :return: None
        """
        self.__server_socket.listen()

        self.__main_loop()

    def __main_loop(self):
        """
        get client requests and start the needed handler
        :return: None
        """
        while True:
            try:
                client, address = self.__server_socket.accept()
            except KeyboardInterrupt:
                break

            start_new_thread(self.handle_client_request, (client, address))

            # # need different handler for http and https
            # request = client.recv(self.__base_buffer)
            #
            # http_method = request.split(b" ")[0]
            #
            # if http_method == b'CONNECT':
            #     start_new_thread(self.handle_https, (client, address, request))
            # else:
            #     start_new_thread(self.handle_http, (client, address, request))

    def handle_client_request(self, client, address):
        # need different handler for http and https
        self.logger.info(f"connection from client {address[0]}", True)
        try:
            request = client.recv(self.__base_buffer)
        except:
            self.logger.error(f"could not receive data from client {address[0]}")
            client.close()
            return

        http_method = request.split(b" ")[0]

        if http_method == b'CONNECT':
            start_new_thread(self.handle_https, (client, address, request))
        else:
            start_new_thread(self.handle_http, (client, address, request))

    def handle_https(self, client_sock, client_address, connect_request):
        """
        handling client proxy connections over https
        :param client_sock: socket - the socket of the client
        :param client_address: tuple - ip and port of the client
        :param connect_request: bytes - http connect request of the client
        :return: None
        """

        # initializing socket to webserver
        server, port = connect_request.split(b" ")[1].split(b":")
        webserver_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            webserver_sock.connect((server.decode(), int(port)))
        except:
            self.logger.warning(f"could not connect to webserver {server.decode()}")
            self.logger.debug(f"{connect_request}")
            
            client_sock.close()

        # reporting to client that connection has been Established
        reply = "HTTP/1.0 200 Connection established\r\n"
        reply += "Proxy-agent: Idan_Proxy\r\n"
        reply += "\r\n"
        client_sock.send(reply.encode())

        # setting to non blocking to allow ping-pong like traffic
        webserver_sock.setblocking(False)
        client_sock.setblocking(False)

        self.logger.info(f"{client_address[0]} made connection with {server.decode()} over https")

        self.web_servers.append(server.decode())

        # main loop of https tunnel
        while True:
            try:
                connect_request = client_sock.recv(self.__base_buffer)
                webserver_sock.sendall(connect_request)
            except BlockingIOError:
                pass
            except:
                break

            try:
                reply = webserver_sock.recv(self.__base_buffer)
                client_sock.sendall(reply)
            except BlockingIOError:
                pass
            except:
                break

        self.logger.info(f"closed connection with {client_address[0]} and server {server.decode()}")

        self.web_servers.remove(server.decode())
        webserver_sock.close()
        client_sock.close()

    def handle_http(self, client_sock, client_address, http_request):
        """
        handling client proxy connections over http
        :param client_sock: socket - the socket of the client
        :param client_address: tuple - ip and port of the client
        :param http_request: bytes - http connect request of the client
        :return: None
        """

        # initializing socket to webserver
        host_line = [data for data in http_request.split(b"\r\n") if b"Host:" in data]

        if len(host_line) < 1:
            self.logger.warning(f"bad http request by client {client_address[0]}")
            #self.logger.debug(f"{http_request}")
            client_sock.close()
            return

        host_line = host_line[0]
        
        # web_server_data = http_request.split(b"\r\n")[1].split(b":")[1:]
        web_server_data = host_line.split(b":")[1:]
        web_server, port = web_server_data[0].strip(), 80 if len(web_server_data) == 1 else web_server_data[1]

        webserver_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.debug(f"{http_request}")

        try:
            webserver_sock.connect((web_server.decode(), int(port)))
        except:
            self.logger.warning(f"could not connect to webserver {web_server.decode()}")
            #self.logger.debug(f"{http_request}")
            client_sock.close()
            return

        self.logger.info(f"{client_address[0]} made connection with {web_server.decode()} over http")
        self.web_servers.append(web_server.decode())

        # getting requested data from client and sending it to the server
        http_request_for_webserver = http_request[:http_request.find(b" ") + 1] + http_request[http_request.find(b"/",
                                                                                                                 http_request.find(
                                                                                                                     b"//") + 2):]
        try:
            webserver_sock.sendall(http_request_for_webserver)
        except:
            self.logger.warning(f"connection to webserver {web_server.decode()} has been closed")
            #self.logger.debug(f"{http_request}")
            client_sock.close()
            webserver_sock.close()
            return

        data = b''
        data_fragment = b'1'

        # getting data from webserver
        while data_fragment:
            try:
                data_fragment = webserver_sock.recv(4096)
            except:
                self.logger.error(f"could not receive data from http server {web_server.decode()}")
                break

            data = data + data_fragment
        else:
            try:
                client_sock.sendall(data)
            except:
                self.logger.warning(f"connection to client {client_address[0]} has been closed")
                #self.logger.debug(f"{http_request}")
                client_sock.close()
                webserver_sock.close()

        self.logger.info(f"closed connection with {client_address[0]} and server {web_server.decode()}")
        self.web_servers.remove(web_server.decode())
        webserver_sock.close()
        client_sock.close()


if __name__ == '__main__':
    proxy = Proxy()
    proxy.start()

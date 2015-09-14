import socket
import select
import sys


class Proxy(object):
    """Accepts connections on listen_address and forwards them to
    target_address
    """
    def __init__(self, listen_address, target_address):
        self.target_address = target_address
        self.channels = {}  # associate client <-> target
        self.connections = {}  # 2nd dict for sockets to be indexed by fileno
        self.buffers = {}
        self.proxy_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.proxy_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.proxy_socket.bind(listen_address)
        self.proxy_socket.listen(1)
        self.proxy_socket.setblocking(0)

        self.epoll = select.epoll()
        self.epoll.register(self.proxy_socket.fileno(), select.EPOLLIN)

        self.running = False

    def accept_new_client(self):
        """Try to connect to the target and when this succeeds, accept the
        client connection.  Keep track of both and their connections
        """
        target = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            target.connect(self.target_address)
        except socket.error as serr:
            print("Error: " + str(serr))
            target = False

        connection, address = self.proxy_socket.accept()
        if target:
            connection.setblocking(0)
            self.epoll.register(connection.fileno(), select.EPOLLIN)
            self.epoll.register(target.fileno(), select.EPOLLIN)

            # save the sockets for the target and client
            self.connections[connection.fileno()] = connection
            self.connections[target.fileno()] = target

            # save the sockets but point them to each other
            self.channels[connection.fileno()] = target
            self.channels[target.fileno()] = connection

            self.buffers[connection.fileno()] = b''
            self.buffers[target.fileno()] = b''
        else:
            connection.send(bytes("Can't connect to {}\n".format(address),
                                  'UTF-8'))
            connection.close()

    def relay_data(self, fileno):
        """Receive a chunk of data on fileno and relay that data to its
        corresponding target socket. Spill over to buffers what can't be sent
        """
        data = self.connections[fileno].recv(1024)
        if len(data) == 0:
            # peer closed connection, shut down socket and
            # wait for EPOLLHUP to clean internal structures
            self.epoll.modify(fileno, 0)
            self.connections[fileno].shutdown(socket.SHUT_RDWR)
        else:
            # if there's already something in the send queue, add to it
            if len(self.buffers[fileno]) > 0:
                self.buffers[fileno] += data
            else:
                try:
                    byteswritten = self.channels[fileno].send(data)
                    if len(data) > byteswritten:
                        self.buffers[fileno] = data[byteswritten:]
                        self.epoll.modify(fileno, select.EPOLLOUT)
                except socket.error:
                    self.connections[fileno].send(
                        bytes("Can't reach server\n", 'UTF-8'))
                    self.epoll.modify(fileno, 0)
                    self.connections[fileno].shutdown(socket.SHUT_RDWR)

    def send_buffer(self, fileno):
        byteswritten = self.channels[fileno].send(self.buffers[fileno])
        if len(self.buffers[fileno]) > byteswritten:
            self.buffers[fileno] = self.buffers[fileno][byteswritten:]
            self.epoll.modify(fileno, select.EPOLLOUT)

    def close_channels(self, fileno):
        """Close the socket and its corresponding target socket and stop
        listening for them"""
        out_fileno = self.channels[fileno].fileno()
        self.epoll.unregister(fileno)

        # close and delete both ends
        self.channels[out_fileno].close()
        self.channels[fileno].close()
        del self.channels[out_fileno]
        del self.channels[fileno]
        del self.connections[out_fileno]
        del self.connections[fileno]

    def main_loop(self):
        self.running = True
        try:
            while self.running:
                events = self.epoll.poll(1)
                for fileno, event in events:
                    if fileno == self.proxy_socket.fileno():
                        self.accept_new_client()
                    elif event & select.EPOLLIN:
                        self.relay_data(fileno=fileno)
                    elif event & select.EPOLLOUT:
                        self.send_buffer(fileno=fileno)
                    elif event & (select.EPOLLERR | select.EPOLLHUP):
                        self.close_channels(fileno=fileno)
                        break
        finally:
            self.epoll.unregister(self.proxy_socket.fileno())
            self.epoll.close()
            self.proxy_socket.shutdown(socket.SHUT_RDWR)
            self.proxy_socket.close()

if __name__ == '__main__':
    server = Proxy(listen_address=('127.0.0.1', 8080),
                   target_address=('127.0.0.1', 8081))
    try:
        server.main_loop()
    except KeyboardInterrupt:
        sys.exit(1)

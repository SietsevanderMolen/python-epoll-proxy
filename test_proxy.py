import threading
import time
import select
import socket
import sys

import pytest

from proxy import Proxy


class EchoServer(object):
    def __init__(self, listen_address):
        self.listen_address = listen_address
        self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        self.server.bind(listen_address) 
        self.server.listen(2) 

    def main_loop(self):
        input = [self.server] 
        while True: 
            inputready,outputready,exceptready = select.select(input,[],[]) 
            for s in inputready: 
                if s == self.server: 
                    client, address = self.server.accept() 
                    input.append(client) 
                else: 
                    data = s.recv(4096) 
                    if data: 
                        s.send(data) 
                    else: 
                        s.close() 
                        input.remove(s) 
        self.server.close()


class EchoClient(object):
    def __init__(self, listen_address):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect(listen_address)

    def echo(self, message):
        self.s.send(bytes(message, 'UTF-8'))
        data = self.s.recv(4096)
        self.s.close()
        return data

def setup_module(module):
    module.server = EchoServer(listen_address=("127.0.0.1", 8081))
    t = threading.Thread(target=server.main_loop, args=())
    t.daemon = True
    t.start()

    module.proxy = Proxy(listen_address=("127.0.0.1", 8080),
                         target_address=("127.0.0.1", 8081))
    u = threading.Thread(target=proxy.main_loop, args=())
    u.daemon = True
    u.start()

def teardown_module(module):
    module.proxy.running = False

def test_without_proxy():
    client = EchoClient(listen_address=("127.0.0.1", 8081))
    data = client.echo(message="echo")
    assert data == b"echo"

def test_hello_world():
    client = EchoClient(listen_address=("127.0.0.1", 8080))
    data = client.echo(message="Hello world!")
    assert data == b"Hello world!"

def test_double_hello_world():
    client1 = EchoClient(listen_address=("127.0.0.1", 8080))
    client2 = EchoClient(listen_address=("127.0.0.1", 8080))
    data1 = client1.echo(message="hello")
    data2 = client2.echo(message="world")
    assert data1 == b"hello"
    assert data2 == b"world"

def test_long():
    message = "Thisisalongmessage"*50
    client = EchoClient(listen_address=("127.0.0.1", 8080))
    data = client.echo(message=message).decode('UTF-8')
    assert data == message

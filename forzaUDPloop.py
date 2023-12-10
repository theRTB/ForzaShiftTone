# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:59:57 2023

@author: RTB
"""

import socket
from concurrent.futures.thread import ThreadPoolExecutor

from fdp import ForzaDataPacket

class ForzaUDPLoop():
    def __init__(self, ip, port, packet_format, loop_func):
        self.threadPool = ThreadPoolExecutor(max_workers=8,
                                             thread_name_prefix="exec")
        self.isRunning = False

        self.ip = ip
        self.port = port
        self.packet_format = packet_format
        self.loop_func = loop_func

    def loop_toggle(self, toggle=None):
        if toggle and not self.isRunning:
            def starting():
                self.isRunning = True
                self.fdp_loop(self.loop_func)
            self.threadPool.submit(starting)
        else:
            def stopping():
                self.isRunning = False
            self.threadPool.submit(stopping)
        return self.isRunning

    def fdp_loop(self, loop_func=None):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.settimeout(1)
                s.bind((self.ip, self.port))
                while self.isRunning:
                    fdp = nextFdp(s, self.packet_format)
                    if fdp is None:
                        continue
    
                    if loop_func is not None:
                        loop_func(fdp)
        except BaseException as e:
            print(e)

    def loop_close(self):
        """close program
        """
        self.isRunning = False
        self.threadPool.shutdown(wait=False)
        
def nextFdp(server_socket: socket, format: str):
    """next fdp

    Args:
        server_socket (socket): socket
        format (str): format

    Returns:
        [ForzaDataPacket]: fdp
    """
    try:
        message, _ = server_socket.recvfrom(1024)
        return ForzaDataPacket(message, packet_format=format)
    except BaseException:
        return None
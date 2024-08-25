# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:59:57 2023

@author: RTB
"""

import socket
from concurrent.futures.thread import ThreadPoolExecutor

from base.fdp import ForzaDataPacket

#consider limiting the recvfrom size to the correct packet size
class ForzaUDPLoop():
    def __init__(self, config, loop_func):
    # def __init__(self, ip, port, packet_format, loop_func):
        self.threadPool = ThreadPoolExecutor(max_workers=8,
                                             thread_name_prefix="exec")
        self.isRunning = False

        self.ip = '' #config.ip #ip not necessary
        self.port = config.port
        self.packet_format = config.packet_format
        self.loop_func = loop_func

    def firststart(self):
        if self.port != '':
            self.toggle(True)

    def toggle(self, toggle=None):
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
                    fdp = self.nextFdp(s)
                    if fdp is None:
                        continue
    
                    if loop_func is not None:
                        loop_func(fdp)
        except BaseException as e:
            print(e)

    def is_running(self):
        return self.isRunning

    def close(self):
        """close program
        """
        self.isRunning = False
        self.threadPool.shutdown(wait=False)
        
    def nextFdp(self, server_socket):
        try:
            rawdata, _ = server_socket.recvfrom(1024)
            return ForzaDataPacket(rawdata, packet_format=self.packet_format)
        except BaseException as e:
            print(f"BaseException {e}")
            return None
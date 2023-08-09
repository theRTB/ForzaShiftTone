# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:59:57 2023

@author: RTB
"""

import socket
from mttkinter import mtTkinter as tkinter
from concurrent.futures.thread import ThreadPoolExecutor

from fdp import ForzaDataPacket

from config import config

#base class for a tkinter GUI that listens to UDP for packets by a forza title
class ForzaUIBase():
    TITLE = 'ForzaUIBase'
    WIDTH, HEIGHT = 400, 200
    def __init__(self):
        self.threadPool = ThreadPoolExecutor(max_workers=8,
                                             thread_name_prefix="exec")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.settimeout(1)
        self.server_socket.bind((config.ip, config.port))

        self.root = tkinter.Tk()
        self.root.title(self.TITLE)
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.resizable(False, False)
        
        self.active = tkinter.IntVar(value=1)

        # self.__init__window()

        # def __init__window(self):
        #     if self.active.get():
        #         self.active_handler()
        #     tkinter.Checkbutton(self.root, text='Active',
        #                         variable=self.active, 
        #                         command=self.active_handler).pack()
        #     self.mainloop()

    def mainloop(self):
        self.root.mainloop()

    def active_handler(self):
        if self.active.get():
            def starting():
                self.isRunning = True
                self.fdp_loop(self.loop_func)
            self.threadPool.submit(starting)
        else:
            def stopping():
                self.isRunning = False
            self.threadPool.submit(stopping)

    def loop_func(self, fdp):
        pass

    def fdp_loop(self, loop_func=None):
        try:
            while self.isRunning:
                fdp = nextFdp(self.server_socket, config.packet_format)
                if fdp is None:
                    continue

                if loop_func is not None:
                    loop_func(fdp)
        except BaseException as e:
            print(e)

    def close(self):
        """close program
        """
        self.isRunning = False
        self.threadPool.shutdown(wait=False)
        self.server_socket.close()
        self.root.destroy()
        
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
# -*- coding: utf-8 -*-
"""
Created on Mon Feb 19 20:46:18 2024

@author: RTB
"""
from mttkinter import mtTkinter as tkinter

from forzabase.forzaudploop import ForzaUDPLoop

class GUIButtonStartStop():
    def __init__(self, root, command):
        self.tkvar = tkinter.StringVar(value='Start')
        self.button = tkinter.Button(root, borderwidth=3, 
                                         textvariable=self.tkvar, 
                                         command=command)

    def toggle(self, toggle):
        self.tkvar.set('Start' if toggle else 'Stop')

    def grid(self, row, column, *args, **kwargs):
        self.button.grid(row=row, column=column, *args, **kwargs)
    
    def pack(self, *args, **kwargs):
        self.button.pack(*args, **kwargs)
    
    def invoke(self):
        self.button.invoke()
        
class GUIStatus():
    def __init__(self, root, value):
        self.tkvar = tkinter.StringVar(value=value)            
        self.label = tkinter.Label(root, textvariable=self.tkvar, 
                                   relief=tkinter.GROOVE, width=12)    

    def grid(self, row, column, *args, **kwargs):
        self.label.grid(row=row, column=column, *args, **kwargs)
    
    def set(self, value):
        self.tkvar.set(value)

class GenericGUIUDPLoop():
    def __init__(self, root, config, loop_func=None):
        super().__init__(config, loop_func=loop_func)
        self.state = 'Stopped'
        
        self.init_tkinter(root, config)        

    def init_tkinter(self, root, config):
        self.frame = tkinter.LabelFrame(root, text='Connection')
        
        self.buttonstartstop = GUIButtonStartStop(self.frame, 
                                                  self.startstop_handler)
        self.status = GUIStatus(self.frame, self.state)
        
        self.buttonstartstop.grid(row=1, column=0)
        self.status.grid(         row=1, column=1, columnspan=2)
    
    def grid(self, row, column, *args, **kwargs):
        self.frame.grid(row=row, column=column, *args, **kwargs)

    #convenience function
    def firststart(self):
        self.startstop_handler() #implied start, not explicit start

    def startstop_handler(self, event=None):
        self.buttonstartstop.toggle(self.is_running()) #toggle text
        self.toggle(True)
    
    def update_status(self, value):
        self.state = value
        self.status.set(self.state)
    
    #same logic as in GTUDPLoop toggle. We seem to be running into a race 
    #condition where self.isRunning is not updated yet to test for status
    #update after calling the base function in GTUDPLoop
    def toggle(self, toggle=None):
        if toggle and not self.isRunning:
            self.update_status('Started')
        else:
            self.update_status('Stopped')
    
        super().toggle(toggle)
    
class GUIForzaUDPLoop(GenericGUIUDPLoop, ForzaUDPLoop):
    def __init__(self, root, config, loop_func=None):
        super().__init__(root, config, loop_func)
        
    def nextFdp(self, server_socket):
        value = super().nextFdp(server_socket)
        
        if value is None and self.state in ['Started', 'Receiving']:
            self.update_status('Timeout')
        if value is not None and self.state in ['Started','Waiting','Timeout']:
            self.update_status('Receiving')
        
        return value

# -*- coding: utf-8 -*-
"""
Created on Mon Feb 19 20:46:18 2024

@author: RTB
"""
from mttkinter import mtTkinter as tkinter

from base.gtudploop import GTUDPLoop

#TODO: update this class to use ipaddress library
class GUITargetIP():
    def __init__(self, root, defaultguivalue=''):
        self.defaultguivalue = defaultguivalue
        
        self.tkvar = tkinter.StringVar(value=defaultguivalue)    
        
        self.label = tkinter.Label(root, text='PS IP')        
        self.entry = tkinter.Entry(root, width=13, textvariable=self.tkvar,
                                   justify=tkinter.RIGHT)
        
        self.hide_ip = False
        self.label.bind('<Double-Button-1>', self.hide_ip_handler)
    
    #sticky and columnspan are not forwarded to the grid function
    def grid(self, column, sticky='', columnspan=1, *args, **kwargs):
        self.label.grid(column=column, sticky=tkinter.E, *args, **kwargs)
        self.entry.grid(column=column+1, sticky=tkinter.W, columnspan=2, 
                                                                *args,**kwargs)

    def toggle(self, toggle):
        state = tkinter.NORMAL if toggle else 'readonly'
        self.entry.config(state=state)

    def get(self):
        return self.tkvar.get()

    def hide_ip_handler(self, event=None):
        fg = '#000000' if self.hide_ip else '#F0F0F0'
        self.entry.config(fg=fg)
        self.hide_ip = not self.hide_ip
        
    def reset(self):
        self.tkvar.set(self.defaultguivalue)

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
        
class GUIGTUDPLoop(GTUDPLoop):
    def __init__(self, root, config, loop_func=None):
        super().__init__(config.target_ip, loop_func=loop_func)
        self.state = 'Stopped'
        
        self.init_tkinter(root, config)        

    def init_tkinter(self, root, config):
        self.frame = tkinter.LabelFrame(root, text='Connection')
        
        self.buttonstartstop = GUIButtonStartStop(self.frame, 
                                                  self.startstop_handler)
        self.gui_ip = GUITargetIP(self.frame, config.target_ip)
        self.status = GUIStatus(self.frame, self.state)
        
        self.gui_ip.grid(         row=0, column=0)
        self.buttonstartstop.grid(row=1, column=0)
        self.status.grid(         row=1, column=1, columnspan=2)
    
    def grid(self, row, column, *args, **kwargs):
        self.frame.grid(row=row, column=column, *args, **kwargs)

    #convenience function
    def firststart(self):
        self.startstop_handler() #implied start, not explicit start

    def startstop_handler(self, event=None):
        if self.gui_ip.get() != '':
            self.buttonstartstop.toggle(self.is_running()) #toggle text
            self.gui_ip.toggle(self.is_running()) #toggle read-only
            self.set_target_ip(self.gui_ip.get()) #set loop IP before start
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
        
    def send_heartbeat(self):
        if self.state in ['Started', 'Timeout']:
            self.update_status('Waiting')
            
        super().send_heartbeat()
        
    def nextGTdp(self):
        value = super().nextGTdp()
        
        if value is None and self.state in ['Waiting', 'Receiving']:
            self.update_status('Timeout')
        if value is not None and self.state in ['Waiting', 'Timeout']:
            self.update_status('Receiving')
        
        return value

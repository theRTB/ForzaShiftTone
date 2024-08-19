# -*- coding: utf-8 -*-
"""
Created on Fri Aug  2 21:01:24 2024

@author: RTB
"""

#replaced tkinter with supposed thread safe tkinter variant
#instead of freezing when the main thread isn't under control of tkinter,
#it now crashes instead. Theoretically, an improvement.
from mttkinter import mtTkinter as tkinter
#import tkinter
# import tkinter.ttk

from base.rpm import RPM

#Consider a defaultguivalue variable
class GUIRPM(RPM):
    def __init__(self, root, hysteresis_percent):
        super().__init__(hysteresis_percent=hysteresis_percent)
        
        self.tkvar = tkinter.IntVar(value=self.defaultvalue)    
        
        self.label = tkinter.Label(root, text='Tach')        
        self.entry = tkinter.Entry(root, width=6, textvariable=self.tkvar,
                                   justify=tkinter.RIGHT, state='readonly')
        self.unit = tkinter.Label(root, text='RPM')
        
        self.update_tach = True
    
    #sticky is not forwarded to the grid function
    def grid(self, column, sticky='', *args, **kwargs):
        self.label.grid(column=column, sticky=tkinter.E, *args, **kwargs)
        self.entry.grid(column=column+1, *args, **kwargs)
        self.unit.grid(column=column+2, sticky=tkinter.W, *args, **kwargs)
    
    def gui_set(self, value):
        self.tkvar.set(round(value))
        
    def reset(self):
        super().reset()
        self.tkvar.set(self.defaultvalue)
        
    def update(self, gtdp):
        super().update(gtdp)
        if self.update_tach:
            self.gui_set(round(gtdp.current_engine_rpm))
        self.update_tach = not self.update_tach
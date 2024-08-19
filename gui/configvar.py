# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:54:19 2023

@author: RTB
"""

import numpy as np
from mttkinter import mtTkinter as tkinter

from base.configvar import DynamicToneOffset

from utility import (packets_to_ms, ms_to_packets, round_to,
                     factor_to_percent, percent_to_factor, Variable)

class GUIConfigVariable(Variable):
    def __init__(self, root, name, value, unit, values, convert_from_gui,
                 convert_to_gui, *args, **kwargs):
        super().__init__(value, *args, **kwargs)
        gui_value = convert_to_gui(value)
        values_gui = list(map(convert_to_gui, values))
        self.convert_from_gui = convert_from_gui
        self.convert_to_gui = convert_to_gui

        self.label = tkinter.Label(root, text=name)
        self.unit = tkinter.Label(root, text=unit)

        self.tkvar = tkinter.IntVar()
        self.spinbox = tkinter.Spinbox(root, state='readonly', width=5,
                                       justify=tkinter.RIGHT,
                                       textvariable=self.tkvar,
                                       readonlybackground='#FFFFFF',
                                       disabledbackground='#FFFFFF',
                                       values=values_gui, command=self.update)
        self.tkvar.set(gui_value) #force spinbox to initial value
        #TODO: maybe try .invoke with buttonup/down? The first up/down click
        #resets the spinbox to the minimum of the range

    def grid(self, row, column=0, *args, **kwargs):
        self.label.grid(  row=row, column=column,   sticky=tkinter.E)
        self.spinbox.grid(row=row, column=column+1)
        self.unit.grid(   row=row, column=column+2, sticky=tkinter.W)

    def config(self, *args, **kwargs):
        self.spinbox.config(*args, **kwargs)

    def gui_get(self):
        return self.spinbox.get()

    def gui_set(self, val):
        self.tkvar.set(val)

    def set(self, val):
        super().set(val)
        val_gui = self.convert_to_gui(val)
        self.gui_set(val_gui)

    def update(self):
        val_gui = self.gui_get()
        val_internal = self.convert_from_gui(val_gui)
        super().set(val_internal)

#Consider adding validation
class GUIAdjustable(GUIConfigVariable):
    def __init__(self, var, *args, **kwargs):
        super().__init__(value=var.get(), *args, **kwargs)
        
        self.var = var
        
    def update(self):
        val_gui = self.gui_get()
        val_internal = self.convert_from_gui(val_gui)
        self.var.set(val_internal)
    
class GUIRevlimitOffset(GUIAdjustable):
    NAME = 'Revlimit'
    UNIT = 'ms'

    def __init__(self, root, config, var):
        # DEFAULTVALUE = config.revlimit_offset
        LOWER = config.revlimit_offset_lower
        UPPER = config.revlimit_offset_upper
        super().__init__(root=root, name=self.NAME, unit=self.UNIT,
                         convert_from_gui=ms_to_packets,
                         convert_to_gui=packets_to_ms, var=var,
                         values=range(LOWER, UPPER+1))
        
class GUIRevlimitPercent(GUIAdjustable):
    NAME = 'Revlimit'
    UNIT = '%'

    def __init__(self, root, config, var):
        # DEFAULTVALUE = config.revlimit_percent
        LOWER = config.revlimit_percent_lower
        UPPER = config.revlimit_percent_upper
        super().__init__(root=root, name=self.NAME, unit=self.UNIT,
                         convert_from_gui=percent_to_factor,
                         convert_to_gui=factor_to_percent,
                         values=np.arange(LOWER, UPPER, 0.001), var=var)
    
class GUIHysteresisPercent(GUIAdjustable):
    NAME = 'Hysteresis'
    UNIT = '%'

    def __init__(self, root, config, var):
        # DEFAULTVALUE = config.hysteresis_percent
        LOWER = config.hysteresis_percent_lower
        UPPER = config.hysteresis_percent_upper
        super().__init__(root=root, name=self.NAME, unit=self.UNIT,
                         convert_from_gui=percent_to_factor,
                         convert_to_gui=factor_to_percent,
                         values=np.arange(LOWER, UPPER, 0.001), var=var)

class GUICheckButton():
    TEXT = 'GUICheckButton'
    COLUMNSPAN = 3
    def __init__(self, root, config, var):
        self.var = var
        self.tkvar = tkinter.IntVar(value=var.get())
        self.button = tkinter.Checkbutton(root, text=self.TEXT, 
                                          variable=self.tkvar, 
                                          command=self.update)

    def grid(self, row, column=0, *args, **kwargs):
        self.button.grid(row=row, column=column, columnspan=self.COLUMNSPAN, 
                         sticky=tkinter.W, *args, **kwargs)

    def get(self):
        return self.tkvar.get()
    
    def update(self):
        value = self.get()
        self.var.set(value)

class GUIIncludeReplay(GUICheckButton):
    TEXT = 'Include replays'

class GUIDynamicToneOffsetToggle(GUICheckButton):
    TEXT = 'Dynamic tone offset'

#TODO: see if removing tone_offset_var=self is possible
#we only need .get and .set, which are from Variable in the end
class GUIToneOffset(GUIConfigVariable, DynamicToneOffset):
    NAME = 'Tone offset'
    UNIT = 'ms'

    def __init__(self, root, config):
        LOWER, UPPER = config.tone_offset_lower, config.tone_offset_upper
        DEFAULTVALUE = config.tone_offset
        
        GUIConfigVariable.__init__(self, root=root, name=self.NAME, 
                         convert_from_gui=ms_to_packets, unit=self.UNIT,
                         convert_to_gui=packets_to_ms, value=DEFAULTVALUE,
                         values=range(LOWER, UPPER+1))
        DynamicToneOffset.__init__(self, tone_offset_var=self, config=config)

    def grid(self, row, column=0, *args, **kwargs):
        self.label.grid(  row=row, column=column,   sticky=tkinter.E,
                                                                  columnspan=2)
        self.spinbox.grid(row=row, column=column+2)
        self.unit.grid(   row=row, column=column+3, sticky=tkinter.W)
    
    #this is called when manually altering Tone Offset through GUI
    #we discard the history if user decides to do so
    def update(self):
        super().update()
        self.reset_to_current_value()
        print(f"DynamicToneOffset reset to {self.value}")

class GUIRevlimit(Variable):
    BG = {'initial':'#F0F0F0', #the possible background colors of the entry
          'guess':  '#FFFFFF', #'guess' is currently not used
          'curve':  '#CCDDCC'}
    def __init__(self, root, defaultguivalue='N/A', *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.defaultguivalue = defaultguivalue
        self.tkvar = tkinter.StringVar(value=defaultguivalue)
        
        self.label = tkinter.Label(root, text='Revlimit')        
        self.entry = tkinter.Entry(root, width=6, textvariable=self.tkvar,
                                   justify=tkinter.RIGHT, state='readonly')
        self.unit = tkinter.Label(root, text='RPM')
    
    def grid(self, column, sticky='', *args, **kwargs):
        self.label.grid(column=column, sticky=tkinter.E, *args, **kwargs)
        self.entry.grid(column=column+1, sticky=sticky, *args, **kwargs)
        self.unit.grid(column=column+2, sticky=tkinter.W, *args, **kwargs)
        
    def set_bg(self, state):
        self.entry.configure(readonlybackground=self.BG.get(state))

    def set(self, value, bg_state='curve'):
        super().set(value)
        self.tkvar.set(int(value))
        self.set_bg(state=bg_state)
        
    def reset(self):
        super().reset()
        self.tkvar.set(self.defaultguivalue)
        self.set_bg(state='initial')

class GUIPeakPower():
    def __init__(self, root, defaultguivalue=''):
        self.defaultguivalue = defaultguivalue
        
        self.tkvar = tkinter.StringVar(value=defaultguivalue)
        
        self.label = tkinter.Label(root, text='Power')
        self.entry = tkinter.Entry(root, textvariable=self.tkvar, width=18,
                                   state='readonly')
    
    #sticky and columnspan are not forwarded to the grid function
    def grid(self, column, sticky='', columnspan=1, *args, **kwargs):
        self.label.grid(column=column, columnspan=1, 
                        sticky=tkinter.E, *args, **kwargs)    
        self.entry.grid(column=column+1, columnspan=4,
                        sticky=tkinter.W, *args, **kwargs) 

    def set(self, rpm, peakpower):
        # string = f'~{peakpower/10:>4.0f} kW at ~{round_to(rpm, 50):>5} RPM'
        string = f'peak at ~{round_to(rpm, 100):>5} RPM'
        self.tkvar.set(string)
        
    def reset(self):
        self.tkvar.set(self.defaultguivalue)

#this class depends on how the volume steps in config are defined
class GUIVolume():
    MIN, MAX, STEP = 0, 100, 25
    def __init__(self, root, config):
        frame = tkinter.Frame(root)
        self.frame = frame
        self.label = tkinter.Label(frame, text='Volume')
        
        self.tkvar = tkinter.IntVar(value=config.volume)
        self.scale = tkinter.Scale(frame, orient=tkinter.VERTICAL, showvalue=1,
                                   from_=self.MAX, to=self.MIN, 
                                   resolution=self.STEP, variable=self.tkvar)
        
        self.label.pack()
        self.scale.pack(expand=True, fill=tkinter.X)

    #sticky and columnspan are not forwarded to the grid function
    def grid(self, row, column, *args, **kwargs):
        self.frame.grid(row=row, column=column, *args, **kwargs)

    def get(self):
        return self.tkvar.get()

    def set(self, value):
        if value in range(self.MIN, self.MAX+1, self.STEP):
            self.tkvar.set(value)

# class GUIButtonVarEdit():
#     def __init__(self, root, command):
#         self.tkvar = tkinter.IntVar(value=1)
#         self.button = tkinter.Checkbutton(root, text='Edit', command=command,
#                                           variable=self.tkvar)

#     def grid(self, row, column, *args, **kwargs):
#         self.button.grid(row=row, column=column, *args, **kwargs)

#     def get(self):
#         return self.tkvar.get()
    
#     def invoke(self):
#         self.button.invoke()


#The in-game revbar scales off the revbar variable in telemetry:
#Starts at 85% and starts blinking at 99%
class GUIRevbarData():
    LOWER, UPPER = 0.85, 0.99
    def __init__(self, root, defaultguivalue='N/A - N/A'):
        self.defaultguivalue = defaultguivalue
        
        self.tkvar = tkinter.StringVar(value=defaultguivalue)    
        
        self.label = tkinter.Label(root, text='Revbar')        
        self.entry = tkinter.Entry(root, width=12, textvariable=self.tkvar,
                                   justify=tkinter.RIGHT, state='readonly')
        self.unit = tkinter.Label(root, text='RPM')
        
        self.grabbed_data = False
    
    #sticky and columnspan are not forwarded to the grid function
    def grid(self, column, sticky='', columnspan=1, *args, **kwargs):
        self.label.grid(column=column, columnspan=1, sticky=tkinter.E, 
                                                               *args, **kwargs)
        self.entry.grid(column=column+1, columnspan=2, *args, **kwargs)
        self.unit.grid(column=column+3, columnspan=1, sticky=tkinter.W, 
                                                               *args, **kwargs)
    
    def set(self, value):
        self.tkvar.set(value)
        
    def reset(self):
        self.tkvar.set(self.defaultguivalue)
        self.grabbed_data = False
        
    def update(self, value):
        if not self.grabbed_data:
            self.set(f'{value*self.LOWER:5.0f} - {value*self.UPPER:5.0f}')
            self.grabbed_data = True


class GUIConfigWindow():
    TITLE='GTShiftTone: Settings'
    CLASSES = { 'hysteresis_percent': GUIHysteresisPercent, 
                'revlimit_percent':   GUIRevlimitPercent,
                'revlimit_offset':    GUIRevlimitOffset,
                'dynamictoneoffset':  GUIDynamicToneOffsetToggle,
                'includereplay':      GUIIncludeReplay}
    
    def __init__(self, root, config, adjustables):
        self.root = root
        self.config = config
        self.window_scalar = config.window_scalar
        
        self.adjustables = adjustables

        self.window = None

    #From: https://stackoverflow.com/questions/33231484/python-tkinter-how-do-i-get-the-window-size-including-borders-on-windows
    #Get x and y coordinates to place graph underneath the main window.
    #This may not scale arbitrarily with varying border sizes and title sizes
    def get_windowoffsets(self):
        root = self.root.winfo_toplevel() #get true toplevel widget
        return (root.winfo_x(),  #why not rootx?
                root.winfo_rooty() + root.winfo_height())

    def handle_adjustables(self):
        for row, (name, var) in enumerate(self.adjustables.items()):
            gui_var = self.CLASSES[name](self.window, self.config, var)
            gui_var.grid(row)
            setattr(self, name, gui_var)
    
    def open(self):
        if self.window is not None: #force existing window to front
            self.window.deiconify()
            self.window.lift()
            return
        
        self.window = tkinter.Toplevel(self.root)
        self.window.title(self.TITLE)
        self.window.protocol('WM_DELETE_WINDOW', self.close)

        #place window underneath main window
        x, y = self.get_windowoffsets()
        self.window.geometry(f"+{x}+{y}")
        
        self.handle_adjustables()

    def close(self):
        self.window.destroy()
        self.window = None

    @classmethod
    def get_names(cls):
        return list(cls.CLASSES.keys())

#enable button once we have a settings window
#adjustables is an array of Variables we can display to adjust
class GUIConfigButton():
    def __init__(self, root, config, adjustables):
        self.button = tkinter.Button(root, text='Settings', command=self.open,
                                     borderwidth=3)

        self.configwindow = GUIConfigWindow(root, config, adjustables)

    def grid(self, row, column, *args, **kwargs):
        self.button.grid(row=row, column=column, *args, **kwargs)

    def open(self):
        self.configwindow.open()
    
    def invoke(self):
        self.button.invoke()
        
    @classmethod
    def get_names(cls):
        return GUIConfigWindow.get_names()
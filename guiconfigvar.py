# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:54:19 2023

@author: RTB
"""

import statistics
import numpy as np
from config import config
from collections import deque
from mttkinter import mtTkinter as tkinter

from utility import (packets_to_ms, ms_to_packets, 
                     factor_to_percent, percent_to_factor)

#maintain a rolling array of the time between beep and actual shift
#caps to the lower and upper limits of the tone_offset variable to avoid
#outliers such as 0 ms reaction time or a delay of seconds or more
#depends on ForzaBeep loop_test_for_shiftrpm and loop_beep
class DynamicToneOffset():
    DEQUE_MIN, DEQUE_MAX = 35, 75

    DEFAULT_TONEOFFSET = config.tone_offset
    OFFSET_LOWER = config.tone_offset_lower
    OFFSET_UPPER = config.tone_offset_upper
    OFFSET_OUTLIER = config.tone_offset_outlier

    def __init__(self, tone_offset_var, *args, **kwargs):
      #  super().__init(*args, **kwargs)
        self.counter = None
        self.offset = self.DEFAULT_TONEOFFSET
        self.deque = deque([self.DEFAULT_TONEOFFSET]*self.DEQUE_MIN,
                           maxlen=self.DEQUE_MAX)
        self.deque_min_counter = 0
        self.tone_offset_var = tone_offset_var

    def start_counter(self):
        #assert self.counter is None
        self.counter = 0

    def increment_counter(self):
        if self.counter is not None:
            self.counter += 1

    def decrement_counter(self):
        if self.counter is not None:
            self.counter -= 1

    def finish_counter(self):
        if self.counter is None:
            return
        if self.counter > self.OFFSET_OUTLIER:
            print(f'DynamicToneOffset: outlier {packets_to_ms(self.counter)} ms, discarded')
            self.reset_counter()
            return

        if self.deque_min_counter <= self.DEQUE_MIN:
            self.deque.popleft()
        else:
            self.deque_min_counter += 1

        value = min(self.OFFSET_UPPER, self.counter)
        value = max(self.OFFSET_LOWER, value)

        self.deque.append(value)
        average = statistics.mean(self.deque)
        print(f'DynamicToneOffset: offset {self.offset:.1f} new average {average:.2f}')
        average = round(average, 1)
        if average != self.offset:
            self.offset = average
            self.apply_offset()
        self.reset_counter()

    def apply_offset(self):
        self.tone_offset_var.set(self.offset)

    def get_counter(self):
        return self.counter

    def reset_counter(self):
        self.counter = None

    def reset_to_current_value(self):
        self.offset = self.tone_offset_var.get()
        self.deque.clear()
        self.deque_min_counter = 0
        self.deque.extend([self.offset]*self.DEQUE_MIN)

class ConfigVariable(object):
    def __init__(self, value, *args, **kwargs):
        self.value = value

    def get(self):
        return self.value

    def set(self, val):
        self.value = val

class GUIConfigVariable(ConfigVariable):
    def __init__(self, root, name, value, unit, values, convert_from_gui,
                 convert_to_gui, row, column=0, *args, **kwargs):
        super().__init__(value, *args, **kwargs)
        gui_value = convert_to_gui(value)
        values_gui = list(map(convert_to_gui, values))
        self.convert_from_gui = convert_from_gui
        self.convert_to_gui = convert_to_gui

        label = tkinter.Label(root, text=name)
        unit = tkinter.Label(root, text=unit)

        self.var = tkinter.IntVar()
        self.spinbox = tkinter.Spinbox(root, state='readonly', width=5,
                                       justify=tkinter.RIGHT,
                                       textvariable=self.var,
                                       readonlybackground='#FFFFFF',
                                       disabledbackground='#FFFFFF',
                                       values=values_gui, command=self.update)
        self.var.set(gui_value) #force spinbox to initial value

        label.grid(       row=row, column=column,   sticky=tkinter.E)
        self.spinbox.grid(row=row, column=column+1)
        unit.grid(        row=row, column=column+2, sticky=tkinter.W)

    def config(self, *args, **kwargs):
        self.spinbox.config(*args, **kwargs)

    def gui_get(self):
        return self.spinbox.get()

    def gui_set(self, val):
        self.var.set(val)

    def set(self, val):
        super().set(val)
        val_gui = self.convert_to_gui(val)
        self.gui_set(val_gui)

    def update(self):
        val_gui = self.gui_get()
        val_internal = self.convert_from_gui(val_gui)
        super().set(val_internal)

class GUIConfigVariable_ToneOffset(GUIConfigVariable, DynamicToneOffset):
    NAME = 'Tone offset'
    LOWER, UPPER = config.tone_offset_lower, config.tone_offset_upper
    DEFAULTVALUE = config.tone_offset
    UNIT = 'ms'

    def __init__(self, root, row, column=0):
        GUIConfigVariable.__init__(self, root=root, name=self.NAME, unit=self.UNIT,
                         convert_from_gui=ms_to_packets, row=row,
                         convert_to_gui=packets_to_ms, value=self.DEFAULTVALUE,
                         values=range(self.LOWER, self.UPPER+1))
        DynamicToneOffset.__init__(self, tone_offset_var=self)

    def update(self):
        super().update()
        self.reset_to_current_value()
        print(f"DynamicToneOffset reset to {self.value}")

class GUIConfigVariable_RevlimitOffset(GUIConfigVariable):
    NAME = 'Revlimit'
    DEFAULTVALUE = config.revlimit_offset
    LOWER = config.revlimit_offset_lower
    UPPER = config.revlimit_offset_upper
    UNIT = 'ms'

    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=ms_to_packets,
                         convert_to_gui=packets_to_ms, value=self.DEFAULTVALUE,
                         values=range(self.LOWER, self.UPPER+1))

class GUIConfigVariable_RevlimitPercent(GUIConfigVariable):
    NAME = 'Revlimit'
    DEFAULTVALUE = config.revlimit_percent
    LOWER = config.revlimit_percent_lower
    UPPER = config.revlimit_percent_upper
    UNIT = '%'

    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=percent_to_factor,
                         convert_to_gui=factor_to_percent,
                         values=np.arange(self.LOWER, self.UPPER, 0.001),
                         value=self.DEFAULTVALUE)

class GUIConfigVariable_HysteresisPercent(GUIConfigVariable):
    NAME = 'Hysteresis'
    DEFAULTVALUE = config.hysteresis_percent
    LOWER = config.hysteresis_percent_lower
    UPPER = config.hysteresis_percent_upper
    UNIT = '%'

    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=percent_to_factor,
                         convert_to_gui=factor_to_percent,
                         values=np.arange(self.LOWER, self.UPPER, 0.001),
                         value=self.DEFAULTVALUE)
    
    def as_rpm(self, fdp):
        return self.get() * fdp.max_engine_rpm
# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
import statistics
import numpy as np
from mttkinter import mtTkinter as tkinter
from collections import deque

import intersect

#Enumlike class
class GearState():
    UNUSED = 0     # gear has not been seen (yet)
    REACHED = 1    # gear has been seen, variance above lower bound
    LOCKED = 2     # variance on gear ratio below lower bound
    CALCULATED = 3 # shift rpm calculated off gear ratios
    
    def reset(self):
        self.state = self.UNUSED
        
    def __init__(self, label):
        self.label = label #only used for asserts
        self.reset()
    
    def set(self, state):
        self.state = state
    
    def to_next(self):
        assert self.state < 3, f'state {self.label} to_next used on CALCULATED state'
        self.state += 1
    
    def to_previous(self):
        assert self.state > 0, f'state {self.label} to_previous used on UNUSED state'
        self.state -= 1

    def is_initial(self):
        return self.state == self.UNUSED
    
    def at_locked(self):
        return self.state == self.LOCKED
    
    def at_least_locked(self):
        return self.state >= self.LOCKED
    
    def is_final(self):
        return self.state == self.CALCULATED

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.value == other.value
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.value >= other.value
        return NotImplemented

#class to hold all variables per individual gear and GUI display
class Gear():
    ENTRY_WIDTH = 6
    DEQUE_LEN = 60
    ROW_COUNT = 3 #for ForzaBeep: how many rows of variables are present per gear
    
    DEFAULT_GUI_VALUE = 'N/A'
    
    BG_UNUSED = '#F0F0F0'
    BG_REACHED = '#ffffff'
    BG_LOCKED = '#ccddcc'

    def __init__(self, root, number, column, starting_row=0):
        self.gear = number
        self.number = tkinter.StringVar(value=f'{number}')
        self.state = GearState(label=f'Gear {number}')
        self.ratio_deque = deque(maxlen=self.DEQUE_LEN)
        
        self.shiftrpm = 99999
        self.shiftrpm_var = tkinter.StringVar()
        self.ratio = tkinter.DoubleVar()
        self.variance = tkinter.DoubleVar()

        self.__init__window(root, column, starting_row)
        self.reset()

    def init_gui_entry(self, root, variable):
        return tkinter.Entry(root, textvariable=variable, state='readonly', 
                             width=self.ENTRY_WIDTH, justify=tkinter.RIGHT)

    def __init__window(self, root, column, starting_row):
        self.label = tkinter.Label(root, textvariable=self.number,
                                   width=self.ENTRY_WIDTH)
        self.entry = self.init_gui_entry(root, self.shiftrpm_var)
        self.entry_ratio = self.init_gui_entry(root, self.ratio)

        self.label.grid(row=starting_row, column=column)
        if self.gear != 10:
            self.entry.grid(row=starting_row+1, column=column)
        self.entry_ratio.grid(row=starting_row+2, column=column)

        self.entry_row = starting_row+1
        self.column = column

    def reset(self):
        self.shiftrpm = 99999
        self.shiftrpm_var.set(self.DEFAULT_GUI_VALUE)
        self.set_ratio(0)
        self.ratio_deque.clear()
        self.state.reset()

        self.variance.set(0)
        self.entry.config(readonlybackground=self.BG_UNUSED)
        self.entry_ratio.config(readonlybackground=self.BG_UNUSED)

    def get_shiftrpm(self):
        return self.shiftrpm

    def set_shiftrpm(self, val):
        self.shiftrpm = int(val)
        self.shiftrpm_var.set(self.shiftrpm)

    def get_ratio(self):
        return self.ratio.get()

    def set_ratio(self, val):
        self.ratio.set(f'{val:.3f}')

    #if we have a new (and better curve) we reduce the state of the gear
    #to have it recalculate the shiftrpm later
    def newrun_decrease_state(self):
        if self.state.is_final():
            self.state.to_previous()

    #if the clutch is engaged, we can use engine rpm and wheel rotation speed
    #to derive the ratio between these two: the gear ratio
    def derive_gearratio(self, fdp):
        if self.state.is_initial():
            self.state.to_next()
            self.entry_ratio.config(readonlybackground=self.BG_REACHED)

        if self.state.at_least_locked():
            return

        rpm = fdp.current_engine_rpm
        if abs(fdp.speed) < 3 or rpm == 0: #if speed below 3 m/s assume faulty data
            return
    
        rad = 0
        var_bound = 1e-08
        if fdp.drivetrain_type == 0: #FWD
            rad = (fdp.wheel_rotation_speed_FL +
                   fdp.wheel_rotation_speed_FR) / 2.0
        elif fdp.drivetrain_type == 1: #RWD
            rad = (fdp.wheel_rotation_speed_RL +
                   fdp.wheel_rotation_speed_RR) / 2.0
        else:  #AWD
            rad = (fdp.wheel_rotation_speed_RL +
                   fdp.wheel_rotation_speed_RR) / 2.0
            var_bound = 1e-04 #loosen bound because of higher variance
            # rad = (fdp.wheel_rotation_speed_FL + fdp.wheel_rotation_speed_FR +
            #         fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 4.0
        if abs(rad) <= 1e-6:
            return
        if rad < 0: #in the case of reverse
            rad = -rad

        self.ratio_deque.append(2 * math.pi * rpm / (rad * 60))
        if len(self.ratio_deque) < 10:
            return
     #   avg = statistics.mean(self.ratio_deque)
        median = statistics.median(self.ratio_deque)
        var = statistics.variance(self.ratio_deque)#, avg)
        self.variance.set(f'{var:.1e}')
        if var < var_bound and len(self.ratio_deque) == self.DEQUE_LEN:
            self.state.to_next() #implied from reached to locked
            self.entry_ratio.config(readonlybackground=self.BG_LOCKED)
            print(f'LOCKED {self.gear}')
        self.set_ratio(median)
        
    def calculate_shiftrpm(self, rpm, power, nextgear):
        if (self.state.at_locked() and nextgear.state.at_least_locked()):
            shiftrpm = calculate_shiftrpm(rpm, power,
                                 self.ratio.get() / nextgear.get_ratio())
            self.set_shiftrpm(shiftrpm)
            self.state.to_next()
            self.entry.config(readonlybackground=self.BG_LOCKED)

def calculate_shiftrpm(rpm, power, ratio):
    intersects = intersect.intersection(rpm, power, rpm*ratio, power)[0]
    shiftrpm = round(intersects[-1],0) if len(intersects) > 0 else rpm[-1]
    print(f"shift rpm {shiftrpm}, drop to {int(shiftrpm/ratio)}, "
          f"drop is {int(shiftrpm*(1.0 - 1.0/ratio))}")

    return shiftrpm
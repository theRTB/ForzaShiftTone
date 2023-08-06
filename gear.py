# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
import statistics
from mttkinter import mtTkinter as tkinter
from collections import deque

import intersect

#drivetrain enum for fdp
DRIVETRAIN_FWD = 0
DRIVETRAIN_RWD = 1
DRIVETRAIN_AWD = 2

#Enumlike class
class GearState():
    UNUSED     = 0 # gear has not been seen (yet)
    REACHED    = 1 # gear has been seen, variance above lower bound
    LOCKED     = 2 # variance on gear ratio below lower bound
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

    def at_initial(self):
        return self.state == self.UNUSED
    
    def at_locked(self):
        return self.state == self.LOCKED
    
    def at_least_locked(self):
        return self.state >= self.LOCKED
    
    def at_final(self):
        return self.state == self.CALCULATED

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.state == other.state
        elif other.__class__ == int:
            return self.state == other
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.state >= other.state
        elif other.__class__ == int:
            return self.state >= other
        return NotImplemented

#class to hold all variables per individual gear and GUI display
class Gear():
    DEQUE_MIN, DEQUE_LEN  = 40, 60
    
    #              FWD    RWD    AWD (awd lower due to center diff variance)
    VAR_BOUNDS = [1e-08, 1e-08, 1e-04]

    def __init__(self, number):
        self.gear = number
        self.state = GearState(label=f'Gear {number}')
        self.ratio_deque = deque(maxlen=self.DEQUE_LEN)
        
        self.shiftrpm = None
        self.ratio = None

        self.reset()

    def reset(self):
        self.ratio_deque.clear()
        self.state.reset()   
        
        self.set_shiftrpm(-1)
        self.set_ratio(0)
        
    def get_shiftrpm(self):
        return self.shiftrpm

    def set_shiftrpm(self, val):
        self.shiftrpm = val

    def get_ratio(self):
        return self.ratio

    def set_ratio(self, val):
        self.ratio = val

    #if we have a new (and better curve) we reduce the state of the gear
    #to have it recalculate the shiftrpm later
    def newrun_decrease_state(self):
        if self.state.at_final():
            self.state.to_previous()
        
    def to_next_state(self):
        self.state.to_next()

    def update(self, fdp):
        if self.state.at_initial():
            self.to_next_state()

        if self.state.at_least_locked():
            return

        ratio = derive_gearratio(fdp)
        if ratio is None:
            return
        
        self.ratio_deque.append(ratio)
        if len(self.ratio_deque) < 10:
            return

        median = statistics.median(self.ratio_deque)
        var = statistics.variance(self.ratio_deque)
        
        var_bound = self.VAR_BOUNDS[fdp.drivetrain_type]
        if var < var_bound and len(self.ratio_deque) >= self.DEQUE_MIN:
            self.to_next_state() #implied from reached to locked
            print(f'LOCKED {self.gear}')
        self.set_ratio(median)
        
    def calculate_shiftrpm(self, rpm, power, nextgear):
        if (self.state.at_locked() and nextgear.state.at_least_locked()):
            shiftrpm = calculate_shiftrpm(rpm, power,
                                 self.get_ratio() / nextgear.get_ratio())
            self.set_shiftrpm(shiftrpm)
            self.to_next_state()

#class for GUI display of class Gear
class GUIGear (Gear):    
    ROW_COUNT = 3 #for ForzaBeep GUI: how many grid rows a gear takes up
    ENTRY_WIDTH = 6
        
    FG_DEFAULT = '#000000'
    BG_UNUSED  = '#F0F0F0'
    BG_REACHED = '#FFFFFF'
    BG_LOCKED  = '#CCDDCC'
    #                             tuple of shiftpm_fg, shiftrpm_bg, 
    #                                       entry_fg    entry_bg
    ENTRY_COLORS = {GearState.UNUSED:     (BG_UNUSED,  BG_UNUSED,  
                                           BG_UNUSED,  BG_UNUSED), 
                    GearState.REACHED:    (BG_UNUSED,  BG_UNUSED,  
                                           FG_DEFAULT, BG_REACHED), 
                    GearState.LOCKED:     (BG_REACHED, BG_REACHED, 
                                           FG_DEFAULT, BG_LOCKED), 
                    GearState.CALCULATED: (FG_DEFAULT, BG_LOCKED,  
                                           FG_DEFAULT, BG_LOCKED)}

    def __init__(self, root, number, column, starting_row=0):
        self.shiftrpm_var = tkinter.IntVar()
        self.ratio_var = tkinter.DoubleVar()
        self.__init__window(root, number, column, starting_row)
        
        super().__init__(number)
                
        # self.reset() #happens in the super init

    def init_gui_entry(self, root, variable):
        return tkinter.Entry(root, textvariable=variable, state='readonly', 
                             width=self.ENTRY_WIDTH, justify=tkinter.RIGHT)

    def __init__window(self, root, number, column, starting_row):
        self.label = tkinter.Label(root, text=f'{number}',
                                   width=self.ENTRY_WIDTH)
        self.shiftrpm_entry = self.init_gui_entry(root, self.shiftrpm_var)
        self.ratio_entry = self.init_gui_entry(root, self.ratio_var)

        self.label.grid(row=starting_row, column=column)
        if number != 10:
            self.shiftrpm_entry.grid(row=starting_row+1, column=column)
        self.ratio_entry.grid(row=starting_row+2, column=column)

        # self.entry_row = starting_row+1
        # self.column = column

    def reset(self):
        super().reset()
        self.update_entry_colors()

    def set_shiftrpm(self, val):
        super().set_shiftrpm(val)
        self.shiftrpm_var.set(int(val))

    def set_ratio(self, val):
        super().set_ratio(val)
        self.ratio_var.set(f'{val:.3f}')

    def get_entry_colors(self):
        for state, colors in self.ENTRY_COLORS.items():
            if state == self.state:
                return colors
    
    def update_entry_colors(self):
        (shiftrpm_fg, shiftrpm_bg, ratio_fg, ratio_bg) =self.get_entry_colors()

        self.shiftrpm_entry.config(readonlybackground=shiftrpm_bg, 
                                   fg=shiftrpm_fg)
        self.ratio_entry.config(readonlybackground=ratio_bg, fg=ratio_fg)
        
    def to_next_state(self):
        super().to_next_state()
        self.update_entry_colors()

#if the clutch is engaged, we can use engine rpm and wheel rotation speed
#to derive the ratio between these two: the gear ratio
def derive_gearratio(fdp):
    rpm = fdp.current_engine_rpm
    if abs(fdp.speed) < 3 or rpm == 0: #if speed below 3 m/s assume faulty data
        return None

    rad = 0
    if fdp.drivetrain_type == DRIVETRAIN_FWD:
        rad = (fdp.wheel_rotation_speed_FL +
               fdp.wheel_rotation_speed_FR) / 2.0
    elif fdp.drivetrain_type == DRIVETRAIN_RWD:
        rad = (fdp.wheel_rotation_speed_RL +
               fdp.wheel_rotation_speed_RR) / 2.0
    else:  #AWD
        rad = (fdp.wheel_rotation_speed_RL +
               fdp.wheel_rotation_speed_RR) / 2.0
        # rad = (fdp.wheel_rotation_speed_FL + fdp.wheel_rotation_speed_FR +
        #     fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 4.0
    if abs(rad) <= 1e-6:
        return None
    if rad < 0: #in the case of reverse
        rad = -rad
    return 2 * math.pi * rpm / (rad * 60)

def calculate_shiftrpm(rpm, power, ratio):
    intersects = intersect.intersection(rpm, power, rpm*ratio, power)[0]
    shiftrpm = round(intersects[-1],0) if len(intersects) > 0 else rpm[-1]
    print(f"shift rpm {shiftrpm:.0f}, drop to {shiftrpm/ratio:.0f}, "
          f"drop is {shiftrpm*(1.0 - 1.0/ratio):.0f}")

    if len(intersects) > 1:
        print("Warning: multiple intersects found: graph may be noisy")
    return shiftrpm
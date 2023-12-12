# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
import statistics
from collections import deque

from mttkinter import mtTkinter as tkinter
import intersect

#import assumes config.load_from has already been called
from config import config
from utility import multi_beep

#Forza Horizon 5 is limited to 10 gears (ignoring reverse)
MAXGEARS = 10

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

#class to hold all variables per individual gear
class Gear():
    DEQUE_MIN, DEQUE_LEN  = 40, 60

    #              FWD    RWD    AWD
    VAR_BOUNDS = [1e-04, 1e-04, 1e-04]

    def __init__(self, number):
        self.gear = number
        self.state = GearState(label=f'Gear {number}')
        self.ratio_deque = deque(maxlen=self.DEQUE_LEN)
        self.shiftrpm = -1
        self.ratio = 0
        self.relratio = 0
        self.variance = math.inf
        self.var_bound = self.VAR_BOUNDS[DRIVETRAIN_RWD]

    def reset(self):
        self.state.reset()
        self.ratio_deque.clear()
        self.set_shiftrpm(-1)
        self.set_ratio(0)
        self.set_relratio(0)
        self.set_variance(math.inf)
        self.var_bound = self.VAR_BOUNDS[DRIVETRAIN_RWD]

    def get_shiftrpm(self):
        return self.shiftrpm

    def set_shiftrpm(self, val):
        self.shiftrpm = val

    def get_ratio(self):
        return self.ratio

    def set_ratio(self, val):
        self.ratio = val
        
    def get_relratio(self):
        return self.relratio
    
    def set_relratio(self, val):
        self.relratio = val
        
    def get_variance(self):
        return self.variance
    
    def set_variance(self, val):
        self.variance = val

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

        if not (ratio := derive_gearratio(fdp)):
            return

        self.ratio_deque.append(ratio)
        if len(self.ratio_deque) < 10:
            return

        median = statistics.median(self.ratio_deque)
        var = statistics.variance(self.ratio_deque)
        self.set_ratio(median)
        self.set_variance(var)

        if self.var_bound is None:
            self.var_bound = self.VAR_BOUNDS[fdp.drivetrain_type]
            
        if (self.variance < self.var_bound and 
                len(self.ratio_deque) >= self.DEQUE_MIN):
            self.to_next_state() #implied from reached to locked
            print(f'LOCKED {self.gear}')
            if config.notification_gear_enabled:
                multi_beep(config.notification_file,
                           config.notification_gear_count,
                           config.notification_gear_delay)

    def calculate_shiftrpm(self, rpm, power, nextgear):
        if (self.state.at_locked() and nextgear.state.at_least_locked()):
            relratio = self.get_ratio() / nextgear.get_ratio()
            shiftrpm = calculate_shiftrpm(rpm, power, relratio)
            
            self.set_relratio(relratio)
            self.set_shiftrpm(shiftrpm)
            
            self.to_next_state()

#class to hold all gears up to the maximum of MAXGEARS
class Gears():
    GEARLIST = range(1, MAXGEARS+1)

    #first element is None to enable a 1:1 mapping of array to Gear number
    #it could be used as reverse gear but not in a usable manner anyway
    def __init__(self):
        self.gears = [None] + [Gear(g) for g in self.GEARLIST]

    def reset(self):
       for g in self.gears[1:]:
           g.reset()

    def newrun_decrease_state(self):
        for g in self.gears[1:]:
            g.newrun_decrease_state() #force recalculation of rpm

    def calculate_shiftrpms(self, rpm, power):
        for g1, g2 in zip(self.gears[1:-1], self.gears[2:]):
            g1.calculate_shiftrpm(rpm, power, g2)

    def get_shiftrpm_of(self, gear):
        if gear > 0:
            return self.gears[int(gear)].get_shiftrpm()
        return -1

    def update_of(self, gear, fdp):
        self.gears[gear].update(fdp)

#class for GUI display of class Gear
class GUIGear (Gear):
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

    def __init__(self, number):
        self.shiftrpm_var = tkinter.IntVar()
        self.ratio_var = tkinter.DoubleVar()
        self.relratio_var = tkinter.StringVar()
        self.variance_var = tkinter.StringVar()
        super().__init__(number)
        super().reset()

        # self.__init__window(root, number, column, starting_row)

    def init_gui_entry(self, root, variable):
        return tkinter.Entry(root, textvariable=variable, state='readonly',
                             width=self.ENTRY_WIDTH, justify=tkinter.RIGHT)

    def init_window(self, root, number, column, starting_row=0):
        self.label = tkinter.Label(root, text=f'{number}',
                                   width=self.ENTRY_WIDTH)
        self.shiftrpm_entry = self.init_gui_entry(root, self.shiftrpm_var)
        self.ratio_entry = self.init_gui_entry(root, self.ratio_var)
        self.variance_entry = self.init_gui_entry(root, self.variance_var)
        self.relratio_entry = tkinter.Entry(root, 
                                textvariable=self.relratio_var,
                                width=self.ENTRY_WIDTH, justify=tkinter.CENTER,
                                state='readonly')

        self.label.grid(row=starting_row, column=column)
        if number != MAXGEARS:
            self.shiftrpm_entry.grid(row=starting_row+1, column=column)
            self.relratio_entry.grid(row=starting_row+2, column=column,
                                     columnspan=2)
        # self.ratio_entry.grid(   row=starting_row+3, column=column)
        self.variance_entry.grid(row=starting_row+1, column=column)
        
        self.update_entry_colors()

    def reset(self):
        super().reset()
        self.update_entry_colors()
        self.variance_entry.grid()

    def set_shiftrpm(self, val):
        super().set_shiftrpm(val)
        self.shiftrpm_var.set(int(val))

    def set_ratio(self, val):
        super().set_ratio(val)
        self.ratio_var.set(f'{val:.3f}')
        
    def set_relratio(self, val):
        super().set_relratio(val)
        self.relratio_var.set(f'{val:.2f}')
        
    def set_variance(self, val):
        super().set_variance(val)
        factor = math.log(val) / math.log(self.var_bound)
        factor = min(max(factor, 0), 1)
        self.variance_var.set(f'{factor:.0%}')

    def get_entry_colors(self):
        for state, colors in self.ENTRY_COLORS.items():
            if state == self.state:
                return colors

    def update_entry_colors(self):
        shiftrpm_fg, shiftrpm_bg, ratio_fg, ratio_bg = self.get_entry_colors()

        self.shiftrpm_entry.config(readonlybackground=shiftrpm_bg,
                                   fg=shiftrpm_fg)
        self.ratio_entry.config(readonlybackground=ratio_bg, fg=ratio_fg)
        self.relratio_entry.config(readonlybackground=shiftrpm_bg, 
                                   fg=shiftrpm_fg)

    def to_next_state(self):
        super().to_next_state()
        self.update_entry_colors()
        if self.state.at_final():
            self.variance_entry.grid_remove()

class GUIGears(Gears):
    LABELS = ['Gear', 'Target', 'Rel. Ratio']#, 'Variance']
    LABEL_WIDTH = 8
    ROW_COUNT = 3 #for ForzaBeep GUI: how many grid rows a gear takes up
    def __init__(self):
        self.gears = [None] + [GUIGear(g) for g in self.GEARLIST]

    def init_window(self, root):
        for i, text in enumerate(self.LABELS):
            tkinter.Label(root, text=text, width=self.LABEL_WIDTH,
                          anchor=tkinter.E).grid(row=i, column=0)

        for i, g in enumerate(self.gears[1:], start=1):
            g.init_window(root, i, i)

#if the clutch is engaged, we can use engine rpm and wheel rotation speed
#to derive the ratio between these two: the gear ratio
def derive_gearratio(fdp):
    rpm = fdp.current_engine_rpm
    if abs(fdp.speed) < 3 or rpm == 0: #if speed below 3 m/s assume faulty data
        return None

    rad = 0
    if fdp.drivetrain_type == DRIVETRAIN_FWD:
        rad = (fdp.wheel_rotation_speed_FL + fdp.wheel_rotation_speed_FR) / 2.0
    elif fdp.drivetrain_type == DRIVETRAIN_RWD:
        rad = (fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 2.0
    else:  #AWD
        rad = (fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 2.0
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
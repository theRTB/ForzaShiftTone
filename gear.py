# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
import statistics
from collections import deque

from mttkinter import mtTkinter as tkinter

from utility import derive_gearratio, calculate_shiftrpm

#The Forza series is limited to 10 gears (ignoring reverse)
MAXGEARS = 10

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

    def __hash__(self):
        return hash(self.state)

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

    def reset(self):
        self.state.reset()
        self.ratio_deque.clear()
        self.set_shiftrpm(-1)
        self.set_ratio(0)
        self.set_relratio(0)
        self.set_variance(math.inf)

    def get_gearnumber(self):
        return self.gear

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

    #return True if we should play gear beep
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
        variance = statistics.variance(self.ratio_deque)
        self.set_ratio(median)
        self.set_variance(variance)

        if (self.variance < self.VAR_BOUNDS[fdp.drivetrain_type] and
                len(self.ratio_deque) >= self.DEQUE_MIN):
            self.to_next_state() #implied from reached to locked
            print(f'LOCKED {self.gear}: {median:.3f}')
            return True

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

    #call update function of current gear in fdp
    #return True if gear has locked and therefore double beep
    def update(self, fdp):
        gear = int(fdp.gear)
        return self.gears[gear].update(fdp)

#class for GUI display of class Gear
#In the GUI the entry for variance is gridded over shiftrpm until shiftrpm
#is calculated. There is a toggle for relative ratio and drivetrain ratio by
#double-clicking the Rel. Ratio / Ratio label in GUIGears
class GUIGear (Gear):
    ENTRY_WIDTH = 6

    FG_DEFAULT = '#000000'
    BG_UNUSED  = '#F0F0F0'
    BG_REACHED = '#FFFFFF'
    BG_LOCKED  = '#CCDDCC'
    #                             tuple of (shiftpm_fg, shiftrpm_bg),
    #                                      (entry_fg    entry_bg)
    ENTRY_COLORS = {GearState.UNUSED:     ((BG_UNUSED,  BG_UNUSED),
                                           (BG_UNUSED,  BG_UNUSED)),
                    GearState.REACHED:    ((BG_UNUSED,  BG_UNUSED),
                                           (FG_DEFAULT, BG_REACHED)),
                    GearState.LOCKED:     ((BG_REACHED, BG_REACHED),
                                           (FG_DEFAULT, BG_LOCKED)),
                    GearState.CALCULATED: ((FG_DEFAULT, BG_LOCKED),
                                           (FG_DEFAULT, BG_LOCKED))}
    for key, (t1, t2) in ENTRY_COLORS.items():
        ENTRY_COLORS[key] = (dict(zip(['fg', 'readonlybackground'], t1)), 
                             dict(zip(['fg', 'readonlybackground'], t2)))

    def __init__(self, number, root):
        super().__init__(number)
        self.var_bound = None
        self.shiftrpm_var = tkinter.IntVar()
        self.ratio_var = tkinter.DoubleVar()
        self.relratio_var = tkinter.StringVar()
        self.variance_var = tkinter.StringVar()
        self.init_window(root)
        self.reset()

    def init_gui_entry(self, root, name, justify=tkinter.RIGHT):
        textvariable = getattr(self, f'{name}_var')
        entry = tkinter.Entry(root, state='readonly', width=self.ENTRY_WIDTH,
                              textvariable=textvariable, justify=justify)
        setattr(self, f'{name}_entry', entry)

    def init_window(self, root):
        self.label = tkinter.Label(root, text=f'{self.get_gearnumber()}',
                                   width=self.ENTRY_WIDTH)
        for name in ['shiftrpm', 'ratio', 'variance']:
            self.init_gui_entry(root, name)
        self.init_gui_entry(root, 'relratio', justify=tkinter.CENTER)

    def init_grid(self, column=None, starting_row=0):
        if column is None:
            column = self.get_gearnumber()
        self.label.grid(row=starting_row, column=column)
        if self.get_gearnumber() != MAXGEARS:
            self.shiftrpm_entry.grid(row=starting_row+1, column=column)
            self.relratio_entry.grid(row=starting_row+2, column=column,
                                      columnspan=2)
        self.variance_entry.grid(row=starting_row+1, column=column)

        #let tkinter memorize grid location, then temporarily hide ratio entry
        self.ratio_entry.grid(row=starting_row+2, column=column)
        self.ratio_entry.grid_remove()

    def reset(self):
        super().reset()
        self.var_bound = None
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
        base = self.var_bound if self.var_bound is not None else 1e-4
        factor = math.log(val, base)
        factor = min(max(factor, 0), 1)
        self.variance_var.set(f'{factor:.0%}')

    def update_entry_colors(self):
        shiftrpm_colors, ratio_colors = self.ENTRY_COLORS[self.state]
        
        self.shiftrpm_entry.config(**shiftrpm_colors)
        self.ratio_entry.config(**ratio_colors)
        self.relratio_entry.config(**shiftrpm_colors)

    def to_next_state(self):
        super().to_next_state()
        self.update_entry_colors()
        if self.state.at_final():
            self.variance_entry.grid_remove()

    def update(self, fdp):
        if self.var_bound is None:
            self.var_bound = self.VAR_BOUNDS[fdp.drivetrain_type]
        return super().update(fdp)

    def toggle_ratio_display(self):
        if self.ratio_entry.winfo_viewable():
            if self.gear != MAXGEARS:
                self.relratio_entry.grid()
            self.ratio_entry.grid_remove()
        else:
            self.relratio_entry.grid_remove()
            self.ratio_entry.grid()

class GUIGears(Gears):
    LABEL_WIDTH = 8
    ROW_COUNT = 3 #for ForzaBeep GUI: how many grid rows a gear takes up
    def __init__(self, root):
        self.gears = [None] + [GUIGear(g, root) for g in self.GEARLIST]
        
        self.init_window(root)

    def init_window(self, root):
        opts = {'anchor':tkinter.E, 'width':self.LABEL_WIDTH}
        self.label_gear = tkinter.Label(root, text='Gear', **opts)
        self.label_target = tkinter.Label(root, text='Target', **opts)

        self.ratio_var = tkinter.StringVar(value='Rel. Ratio')
        self.label_ratio = tkinter.Label(root, textvariable=self.ratio_var,
                                         **opts)
        self.label_ratio.bind('<Double-Button-1>', self.ratio_handler)
        
    def init_grid(self):
        self.label_gear.grid(row=0, column=0)
        self.label_target.grid(row=1, column=0)
        self.label_ratio.grid(row=2, column=0)
        
        for i, g in enumerate(self.gears[1:], start=1):
            g.init_grid()

    def ratio_handler(self, event=None):
        if self.ratio_var.get() == 'Rel. Ratio':
            self.ratio_var.set('Ratio')
        else:
            self.ratio_var.set('Rel. Ratio')
        for gear in self.gears[1:]:
            gear.toggle_ratio_display()
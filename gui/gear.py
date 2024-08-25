# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math

from base.gear import Gear, GearState, MAXGEARS, Gears

from mttkinter import mtTkinter as tkinter

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

    def __init__(self, number, root, config):
        super().__init__(number, config)
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
    def __init__(self, root, config):
        self.gears = [None] + [GUIGear(g, root, config) for g in self.GEARLIST]
        
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
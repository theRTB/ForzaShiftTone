# -*- coding: utf-8 -*-
"""
Created on Sat Nov  4 14:50:56 2023

@author: RTB
"""

from mttkinter import mtTkinter as tkinter
#import tkinter
#import tkinter.ttk
import math
import numpy as np

# import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)

#class responsible for handling a tkinter button in the gui to display the
#power graph when it has been collected. The button is disabled until the user
#has collected a curve.
class ButtonGraph():
    TITLE = "ForzaShiftTone: Power graph"
    WIDTH, HEIGHT= 745, 600

    def __init__(self, root, handler, config):
        self.root = root
        self.window_scalar = config.window_scalar

        self.button = tkinter.Button(root, text='View\nGraphs', borderwidth=3)
        self.button.bind('<Button-1>', handler)
        self.disable()

        self.window_open = False

    def reset(self):
        self.disable()

    def close(self):
        self.window_open = False
        self.window.destroy()

    def enable(self):
        self.button.config(state=tkinter.ACTIVE)

    def disable(self):
        self.button.config(state=tkinter.DISABLED)

    def is_disabled(self):
        return self.button.cget('state') == tkinter.DISABLED

    def grid(self, *args, **kwargs):
        self.button.grid(*args, **kwargs)

    #100% scaling is 96 dpi in Windows, tkinter assumes 72 dpi
    #window_scalar allows the user to scale the window up or down
    #the UI was designed at 150% scaling or 144 dpi
    def get_scaledwidthheight(self, width, height):
        screen_dpi = self.root.winfo_fpixels('1i')
        size_factor = screen_dpi / 144 * self.window_scalar
        width = math.ceil(width * size_factor)
        height = math.ceil(height * size_factor)

        return (width, height)

    #From: https://stackoverflow.com/questions/33231484/python-tkinter-how-do-i-get-the-window-size-including-borders-on-windows
    #Get x and y coordinates to place graph underneath the main window.
    #This may not scale arbitrarily with varying border sizes and title sizes
    def get_windowoffsets(self):
        height_root = self.root.winfo_height()
        x_root = self.root.winfo_x()
        y_root = self.root.winfo_rooty()
        x = x_root
        y = y_root + height_root

        return (x, y)

    def plot_power2(self, fig, curve):
        ax = fig.subplots(1)
        fig.set_size_inches(8, 8)
        ax.plot(curve.rpm, curve.power/1000)
        ax.grid()
        
        ax.set_title(self.title)  
        ax.set_xlabel("rpm")
        ax.set_ylabel("power (kW)")
        
        i = np.argmax(curve.power)
        peak_power = curve.power[i]/1000
        peak_power_rpm = int(round(curve.rpm[i]/50, 0)*50)
        finalpower = curve.power[-1]/1000
        finalrpm = int(round(curve.rpm[-1]/50, 0)*50)
        
        j = np.argmin(np.abs(curve.power[:-2] - finalpower*1000))
        testrpm = curve.rpm[j]
        
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()
        
        # ax.hlines(finalpower, finalrpm*.95, finalrpm, linestyle='dotted')
        # ax.vlines(finalrpm, ymin, ymax, linestyle='dotted')
        # ax.annotate(int(finalrpm), (finalrpm, ymin))
        
        ax.hlines(finalpower, testrpm, finalrpm, linestyle='dotted')
        ax.hlines(peak_power, peak_power_rpm*.95, finalrpm, linestyle='dotted')
        ax.vlines(peak_power_rpm, ymax*.85, ymax, linestyle='dotted')
        ax.vlines(testrpm, ymax*.85, ymax, linestyle='dotted')
        
        ax.annotate(round(finalpower,1), (finalrpm, finalpower))
        ax.annotate(round(peak_power,1), (finalrpm, peak_power))
        ax.annotate(int(peak_power_rpm), (peak_power_rpm, ymax*.85))        
        ax.annotate(int(testrpm), (testrpm, ymax*.85))
        
        if self.minrpm is not None:
            xmin = self.minrpm
        else:
            minrpm = min(curve.rpm)
            xmin = minrpm - minrpm % 1000
        
        ax.set_xlim(xmin, finalrpm)
        ax.set_ylim(ymin, ymax)
        # ax.set_ylim(finalpower*0.9, ymax)
        
        xticks = ax.get_xticks()
        xticks[-1] = finalrpm
        ax.set_xticks(xticks)

    def plot_power(self, fig, curve):
        ax = fig.subplots(1)
        ax.plot(curve.rpm, curve.power/1000)
        ax.set_xlabel('rpm')
        ax.set_ylabel('power (kW)')
        ax.format_coord = lambda x,y: f'{x:>5.0f} rpm: {y:4.1f} kW'
        ax.grid()
        
    #is called by graphbutton_handler in gui if there is a curve
    def create_graphwindow(self, curve):
        if self.window_open or curve is None:
            return
        self.window_open = True

        self.window = tkinter.Toplevel(self.root)
        self.window.title(self.TITLE)
        self.window.protocol('WM_DELETE_WINDOW', self.close)

        width, height = self.get_scaledwidthheight(self.WIDTH, self.HEIGHT)
        x, y = self.get_windowoffsets()
        self.window.geometry(f"{width}x{height}+{x}+{y}")

        fig = Figure(figsize=(5,5), dpi=72, layout="constrained")
        canvas = FigureCanvasTkAgg(fig, master=self.window)
        toolbar = NavigationToolbar2Tk(canvas, self.window,
                                            pack_toolbar=False)

        toolbar.pack(side=tkinter.BOTTOM, fill=tkinter.X)
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH,
                                          expand=False)


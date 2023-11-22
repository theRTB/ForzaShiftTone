# -*- coding: utf-8 -*-
"""
Created on Sat Nov  4 14:50:56 2023

@author: RTB
"""

from mttkinter import mtTkinter as tkinter
#import tkinter
#import tkinter.ttk
import numpy as np

#Change default DPI when saving an image
import matplotlib.pyplot as plt
plt.rcParams['savefig.dpi'] = 100

from matplotlib.figure import Figure
from matplotlib.ticker import MultipleLocator
from matplotlib.backends.backend_tkagg import (FigureCanvasTkAgg,
                                               NavigationToolbar2Tk)

#From: https://stackoverflow.com/questions/12695678/how-to-modify-the-navigation-toolbar-easily-in-a-matplotlib-figure-window
#remove dysfunctional Subplots button from toolbar
class NavigationToolbar(NavigationToolbar2Tk):
    # only display the buttons we need
    toolitems = [t for t in NavigationToolbar2Tk.toolitems if
                 t[0] != 'Subplots']
    
    def __init__(self, carname_var, *args, **kwargs):
        self.carname_var = carname_var
        super().__init__(*args, **kwargs)
    
    def save_figure(self, *args):
        if title := self.carname_var.get():
            self.canvas.figure.suptitle(title)
        super().save_figure(self, *args)
        self.canvas.figure.suptitle('')
        self.canvas.draw_idle()

#class responsible for handling a tkinter button in the gui to display the
#power graph when it has been collected. The button is disabled until the user
#has collected a curve.
class ButtonGraph():
    TITLE = "ForzaShiftTone: Power graph"
    #target width and height of the graph not the window
    WIDTH, HEIGHT= 745, 500 
    FIGURE_DPI = 72

    def __init__(self, root, handler, config):
        self.root = root
        self.window_scalar = config.window_scalar
        self.power_percentile = config.graph_power_percentile

        self.window_open = False

        self.button = tkinter.Button(root, text='View\nGraphs', borderwidth=3,
                                     command=handler, state=tkinter.DISABLED)

    def reset(self):
        self.disable()

    def close(self):
        self.window_open = False
        self.window.destroy()

    #enable the button in the GUI
    def enable(self):
        self.button.config(state=tkinter.ACTIVE)

    #disable the button in the GUI
    def disable(self):
        self.button.config(state=tkinter.DISABLED)

    def is_disabled(self):
        return self.button.cget('state') == tkinter.DISABLED

    def grid(self, *args, **kwargs):
        self.button.grid(*args, **kwargs)

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

    def plot_power(self, ax, curve, revlimit_percent):
        #filter curve to respected rev limit rounded to the nearest 50
        revlimit = round(curve.rpm[-1]/50)*50
        curve_filter = curve.rpm <= revlimit_percent*revlimit
        rpm = curve.rpm[curve_filter]
        power = curve.power[curve_filter] / 1000
        ax.plot(rpm, power)
        ax.grid()

        ax.set_xlabel("rpm")
        ax.set_ylabel("power (kW)")

        i = np.argmax(power)
        peak_power = power[i]
        peak_power_rpm = round(rpm[i]/50)*50
        final_power = power[-1]
        final_rpm = round(rpm[-1]/50)*50

        #override x,y point display in toolbar
        ax.format_coord = lambda x,y: f'{x:>5.0f} rpm: {y:>4.1f} kW ({y/peak_power:>4.1%})'

        #get axis limits to force limits later, annotating moves some of these
        xmin, xmax = ax.get_xlim()
        ymin, ymax = ax.get_ylim()

        ypeak = peak_power*.90
        #emphasize location of peak power with dotted lines
        ax.hlines(peak_power, peak_power_rpm*.90, final_rpm,
                  linestyle='dotted')
        ax.vlines(peak_power_rpm, ypeak, ymax, linestyle='dotted')

        #annotate peak power, and power at respected revlimit
        ax.annotate(round(final_power,1), (final_rpm, final_power),
                    verticalalignment='top', horizontalalignment='left')
        ax.annotate(round(peak_power,1), (final_rpm, peak_power),
                    verticalalignment='center')
        ax.annotate(int(peak_power_rpm), (peak_power_rpm, ypeak),
                    verticalalignment='top', horizontalalignment='center')

        #draw the defined underfill with rpm values for lower/upper limit
        power_filter = power >= self.power_percentile*peak_power
        rpm_filtered = rpm[power_filter]
        power_filtered = power[power_filter]
        ax.fill_between(rpm_filtered, power_filtered, alpha=0.15, color='b')
        lower_limit = int(rpm_filtered[0])
        upper_limit = int(rpm_filtered[-1])
        ymid = (ymin+peak_power) /2
        #display a double arrow'd line for the visual width of the underfill
        ax.annotate(text='', xy=(lower_limit,ymid), xytext=(upper_limit,ymid),
                    arrowprops=dict(arrowstyle='<->',shrinkA=0, shrinkB=0))
        #display the lower limit, and
        #if upper limit not equal to revlimit: display upper limit
        ax.annotate(lower_limit, (lower_limit, ymin),
                    verticalalignment='bottom', horizontalalignment='left')
        if round(rpm_filtered[-1]/50)*50 != final_rpm:
            y_upperlimit = ymin + 0.05 * (peak_power - ymin)
            ax.annotate(upper_limit, (upper_limit, y_upperlimit),
                        verticalalignment='bottom',horizontalalignment='right')

        #draw the percentage of peak power the underfill covers
        #nudge percentile upwards, drop ratio a little relative to ymid
        x = (lower_limit + upper_limit)/2
        ratio = upper_limit/lower_limit
        ax.annotate(f'{self.power_percentile:.1%}', (x, ymid*1.01),
                    verticalalignment='bottom', horizontalalignment='center')
        ax.annotate(f'ratio {ratio:.2f}', (x, ymid*0.98),
                    verticalalignment='top', horizontalalignment='center')

        #add minor ticks per 100 rpm including alpha'd grid lines
        ax.xaxis.set_minor_locator(MultipleLocator(100))
        ax.xaxis.grid(True, which='minor', alpha=0.2)

        #rewrite final xtick to '<revlimit> respected revlimit'
        #if next-to-last tick is within 700 rpm: remove to avoid overlap
        xticks = ax.get_xticks()
        xticklabels = ax.get_xticklabels()
        if final_rpm - xticks[-2] <= 700:
            xticklabels[-2] = ''
        xticklabels[-1] = f'{final_rpm}\nrespected\nrevlimit'
        xticks[-1] = final_rpm
        ax.set_xticks(xticks)
        ax.set_xticklabels(xticklabels)

        #set lower limit of graph to first multiple of 1000 below min rpm
        minrpm = min(rpm)
        xmin = minrpm - minrpm % 1000
        
        #reapply the axis limits and force respected rev limit as max
        ax.set_xlim(xmin, final_rpm)
        ax.set_ylim(ymin, ymax)

    #100% scaling is 96 dpi in Windows, matplotlib is set to 72 dpi
    #window_scalar allows the user to scale the window up or down
    def get_scaledfigsize(self):
        screen_dpi = self.root.winfo_fpixels('1i')
        scaling = screen_dpi / 96
        graph_dpi = self.FIGURE_DPI * scaling
        width = self.WIDTH / (graph_dpi / self.window_scalar)
        height = self.HEIGHT / (graph_dpi / self.window_scalar)

        return (width, height)

    #is called by graphbutton_handler in gui if there is a curve
    #revlimit_pct is used to limit the y-axis, it will only display up to the
    #percentage of revlimit
    #window size is explicitly not set: the pyplot will otherwise not scale
    #properly when resizing the window
    def create_graphwindow(self, curve, revlimit_percent):
        if self.window_open or curve is None:
            return
        self.window_open = True

        self.window = tkinter.Toplevel(self.root)
        self.window.title(self.TITLE)
        self.window.protocol('WM_DELETE_WINDOW', self.close)

        x, y = self.get_windowoffsets()
        self.window.geometry(f"+{x}+{y}")

        fig = Figure(figsize=self.get_scaledfigsize(), dpi=self.FIGURE_DPI,
                     layout="constrained")
        ax = fig.subplots(1)
        self.plot_power(ax, curve, revlimit_percent)

        canvas = FigureCanvasTkAgg(fig, master=self.window)

        #add a Car: (entry) frame up top for entering the car name
        #this is manual entry, automating is possible but very time consuming
        #the carname is added as title when saving the figure
        frame = tkinter.Frame(self.window)
        carname_var = tkinter.StringVar(value='')
        tkinter.Label(frame, text='Car:').pack(side=tkinter.LEFT)
        car_entry = tkinter.Entry(frame, textvariable=carname_var)
        car_entry.pack(side=tkinter.RIGHT, fill=tkinter.X, expand=True)

        frame.pack(side=tkinter.TOP, fill=tkinter.X)
        NavigationToolbar(canvas=canvas, window=self.window, 
                          carname_var=carname_var)
        canvas.get_tk_widget().pack(side=tkinter.TOP, fill=tkinter.BOTH,
                                          expand=True)

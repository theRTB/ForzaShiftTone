# -*- coding: utf-8 -*-
"""
Created on Sun Aug 18 10:36:50 2024

@author: RTB
"""

#replaced tkinter with supposed thread safe tkinter variant
#instead of freezing when the main thread isn't under control of tkinter,
#it now crashes instead. Theoretically, an improvement.
from mttkinter import mtTkinter as tkinter
#import tkinter
import tkinter.ttk

#tell Windows we are DPI aware
import ctypes
PROCESS_SYSTEM_DPI_AWARE = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)

from base.gtbeep import GTBeep

#TODO: is there an alternative way to use config?
from config import config, FILENAME_SETTINGS
config.load_from(FILENAME_SETTINGS)

from gui.gtudploop import GUIGTUDPLoop
from gui.rpm import GUIRPM
from gui.history import GUIHistory
from gui.carordinal import GUICarOrdinal
from gui.gear import GUIGears
from gui.configvar import (GUIPeakPower, GUIToneOffset, GUIRevbarData,
                           GUIRevlimit, GUIVolume, GUIConfigButton)
from gui.enginecurve import GUIEngineCurve

from utility import Variable

#TODO:
    # hide 0.00 rel ratio on final gear: add finalgear option somehow
    # rework row display on shift history: it visibles rotates due to slowness
    # move to labels instead
    #Grey out gear 9 and 10: non-functional for GT7
    #Maybe phase out Settings window to extend main window to the right?
    #Grid variables into those
    #Brief shift history of the last 5 shifts or so in main window?
    
    #Copy button: open Textbox with various stats pasted for copy and paste
    
    # Test if window scalar config variable works as expected
    # Test if changing dpi works as expected
    
#tkinter GUI wrapper around GTBeep
class GUIGTBeep(GTBeep):
    TITLE = "GTShiftTone: Dynamic shift tone for Gran Turismo 7"
    WIDTH, HEIGHT = 815, 239 #most recent dump of size at 150% scaling
    WRITEBACK_VARS = ['revlimit_percent', 'revlimit_offset', #'tone_offset',
                      'hysteresis_percent', 'volume', 'target_ip', 
                      'window_x', 'window_y', 'dynamictoneoffset',
                      'includereplay', 'window_x', 'window_y', 'target_ip']
    
    def __init__(self):
        super().__init__()
        
        self.root.mainloop()
        
    def init_vars(self):
        super().init_vars()
        self.init_tkinter()
        self.init_gui_vars()
        self.init_gui_grid()
    
    def init_tkinter(self):
        self.root = tkinter.Tk()
        self.root.title(self.TITLE)
        
        #100% scaling is ~96 dpi in Windows, tkinter assumes ~72 dpi
        #window_scalar allows the user to scale the window up or down
        #the UI was designed at 150% scaling or ~144 dpi
        #we have to fudge width a bit if scaling is 100%
        screen_dpi = self.root.winfo_fpixels('1i')
        dpi_factor = (96/72) * (screen_dpi / 96) * config.window_scalar
        # size_factor = screen_dpi / 144 * config.window_scalar
        # width = math.ceil(self.WIDTH * size_factor)
        # height = math.ceil(self.HEIGHT * size_factor)
        # if screen_dpi <= 96.0:
        #     width += 40 #hack for 100% size scaling in Windows
        
        # self.root.geometry(f"{width}x{height}") #not required
        if config.window_x is not None and config.window_y is not None:
            self.root.geometry(f'+{config.window_x}+{config.window_y}')
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.resizable(False, False)
        self.root.tk.call('tk', 'scaling', dpi_factor)
        # self.root.attributes('-toolwindow', True) #force on top

    def init_gui_buttonframe(self):
        frame = tkinter.Frame(self.root)
        
        adjustables = { name:getattr(self, name) 
                                      for name in GUIConfigButton.get_names() }
        self.buttonconfig = GUIConfigButton(frame, config, adjustables)
        self.buttonreset = tkinter.Button(frame, text='Reset', borderwidth=3, 
                                          command=self.reset)
        self.history = GUIHistory(frame, config=config)
        
        self.buttonframe = frame
        
    def init_gui_vars(self):
        root = self.root
        self.loop = GUIGTUDPLoop(root, config, loop_func=self.loop_func)
        
        self.gears = GUIGears(root, config)
        self.revlimit = GUIRevlimit(root, defaultvalue=-1)
        
        self.tone_offset = GUIToneOffset(root, config)
        
        self.rpm = GUIRPM(root, hysteresis_percent=self.hysteresis_percent)
        self.volume = GUIVolume(root, config)
        self.peakpower = GUIPeakPower(root)
        self.revbardata = GUIRevbarData(root)
        self.car_ordinal = GUICarOrdinal(root)
        
        self.curve = GUIEngineCurve(root, self.buttongraph_handler, 
                                          config)
        
        self.init_gui_buttonframe()

    def init_gui_grid_buttonframe(self):
        self.buttonconfig.grid(row=0, column=0)
        self.buttonreset.grid( row=0, column=1)
        self.history.grid(     row=0, column=2)

    def init_gui_grid(self):
        self.gears.init_grid()
        row = GUIGears.ROW_COUNT #start from row below gear display
        
        #force minimum row size for other rows
        # self.root.rowconfigure(index=row+3, weight=1000)
        
        self.volume.grid(      row=0,     column=12, rowspan=4)         
       
        self.revlimit.grid(    row=row,   column=0)  
        self.revbardata.grid(  row=row,   column=3)
        self.loop.grid(        row=row,   column=8,  rowspan=3, columnspan=3,
                                                             sticky=tkinter.EW)  
        
        self.peakpower.grid(   row=row+1, column=0)           
        self.buttonframe.grid( row=row+1, column=4,             columnspan=4)        
        self.curve.grid(       row=row+1, column=12, rowspan=3)
        
        self.init_gui_grid_buttonframe()
        
        self.rpm.grid(         row=row+3, column=0)
        self.tone_offset.grid( row=row+3, column=3)
        self.car_ordinal.grid( row=row+3, column=7)

    def reset(self):
        super().reset()
        self.peakpower.reset()
        self.revbardata.reset()

    def buttongraph_handler(self, event=None):
        self.curve.create_window(self.revlimit_percent.get(),
                                 self.car_ordinal.get_name())

    #called when car ordinal changes or data collector finishes a run
    def handle_curve_change(self, gtdp, *args, **kwargs):
        super().handle_curve_change(gtdp, *args, **kwargs)
        if not self.curve.is_loaded():
            return
        
        self.peakpower.set(*self.curve.get_peakpower_tuple())

    def close(self):
        #Used to update WIDTH and HEIGHT if necessary
        # print(f'x {self.root.winfo_width()}, y {self.root.winfo_height()}')
        
        self.config_writeback()
        super().close()
        self.root.destroy()

    #write all GUI configurable settings to the config file
    def config_writeback(self, varlist=WRITEBACK_VARS):
        #grab x,y position to save as window_x and window_y
        self.window_x = Variable(self.root.winfo_x())
        self.window_y = Variable(self.root.winfo_y())
        
        #hack to get ip from loop
        self.target_ip = Variable(self.loop.get_target_ip())
        
        super().config_writeback(varlist)
        
def main():
    global gtbeep #for debugging
    gtbeep = GUIGTBeep()

if __name__ == "__main__":
    main()
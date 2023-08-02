# -*- coding: utf-8 -*-
"""
Created on Sun May  7 19:35:24 2023

@author: RTB
"""
import math
import socket
from mttkinter import mtTkinter as tkinter
#import tkinter #replaced with supposed thread safe tkinter variant
#import tkinter.ttk
import winsound
import statistics
from concurrent.futures.thread import ThreadPoolExecutor
from collections import deque
import numpy as np

#for importing config
import json
from os.path import exists

#tell Windows we are DPI aware. We are not, but this gets around
#tkinter scaling inconsistently.
import ctypes
PROCESS_SYSTEM_DPI_AWARE = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)

from fdp import ForzaDataPacket



FILENAME_SETTINGS = 'config.json'

class constants():
    ip = '127.0.0.1'
    port = 12350
    packet_format = 'fh4'
    sound_file = 'audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav'
    sound_files = {  0:'audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav',
                   -10:'audiocheck.net_sin_1000Hz_-13dBFS_0.1s.wav',
                   -20:'audiocheck.net_sin_1000Hz_-23dBFS_0.1s.wav',
                   -30:'audiocheck.net_sin_1000Hz_-33dBFS_0.1s.wav' }
    
    beep_counter_max = 30 #minimum number of frames between beeps = 0.33ms
    beep_rpm_pct = 0.75 #counter resets below this percentage of beep rpm

    tone_offset = 17 #if specified rpm predicted to be hit in x packets: beep
    tone_offset_lower =  9
    tone_offset_upper = 25
    
    revlimit_percent = 0.996 #respected rev limit for trigger revlimit as pct%
    revlimit_percent_lower = 0.950
    revlimit_percent_upper = 0.998
    
    revlimit_offset = 5 #additional buffer in x packets for revlimit
    revlimit_offset_lower = 3
    revlimit_offset_upper = 8
    
    hysteresis = 1
    hysteresis_steps = [0, 1, 5, 25, 50, 100, 250, 500]
    
    log_full_shiftdata = False
    log_basic_shiftdata = True
    we_beep_max = 30 #print previous packets for up to x packets after shift
    
    #as rpm ~ speed, and speed ~ tanh, linear regression + extrapolation 
    #overestimates slope and intercept. Keeping the deque short limits this
    linreg_len_min = 15
    linreg_len_max = 20 
        
    @classmethod
    def get_dict(cls):
        blocklist = ['update', 'get_dict', 'load_from', 'write_to']
        return {k:v for k,v in cls.__dict__.items() 
                                        if k not in blocklist and k[0] != '_'}

    @classmethod
    def load_from(cls, filename):
        if not exists(filename):
            return
        with open(filename) as file:
            file_config = json.load(file)
            for k,v in file_config.items():
                if k == 'sound_files':
                    v = {int(key):value for key, value in v.items()}
                setattr(cls, k, v)
    
    @classmethod
    def write_to(cls, filename):
        with open(filename, 'w') as file:
            json.dump(cls.get_dict(), file, indent=4)

constants.load_from(FILENAME_SETTINGS)
#constants.write_to(FILENAME_SETTINGS)
        
#collects an array of packets at full throttle
#if the user lets go of throttle, changes gear: reset
#revlimit is confirmed by: the initial run, then x packets with negative power,
#   then a packet with positive power. All at 100% throttle
#Then cut down the array to force boost to be at or above the boost in the
#   final packet
#if power at the first packet is lower (or equal) to the power in the final
#   packet, we have a power curve that is complete enough to do shift rpm
#   rpm calculations with it.
class RunCollector():
    MINLEN = 30
    def __init__(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1

    def update(self, fdp):
        if self.state == 'WAIT':
            if (fdp.accel == 255 and self.prev_rpm < fdp.current_engine_rpm and
                fdp.power > 0):
                self.state = 'RUN'
                self.gear_collected = fdp.gear

        if self.state == 'RUN':
          #  print(f"RUN {fdp.current_engine_rpm}, {fdp.power} {fdp.accel}")
            if fdp.accel < 255:
                # print("RUN RESET")
                self.reset() #back to WAIT
                return
            elif fdp.power <= 0:
                self.state = 'MAYBE_REVLIMIT'
            else:
                self.run.append(fdp)

        if self.state == 'MAYBE_REVLIMIT':
          #  print("MAYBE_REVLIMIT")
            if fdp.accel < 255:
             #   print("MAYBE_REVLIMIT RESET ACCEL NOT FULL")
                self.reset() #back to WAIT
                return
            if fdp.gear != self.gear_collected:
             #   print("MAYBE_REVLIMIT RESET GEAR CHANGED")
                self.reset() #user messed up
                return
            if len(self.run) == 1:
                # print("MAYBE_REVLIMIT RESET LENGTH 1")
                self.reset() #erronous run
                return
            if fdp.power > 0:
                self.state = 'TEST'

        if self.state == 'TEST':
            # print("TEST")
            max_boost = self.run[-1].boost
            # len_before = len(self.run)
            self.run = [p for p in self.run if p.boost >= max_boost-1e-03]
            # print(f'TEST len base {len_before} len max boost {len(self.run)}')
            if len(self.run) < self.MINLEN:
                # print("TEST FAILS MINLEN TEST")
                self.reset()
                return
            if self.run[0].power > self.run[-1].power:
                # print("TEST RESET RUN NOT COMPLETE")
                self.reset() #run not clean, started too high rpm
                return
            self.state = 'DONE'

        self.prev_rpm = fdp.current_engine_rpm

    def run_completed(self):
        return self.state == 'DONE'

    def get_revlimit_if_done(self):
        if self.state != 'DONE':
            return None
        return self.run[-1].current_engine_rpm
    
    def get_gear(self):
        if self.gear_collected == -1:
            return None
        return self.gear_collected

    def get_run(self):
        return self.run

    def reset(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1

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

#base class for a tkinter GUI that listens to UDP for packets by a forza title
class ForzaUIBase():
    TITLE = 'ForzaUIBase'
    WIDTH, HEIGHT = 400, 200
    def __init__(self):
        self.threadPool = ThreadPoolExecutor(max_workers=8,
                                             thread_name_prefix="exec")

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.settimeout(1)
        self.server_socket.bind((constants.ip, constants.port))

        self.root = tkinter.Tk()
        self.root.title(self.TITLE)
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.active = tkinter.IntVar(value=1)

        # self.__init__window()

        # def __init__window(self):
        #     if self.active.get():
        #         self.active_handler()
        #     tkinter.Checkbutton(self.root, text='Active',
        #                         variable=self.active, 
        #                         command=self.active_handler).pack()
        #     self.mainloop()

    def mainloop(self):
        self.root.mainloop()

    def active_handler(self):
        if self.active.get():
            def starting():
                self.isRunning = True
                self.fdp_loop(self.loop_func)
            self.threadPool.submit(starting)
        else:
            def stopping():
                self.isRunning = False
            self.threadPool.submit(stopping)

    def loop_func(self, fdp):
        pass

    def fdp_loop(self, loop_func=None):
        try:
            while self.isRunning:
                fdp = nextFdp(self.server_socket, constants.packet_format)
                if fdp is None:
                    continue

                if loop_func is not None:
                    loop_func(fdp)
        except BaseException as e:
            print(e)

    def close(self):
        """close program
        """
        self.isRunning = False
        self.threadPool.shutdown(wait=False)
        self.server_socket.close()
        self.root.destroy()

#maintain a rolling array of the time between beep and actual shift
#caps to the lower and upper limits of the tone_offset variable to avoid
#outliers such as 0 ms reaction time or a delay of seconds or more
#depends on ForzaBeep loop_test_for_shiftrpm and loop_beep
class DynamicToneOffset():
    DEQUE_MIN, DEQUE_MAX = 35, 75
    
    DEFAULT_TONEOFFSET = constants.tone_offset
    OFFSET_LOWER = constants.tone_offset_lower
    OFFSET_UPPER = constants.tone_offset_upper
    
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
        if self.deque_min_counter <= self.DEQUE_MIN:
            self.deque.popleft()
        else:
            self.deque_min_counter += 1
        value = min(self.OFFSET_UPPER, self.counter)
        value = max(self.OFFSET_LOWER, value)
        self.deque.append(value)
        average = statistics.mean(self.deque)
        print(f'DynamicToneOffset: offset {self.offset} new average {average:.2f}')
        average = int(round(average, 0))
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
        return self.var.get()
    
    def gui_set(self, val):
        self.var.set(val)
        
    def set(self, val):
        super().set(val)
        val_gui = self.convert_to_gui(val)
        self.gui_set(val_gui)
        
    def update(self):
        val_gui = self.gui_get()
        val_internal = self.convert_from_gui(val_gui)
        self.set(val_internal)

class GUIConfigVariable_ToneOffset(GUIConfigVariable, DynamicToneOffset):
    NAME = 'Tone offset'
    LOWER, UPPER = constants.tone_offset_lower, constants.tone_offset_upper
    DEFAULTVALUE = constants.tone_offset
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
    DEFAULTVALUE = constants.revlimit_offset
    LOWER = constants.revlimit_offset_lower
    UPPER = constants.revlimit_offset_upper
    UNIT = 'ms'
    
    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=ms_to_packets, 
                         convert_to_gui=packets_to_ms, value=self.DEFAULTVALUE,
                         values=range(self.LOWER, self.UPPER+1))
        
class GUIConfigVariable_RevlimitPercent(GUIConfigVariable):
    NAME = 'Revlimit'
    DEFAULTVALUE = constants.revlimit_percent
    LOWER = constants.revlimit_percent_lower
    UPPER = constants.revlimit_percent_upper
    UNIT = '%'
    
    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=percent_to_factor, 
                         convert_to_gui=factor_to_percent, 
                         values=np.arange(self.LOWER, self.UPPER, 0.001),
                         value=self.DEFAULTVALUE)

class GUIConfigVariable_Hysteresis(GUIConfigVariable):
    NAME = 'Hysteresis'
    DEFAULTVALUE = constants.hysteresis
    UNIT = 'rpm'
    
    def __init__(self, root, row, column=0):
        super().__init__(root=root, name=self.NAME, unit=self.UNIT, row=row,
                         convert_from_gui=lambda x: x, column=column,
                         convert_to_gui=lambda x: x, 
                         values=constants.hysteresis_steps,
                         value=self.DEFAULTVALUE)

class ForzaBeep(ForzaUIBase):
    TITLE = "ForzaBeep: it beeps, you shift"
    WIDTH, HEIGHT = 745, 255

    MAXGEARS = 10

    MIN_THROTTLE_FOR_BEEP = 255
    REVLIMIT_GUESS = 750  #revlimit = engine_limit - guess
    #distance between revlimit and engine limit varies between 100 and 2000
    #with the most common value at 500. 750 is the rough average.

    DEFAULT_GUI_VALUE = 'N/A'
    
    REVLIMIT_BG_NA = '#F0F0F0'
    REVLIMIT_BG_GUESS = '#ffffff'
    REVLIMIT_BG_CURVE = '#ccddcc'

    def __init__(self):
        super().__init__()
        self.__init__vars()
        self.__init__window()
        self.mainloop()

    def __init__vars(self):
        self.isRunning = False
        self.we_beeped = 0
        self.beep_counter = 0
        self.curve = None

        self.rpm = tkinter.IntVar(value=0)
        self.revlimit = -1
        self.revlimit_var = tkinter.StringVar(value=self.DEFAULT_GUI_VALUE)
        
        self.edit_var = tkinter.IntVar(value=0)
        
        self.volume = tkinter.IntVar(value=0)

        self.runcollector = RunCollector()
        self.lookahead = Lookahead(constants.linreg_len_min,
                                   constants.linreg_len_max)

        self.shiftdelay_deque = deque(maxlen=120)
        
        self.hysteresis_rpm = 0

        self.car_ordinal = None

    def __init__window_buffers_frame(self, row):
        frame = tkinter.LabelFrame(self.root, text='Buffers / Configurables')
        frame.grid(row=row, column=5, rowspan=4, columnspan=4, stick='EW')
        
        self.revlimit_percent = GUIConfigVariable_RevlimitPercent(frame, 0)
        self.revlimit_offset = GUIConfigVariable_RevlimitOffset(frame, 1)
        self.tone_offset = GUIConfigVariable_ToneOffset(frame, 2)
        self.hysteresis = GUIConfigVariable_Hysteresis(frame, 3)

        tkinter.Checkbutton(frame, text='Edit',
                            variable=self.edit_var, command=self.edit_handler
                            ).grid(row=0, column=3, #columnspan=2,
                                   sticky=tkinter.W)    
        self.edit_handler()

    def __init__window(self):
        for i, text in enumerate(['Gear', 'Target', 'Ratio']):
            tkinter.Label(self.root, text=text, width=7, anchor=tkinter.E
                          ).grid(row=i, column=0)

        self.gears = [None] + [Gear(self.root, g, g) for g in range(1, 11)]

        row = Gear.ROW_COUNT

        tkinter.Label(self.root, text='Revlimit').grid(row=row, column=0,
                                                       sticky=tkinter.E)
        self.revlimit_entry = tkinter.Entry(self.root, width=6, 
                                            state='readonly',
                                            justify=tkinter.RIGHT,
                                            textvariable=self.revlimit_var)
        self.revlimit_entry.grid(row=row, column=1)
        tkinter.Label(self.root, text='RPM').grid(row=row, column=2,
                                                  sticky=tkinter.W)

        resetbutton = tkinter.Button(self.root, text='Reset', borderwidth=3)
        resetbutton.grid(row=row, column=3, rowspan=2)
        resetbutton.bind('<Button-1>', self.reset)

        self.__init__window_buffers_frame(row)

        tkinter.Scale(self.root, orient=tkinter.VERTICAL, showvalue=0,
                      from_=0, to=-30, variable=self.volume, resolution=10
                      ).grid(row=row, column=10, columnspan=1, rowspan=3,
                             sticky=tkinter.E)
        
        row += 1 #continue on next row
 
        tkinter.Label(self.root, text='Volume').grid(row=row, column=9, 
                                                     columnspan=2)
        
        row += 1 #continue on next row
        
        tkinter.Label(self.root, text='Tach').grid(row=row, column=0, 
                                                  sticky=tkinter.E)     
        tkinter.Entry(self.root, textvariable=self.rpm, width=6,
                      justify=tkinter.RIGHT, state='readonly'
                      ).grid(row=row, column=1, sticky=tkinter.W)
        tkinter.Label(self.root, text='RPM').grid(row=row, column=2, 
                                                  sticky=tkinter.W) 
        
        if self.active.get():
            self.active_handler()
        tkinter.Checkbutton(self.root, text='Active',
                            variable=self.active, command=self.active_handler
                            ).grid(row=row, column=3, columnspan=2,
                                   sticky=tkinter.W)
                               
    def edit_handler(self):
        varlist = [self.revlimit_offset, self.revlimit_percent, 
                   self.tone_offset, self.hysteresis]
        if self.edit_var.get():
            for var in varlist:
                var.config(state='readonly')
        else:
            for var in varlist:
                var.config(state=tkinter.DISABLED)

    def reset(self, *args):
        self.runcollector.reset()
        self.lookahead.reset()
        
        self.we_beeped = 0
        self.beep_counter = 0
        self.curve = None
        self.car_ordinal = None
        
        self.rpm.set(0)
        self.revlimit = -1
        self.revlimit_var.set(self.DEFAULT_GUI_VALUE)
        
        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter()
        self.hysteresis_rpm = 0
        
        self.revlimit_entry.configure(readonlybackground=self.REVLIMIT_BG_NA)
        
        for g in self.gears[1:]:
            g.reset()

    def get_soundfile(self):
        return constants.sound_files[self.volume.get()]

    def get_revlimit(self):
        return self.revlimit

    def set_revlimit(self, val):
        self.revlimit = int(val)
        self.revlimit_var.set(self.revlimit)

    #TODO: investigate bug where current_engine_rpm or the hysteresis get value
    #is a string and the math breaks down
    def loop_hysteresis(self, fdp):
        rpm = fdp.current_engine_rpm
        if abs(rpm - self.hysteresis_rpm) >= self.hysteresis.get():
            self.hysteresis_rpm = rpm

    def loop_car_ordinal(self, fdp):
        if self.car_ordinal is None and fdp.car_ordinal != 0:
            self.car_ordinal = fdp.car_ordinal
        elif fdp.car_ordinal == 0:
            return
        elif self.car_ordinal != fdp.car_ordinal:
            self.reset()
            self.car_ordinal = fdp.car_ordinal
            print(f"Ordinal changed to {self.car_ordinal}, resetting!")

    #grab curve if we collected a complete run
    #update curve if we collected a run in an equal or higher gear
    #we test if this leads to a more accurate run with a better rev limit 
    #defined
    def loop_runcollector(self, fdp):
        self.runcollector.update(fdp)

        if not self.runcollector.run_completed():
            return
            
        if self.curve is None:
            # print("FIRST RUN DONE!")
            self.curve = self.runcollector.get_run()
            self.set_revlimit(self.curve[-1].current_engine_rpm)
            self.revlimit_entry.configure(
                                readonlybackground=self.REVLIMIT_BG_CURVE)
            # print(f'revlimit set: {self.revlimit.get()}')
        elif (self.runcollector.get_revlimit_if_done() > self.get_revlimit()
              and self.runcollector.get_gear() >= self.curve[0].gear):
                # print(f"NEW RUN DONE! len {len(newrun)} gear is higher")
                self.curve = self.runcollector.get_run()
                self.set_revlimit(self.curve[-1].current_engine_rpm)
                for g in self.gears[1:]:
                    g.newrun_decrease_state() #force recalculation of rpm
                    # print(f"Gear {g.gear} reset to LOCKED")
                # print(f'revlimit set: {self.revlimit.get()}')
        else:
            pass
            # print(f"NEW RUN DONE! len {len(newrun)} gear lower or revlimit lower: discarded")
        self.runcollector.reset()

    def loop_calculate_shiftrpms(self):
        if self.curve is not None:
            rpm = [p.current_engine_rpm for p in self.curve]
            power = [p.power for p in self.curve]

            #filter rpm and power
            #sort according to rpm?

            for g1, g2 in zip(self.gears[1:-1], self.gears[2:]):
                g1.calculate_shiftrpm(rpm, power, g2)
                # print(f"gear {g1.gear} shiftrpm set: {shiftrpm}")

    #we assume power is negative between gear change and first frame of shift
    #accel has to be positive at all times, otherwise we don't know for sure
    #where the shift starts
    def loop_test_for_shiftrpm(self, fdp):
        if (len(self.shiftdelay_deque) == 0 or
                self.shiftdelay_deque[0].gear >= fdp.gear or
                self.shiftdelay_deque[0].gear == 0): #case gear reverse
            self.shiftdelay_deque.appendleft(fdp)
            self.tone_offset.increment_counter()
            return

        #case gear has gone up
        prev_packet = fdp
        shiftrpm = None
        for packet in self.shiftdelay_deque:
            if packet.accel == 0:
                return
            if prev_packet.power < 0 and packet.power >= 0:
                shiftrpm = packet.current_engine_rpm
                break
            prev_packet = packet
            self.tone_offset.decrement_counter()
        if shiftrpm is not None:
            optimal = self.gears[fdp.gear-1].get_shiftrpm()
            beep_distance = self.tone_offset.get_counter()
            self.tone_offset.finish_counter()
            beep_distance_ms = 'N/A'
            if beep_distance is not None:
                beep_distance_ms = packets_to_ms(beep_distance)
            if constants.log_basic_shiftdata:
                print(f"gear {fdp.gear-1}-{fdp.gear}: {shiftrpm:.0f} actual shiftrpm, {optimal} optimal, {shiftrpm - optimal:4.0f} difference, {beep_distance_ms} ms distance to beep")
                print("-"*50)
        self.we_beeped = 0
        self.shiftdelay_deque.clear() #TODO: test if moving this out of the if works better
        self.tone_offset.reset_counter()

    def loop_beep(self, fdp, rpm):
        beep_rpm = self.gears[int(fdp.gear)].get_shiftrpm()
        if self.beep_counter <= 0:
            if self.test_for_beep(beep_rpm, self.get_revlimit(), fdp):
                self.beep_counter = constants.beep_counter_max
                self.we_beeped = constants.we_beep_max
                self.tone_offset.start_counter()
                beep(filename=self.get_soundfile())
            elif rpm < math.ceil(beep_rpm*constants.beep_rpm_pct):
                self.beep_counter = 0
        elif self.beep_counter > 0 and rpm < beep_rpm:
            self.beep_counter -= 1

    def loop_guess_revlimit(self, fdp):
        if self.get_revlimit() == -1:
            self.set_revlimit(fdp.engine_max_rpm - self.REVLIMIT_GUESS)
            self.revlimit_entry.configure(
                                    readonlybackground=self.REVLIMIT_BG_GUESS)
            print(f'guess revlimit: {self.get_revlimit()}')

    def loop_func(self, fdp):
        if not fdp.is_race_on:
            return
        
        gear = int(fdp.gear)
        if gear < 1 or gear > 10:
            return
        
        rpm = fdp.current_engine_rpm
        self.rpm.set(int(rpm))     
        
        self.loop_car_ordinal(fdp) #reset if car ordinal changes        
        self.loop_guess_revlimit(fdp) #guess revlimit if not defined yet
        self.loop_hysteresis(fdp) #update self.hysteresis_rpm        
        self.lookahead.add(self.hysteresis_rpm) #update linear regresion
        self.loop_runcollector(fdp) #add data point for curve collecting
        self.loop_calculate_shiftrpms()
        self.loop_test_for_shiftrpm(fdp) #test if we have shifted
        self.gears[gear].derive_gearratio(fdp)
        self.loop_beep(fdp, rpm) #test if we need to beep
        
        if self.we_beeped > 0 and constants.log_full_shiftdata:
            print(f'rpm {rpm:.0f} torque {fdp.torque:.1f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f} count {constants.we_beep_max-self.we_beeped+1}')
            self.we_beeped -= 1

    #to account for torque not being flat, we take a linear approach
    #we take the ratio of the current torque and the torque at the shift rpm
    # if < 1: the overall acceleration will be lower than a naive guess
    #         therefore, scale the slope down: trigger will happen later
    # if > 1: the car will accelerate more. This generally cannot happen unless
    # there is partial throttle.
    def torque_ratio_test(self, target_rpm, offset, fdp):
        torque_ratio = 1
        if self.curve and fdp.torque != 0:
            rpms = np.array([p.current_engine_rpm for p in self.curve])
            i = np.argmin(np.abs(rpms - target_rpm))
            target_torque = self.curve[i].torque
            torque_ratio = target_torque / fdp.torque

        return (self.lookahead.test(target_rpm, offset, torque_ratio),
                torque_ratio)

    def test_for_beep(self, shiftrpm, revlimit, fdp):
        if fdp.accel < self.MIN_THROTTLE_FOR_BEEP:
            return False
        tone_offset = self.tone_offset.get()

        from_gear, from_gear_ratio = self.torque_ratio_test(shiftrpm,
                                                            tone_offset, fdp)
        # from_gear = from_gear and fdp.accel >= self.MIN_THROTTLE_FOR_BEEP
        
        revlimit_pct, revlimit_pct_ratio = self.torque_ratio_test(
            revlimit*self.revlimit_percent.get(), tone_offset, fdp)
        revlimit_time, revlimit_time_ratio = self.torque_ratio_test(
            revlimit, (tone_offset + self.revlimit_offset.get()), fdp)

        if from_gear and constants.log_full_shiftdata:
            print(f'beep from_gear: {shiftrpm}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {from_gear_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_pct and constants.log_full_shiftdata:
            print(f'beep revlimit_pct: {revlimit*self.revlimit_percent.get()}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_pct_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_time and constants.log_full_shiftdata:
            print(f'beep revlimit_time: {revlimit}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_time_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        return from_gear or revlimit_pct or revlimit_time
    
    def close(self):
        constants.tone_offset = self.tone_offset.get()
        constants.write_to(FILENAME_SETTINGS)
        super().close()

#class that maintains a deque used for linear regression. This smooths the rpms
#and provides a slope to predict future RPM values.
class Lookahead():
    def __init__(self, minlen, maxlen):
        self.minlen = minlen
        self.deque = deque(maxlen=maxlen)
        self.clear_linreg_vars()

    def add(self, rpm):
        self.deque.append(rpm)
        self.set_linreg_vars()

    #x is the frame distance to the most recently added point
    #this has the advantage that the slope is counted from the most recent point
    def set_linreg_vars(self):
        if len(self.deque) < self.minlen:
            return
        x, y = range(-len(self.deque)+1, 1), self.deque
        self.slope, self.intercept = statistics.linear_regression(x, y)

    #slope factor is used to shape the prediction with more information than
    #from just the linear regression. As RPM is not linear, it will otherwise
    #overestimate consistently.
    def test(self, target_rpm, lookahead, slope_factor=1):
        if (len(self.deque) < self.minlen or self.slope <= 0 or 
            slope_factor <= 0):
            return False
        distance = (target_rpm - self.intercept) / (self.slope * slope_factor)
        return 0 <= distance <= lookahead
    
    def reset(self):
        self.deque.clear()
        self.clear_linreg_vars()

    def clear_linreg_vars(self):
        self.slope, self.intercept = None, None

def beep(filename=constants.sound_file):
    try:
        winsound.PlaySound(filename,
                           winsound.SND_FILENAME | winsound.SND_ASYNC |
                           winsound.SND_NODEFAULT)
    except:
        print("Sound failed to play")

import intersect
def calculate_shiftrpm(rpm, power, ratio):
    rpm = np.array(rpm)
    power = np.array(power)
    X=0
    intersects = intersect.intersection(rpm, power, rpm*ratio, power)[X]
 #   print(intersects)
    shiftrpm = round(intersects[-1],0) if len(intersects) > 0 else rpm[-1]
    print(f"shift rpm {shiftrpm}, drop to {int(shiftrpm/ratio)}, "
          f"drop is {int(shiftrpm*(1.0 - 1.0/ratio))}")

    return shiftrpm

#convert a packet rate of 60hz to integer milliseconds
def packets_to_ms(val):
    return int(1000*val/60)

#convert integer milliseconds to a packet rate of 60hz
def ms_to_packets(val):
    return int(round(60*int(val)/1000, 0))

#factor is a scalar
def factor_to_percent(val):
    return round(100*val, 1)

#factor is a scalar
def percent_to_factor(val):
    return float(val)/100

def nextFdp(server_socket: socket, format: str):
    """next fdp

    Args:
        server_socket (socket): socket
        format (str): format

    Returns:
        [ForzaDataPacket]: fdp
    """
    try:
        message, _ = server_socket.recvfrom(1024)
        return ForzaDataPacket(message, packet_format=format)
    except BaseException:
        return None

def main():
    global beep
    beep = ForzaBeep()

if __name__ == "__main__":
    main()
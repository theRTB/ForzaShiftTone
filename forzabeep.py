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

#tell Windows we are DPI aware. We are not, but this gets around
#tkinter scaling inconsistently.
import ctypes
PROCESS_SYSTEM_DPI_AWARE = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)

from fdp import ForzaDataPacket

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
    revlimit_percent = 0.996 #respected rev limit for trigger revlimit
    revlimit_offset = 5 #additional margin in packets for revlimit

    log_full_shiftdata = True
    
    #as rpm ~ speed, and speed ~ tanh, linear regression + extrapolation 
    #overestimates slope and intercept. Keeping the deque short limits this
    linreg_len_min = 15
    linreg_len_max = 20 

    we_beep_max = 30 #print previous packets for up to x packets after shift

class RunCollector():
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
            elif fdp.gear != self.gear_collected:
             #   print("MAYBE_REVLIMIT RESET GEAR CHANGED")
                self.reset() #user messed up
                return
            elif len(self.run) == 1:
             #   print("MAYBE_REVLIMIT RESET LENGTH 1")
                self.reset() #erronous run
                return
            elif fdp.power > 0:
                self.state = 'TEST'

        if self.state == 'TEST':
          #  print("TEST")
            if self.run[0].power > self.run[-1].power:
            #    print("TEST RESET RUN NOT COMPLETE")
                self.reset() #run not clean, started too high rpm
                return
            self.state = 'DONE'
            #TODO: add test for boost:
                #boost at equal power must be equal boost to revlimit boost

        self.prev_rpm = fdp.current_engine_rpm

    def run_completed(self):
        return self.state == 'DONE'

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

    #if we have a new (and better trace) we reduce the state of the gear
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
        # self.listener = Listener(on_press=self.on_press)

        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server_socket.settimeout(1)
        self.server_socket.bind((constants.ip, constants.port))

        self.root = tkinter.Tk()
        self.root.title(self.TITLE)
        self.root.geometry(f"{self.WIDTH}x{self.HEIGHT}")
        self.root.protocol('WM_DELETE_WINDOW', self.close)

        self.active = tkinter.IntVar(value=1)

        # self.__init__window()

    # def __init__vars(self):
    #     print("base __init__vars got called")
    #     pass

    # def __init__window(self):
    #     print("base __init__window got called")
    #     if self.active.get():
    #         self.active_handler()
    #     tkinter.Checkbutton(self.root, text='Active',
    #                         variable=self.active, command=self.active_handler
    #                         ).pack()

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
     #   self.listener.stop()
        self.root.destroy()

class ForzaBeep(ForzaUIBase):
    TITLE = "ForzaBeep: it beeps, you shift"
    WIDTH, HEIGHT = 785, 205

    MAXGEARS = 10

    MIN_THROTTLE_FOR_BEEP = 255
    REVLIMIT_GUESS = 750  #revlimit = engine_limit - guess
    #distance between revlimit and engine limit varies between 500 and 1250ish

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
        self.tone_offset = constants.tone_offset
        self.revlimit_percent = constants.revlimit_percent
        self.revlimit_offset = constants.revlimit_offset
        
        self.volume = tkinter.IntVar(value=0)

        self.runcollector = RunCollector()
        self.lookahead = Lookahead(constants.linreg_len_min,
                                   constants.linreg_len_max)

        self.shiftdelay_deque = deque(maxlen=120)

        self.car_ordinal = None

    
    def __init_spinbox(self, name, value, spinbox_dict, row, column):
        label = tkinter.Label(self.root, text=name)
                 
        var = tkinter.StringVar()  
        spinbox = tkinter.Spinbox(self.root, state='readonly',
                        width=5, justify=tkinter.RIGHT, textvariable=var,
                        readonlybackground='#FFFFFF', **spinbox_dict)

        var.set(value)
        label.grid(row=row, column=column, columnspan=2, sticky='E')
        spinbox.grid(row=row, column=column+2)
        return spinbox
        
    def get_tone_offset(self):
        return self.tone_offset
    
    #tone_offset_gui is in integer milliseconds, rounding lets us recover
    #the original distance in packets
    def update_tone_offset(self):
        self.tone_offset = round(60*int(self.tone_offset_gui.get())/1000, 0)
        
    def __init_spinbox_tone_offset(self, row, column):
        name = 'Tone offset (ms)'
        spinbox_dict = {'values':[int(1000*x/60) for x in range(10, 22)],
                        'command':self.update_tone_offset}
        value = int(1000*constants.tone_offset/60)
        
        self.tone_offset_gui = self.__init_spinbox(name, value, spinbox_dict, 
                                                   row, column)

    def get_revlimit_percent(self):
        return self.revlimit_percent
    
    def update_revlimit_percent(self):
        self.revlimit_percent = float(self.revlimit_percent_gui.get())/100
        
    def __init_spinbox_revlimit_percent(self, row, column):
        name = 'Revlimit (%)'
        spinbox_dict = {'values':[x/10 for x in range(950, 999)],
                        'command':self.update_revlimit_percent}
        value = round(100*constants.revlimit_percent, 1)
        
        self.revlimit_percent_gui = self.__init_spinbox(name, value, 
                                                        spinbox_dict, 
                                                        row, column)

    def get_revlimit_offset(self):
        return self.revlimit_offset
    
    def update_revlimit_offset(self):
        self.revlimit_ms = round(60*int(self.revlimit_ms_gui.get())/1000, 0)
        
    def __init_spinbox_revlimit_offset(self, row, column):
        name = 'Revlimit (ms)'
        spinbox_dict = {'values':[int(1000*x/60) for x in range(2, 8)],
                        'command':self.update_revlimit_offset}
        value = int(1000*constants.revlimit_offset/60)
        
        self.revlimit_offset_gui = self.__init_spinbox(name, value, 
                                                       spinbox_dict, 
                                                       row, column)

    def __init__window(self):
        for i, text in enumerate(['Gear', 'Shift RPM', 'Ratio', 'RPM:']):
            tkinter.Label(self.root, text=text, width=8, anchor=tkinter.E
                          ).grid(row=i, column=0)

        self.gears = [None] + [Gear(self.root, g, g) for g in range(1, 11)]

        row = Gear.ROW_COUNT

        tkinter.Label(self.root, textvariable=self.rpm, width=5,
                      justify=tkinter.RIGHT, anchor=tkinter.E
                      ).grid(row=row, column=1, sticky=tkinter.W)

        tkinter.Label(self.root, text='Revlimit').grid(row=row, column=3)
        self.revlimit_entry = tkinter.Entry(self.root, width=6, 
                                            state='readonly', 
                                            justify=tkinter.RIGHT,
                                            textvariable=self.revlimit_var)
        self.revlimit_entry.grid(row=row, column=4)

        resetbutton = tkinter.Button(self.root, text='Reset', borderwidth=3)
        resetbutton.grid(row=row, column=5)
        resetbutton.bind('<Button-1>', self.reset)

        if self.active.get():
            self.active_handler()
        tkinter.Checkbutton(self.root, text='Active',
                            variable=self.active, command=self.active_handler
                            ).grid(row=row, column=6, columnspan=2,
                                   sticky=tkinter.W)
                                   
        tkinter.Scale(self.root, label='Volume dB', orient=tkinter.HORIZONTAL,
                      from_=0, to=-30, variable=self.volume, resolution=10
                      ).grid(row=row, column=9, columnspan=2, rowspan=2)
        
        row += 1 #continue on next row
        
        self.__init_spinbox_tone_offset(row, column=0)
        self.__init_spinbox_revlimit_percent(row, column=3)
        self.__init_spinbox_revlimit_offset(row, column=6)
        
        
        # self.init_gui_variable('Revlimit %', self.revlimit_percent, row, 3)
       # self.init_gui_variable('Revlimit ms', self.revlimit_offset, row, 6)
        # tkinter.Label(self.root, text='Tone offset').grid(row=row, column=1,
        #                                                   columnspan=2)
        # tkinter.Entry(self.root, textvariable=self.tone_offset,
        #               width=6, justify=tkinter.RIGHT).grid(row=row, column=3)

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
        
        self.entry.config()
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
    #update curve if we collected a run in a higher gear
    #we can assume that this leads to a more accurate run with a better
    #rev limit defined
    def loop_runcollector(self, fdp):
        self.runcollector.update(fdp)

        if self.runcollector.run_completed():
            if self.curve is None:
            #    print("FIRST RUN DONE!")
                self.curve = self.runcollector.get_run()
                self.set_revlimit(self.curve[-1].current_engine_rpm)
                self.revlimit_entry.configure(
                                    readonlybackground=self.REVLIMIT_BG_CURVE)
            #    print(f'revlimit set: {self.revlimit.get()}')
            else:
                newrun = self.runcollector.get_run()
                if self.curve[0].gear < newrun[0].gear:
                #    print(f"NEW RUN DONE! len {len(newrun)} gear is higher")
                    self.curve = newrun
                    self.set_revlimit(self.curve[-1].current_engine_rpm)
                    for g in self.gears[1:]:
                        g.newrun_decrease_state()
                            #print(f"Gear {g.gear} reset to LOCKED")
              #      print(f'revlimit set: {self.revlimit.get()}')
                else:
                    pass
               #     print(f"NEW RUN DONE! len {len(newrun)} gear not higher: discarded")
            self.runcollector.reset()

    def loop_calculate_shiftrpms(self):
        if self.curve is not None:
            rpm = [p.current_engine_rpm for p in self.curve]
            power = [p.power for p in self.curve]

            #filter rpm and power
            #sort according to rpm?
            #filter power

            for g1, g2 in zip(self.gears[1:-1], self.gears[2:]):
                g1.calculate_shiftrpm(rpm, power, g2)
               #     print(f"gear {g1.gear} shiftrpm set: {shiftrpm}")

    #we assume power is negative between gear change and first frame of shift
    #accel has to be positive at all times, otherwise we don't know for sure
    #where the shift starts
    def loop_test_for_shiftrpm(self, fdp):
        if (len(self.shiftdelay_deque) == 0 or
                self.shiftdelay_deque[0].gear >= fdp.gear or
                self.shiftdelay_deque[0].gear == 0): #case gear reverse
            self.shiftdelay_deque.appendleft(fdp)
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
        if shiftrpm is not None:
            optimal = self.gears[fdp.gear-1].get_shiftrpm()
            if constants.log_full_shiftdata:
                print(f"gear {fdp.gear-1}-{fdp.gear}: {shiftrpm:.0f} actual shiftrpm, {optimal} optimal, {shiftrpm - optimal:4.0f} difference")
                print("-"*50)
            self.we_beeped = 0
            self.shiftdelay_deque.clear() #TODO: test if moving this out of the if works better

    def loop_beep(self, fdp, rpm):
        beep_rpm = self.gears[int(fdp.gear)].get_shiftrpm()
        if self.beep_counter <= 0:
            if self.test_for_beep(beep_rpm, self.get_revlimit(), fdp):
                self.beep_counter = constants.beep_counter_max
                self.we_beeped = constants.we_beep_max
                beep(filename=self.get_soundfile())
            elif rpm < math.ceil(beep_rpm*constants.beep_rpm_pct):
                self.beep_counter = 0
        elif self.beep_counter > 0 and rpm < beep_rpm:
            self.beep_counter -= 1

    def loop_func(self, fdp):
        self.loop_car_ordinal(fdp) #reset if car ordinal changes
        
        rpm = fdp.current_engine_rpm
        self.rpm.set(int(rpm))

        gear = int(fdp.gear)
        if gear < 1 or gear > 10:
            return
        if not fdp.is_race_on:
            return

        self.lookahead.add(fdp)

        self.loop_runcollector(fdp)

        self.loop_calculate_shiftrpms()

        if self.get_revlimit() == -1:
            self.set_revlimit(fdp.engine_max_rpm - self.REVLIMIT_GUESS)
            self.revlimit_entry.configure(
                                    readonlybackground=self.REVLIMIT_BG_GUESS)
            print(f'guess revlimit: {self.get_revlimit()}')

        self.loop_test_for_shiftrpm(fdp)

        if self.we_beeped > 0 and constants.log_full_shiftdata:
            print(f'rpm {rpm:.0f} torque {fdp.torque:.1f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f} count {constants.we_beep_max-self.we_beeped+1}')
            self.we_beeped -= 1
            
        self.gears[gear].derive_gearratio(fdp)

        self.loop_beep(fdp, rpm)

       # self.last_fdp = fdp

    #to account for torque not being flat, we take a linear approach
    #we take the ratio of the current torque and the torque at the shift rpm
    # if < 1: the overall acceleration will be lower than a naive guess
    #         therefore, scale the slope down: trigger will happen later
    # if > 1: the car will accelerate more. This is generally not happen unless
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
        tone_offset = self.get_tone_offset()

        from_gear, from_gear_ratio = self.torque_ratio_test(shiftrpm,
                                                            tone_offset, fdp)
        # from_gear = from_gear and fdp.accel >= self.MIN_THROTTLE_FOR_BEEP
        
        revlimit_pct, revlimit_pct_ratio = self.torque_ratio_test(
            revlimit*self.get_revlimit_percent(), tone_offset, fdp)
        revlimit_time, revlimit_time_ratio = self.torque_ratio_test(
            revlimit, (tone_offset + self.get_revlimit_offset()), fdp)

        # from_gear = self.lookahead.test(shiftrpm, tone_offset)
        # revlimit_pct = self.lookahead.test(revlimit*self.revlimit_percent.get()
        #                                    , tone_offset)
        # revlimit_time = self.lookahead.test(revlimit, (tone_offset +
        #                                            self.revlimit_offset.get()))

        if from_gear and constants.log_full_shiftdata:
            print(f'beep from_gear: {shiftrpm}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {from_gear_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        if revlimit_pct and constants.log_full_shiftdata:
            print(f'beep revlimit_pct: {revlimit*self.get_revlimit_percent()}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_pct_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        if revlimit_time and constants.log_full_shiftdata:
            print(f'beep revlimit_time: {revlimit}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_time_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        #print(f'fromgear {from_gear} revlimitpct {revlimit_pct} revlimit_time {revlimit_time} rpm {self.rpm.get()}')
        return from_gear or revlimit_pct or revlimit_time

#class that maintains a deque used for linear regression. This smooths the rpms
#and provides a slope to predict future RPM values.
class Lookahead():
    def __init__(self, minlen, maxlen):
        self.minlen = minlen
        self.deque = deque(maxlen=maxlen)
        self.clear_linreg_vars()

    def add(self, fdp):
        self.deque.append(fdp.current_engine_rpm)
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
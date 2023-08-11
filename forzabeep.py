# -*- coding: utf-8 -*-
"""
Created on Sun May  7 19:35:24 2023

@author: RTB
"""

#replaced tkinter with supposed thread safe tkinter variant
#instead of freezing when the main thread isn't under control of tkinter,
#it now crashes instead. Theoretically, an improvement.
from mttkinter import mtTkinter as tkinter
#import tkinter
#import tkinter.ttk

import math
import winsound
from collections import deque

#tell Windows we are DPI aware. We are not, but this gets around
#tkinter scaling inconsistently.
import ctypes
PROCESS_SYSTEM_DPI_AWARE = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)

from config import config, FILENAME_SETTINGS
#load configuration from config.json, class GUIConfigVariable depends on this
config.load_from(FILENAME_SETTINGS)

from gear import GUIGears, MAXGEARS
from curve import Curve
from lookahead import Lookahead
from ForzaUIBase import ForzaUIBase
from runcollector import RunCollector
from guiconfigvar import (GUIConfigVariable_RevlimitPercent,
                          GUIConfigVariable_RevlimitOffset,
                          GUIConfigVariable_ToneOffset,
                          GUIConfigVariable_Hysteresis, packets_to_ms)

class ForzaBeep(ForzaUIBase):
    TITLE = "ForzaShiftTone: Dynamic shift tone for Forza Horizon 5"
    WIDTH, HEIGHT = 745, 255

    MAXGEARS = 10
    
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

        self.gears = GUIGears()

        self.revlimit = -1

        self.runcollector = RunCollector()
        self.lookahead = Lookahead(config.linreg_len_min,
                                   config.linreg_len_max)

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

        self.edit_var = tkinter.IntVar(value=0)
        tkinter.Checkbutton(frame, text='Edit', variable=self.edit_var,
                            command=self.edit_handler).grid(row=0, column=3,
                                                            sticky=tkinter.W)
        self.edit_handler()

    def __init__window(self):
        self.gears.init_window(self.root)

        row = GUIGears.ROW_COUNT #start from row below gear display

        self.revlimit_var = tkinter.StringVar(value=self.DEFAULT_GUI_VALUE)
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

        self.volume = tkinter.IntVar(value=config.volume)
        tkinter.Scale(self.root, orient=tkinter.VERTICAL, showvalue=0,
                      from_=0, to=-30, variable=self.volume, resolution=10
                      ).grid(row=row, column=10, columnspan=1, rowspan=3,
                             sticky=tkinter.E)

        row += 1 #continue on next row

        tkinter.Label(self.root, text='Volume').grid(row=row, column=9,
                                                     columnspan=2)

        row += 1 #continue on next row

        self.rpm = tkinter.IntVar(value=0)
        tkinter.Label(self.root, text='Tach').grid(row=row, column=0,
                                                  sticky=tkinter.E)
        tkinter.Entry(self.root, textvariable=self.rpm, width=6,
                      justify=tkinter.RIGHT, state='readonly'
                      ).grid(row=row, column=1, sticky=tkinter.W)
        tkinter.Label(self.root, text='RPM').grid(row=row, column=2,
                                                  sticky=tkinter.W)

        #defined in ForzaUIBase, controls whether the loop runs
        if self.active.get():     #trigger loop if active by default
            self.active_handler() #comparable to tkinter mainloop func
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

        self.gears.reset()

    def get_soundfile(self):
        return config.sound_files[self.volume.get()]

    def get_revlimit(self):
        return self.revlimit

    def set_revlimit(self, val):
        self.revlimit = int(val)
        self.revlimit_var.set(self.revlimit)

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

        newrun_better = ( self.curve is not None and
                self.runcollector.get_revlimit_if_done() > self.get_revlimit()
                and self.runcollector.get_gear() >= self.curve.get_gear() )

        if self.curve is None or newrun_better:
            self.curve = Curve(self.runcollector.get_run())
            self.set_revlimit(self.curve.get_revlimit())

        if self.curve is None: #let user know we have a curve
            self.revlimit_entry.configure(
                                readonlybackground=self.REVLIMIT_BG_CURVE)
        elif newrun_better: #force recalculation of rpm if possible
            self.gears.newrun_decrease_state()
        self.runcollector.reset()

    def loop_calculate_shiftrpms(self):
        if self.curve is None:
            return
        self.gears.calculate_shiftrpms(self.curve.rpm, self.curve.power)

    #we assume power is negative between gear change and first frame of shift
    #accel has to be positive at all times, otherwise we don't know for sure
    #where the shift starts
    #tone_offset.counter runs until a shift upwards happens
    #if so, we run backwards until the packet where power is negative and
    #the previous packet's power  is positive: the actual point of shifting
    def loop_test_for_shiftrpm(self, fdp):
        if (len(self.shiftdelay_deque) == 0 or 
            self.shiftdelay_deque[0].gear == fdp.gear):
            self.shiftdelay_deque.appendleft(fdp)
            self.tone_offset.increment_counter()
            return
        if self.shiftdelay_deque[0].gear > fdp.gear: #reset on downshift
            self.shiftdelay_deque.clear()
            self.tone_offset.reset_counter()
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
            optimal = self.gears.get_shiftrpm_of(fdp.gear-1)
            beep_distance = self.tone_offset.get_counter()
            self.tone_offset.finish_counter() #update dynamic offset logic
            beep_distance_ms = 'N/A'
            if beep_distance is not None:
                beep_distance_ms = packets_to_ms(beep_distance)
            if config.log_basic_shiftdata:
                print(f"gear {fdp.gear-1}-{fdp.gear}: {shiftrpm:.0f} actual shiftrpm, {optimal} optimal, {shiftrpm - optimal:4.0f} difference, {beep_distance_ms} ms distance to beep")
                print("-"*50)
        self.we_beeped = 0
        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter()

    def loop_beep(self, fdp, rpm):
        beep_rpm = self.gears.get_shiftrpm_of(fdp.gear)
        if self.beep_counter <= 0:
            if self.test_for_beep(beep_rpm, self.get_revlimit(), fdp):
                self.beep_counter = config.beep_counter_max
                self.we_beeped = config.we_beep_max
                self.tone_offset.start_counter()
                beep(filename=self.get_soundfile())
            elif rpm < math.ceil(beep_rpm*config.beep_rpm_pct):
                self.beep_counter = 0
        elif (self.beep_counter > 0 and (rpm < beep_rpm or beep_rpm == -1)):
            self.beep_counter -= 1

    def loop_guess_revlimit(self, fdp):
        if self.get_revlimit() == -1:
            self.set_revlimit(fdp.engine_max_rpm - config.revlimit_guess)
            self.revlimit_entry.configure(
                                    readonlybackground=self.REVLIMIT_BG_GUESS)
            print(f'guess revlimit: {self.get_revlimit()}')

    def loop_func(self, fdp):
        if not fdp.is_race_on:
            return

        gear = int(fdp.gear)
        if gear < 1 or gear > MAXGEARS:
            return

        rpm = fdp.current_engine_rpm
        self.rpm.set(int(rpm))

        self.loop_car_ordinal(fdp) #reset if car ordinal changes
        self.loop_guess_revlimit(fdp) #guess revlimit if not defined yet
        self.loop_hysteresis(fdp) #update self.hysteresis_rpm
        self.lookahead.add(self.hysteresis_rpm) #update linear regresion
        self.loop_runcollector(fdp) #add data point for curve collecting
        self.gears.update_of(gear, fdp) #update gear ratio and state of gear
        self.loop_calculate_shiftrpms() #derive shift
        self.loop_test_for_shiftrpm(fdp) #test if we have shifted
        self.loop_beep(fdp, rpm) #test if we need to beep

        if self.we_beeped > 0 and config.log_full_shiftdata:
            print(f'rpm {rpm:.0f} torque {fdp.torque:.1f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f} count {config.we_beep_max-self.we_beeped+1}')
            self.we_beeped -= 1

    #to account for torque not being flat, we take a linear approach
    #we take the ratio of the current torque and the torque at the shift rpm
    # if < 1: the overall acceleration will be lower than a naive guess
    #         therefore, scale the slope down: trigger will happen later
    # if > 1: the car will accelerate more. This generally cannot happen unless
    # there is partial throttle.
    def torque_ratio_test(self, target_rpm, offset, fdp):
        torque_ratio = 1
        if self.curve is not None and fdp.torque != 0:
            target_torque = self.curve.torque_at_rpm(target_rpm)
            torque_ratio = target_torque / fdp.torque

        return (self.lookahead.test(target_rpm, offset, torque_ratio),
                torque_ratio)

    def test_for_beep(self, shiftrpm, revlimit, fdp):
        if fdp.accel < config.min_throttle_for_beep:
            return False
        tone_offset = self.tone_offset.get()

        from_gear, from_gear_ratio = self.torque_ratio_test(shiftrpm,
                                                            tone_offset, fdp)
        # from_gear = from_gear and fdp.accel >= constants.min_throttle_for_beep

        revlimit_pct, revlimit_pct_ratio = self.torque_ratio_test(
            revlimit*self.revlimit_percent.get(), tone_offset, fdp)
        revlimit_time, revlimit_time_ratio = self.torque_ratio_test(
            revlimit, (tone_offset + self.revlimit_offset.get()), fdp)

        if from_gear and config.log_full_shiftdata:
            print(f'beep from_gear: {shiftrpm}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {from_gear_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_pct and config.log_full_shiftdata:
            print(f'beep revlimit_pct: {revlimit*self.revlimit_percent.get()}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_pct_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_time and config.log_full_shiftdata:
            print(f'beep revlimit_time: {revlimit}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_time_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        return from_gear or revlimit_pct or revlimit_time

    def close(self):
        #write all GUI configurable settings to the config file
        gui_vars = ['revlimit_percent', 'revlimit_offset', 'tone_offset',
                    "hysteresis", 'volume']
        for variable in gui_vars:
            setattr(config, variable, getattr(self, variable).get())
        config.write_to(FILENAME_SETTINGS)
        super().close()



def beep(filename=config.sound_file):
    try:
        winsound.PlaySound(filename,
                           winsound.SND_FILENAME | winsound.SND_ASYNC |
                           winsound.SND_NODEFAULT)
    except:
        print("Sound failed to play")

def main():
    global forzabeep #for debugging
    forzabeep = ForzaBeep()

if __name__ == "__main__":
    main()
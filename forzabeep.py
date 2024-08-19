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
from collections import deque

#tell Windows we are DPI aware
import ctypes
PROCESS_SYSTEM_DPI_AWARE = 1
PROCESS_PER_MONITOR_DPI_AWARE = 2
ctypes.windll.shcore.SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)

from config import config, FILENAME_SETTINGS
config.load_from(FILENAME_SETTINGS)

from gear import Gears, GUIGears, MAXGEARS
from curve import Curve
from lookahead import Lookahead
from forzaUDPloop import ForzaUDPLoop
from runcollector import RunCollector
from utility import beep, multi_beep, packets_to_ms, Variable
from buttongraph import GUIButtonGraph
from guiconfigvar import (GUIRevlimitPercent, GUIRevlimitOffset, GUIToneOffset,
                          GUIHysteresisPercent, GUIRevlimit, GUIVolume, 
                          GUIPeakPower, GUITach, GUIButtonStartStop, 
                          GUIButtonVarEdit)
        
#main class for ForzaShiftTone
#it is responsible for creating and managing the tkinter window
#and maintains the loop logic
#splitting these two has resulted in the window not responding for several
#seconds after launching, despite the back-end still updating
class ForzaBeep():
    TITLE = "ForzaShiftTone: Dynamic shift tone for the Forza series"
    WIDTH, HEIGHT = 750, 252
    
    def __init__(self):
        self.loop = ForzaUDPLoop(ip=config.ip, port=config.port, 
                                 packet_format=None,
                                 loop_func=self.loop_func)
        self.init_tkinter()
        self.init_vars()
        self.init_gui_vars()
        self.init_gui_grid()
        
        self.buttonstartstop.invoke() #trigger start of loop
        self.root.mainloop()

    def init_tkinter(self):
        self.root = tkinter.Tk()
        self.root.title(self.TITLE)
        
        #100% scaling is ~96 dpi in Windows, tkinter assumes ~72 dpi
        #window_scalar allows the user to scale the window up or down
        #the UI was designed at 150% scaling or ~144 dpi
        #we have to fudge width a bit if scaling is 100%
        screen_dpi = self.root.winfo_fpixels('1i')
        dpi_factor = (96/72) * (screen_dpi / 96) * config.window_scalar
        size_factor = screen_dpi / 144 * config.window_scalar
        width = math.ceil(self.WIDTH * size_factor)
        height = math.ceil(self.HEIGHT * size_factor)
        if screen_dpi <= 96.0:
            width += 40 #hack for 100% size scaling in Windows
        
        # self.root.geometry(f"{width}x{height}") #not required
        self.root.protocol('WM_DELETE_WINDOW', self.close)
        self.root.resizable(False, False)
        self.root.tk.call('tk', 'scaling', dpi_factor)
        # self.root.attributes('-toolwindow', True) #force on top

    def init_vars(self):
        self.gears = Gears()
        self.runcollector = RunCollector(config=config)
        self.lookahead = Lookahead(config.linreg_len_min,
                                   config.linreg_len_max)
        self.we_beeped = 0
        self.beep_counter = 0
        self.debug_target_rpm = -1
        self.revlimit = Variable(defaultvalue=-1)
        self.rpm_hysteresis = 0
        
        self.curve = None

        self.shiftdelay_deque = deque(maxlen=120)

        self.car_ordinal = None
        self.car_performance_index = None
        
        self.print_packet_format = True

    def init_gui_vars(self):
        root = self.root
        self.gears = GUIGears(root)
        self.revlimit = GUIRevlimit(root, defaultvalue=-1)
        self.volume = GUIVolume(root, value=config.volume)
        self.peakpower = GUIPeakPower(root)
        self.tach = GUITach(root)
        self.buttonreset = tkinter.Button(root, text='Reset', borderwidth=3, 
                                          command=self.reset)
        self.buttonstartstop = GUIButtonStartStop(root, self.startstop_handler)
        self.buttongraph = GUIButtonGraph(root, self.buttongraph_handler, 
                                          config)
        
        frame = tkinter.LabelFrame(root, text='Variables')
        self.varframe = frame
        
        self.tone_offset = GUIToneOffset(frame, config)
        self.hysteresis_percent = GUIHysteresisPercent(frame, config)
        self.revlimit_percent = GUIRevlimitPercent(frame, config)
        self.revlimit_offset = GUIRevlimitOffset(frame, config)
        self.buttonvaredit = GUIButtonVarEdit(frame, self.edit_handler)
        self.buttonvaredit.invoke() #trigger disabling of var boxes
        
    def init_gui_grid(self):
        # for r in range(5):
        #     self.root.rowconfigure(index=r, weight=1)
        self.gears.init_grid()
        row = GUIGears.ROW_COUNT #start from row below gear display
        
        #force minimum row size for other rows
        self.root.rowconfigure(index=row+3, weight=1000)
       
        self.revlimit.grid(       row=row,   column=0)    
        self.varframe.grid(       row=row,   column=5, rowspan=4, columnspan=4, 
                                                            sticky=tkinter.EW)  
        self.volume.grid(         row=row,   column=9)        
        
        self.peakpower.grid(      row=row+1, column=0)   
        
        self.buttonreset.grid(    row=row+2, column=3)
        self.buttonstartstop.grid(row=row+2, column=4)
        self.buttongraph.grid(    row=row+2, column=9, rowspan=2, columnspan=2,
                                                          sticky=tkinter.SW)
        
        self.tach.grid(           row=row+3, column=0)
        
        #these variables are gridded into varframe
        self.tone_offset.grid(       row=0, column=0)
        self.hysteresis_percent.grid(row=1, column=0)
        self.revlimit_percent.grid(  row=2, column=0)
        self.revlimit_offset.grid(   row=3, column=0)
        self.buttonvaredit.grid(     row=0, column=3)
        
    def startstop_handler(self, event=None):
        self.buttonstartstop.toggle(self.loop.is_running())
        self.loop.toggle(True)

    def buttongraph_handler(self, event=None):
        self.buttongraph.create_window(self.curve, self.revlimit_percent.get())

    #enable or disable modification of the four listed variable spinboxes
    def edit_handler(self):
        state = 'readonly' if self.buttonvaredit.get() else tkinter.DISABLED
        for var in [self.revlimit_offset, self.revlimit_percent,
                    self.tone_offset, self.hysteresis_percent]:
            var.config(state=state)
                
    def reset(self, *args):
        self.runcollector.reset()
        self.lookahead.reset()

        self.we_beeped = 0
        self.beep_counter = 0
        self.debug_target_rpm = -1
        self.curve = None
        
        self.car_ordinal = None
        self.car_performance_index = None

        self.tach.reset()
        self.revlimit.reset()
        self.peakpower.reset()
        self.buttongraph.reset()

        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter()
        self.rpm_hysteresis = 0

        self.gears.reset()

    #reset if the car_ordinal or the PI changes
    def loop_test_car_changed(self, fdp):
        if fdp.car_ordinal == 0:
            return
        if (self.car_ordinal != fdp.car_ordinal or
            self.car_performance_index != fdp.car_performance_index):
            self.reset()
            self.car_ordinal = fdp.car_ordinal
            self.car_performance_index = fdp.car_performance_index
            print(f'New ordinal {self.car_ordinal}, PI {fdp.car_performance_index}: resetting!')
            print(f'Hysteresis: {self.hysteresis_percent.as_rpm(fdp):.1f} rpm')
            print(f'Engine: {fdp.engine_idle_rpm:.0f} min rpm, {fdp.engine_max_rpm:.0f} max rpm')

    def loop_update_rpm(self, fdp):
        rpm = fdp.current_engine_rpm
        
        hysteresis = self.hysteresis_percent.as_rpm(fdp)
        if abs(rpm - self.rpm_hysteresis) >= hysteresis:
            self.rpm_hysteresis = rpm

        self.tach.update(rpm)

    def loop_guess_revlimit(self, fdp):
        if config.revlimit_guess != -1 and self.revlimit.get() == -1:
            self.revlimit.set(fdp.engine_max_rpm - config.revlimit_guess, 
                              state='guess')
            print(f'guess revlimit: {self.revlimit.get()}')    

    def loop_linreg(self, fdp):
        self.lookahead.add(self.rpm_hysteresis) #update linear regresion

    def loop_runcollector_setcurve(self):
        self.curve = Curve(self.runcollector.get_run())
        self.revlimit.set(self.curve.get_revlimit())
        self.peakpower.set(*self.curve.get_peakpower_tuple())
        self.buttongraph.enable()
        
        if config.notification_power_enabled:
            multi_beep(config.notification_file,
                       config.notification_file_duration,
                       config.notification_power_count,
                       config.notification_power_delay)
            
    #grab curve if we collected a complete run
    #update curve if we collected a run in an equal or higher gear
    #test if this leads to a more accurate run with a better rev limit defined
    #we stop testing if the run is long enough using the variable in config:
    #runcollector_minlen_lock
    def loop_runcollector(self, fdp):
        self.runcollector.update(fdp)

        if not self.runcollector.is_run_completed():
            return

        newrun_better = (self.curve is not None and
                         self.runcollector.is_newrun_better(self.curve))

        if self.curve is None or newrun_better:
            self.loop_runcollector_setcurve()

        if newrun_better: #force recalculation of rpm if possible
            self.gears.newrun_decrease_state()
            
        if self.runcollector.is_run_final():
            self.runcollector.set_run_final()
        else:
            self.runcollector.reset()

    def loop_update_gear(self, fdp):
        if fdp.clutch > 0:
            return
        if self.gears.update(fdp) and config.notification_gear_enabled:
            multi_beep(config.notification_file,
                       config.notification_file_duration,
                       config.notification_gear_count,
                       config.notification_gear_delay)

    def loop_calculate_shiftrpms(self):
        if self.curve is None:
            return
        self.gears.calculate_shiftrpms(self.curve.rpm, self.curve.power)

    def debug_log_basic_shiftdata(self, shiftrpm, gear, beep_distance):
        target = self.debug_target_rpm
        difference = 'N/A' if target == -1 else f'{shiftrpm - target:4.0f}'
        beep_distance_ms = 'N/A'
        if beep_distance is not None:
            beep_distance_ms = packets_to_ms(beep_distance)
        print(f"gear {gear-1}-{gear}: {shiftrpm:.0f} actual shiftrpm, {target:.0f} target, {difference} difference, {beep_distance_ms} ms distance to beep")
        print("-"*50)

    #we assume power is negative between gear change and first frame of shift
    #accel has to be positive at all times, otherwise we don't know for sure
    #where the shift starts
    #tone_offset.counter runs until a shift upwards happens
    #if so, we run backwards until the packet where power is negative and
    #the previous packet's power is positive: the actual point of shifting
    def loop_test_for_shiftrpm(self, fdp):
        #case gear is the same in new fdp or we start from zero
        if (len(self.shiftdelay_deque) == 0 or 
            self.shiftdelay_deque[0].gear == fdp.gear):
            self.shiftdelay_deque.appendleft(fdp)
            self.tone_offset.increment_counter()
            return
        #case gear has gone down: reset
        if self.shiftdelay_deque[0].gear > fdp.gear:
            self.shiftdelay_deque.clear()
            self.tone_offset.reset_counter()
            self.debug_target_rpm = -1 #reset target rpm
            return
        #case gear has gone up
        prev_packet = fdp
        shiftrpm = None
        for packet in self.shiftdelay_deque:
            if packet.accel == 0:
                break
            if prev_packet.power < 0 and packet.power >= 0:
                shiftrpm = packet.current_engine_rpm
                break
            prev_packet = packet
            self.tone_offset.decrement_counter()
        if shiftrpm is not None:
            counter = self.tone_offset.get_counter()
            self.tone_offset.finish_counter() #update dynamic offset logic
            if config.log_basic_shiftdata:
                self.debug_log_basic_shiftdata(shiftrpm, fdp.gear, counter)
        self.we_beeped = 0
        self.debug_target_rpm = -1
        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter()

    #play beep depending on volume. If volume is zero, skip beep
    def do_beep(self):
        if volume_level := self.volume.get():
            beep(filename=config.sound_files[volume_level])

    def loop_beep(self, fdp):
        rpm = fdp.current_engine_rpm
        beep_rpm = self.gears.get_shiftrpm_of(fdp.gear)
        if self.beep_counter <= 0:
            if self.test_for_beep(beep_rpm, fdp):
                self.beep_counter = config.beep_counter_max
                self.we_beeped = config.we_beep_max
                self.tone_offset.start_counter()
                self.do_beep()
            elif rpm < math.ceil(beep_rpm*config.beep_rpm_pct):
                self.beep_counter = 0
        elif (self.beep_counter > 0 and (rpm < beep_rpm or beep_rpm == -1)):
            self.beep_counter -= 1

    def debug_log_full_shiftdata(self, fdp):
        if self.we_beeped > 0 and config.log_full_shiftdata:
            print(f'rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f} count {config.we_beep_max-self.we_beeped+1}')
            self.we_beeped -= 1

    def loop_func(self, fdp):
        if self.print_packet_format:
            print(f"Format: {fdp.packet_format}")
            self.print_packet_format = False
        
        print(f'rpm {fdp.current_engine_rpm} gear {fdp.gear}')
        #skip if not racing or gear number outside valid range
        if not(fdp.is_race_on and (1 <= int(fdp.gear) <= MAXGEARS)):
            return

        self.loop_test_car_changed(fdp) #reset if car ordinal/PI changes
        self.loop_update_rpm(fdp) #update tach and hysteresis rpm
        self.loop_guess_revlimit(fdp) #guess revlimit if not defined yet
        self.loop_linreg(fdp) #update lookahead with hysteresis rpm
        self.loop_runcollector(fdp) #add data point for curve collecting
        self.loop_update_gear(fdp) #update gear ratio and state of gear
        self.loop_calculate_shiftrpms() #derive shift rpm if possible
        self.loop_test_for_shiftrpm(fdp) #test if we have shifted
        self.loop_beep(fdp) #test if we need to beep

        self.debug_log_full_shiftdata(fdp)

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

    #make sure the target_rpm is the lowest rpm trigger of all triggered beeps
    def update_target_rpm(self, val):
        if self.debug_target_rpm == -1:
            self.debug_target_rpm = val
        else:
            self.debug_target_rpm = min(self.debug_target_rpm, val)

    def test_for_beep(self, shiftrpm, fdp):
        #enforce minimum throttle for beep to occur
        if fdp.accel < config.min_throttle_for_beep:
            return False
        tone_offset = self.tone_offset.get()
        revlimit = self.revlimit.get()

        from_gear, from_gear_ratio = self.torque_ratio_test(shiftrpm,
                                                            tone_offset, fdp)
        #from_gear = from_gear and fdp.accel >= constants.min_throttle_for_beep

        revlimit_pct, revlimit_pct_ratio = self.torque_ratio_test(
            revlimit*self.revlimit_percent.get(), tone_offset, fdp)
        revlimit_time, revlimit_time_ratio = self.torque_ratio_test(
            revlimit, (tone_offset + self.revlimit_offset.get()), fdp)

        if from_gear:
            self.update_target_rpm(shiftrpm)
        if revlimit_pct:
            factor = self.revlimit_percent.get()
            self.update_target_rpm(revlimit*factor)
        if revlimit_time:
            slope, intercept = self.lookahead.slope, self.lookahead.intercept
            self.update_target_rpm(intercept + slope*tone_offset)
        
        if from_gear and config.log_full_shiftdata:
            print(f'beep from_gear: {shiftrpm}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {from_gear_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_pct and config.log_full_shiftdata:
            print(f'beep revlimit_pct: {revlimit*self.revlimit_percent.get()}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_pct_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_time and config.log_full_shiftdata:
            print(f'beep revlimit_time: {revlimit}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque {fdp.torque:.1f} trq_ratio {revlimit_time_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        return from_gear or revlimit_pct or revlimit_time

    #write all GUI configurable settings to the config file
    def config_writeback(self):
        try:
            gui_vars = ['revlimit_percent', 'revlimit_offset', 'tone_offset',
                        'hysteresis_percent', 'volume']
            for variable in gui_vars:
                setattr(config, variable, getattr(self, variable).get())
            config.write_to(FILENAME_SETTINGS)
        except:
            print("Failed to write GUI variables to config file")

    def close(self):
        self.loop.close()
        self.config_writeback()
        self.root.destroy()

def main():
    global forzabeep #for debugging
    forzabeep = ForzaBeep()

if __name__ == "__main__":
    main()
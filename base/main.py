# -*- coding: utf-8 -*-
"""
Created on Sun Aug 18 10:45:28 2024

@author: RTB
"""

import math

from collections import deque

from config import config, FILENAME_SETTINGS
config.load_from(FILENAME_SETTINGS)

from base.forzaudploop import ForzaUDPLoop
from base.rpm import RPM
from base.history import History
from base.carordinal import CarOrdinal
from base.gear import Gears, MAXGEARS
from base.enginecurve import EngineCurve
from base.shiftdump import ShiftDump
from base.configvar import (HysteresisPercent, DynamicToneOffsetToggle, Volume,
                            RevlimitPercent, RevlimitOffset, ToneOffset, 
                            IncludeReplay)
from base.lookahead import Lookahead
from base.runcollector import RunCollector

from utility import beep, multi_beep, Variable


#TODO:
    #Include button to delete curve: it may not be a good one
    
    #Include reset if PI changes  
    
#NOTES:


#main class for ForzaShiftTone
#it is responsible for the main loop
class ForzaBeep():
    def __init__(self):
        self.init_vars()     
        self.loop.firststart() #trigger start of loop

    #variables are defined again in init_gui_vars, purpose is to split baseline
    #and gui eventually
    def init_vars(self):
        self.loop = ForzaUDPLoop(config, loop_func=self.loop_func)
        self.gears = Gears(config)
        self.datacollector = RunCollector(config)
        self.lookahead = Lookahead(config)
        self.history = History(config)
        
        self.car_ordinal = CarOrdinal()
        
        self.tone_offset = ToneOffset(config)
        self.hysteresis_percent = HysteresisPercent(config)
        self.revlimit_percent = RevlimitPercent(config)
        self.revlimit_offset = RevlimitOffset(config)
        self.dynamictoneoffset = DynamicToneOffsetToggle(config)
        self.includereplay = IncludeReplay(config)
        
        # self.shiftdump = ShiftDump(self.lookahead)
        
        self.rpm = RPM(hysteresis_percent=self.hysteresis_percent)
        self.volume = Volume(config)
        
        self.we_beeped = 0
        self.beep_counter = 0
        self.debug_target_rpm = -1
        self.revlimit = Variable(defaultvalue=-1)
        
        self.curve = EngineCurve(config)

        self.shiftdelay_deque = deque(maxlen=120)

    def reset(self, *args):
        self.rpm.reset()
        self.history.reset()
        self.car_ordinal.reset()
        self.gears.reset()
        self.lookahead.reset()
        self.datacollector.reset()
        self.revlimit.reset()
        self.curve.reset()
        
        self.we_beeped = 0
        self.beep_counter = 0
        self.debug_target_rpm = -1

        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter() #should this be reset_to_current_value?
    
    #called when car ordinal changes or data collector finishes a run
    def handle_curve_change(self, fdp, *args, **kwargs):
        print("Handle_curve_change")
        self.curve.update(fdp, *args, **kwargs)
                
        if not self.curve.is_loaded():
            return
        
        print("Setting data because curve is loaded")
        self.revlimit.set(self.curve.get_revlimit())        
        self.gears.calculate_shiftrpms(*self.curve.get_rpmpower())
        
        if config.notification_power_enabled:
            multi_beep(config.notification_file,
                       config.notification_file_duration,
                       config.notification_power_count,
                       config.notification_power_delay)

    #reset if the car_ordinal changes
    #if a car has more than 8 gears, the packet won't contain the ordinal as
    #the 9th gear will overflow into the car ordinal location
    def loop_test_car_changed(self, fdp):
        ordinal = fdp.car_ordinal
        if ordinal <= 0 or ordinal > 1e5:
            return
        
        if self.car_ordinal.test(ordinal):
            self.reset()
            self.car_ordinal.set(ordinal)
            print(f'New ordinal {self.car_ordinal.get()}, PI {fdp.car_performance_index}, resetting!')
            print(f'New car: {self.car_ordinal.get_name()}')
            print(f'Hysteresis: {self.hysteresis_percent.as_rpm(fdp):.1f} rpm')
            print(f'Engine: {fdp.engine_idle_rpm:.0f} min rpm, {fdp.engine_max_rpm:.0f} max rpm')
            
            self.handle_curve_change(fdp)

    #update internal rpm taking the hysteresis value into account:
    #only update if the difference between previous and current rpm is large
    def loop_update_rpm(self, fdp):
        self.rpm.update(fdp)

    #Not currently used
    def loop_guess_revlimit(self, fdp):
        if config.revlimit_guess != -1 and self.revlimit.get() == -1:
            self.revlimit.set(fdp.engine_max_rpm - config.revlimit_guess, 
                              state='guess')
            print(f'guess revlimit: {self.revlimit.get()}')    

    def loop_linreg(self, fdp):
        self.lookahead.add(self.rpm.get()) #update linear regresion

    #set curve with drag data if we collected a complete run
    def loop_datacollector(self, fdp):
        if self.curve.is_loaded():
            return
        
        self.datacollector.update(fdp)

        if not self.datacollector.is_run_completed():
            return

        #state: No curve loaded and datacollector run is completed
        print("shipping data to EngineCurve")
        self.handle_curve_change(fdp, **self.datacollector.get_data())

    def loop_update_gear(self, fdp):
        if fdp.clutch > 0:
            return
        if self.gears.update(fdp) and config.notification_gear_enabled:
            multi_beep(config.notification_file,
                       config.notification_file_duration,
                       config.notification_gear_count,
                       config.notification_gear_delay)

    #update call with get_rpmpower
    def loop_calculate_shiftrpms(self, _):
        if self.curve.is_loaded():
            self.gears.calculate_shiftrpms(*self.curve.get_rpmpower())

    #Function to derive the rpm the player started an upshift at full throttle
    #FM disengages the clutch in 1 frame according to telemetry
    #Ingame telemetry will correctly show the clutch, we do not have that info
    #We have engine braking as negative power for x frames
    #Transmission then goes into neutral, then into the next gear
    #Then power is still negative but the internal throttle is then ramped up
    #until we are back at full power. Also invisible in Data Out.
    #TODO: With a power curve we can derive a full shift duration
    def loop_test_for_shiftrpm(self, fdp):
        #case gear is the same in new fdp or we start from zero
        if (len(self.shiftdelay_deque) == 0 or 
            (prevgear := self.shiftdelay_deque[0].gear) == fdp.gear or
            (prevgear != 11 and fdp.gear == 11)):
            self.shiftdelay_deque.appendleft(fdp)
            self.tone_offset.increment_counter()
            return
        # #case gear has gone down: reset
        # if prevgear != 11 and prevgear > fdp.gear:
        #     self.shiftdelay_deque.clear()
        #     self.tone_offset.reset_counter()
        #     self.debug_target_rpm = -1 #reset target rpm
        #     return
        #case gear has gone up or down after a shift
        # prev_packet = fdp
        shiftrpm = None
        for packet in self.shiftdelay_deque:
            if packet.accel != 255:
                break
            if packet.gear == 11:
                self.tone_offset.decrement_counter()
                continue
            if packet.gear + 1 != fdp.gear: #reset if downshift
                break
            if packet.power < 0:
                self.tone_offset.decrement_counter()
                continue
            shiftrpm = packet.current_engine_rpm
            break

            self.tone_offset.decrement_counter()
            
        if shiftrpm is not None: #fdp.gear is the upshifted gear, one too high
            self.history.update(self.debug_target_rpm, shiftrpm, fdp.gear-1, 
                                self.tone_offset.get_counter())
            if self.dynamictoneoffset.get():
                self.tone_offset.finish_counter() #update dynamic offset logic
        self.we_beeped = 0
        self.debug_target_rpm = -1
        self.shiftdelay_deque.clear()
        self.tone_offset.reset_counter()

    #play beep depending on volume. If volume is zero, skip beep
    def do_beep(self):
        if volume_level := self.volume.get():
            beep(filename=config.sound_files[volume_level])

    def loop_beep(self, fdp):
        if fdp.gear > MAXGEARS:
            return
        if self.gears.is_highest(fdp.gear):
            return #No beep including revlimit in highest gear
        rpm = fdp.current_engine_rpm
        beep_rpm = self.gears.get_shiftrpm_of(fdp.gear)
        # print(f"beep_rpm {beep_rpm}")
        if self.beep_counter <= 0:
            # print("beep counter <= 0")
            if self.test_for_beep(beep_rpm, fdp):
                self.beep_counter = config.beep_counter_max
                self.we_beeped = config.we_beep_max
                self.tone_offset.start_counter()
                # print(f'Beep at {fdp.current_engine_rpm:.0f} rpm')
                self.do_beep()
            elif rpm < math.ceil(beep_rpm*config.beep_rpm_pct):
                self.beep_counter = 0 #consider -= beep_duration
        elif (self.beep_counter > 0 and (rpm < beep_rpm or beep_rpm == -1)):
            self.beep_counter -= 1

    def debug_log_full_shiftdata(self, fdp):
        if self.we_beeped > 0 and config.log_full_shiftdata:
            print(f'rpm {fdp.current_engine_rpm:.0f} in_gear {fdp.in_gear} throttle {fdp.accel} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f} count {config.we_beep_max-self.we_beeped+1}')
            self.we_beeped -= 1

    def loop_shiftdump(self, fdp):
        self.shiftdump.update(fdp)

    #this function is called by the loop whenever a new packet arrives
    def loop_func(self, fdp):        
        #skip if not racing or gear number outside valid range
        if not(self.includereplay.test(fdp) and self.gears.is_valid(fdp)):
            return

        funcs = [
             'loop_test_car_changed', #reset if car ordinal/PI changes
             'loop_update_rpm',       #update tach and hysteresis rpm
             'loop_guess_revlimit',   #guess revlimit if not defined yet
             'loop_linreg',           #update lookahead with hysteresis rpm
             'loop_datacollector',    #add data point for curve collecting
             'loop_update_gear',      #update gear ratio and state of gear
             'loop_calculate_shiftrpms',#derive shift rpm if possible
             'loop_test_for_shiftrpm',#test if we have shifted
             'loop_beep',             #test if we need to beep
             # 'loop_shiftdump',        #dump a table when a shift happens
             'debug_log_full_shiftdata'             
                ]
        for funcname in funcs:
            try:
                getattr(self, funcname)(fdp)
            except BaseException as e:
                print(f'{funcname} {e}')

    #TODO: Move the torque ratio function to PowerCurve
    #to account for torque not being flat, we take a linear approach
    #we take the ratio of the current torque and the torque at the shift rpm
    # if < 1: the overall acceleration will be lower than a naive guess
    #         therefore, scale the slope down: trigger will happen later
    # if > 1: the car will accelerate more. This generally cannot happen unless
    # there is partial throttle.
    # Returns a boolean if target_rpm is predicted to be hit in 'offset' number
    # of packets (assumed at 60hz) and the above factor for debug printing
    def torque_ratio_test(self, target_rpm, offset, fdp):
        torque_ratio = 1
        if self.curve.is_loaded():
            fdp_torque = self.curve.torque_at_rpm(fdp.current_engine_rpm)
            if fdp_torque == 0:
                return
            target_torque = self.curve.torque_at_rpm(target_rpm)
            torque_ratio = target_torque / fdp_torque

        return (self.lookahead.test(target_rpm, offset, torque_ratio),
                torque_ratio)

    #make sure the target_rpm is the lowest rpm trigger of all triggered beeps
    #used for debug logging
    def update_target_rpm(self, val):
        if self.debug_target_rpm == -1:
            self.debug_target_rpm = val
        else:
            self.debug_target_rpm = min(self.debug_target_rpm, val)

    #test for the three beep triggers:
        #if shiftrpm of gear will be hit in x time (from_gear)
        #if revlimit will be hit in x+y time
        #if percentage of revlimit will be hit in x time
    def test_for_beep(self, shiftrpm, fdp):
        #enforce minimum throttle for beep to occur
        if fdp.accel < config.min_throttle_for_beep:
            return False
        tone_offset = self.tone_offset.get()
        revlimit = self.revlimit.get()

        from_gear, from_gear_ratio = self.torque_ratio_test(shiftrpm,
                                                            tone_offset, fdp)
        # print(f"from gear {from_gear} {from_gear_ratio}")
        #possible idea: Always enable revlimit beep regardless of throttle
        #This may help shifting while getting on the power gradually
        #from_gear = from_gear and fdp.accel >= constants.min_throttle_for_beep

        revlimit_pct, revlimit_pct_ratio = self.torque_ratio_test(
            revlimit*self.revlimit_percent.get(), tone_offset, fdp)
        revlimit_time, revlimit_time_ratio = self.torque_ratio_test(
            revlimit, (tone_offset + self.revlimit_offset.get()), fdp)

        if from_gear:
            self.update_target_rpm(shiftrpm)            
        if revlimit_pct:
            rpm_revlimit_pct = revlimit*self.revlimit_percent.get()
            self.update_target_rpm(rpm_revlimit_pct)            
        if revlimit_time:
            slope, intercept = self.lookahead.slope, self.lookahead.intercept
            rpm_revlimit_time = intercept + slope*tone_offset
            self.update_target_rpm(rpm_revlimit_time)
        
        if from_gear and config.log_full_shiftdata:
            print(f'beep from_gear: {shiftrpm:.0f}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque N/A trq_ratio {from_gear_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_pct and config.log_full_shiftdata:
            print(f'beep revlimit_pct: {rpm_revlimit_pct:.0f}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque N/A trq_ratio {revlimit_pct_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')
        if revlimit_time and config.log_full_shiftdata:
            print(f'beep revlimit_time: {rpm_revlimit_time:.0f}, gear {fdp.gear} rpm {fdp.current_engine_rpm:.0f} torque N/A trq_ratio {revlimit_time_ratio:.2f} slope {self.lookahead.slope:.2f} intercept {self.lookahead.intercept:.2f}')

        return from_gear or revlimit_pct or revlimit_time

    #write all settings that can change to the config file
    def config_writeback(self, varlist=['tone_offset']):        
        try:
            for variable in varlist:
                setattr(config, variable, getattr(self, variable).get())
            config.write_to(FILENAME_SETTINGS)
        except Exception as e: 
            print(e)
            print("Failed to write variables to config file")

    def close(self):
        self.loop.close()
        self.config_writeback()

def main():
    global forzabeep #for debugging
    forzabeep = ForzaBeep()

if __name__ == "__main__":
    main()
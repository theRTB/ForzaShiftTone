# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 21:03:42 2023

@author: RTB
"""

from utility import deloop_and_sort
from config import config

#collects an array of packets at full throttle
#if the user lets go of throttle, changes gear: reset
#revlimit is confirmed by: the initial run, then x packets with negative power,
#   then a packet with positive power. All at 100% throttle
#Then cut down the array to force boost to be at or above the boost multiplied
#   by the percentage in config with a small fudge factor of 0.001
#if power at the first packet is lower (or equal) to the power in the final
#   packet, we have a power curve that is complete enough to do shift rpm
#   rpm calculations with it.
class RunCollector():
    MINLEN = config.runcollector_minlen
    REMOVE_INITIAL = config.runcollector_remove_initial
    LOWER_LIMIT_BOOST = config.runcollector_pct_lower_limit_boost
    def __init__(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1

    def filter_run(self):
        if len(self.run) > self.REMOVE_INITIAL:
            del self.run[:self.REMOVE_INITIAL]
        peak_boost = max([p.boost for p in self.run])
        lowest_boost = peak_boost * self.LOWER_LIMIT_BOOST - 1e-3
        while len(self.run) > 0 and self.run[0].boost < lowest_boost:
            del self.run[0]
        # self.run = [p for p in self.run if p.boost >= lowest_boost]
        self.run = deloop_and_sort(array=self.run, 
                                   key_x=lambda p: p.current_engine_rpm, 
                                   key_y=lambda p: p.power, 
                                   key_sort=lambda p: p.current_engine_rpm)

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
            self.filter_run()
            # len_before = len(self.run)
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
        
        # if self.state == 'DONE':
        #     if self.is_run_final():
        #         self.state = 'FINAL'

        self.prev_rpm = fdp.current_engine_rpm

    def is_run_completed(self):
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

    #new run is considered better if:
    # - gear is equal or higher
    # - length of new run is equal or longer
    # - either or both:
    #    - revlimit is higher
    #    - starting rpm is lower
    def is_newrun_better(self, old_curve):
        if not self.is_run_completed():
            return False
        
        if ((self.get_revlimit_if_done() >= old_curve.get_revlimit()
             or self.run[0].current_engine_rpm <= old_curve.rpm[0])
             and self.get_gear() >= old_curve.get_gear()
             and len(self.run) >= len(old_curve.rpm)):
            print("Runcollector: new run better")
            return True
        return False
    
    #TODO: add more requirements to a locked run
    #minimum rpm: 2x idle rpm or so?
    def is_run_final(self):
        if len(self.run) > config.runcollector_minlen_lock:
            print(f"Runcollector: Run is final, len {len(self.run)/60:.1f}s")
            return True
        return False

    def set_run_final(self):
        self.state = 'FINAL'

    def reset(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1
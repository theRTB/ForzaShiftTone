# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 21:03:42 2023

@author: RTB
"""

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
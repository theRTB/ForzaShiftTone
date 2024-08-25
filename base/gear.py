# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
import statistics
from collections import deque

from mttkinter import mtTkinter as tkinter

from utility import derive_gearratio, calculate_shiftrpm

#The Forza series is limited to 10 gears (ignoring reverse)
MAXGEARS = 10

#Enumlike class
class GearState():
    UNUSED     = 0 # gear has not been seen (yet)
    REACHED    = 1 # gear has been seen, variance above lower bound
    LOCKED     = 2 # variance on gear ratio below lower bound
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

    def at_initial(self):
        return self.state == self.UNUSED

    def at_locked(self):
        return self.state == self.LOCKED

    def at_least_locked(self):
        return self.state >= self.LOCKED

    def at_final(self):
        return self.state == self.CALCULATED

    def __hash__(self):
        return hash(self.state)

    def __eq__(self, other):
        if self.__class__ is other.__class__:
            return self.state == other.state
        elif other.__class__ == int:
            return self.state == other
        return NotImplemented

    def __ge__(self, other):
        if self.__class__ is other.__class__:
            return self.state >= other.state
        elif other.__class__ == int:
            return self.state >= other
        return NotImplemented

#class to hold all variables per individual gear
class Gear():
    DEQUE_MIN, DEQUE_LEN  = 40, 60

    #              FWD    RWD    AWD
    VAR_BOUNDS = [1e-04, 1e-04, 1e-04]

    def __init__(self, number, config):
        self.gear = number
        self.state = GearState(label=f'Gear {number}')
        self.ratio_deque = deque(maxlen=self.DEQUE_LEN)
        self.shiftrpm = -1
        self.ratio = 0
        self.relratio = 0
        self.variance = math.inf

    def reset(self):
        self.state.reset()
        self.ratio_deque.clear()
        self.set_shiftrpm(-1)
        self.set_ratio(0)
        self.set_relratio(0)
        self.set_variance(math.inf)

    def get_gearnumber(self):
        return self.gear

    def get_shiftrpm(self):
        return self.shiftrpm

    def set_shiftrpm(self, val):
        self.shiftrpm = val

    def get_ratio(self):
        return self.ratio

    def set_ratio(self, val):
        self.ratio = val

    def get_relratio(self):
        return self.relratio

    def set_relratio(self, val):
        self.relratio = val

    def get_variance(self):
        return self.variance

    def set_variance(self, val):
        self.variance = val

    #if we have a new (and better curve) we reduce the state of the gear
    #to have it recalculate the shiftrpm later
    def newrun_decrease_state(self):
        if self.state.at_final():
            self.state.to_previous()

    def to_next_state(self):
        self.state.to_next()

    #return True if we should play gear beep
    def update(self, fdp):
        if self.state.at_initial():
            self.to_next_state()

        if self.state.at_least_locked():
            return

        if not (ratio := derive_gearratio(fdp)):
            return

        self.ratio_deque.append(ratio)
        if len(self.ratio_deque) < 10:
            return

        median = statistics.median(self.ratio_deque)
        variance = statistics.variance(self.ratio_deque)
        self.set_ratio(median)
        self.set_variance(variance)

        if (self.variance < self.VAR_BOUNDS[fdp.drivetrain_type] and
                len(self.ratio_deque) >= self.DEQUE_MIN):
            self.to_next_state() #implied from reached to locked
            print(f'LOCKED {self.gear}: {median:.3f}')
            return True

    def calculate_shiftrpm(self, rpm, power, nextgear):
        if (self.state.at_locked() and nextgear.state.at_least_locked()):
            relratio = self.get_ratio() / nextgear.get_ratio()
            print(f"Calculating shiftrpm for gear {self.gear}, relratio {relratio:.2f}")
            shiftrpm = calculate_shiftrpm(rpm, power, relratio)

            self.set_relratio(relratio)
            self.set_shiftrpm(shiftrpm)

            self.to_next_state()

#class to hold all gears up to the maximum of MAXGEARS
class Gears():
    GEARLIST = range(1, MAXGEARS+1)

    #first element is None to enable a 1:1 mapping of array to Gear number
    #it could be used as reverse gear but not in a usable manner anyway
    def __init__(self, config):
        self.gears = [None] + [Gear(g, config) for g in self.GEARLIST]

    def reset(self):
       for g in self.gears[1:]:
           g.reset()

    def newrun_decrease_state(self):
        for g in self.gears[1:]:
            g.newrun_decrease_state() #force recalculation of rpm

    def calculate_shiftrpms(self, rpm, power):
        for g1, g2 in zip(self.gears[1:-1], self.gears[2:]):
            g1.calculate_shiftrpm(rpm, power, g2)

    def get_shiftrpm_of(self, gear):
        if 0 < gear <= MAXGEARS:
            return self.gears[int(gear)].get_shiftrpm()
        return -1

    #TODO: implement highest gear seen
    def is_highest(self, gear):
        return False

    #Gear 1 - 10 are valid. Gear 0 is reverse. Gear 11 is neutral.
    def is_valid(self, fdp):
        gear = int(fdp.gear)
        return 0 < gear <= 11

    #call update function of current gear in fdp
    #return True if gear has locked and therefore double beep
    def update(self, fdp):
        gear = int(fdp.gear)
        if gear == 0 or gear > MAXGEARS:
            return
        return self.gears[gear].update(fdp)
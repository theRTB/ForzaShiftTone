# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:46:58 2023

@author: RTB
"""
import math
from collections import deque

from utility import calculate_shiftrpm

#Taken from ForzaShiftTone. GT7 telemetry officially goes up to 8 gears, but
#if a car has more than 8, it will overflow into other variables. This logic 
#has not been programmed in, so effectively only 8 gears. If we set this to 8
#the GUI doesn't align properly.
MAXGEARS = 10

#Enumlike class
class GearState():
    UNUSED     = 0 # gear has not been seen (yet)
    REACHED    = 1 # gear has been seen (effectively unused for GT7)
    LOCKED     = 2 # gear ratio grabbed from data packet
    CALCULATED = 3 # shift rpm calculated off gear ratios and power curve

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
    def update(self, gtdp, prevgear):
        if self.state.at_initial():
            self.to_next_state()

        if self.state.at_least_locked():
            return
        if not (ratio := round(gtdp.gears[self.gear], 3)):
            return
        
        self.set_ratio(ratio)
        
        #we use a reverse logic here because the gears are locked sequentially
        #1 is set then 2, then 3, etc
        #but we need the 'next gear' to get the relative ratio which is not set
        #yet at that point.
        if prevgear is not None and prevgear.state.at_least_locked():
            relratio =  prevgear.get_ratio() / ratio
            prevgear.set_relratio(relratio)
            
        self.to_next_state() #implied from reached to locked
        print(f'LOCKED {self.gear}: {ratio:.3f}')
        return True

    def calculate_shiftrpm(self, rpm, power, nextgear):
        if (self.state.at_locked() and nextgear.state.at_least_locked()):
            relratio = self.get_ratio() / nextgear.get_ratio()
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
        self.highest = None
        for g in self.gears[1:]:
           g.reset()

    def newrun_decrease_state(self):
        for g in self.gears[1:]:
            g.newrun_decrease_state() #force recalculation of rpm

    def calculate_shiftrpms(self, rpm, power):
        for g1, g2 in zip(self.gears[1:-1], self.gears[2:]):
            g1.calculate_shiftrpm(rpm, power, g2)

    def get_shiftrpm_of(self, gear):
        if gear > 0 and gear <= MAXGEARS:
            return self.gears[int(gear)].get_shiftrpm()
        return -1

    def is_highest(self, gearnr):
        return self.highest == gearnr

    #call update function of gear 1 to 8. We haven't updated the GUI display
    #because it messes up the available space
    #add the previous gear for relative ratio calculation
    def update(self, gtdp):
        highest = 0
        for gear, prevgear in zip(self.gears[1:-2], [None] + self.gears[1:-3]):
            if gtdp.gears[gear.gear] != 0.000:
                gear.update(gtdp, prevgear)
                highest += 1
        if not self.highest:
            self.highest = highest
            print(f'Highest gear: {self.highest}')
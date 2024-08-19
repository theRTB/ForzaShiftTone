# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:54:19 2023

@author: RTB
"""

import statistics
from collections import deque

from utility import packets_to_ms, Variable

#maintain a rolling array of the time between beep and actual shift
#caps to the lower and upper limits of the tone_offset variable to avoid
#outliers such as 0 ms reaction time or a delay of seconds or more
#depends on ForzaBeep loop_test_for_shiftrpm and loop_beep
class DynamicToneOffset():
    DEQUE_MIN, DEQUE_MAX = 35, 75

    def __init__(self, tone_offset_var, config, *args, **kwargs):
        self.default_toneoffset = config.tone_offset
        self.offset_lower = config.tone_offset_lower
        self.offset_upper = config.tone_offset_upper
        self.offset_outlier = config.tone_offset_outlier
        
        self.counter = None
        self.offset = self.default_toneoffset
        self.deque = deque([self.default_toneoffset]*self.DEQUE_MIN,
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
        
        if self.counter < 0:
            print(f'DynamicToneOffset: erronous {packets_to_ms(self.counter)} ms, discarded')
            self.reset_counter()
            return
            
        if self.counter > self.offset_outlier:
            print(f'DynamicToneOffset: outlier {packets_to_ms(self.counter)} ms, discarded')
            self.reset_counter()
            return

        if self.deque_min_counter <= self.DEQUE_MIN:
            self.deque.popleft()
        else:
            self.deque_min_counter += 1

        value = min(self.offset_upper, self.counter)
        value = max(self.offset_lower, value)

        self.deque.append(value)
        average = statistics.mean(self.deque)
        print(f'DynamicToneOffset: offset {self.offset:.1f} new average {average:.2f}')
        average = round(average, 1)
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

class ToneOffset(Variable, DynamicToneOffset):
    def __init__(self, config):
        Variable.__init__(self, defaultvalue=config.tone_offset)
        DynamicToneOffset.__init__(self, tone_offset_var=self, config=config)

class Volume(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.volume)

class RevlimitOffset(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.revlimit_offset)

class RevlimitPercent(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.revlimit_percent)

class HysteresisPercent(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.hysteresis_percent)

    def as_rpm(self, fdp):
        return self.get() * fdp.engine_max_rpm

class IncludeReplay(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.includereplay)
        
    def test(self, gtdp):
        return (self.get() or gtdp.cars_on_track)

class DynamicToneOffsetToggle(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.dynamictoneoffset)
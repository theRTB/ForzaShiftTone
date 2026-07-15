# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:54:19 2023

@author: RTB
"""

import statistics
from collections import deque
from threading import Timer

from utility import packets_to_ms, Variable, tryplaysound

#maintain a rolling array of the time between beep and actual shift
#caps to the lower and upper limits of the tone_offset variable to avoid
#outliers such as 0 ms reaction time or a delay of seconds or more
#depends on ForzaBeep loop_test_for_shiftrpm and loop_beep
class DynamicToneOffset:
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
        
        if self.counter < 0 or self.counter > self.offset_outlier:
            value = packets_to_ms(self.counter)
            print(f'DynamicToneOffset: erronous {value} ms, discarded')
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

#Class to handle the bluetooth keepalive logic
# If enabled, will play an empty sound file repeatedly and is overridden by the
# beep. After the beep, Volume reapplies the keepalive loop
# There is no explicit (threaded) loop, a Timer is used instead
class BluetoothKeepalive:
    def __init__(self, config, bluetooth_keepalive_var):
        self.bluetooth_keepalive =  bluetooth_keepalive_var

        self.bluetooth_keepalive_file = config.bluetooth_keepalive_file
        self.bluetooth_keepalive_duration = config.bluetooth_keepalive_duration
        self.bluetooth_keepalive_delay = config.bluetooth_keepalive_delay

        #None Timer so that we can always call the Timer functions elsewhere
        self.t = Timer(0.0, lambda: None)
        self.t.start()

    # Called when Volume.beep() is called, covers resetting of keepalive
    def handle_beep(self):
        if self.bluetooth_keepalive.get():
            self.t.cancel()
            delay = self.bluetooth_keepalive_duration
            self.repeat_bluetooth_keepalive(delay=delay)

    # Does not override a currently playing sound
    # In case a beep is played when the bluetooth keepalive sound refreshes
    def play_bluetooth_keepalive(self):
        filename = self.bluetooth_keepalive_file
        # print(f"Playing bluetooth keepalive! {filename}")
        tryplaysound(filename)

    # if delay is set, delay the first playing of the keepalive, play then loop
    # otherwise, play keepalive and then loop
    def repeat_bluetooth_keepalive(self, delay=None):
        if delay is None:
            # delay = (self.bluetooth_keepalive_duration +
            #          self.bluetooth_keepalive_delay)
            delay = self.bluetooth_keepalive_delay
            self.play_bluetooth_keepalive()

        if self.bluetooth_keepalive.get():
            self.t = Timer(delay, self.repeat_bluetooth_keepalive)
            self.t.start()

    def start_bluetooth_keepalive(self):
        print("Starting bluetooth keepalive loop")
        self.repeat_bluetooth_keepalive()

    # This will most likely stop a beep as well
    def stop_bluetooth_keepalive(self):
        print("Stopping bluetooth keepalive loop")
        self.t.cancel()
        tryplaysound(None)

    def start(self, force=False):
        if force:
            self.bluetooth_keepalive.enable()
        self.start_bluetooth_keepalive()

    def stop(self):
        if self.bluetooth_keepalive.get():
            self.stop_bluetooth_keepalive()

    def reset(self):
        self.stop()
        self.start()

# Class to manage playing the upshift beep and making sure the optional
# bluetooth keepalive is played: without this the BT connect could go into
# standby and a beep would not be played or be garbled or heavily delayed
# The toggle to play the keepalive is from outside this class
class Volume(Variable, BluetoothKeepalive):
    def __init__(self, config, bluetooth_keepalive_var):
        Variable.__init__(self, defaultvalue=config.volume)
        BluetoothKeepalive.__init__(self, config, bluetooth_keepalive_var)

        self.sound_file = config.sound_file
        self.sound_files = config.sound_files

    def beep(self):
        if (volume_level := self.get()) == 0:
            return

        filename = self.sound_files[volume_level]
        # print(f"Playing {filename}")
        tryplaysound(filename)
    
        BluetoothKeepalive.handle_beep(self)
       
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

#TODO: Test if this makes any sense
class IncludeReplay(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.includereplay)
        
    def test(self, fdp):
        return self.get() or fdp.is_race_on

class DynamicToneOffsetToggle(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.dynamictoneoffset)

class BluetoothKeepaliveToggle(Variable):
    def __init__(self, config):
        super().__init__(defaultvalue=config.bluetooth_keepalive)

    def enable(self):
        self.set(True)

    def disable(self):
        self.set(False)

    def toggle(self):
        self.set(not(self.get()))
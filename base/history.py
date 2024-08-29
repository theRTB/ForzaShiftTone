# -*- coding: utf-8 -*-
"""
Created on Wed Jul 17 19:59:17 2024

@author: RTB
"""
from utility import packets_to_ms

class History():
    COLUMNS = ['target', 'shiftrpm', 'gear', 'beep_distance']
    def __init__(self, config):
        self.log_basic_shiftdata = config.log_basic_shiftdata
        self.history = []
    
    def get_shiftpoint(self, target, shiftrpm, gear, beep_distance):
        data = ['N/A' if target == -1 else int(target),
              int(shiftrpm),
              gear,
              'N/A' if beep_distance is None else packets_to_ms(beep_distance)]
                    
        return dict(zip(self.COLUMNS, data))
    
    def add_shiftdata(self, point):
        self.history.append(point)
    
    def debug_log_basic_shiftdata(self, target, shiftrpm, gear, 
                                  beep_distance):
        # target = self.debug_target_rpm
        difference = 'N/A' if target == -1 else f'{shiftrpm - target:4.0f}'
        beep_distance_ms = 'N/A'
        if beep_distance is not None:
            beep_distance_ms = packets_to_ms(beep_distance)
        print(f"gear {gear}-{gear+1}: {shiftrpm:.0f} actual shiftrpm, {target:.0f} target, {difference} difference, {beep_distance_ms} ms distance to beep")
        print("-"*50)
    
    def update(self, target, shiftrpm, gear, beep_distance):
        point = self.get_shiftpoint(target, shiftrpm, gear, beep_distance)
        self.add_shiftdata(point)
        if self.log_basic_shiftdata:
            self.debug_log_basic_shiftdata(target, shiftrpm, gear, 
                                           beep_distance)

    def reset(self):
        self.history.clear()
    
    #display statistics on difference between target and actual
    #distance between expected and actual distance between beep and shift
    def statistics(self):
        pass
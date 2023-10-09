# -*- coding: utf-8 -*-
"""
Created on Fri Aug  4 21:15:45 2023

@author: RTB
"""
import numpy as np

#TODO:filter and smooth the rpm array
#     power and torque should be more stable inherently on a single run

class Curve ():
    def __init__(self, packets):
        self.gear = packets[0].gear
        self.rpm = np.array([p.current_engine_rpm for p in packets])
        self.power = np.array([p.power for p in packets])
        self.torque = np.array([p.torque for p in packets])
        self.boost = np.array([p.boost for p in packets])
    
    def get_gear(self):
        return self.gear
    
    def get_peakpower_index(self):
        return np.argmax(self.power)
    
    #not necessarily the highest rpm, but valid for our purposes
    def get_revlimit(self):
        return self.rpm[-1]
    
    def torque_at_rpm(self, target_rpm):
        i = np.argmin(np.abs(self.rpm - target_rpm))
        return self.torque[i]
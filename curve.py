# -*- coding: utf-8 -*-
"""
Created on Fri Aug  4 21:15:45 2023

@author: RTB
"""
import numpy as np

class Curve ():
    def __init__(self, packets):
        self.array = packets
        self.rpm = np.array([p.current_engine_rpm for p in packets])
        self.power = np.array([p.power for p in packets])
        self.torque = np.array([p.torque for p in packets])
# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 21:05:07 2023

@author: RTB
"""

import statistics
from collections import deque

#class that maintains a deque used for linear regression. This smooths the rpms
#and provides a slope to predict future RPM values.
class Lookahead():
    def __init__(self, minlen, maxlen):
        self.minlen = minlen
        self.deque = deque(maxlen=maxlen)
        self.clear_linreg_vars()

    def add(self, rpm):
        self.deque.append(rpm)
        self.set_linreg_vars()

    #x is the frame distance to the most recently added point
    #this has the advantage that the slope is counted from the most recent point
    def set_linreg_vars(self):
        if len(self.deque) < self.minlen:
            return
        x, y = range(-len(self.deque)+1, 1), self.deque
        self.slope, self.intercept = statistics.linear_regression(x, y)

    #slope factor is used to shape the prediction with more information than
    #from just the linear regression. As RPM is not linear, it will otherwise
    #overestimate consistently.
    def test(self, target_rpm, lookahead, slope_factor=1):
        if (len(self.deque) < self.minlen or self.slope <= 0 or 
            slope_factor <= 0):
            return False
        distance = (target_rpm - self.intercept) / (self.slope * slope_factor)
        return 0 <= distance <= lookahead
    
    def reset(self):
        self.deque.clear()
        self.clear_linreg_vars()

    def clear_linreg_vars(self):
        self.slope, self.intercept = None, None
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  2 21:00:26 2024

@author: RTB
"""

from utility import Variable

#need raw rpm and hysteresis rpm
#GUIRPM then extends this class
class RPM(Variable):
    def __init__(self, hysteresis_percent):
        super().__init__(defaultvalue=0)
        self.hysteresis_percent = hysteresis_percent
    
    def update(self, gtdp):
        rpm = round(gtdp.current_engine_rpm)
        
        hysteresis = self.hysteresis_percent.as_rpm(gtdp)
        if abs(rpm - self.get()) >= hysteresis:
            self.set(rpm)
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  4 21:15:45 2023

@author: RTB
"""
import numpy as np

from utility import round_to

#This class holds a subset of the packet variables split into separate arrays
#the packets are sorted in runcollector as well as loops removed
#in this class we then force the final point to be a multiple of revlimit_round
#extrapolating data if need be, else strip points until only the last point is
#above revlimit, then set that point's rpm value to equal revlimit without
#adjusting the other data of that point

class Curve ():
    REVLIMIT_ROUND = 50
    REVLIMIT_ROUND_OFFSET = 10
    def __init__(self, packets, config=None):
        self.gear = packets[0].gear
        
        #initialize to python arrays, as numpy arrays do not resize
        self.rpm = [p.current_engine_rpm for p in packets]
        self.power = [p.power for p in packets]
        self.torque = [p.torque for p in packets]
        self.boost = [p.boost for p in packets]
    
        self.correct_final_point(config)
    
        #convert to numpy array as possible resizing has been done
        for var in ['rpm', 'power', 'torque', 'boost']:
            setattr(self, var, np.array(getattr(self, var)))
    
    #We move the rounding point by 5, so 
    #0-5 is rounded down and 6-20 is rounded up instead of 12.5 as middle
    def correct_final_point(self, config):
        revlimit_round = getattr(config, 'revlimit_round', self.REVLIMIT_ROUND)
        revlimit_round_offset = getattr(config, 'revlimit_round_offset',
                                        self.REVLIMIT_ROUND_OFFSET)
        
        rpm_diff = self.rpm[-1] % revlimit_round
        revlimit = round_to(self.rpm[-1]+revlimit_round_offset, revlimit_round)
        
        if rpm_diff <= revlimit_round/2-revlimit_round_offset:
            print("Curve above")
            #case rpm is above assumed revlimit:
            #remove points until only the last point is above revlimit
            #set last point rpm to revlimit
            while self.rpm[-2] >= revlimit:
                del self.rpm[-1]
            self.rpm[-1] = revlimit
            print(f'revlimit {revlimit}')
        else: #case rpm is below assumed revlimit
            print("Curve below")
            #we add a new point with linear extrapolation to revlimit
            x1, x2 = self.rpm[-2:]
            print(f'x1 {x1:.3f} x2 {x2:.3f} revlimit {revlimit}')
            self.rpm.append(revlimit)
            for array in [self.power, self.torque, self.boost]:
                y1, y2 = array[-2:]
                ynew = (y2 - y1) / (x2 - x1) * (revlimit - x2) + y2
                array.append(ynew)
                print(f'y1 {y1:.3f} y2 {y2:.3f} ynew {ynew:.3f}')
                
    def get_gear(self):
        return self.gear
    
    #get peak power according to peak power rounded to 0.1kW
    #the rounding is necessary to avoid some randomness in collecting a curve
    def get_peakpower_tuple(self, decimals=-2):
        power_rounded = np.round(self.power, decimals) #100W -> 0.1kW accuracy
        index = np.argmax(power_rounded)
        return (self.rpm[index], max(power_rounded))
    
    def get_revlimit(self):
        return self.rpm[-1]
    
    #TODO: linear interpolation and possibly extrapolation
    def torque_at_rpm(self, target_rpm):
        i = np.argmin(np.abs(self.rpm - target_rpm))
        return self.torque[i]
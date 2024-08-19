# -*- coding: utf-8 -*-
"""
Created on Tue Aug 13 22:33:15 2024

@author: RTB
"""

import csv
import numpy as np
from os.path import exists

from os import makedirs
makedirs('curves/', exist_ok=True) #create curves folder if not exists

from utility import np_drag_fit

#poorly named: does not extend Curve
#Given an array of consecutive rpm/accel points at full throttle and an array
#of consecutive accel points with the clutch disengaged we can derive a torque
#curve and thus a power curve.
#TODO: Do we round revlimit? It is generally above true revlimit.
#At stock, revlimit is a multiple of 100, but upgrades can be things like 3%
#more revs and make it a random number. 
#Appending a single value to an np.array is not efficient
#Assumes the last section to be accurate for appending the final point
# If this is increasing instead of (normally) decreasing, final point will be
# further off than it should be. This is generally fine because the last point
# has been through a rolling average of 21 points
class EngineCurve():
    COLUMNS = ['rpm', 'power', 'torque']
    DELIMITER = '\t'
    ENCODING = 'ISO-8859-1' #why not UTF-8?
    FOLDER = 'curves'
    FILENAME = lambda _, gtdp: f'{EngineCurve.FOLDER}/{gtdp.car_ordinal}.tsv'
    
    #code duplication, but calling reset in __init__ causes issues with
    #inheritance
    def __init__(self, config, *args, **kwargs):
        for var in ['curve_state', 'rpm', 'power', 'torque', 'revlimit']:
            setattr(self, var, None)

    def reset(self):
        for var in ['curve_state', 'rpm', 'power', 'torque', 'revlimit']:
            setattr(self, var, None)

    def is_loaded(self):
        return self.curve_state == True

    #called once to update curve
    def update(self, gtdp, *args, **kwargs):
        if self.curve_state:
            return #this should not happen though
        
        filename = self.FILENAME(gtdp)
        if exists(filename): #file exists
            self.load(filename)
            self.curve_state = True
            print(f'Loaded curve from {filename}')
        elif len(kwargs) > 0:
            self.curve_state = True
            self.init_from_drag_fit(*args, **kwargs)
            self.save(filename)
            print(f'Saved curve to {filename}')
        else:
            self.curve_state = False
            print("No curve loaded, waiting for DataCollector")

    # def init_from_file(self, filename, *args, **kwargs):
    #     self.load(filename)
    
    def init_from_drag_fit(self, *args, **kwargs):
        accelrun = kwargs.get('accelrun', None)
        if accelrun is None: # and len(args) > 0: #TODO defensive programming
            accelrun = args[0]
        result = np_drag_fit(*args, **kwargs)
        self.revlimit = accelrun.revlimit
        self.rpm, self.torque, self.power = result
        
        self.correct_final_point()

    def correct_final_point(self):
        x1, x2 = self.rpm[-2:]
        # print(f'x1 {x1:.3f} x2 {x2:.3f} revlimit {self.revlimit}')
        np.append(self.rpm, self.revlimit)
        self.rpm = np.append(self.rpm, self.revlimit)
        for name in ['power', 'torque']: #,'boost']:
            array = getattr(self, name)
            y1, y2 = array[-2:]
            ynew = (y2 - y1) / (x2 - x1) * (self.revlimit - x2) + y2
            setattr(self, name, np.append(array, ynew))
            # print(f'y1 {y1:.3f} y2 {y2:.3f} ynew {ynew:.3f}')

    #get peak power according to peak power rounded to 0.x
    #the rounding is necessary to avoid some randomness in collecting a curve
    def get_peakpower_tuple(self, decimals=1):
        power_rounded = np.round(self.power, decimals)
        index = np.argmax(power_rounded)
        return (self.rpm[index], max(power_rounded))

    def get_revlimit(self):
        return self.rpm[-1]

    def get_rpmpower(self):
        return (self.rpm, self.power)

    #TODO: linear interpolation and possibly extrapolation
    def torque_at_rpm(self, target_rpm):
        i = np.argmin(np.abs(self.rpm - target_rpm))
        return self.torque[i]
    
    def torque_ratio(self, gtdp, target_rpm):
        torque_ratio = 1
        if self.is_loaded():
            rpm = gtdp.current_engine_rpm
            if not (gtdp_torque := self.torque_at_rpm(rpm)):
                return torque_ratio #this should not happen
            target_torque = self.torque_at_rpm(target_rpm)
            torque_ratio = target_torque / gtdp_torque
        return torque_ratio
    
    def save(self, filename, overwrite=True):
        if exists(filename):
            if not overwrite:
                print(f'file {filename} already exists, aborted by bool')
                return False
            else:
                print(f'file {filename} already exists, overwriting')

        data = [getattr(self, column) for column in self.COLUMNS]
        
        #hardcoding adjustment to rpm, power and torque output
        data[0] = [f'{rpm:.0f}' for rpm in data[0]] 
        data[1] = [f'{power:.2f}' for power in data[1]]
        data[2] = [f'{torque:.2f}' for torque in data[2]]
        
        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile, delimiter=self.DELIMITER)
            writer.writerow(self.COLUMNS)
            
            #flip array structure from per column to per row before writing
            writer.writerows(zip(*data)) 
            
        return True #TODO: add catch to with statement because write may fail

    def load(self, filename):
        if not exists(filename):
            print(f'file {filename} does not exist')
            return
        
        with open(filename, encoding=self.ENCODING) as rawcsv:
            csvobject = csv.reader(rawcsv, delimiter=self.DELIMITER)
            headers = next(csvobject)
            csvdata = [[float(p) for p in row] for row in csvobject]
        
        #flip array structure from per row to per column
        rawdata = list(zip(*csvdata))
        
        for name, array in zip(headers, rawdata):
            setattr(self, name, np.array(array))
            if name not in self.COLUMNS:
                print(f'LOAD: Unexpected column {name} found, loaded anyway')
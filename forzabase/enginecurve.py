# -*- coding: utf-8 -*-
"""
Created on Tue Aug 13 22:33:15 2024

@author: RTB
"""

import csv
import numpy as np
from os.path import exists

# create folder structure if it doesn't exist
from os import makedirs
makedirs('curves/', exist_ok=True)

from utility import simplify_curve, round_to

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
    FILENAME = lambda _, fdp: f'{EngineCurve.FOLDER}/{fdp.car_ordinal}.tsv'
    ROUND = 100 #round the saved curve to multiples of round
    DECIMALS = 1 #save power/torque to 1 decimal accuracy
    ROUND_REVLIMIT = 50 #covers 99.9% of all standard revlimits

    def __init__(self, config, *args, **kwargs):
        self.curve_state = None
        self.rpm = None
        self.power = None
        self.torque = None
        self.revlimit = None

    def reset(self):
        for var in ['curve_state', 'rpm', 'power', 'torque', 'revlimit']:
            setattr(self, var, None)

    def is_loaded(self):
        return self.curve_state == True

    #called once to update curve
    def update(self, fdp, *args, **kwargs):
        if self.curve_state:
            return

        if 'accelrun' in kwargs.keys() and 'dragrun' in kwargs.keys():
            self.curve_state = True
            self.init_from_run(*args, **kwargs)

            filename = self.FILENAME(fdp) if fdp is not None else None
            if fdp.car_ordinal:
                self.save(filename)
                print(f'Saved curve to {filename}')
            else:
                print("Curve not saved: no car ordinal")
        elif 'run' in kwargs.keys():
            self.curve_state = True
            self.init_from_run(*args, **kwargs)
            filename = self.FILENAME(fdp)
            returnstatus = self.save(filename)
            if returnstatus:
                print(f'Saved curve to {filename}')
        elif self.file_exists(fdp):
            self.init_from_file(fdp, *args, **kwargs)
            #curve_state set to true in function
        else:
            self.curve_state = False
            print("No curve loaded, waiting for DataCollector")

    #TODO: consider rewriting to use path library
    def file_exists(self, fdp):
        if fdp is None:
            return False

        filename = self.FILENAME(fdp)
        return exists(filename)

    #gtdp is assumed to not be None here because files_exist tests for this
    def init_from_file(self, fdp, *args, **kwargs):
        filename = self.FILENAME(fdp)
        if exists(filename):
            self.load(filename)
            print(f'Loaded curve from {filename}')
            self.curve_state = True

    #TODO: get revlimit from runcollector
    def init_from_run(self, run, *args, **kwargs):
        rpm = np.array([p.current_engine_rpm for p in run])
        power = np.array([p.power for p in run]) / 1000 #W -> kW
        torque = np.array([p.torque for p in run])
        
        #round revlimit to nearest 50 (default)
        self.revlimit = round_to(max(rpm), 50)
        
        self.rpm, self.torque = simplify_curve(rpm, torque, xmax=self.revlimit, 
                                               n=self.ROUND) 
        _ , self.power = simplify_curve(rpm, power, xmax=self.revlimit, 
                                        n=self.ROUND)      

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
    
    #TODO: use this instead of torque_ratio_test in ForzaBeep
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
        data[1] = [f'{power:.{self.DECIMALS}f}' for power in data[1]]
        data[2] = [f'{torque:.{self.DECIMALS}f}' for torque in data[2]]
        
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
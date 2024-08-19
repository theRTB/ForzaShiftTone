# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 10:23:57 2023

@author: RTB
"""
#A collection of various utility functions for the rest of the files

#general purpose variable class
class Variable(object):
    def __init__(self, defaultvalue=None, *args, **kwargs):
        self.value = defaultvalue
        self.defaultvalue = defaultvalue

    def get(self):
        return self.value

    def set(self, value):
        self.value = value
    
    def reset(self):
        self.value = self.defaultvalue



#modified from stackoverflow code, limited how far the algorithm looks ahead
#a single run of a power/rpm curve tends to have oscillations, where the power
#increases above the expected level for the rpm value but then drops and
#the curve intersects with itself. After this, the power/rpm returns to normal.
#we detect an intersection and assume a loop. We remove the loop.
#finally, without loops it is safe to sort based on rpm for a cleaner curve.
#With loops, sorting on rpm leads to a subtle sawtooth pattern

#From: https://stackoverflow.com/questions/65532031/how-to-find-number-of-self-intersection-points-on-2d-plot
def intersection(x1,x2,x3,x4,y1,y2,y3,y4):
    if d := (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4):
        xs = ((x1*y2-y1*x2)*(x3-x4) - (x1-x2)*(x3*y4-y3*x4)) / d
        ys = ((x1*y2-y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-y3*x4)) / d
        if (xs >= min(x1,x2) and xs <= max(x1,x2) and
            xs >= min(x3,x4) and xs <= max(x3,x4)):
            return xs, ys

import itertools as it
def get_loops(x, y, max_loop=50):
    ind = list(it.repeat(1, len(x)))
    i = 0
    while i < len(x) - 2:
        for j in range(i + 2, min(len(x) - 2, i + max_loop)):
            if intersection(x[i],x[i+1],x[j],x[j+1], y[i],y[i+1],y[j],y[j+1]):
                ind[i+1:j+1] = it.repeat(0, j-i)
                i = j #skip ahead
                break
        else:
            i += 1
    return ind

def deloop_and_sort(array, key_x, key_y, key_sort, max_loop=50):
    selectors = get_loops(x=[key_x(a) for a in array], 
                          y=[key_y(a) for a in array], max_loop=max_loop)
    return sorted(it.compress(array, selectors), key=key_sort)

def round_to(val, n):
    return round(val/n)*n



import winsound
from config import config

def beep(filename=config.sound_file):
    try:
        winsound.PlaySound(filename, (winsound.SND_FILENAME | 
                           winsound.SND_ASYNC | winsound.SND_NODEFAULT))
    except:
        print(f"Sound failed to play: {filename}")

from threading import Timer
def multi_beep(filename=config.sound_file, duration=0.1, count=2, delay=0.1):
    for number in range(count):
        t = Timer(number*(duration+delay), lambda: beep(filename))
        t.start()



#Only necessary for Forza series
import math
#drivetrain enum for fdp
DRIVETRAIN_FWD = 0
DRIVETRAIN_RWD = 1
DRIVETRAIN_AWD = 2

#if the clutch is engaged, we can use engine rpm and wheel rotation speed
#to derive the ratio between these two: the drivetrain ratio
#AWD only considers rear tires due to complicating factors if front/rear are of
#different sizes, as well as different slip ratios
#since we are ultimately only interested in relative ratios, the fact that the
#derived drivetrain ratio is not 100% correct for AWD is not that important.
def derive_gearratio(fdp):
    rpm = fdp.current_engine_rpm
    if abs(fdp.speed) < 3 or rpm == 0: #if speed below 3 m/s assume faulty data
        return None

    rad = 0
    if fdp.drivetrain_type == DRIVETRAIN_FWD:
        rad = (fdp.wheel_rotation_speed_FL + fdp.wheel_rotation_speed_FR) / 2.0
    elif fdp.drivetrain_type == DRIVETRAIN_RWD:
        rad = (fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 2.0
    else:  #AWD
        rad = (fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 2.0
        # rad = (fdp.wheel_rotation_speed_FL + fdp.wheel_rotation_speed_FR +
        #     fdp.wheel_rotation_speed_RL + fdp.wheel_rotation_speed_RR) / 4.0
    if abs(rad) <= 1e-6:
        return None
    if rad < 0: #in the case of reverse
        rad = -rad
    return 2 * math.pi * rpm / (rad * 60)



import intersect
#determine shift rpm by finding the intersection point of two power curves:
# one as is, the other multiplied by the relative ratio of the two consecutive
# gears. The second is how much longer the next gear is relatively.
#intersect.intersections gives a tuple where the first value is an array of
#point on the x-axis where intersection occurs, the second is the y-axis
#we are only interested in the x-axis and we assume the last intersection is
#the most accurate one.
def calculate_shiftrpm(rpm, power, relratio):
    intersects = intersect.intersection(rpm, power, rpm*relratio, power)[0]
    shiftrpm = round(intersects[-1],0) if len(intersects) > 0 else rpm[-1]
    print(f"shift rpm {shiftrpm:.0f}, drop to {shiftrpm/relratio:.0f}, "
          f"drop is {shiftrpm*(1.0 - 1.0/relratio):.0f}")

    if len(intersects) > 1:
        print("Warning: multiple intersects found: graph may be noisy")

    return shiftrpm



import numpy as np
from numpy.polynomial import Polynomial

#From: https://stackoverflow.com/questions/20618804/how-to-smooth-a-curve-for-a-dataset
#renamed to rolling_avg instead of smooth
#Apply a rolling average of box_pts points
#this will cause the first and last box_pts//2 points to be inaccurate if mode 
#'same' is used. Defaults to 'valid', which truncates approximately half the
#size of box_pts from either side of y. We add the right side back later
#through linear extrapolation
def rolling_avg(y, box_pts, mode='valid'):
    box = np.ones(box_pts)/box_pts
    y_smooth = np.convolve(y, box, mode=mode)
    return y_smooth

#redefine x, y graph to only have multiples of n as points of x with linear
#interpolation of y values
#x is assumed to be sorted and increases monotonically
#optionally include a 'true' xmax to extend/shorten the curve to
#the final point of x array is included
def simplify_curve(x, y, xmax=None, n=100):
    xmax = x[-1] if xmax is None else xmax
    startx = math.ceil(x[0]/n)*n
    newx = np.arange(startx, xmax+1, n)
    newy = np.interp(newx, x, y)
    
    return (newx, newy)

#Derives an rpm/torque curve from an rpm/accel curve up to revlimit along with
#an array of consecutive velocity/accel points at high speed. The 
#initial rolling average of 3 points is to correct unusual behavior from for
#example the Bugatti VGT where the data points oscillate every other point
#TODO: implement bounds: at the moment only dragrun lower bound works
#TODO: GT7 power curves are linear interpolation between points per 500 rpm
#  From 1000 to the closest multiple of 500 near revlimit. Distance between
#  the next-to-last point to revlimit can be smaller than 500. Do we do
#  anything with this?
def np_drag_fit(accelrun, dragrun, dragrun_bounds=(10, None), 
                accelrun_bounds=(0, None), smoothing='multi_rolling', 
                accelrun_smooth=[3,21], sort_rpm=True, interval=100):

    if smoothing == 'rolling':
        accelrun.rolling_avg(box_pts=accelrun_smooth)
    if smoothing == 'multi_rolling':
        accelrun.multi_rolling_avg(box_pts_array=accelrun_smooth)
    # elif smoothing == 'lowpass':
    #     accelrun.low_pass_filter(bandlimit=accelrun_smooth)
        
    dragP = Polynomial.fit(dragrun.v[dragrun_bounds[0]:], 
                           dragrun.a[dragrun_bounds[0]:], deg=[1,2], 
                           domain=[0, max(accelrun.v)], 
                           window=[0, max(accelrun.v)])
    
    torque_shape = accelrun.a - dragP(accelrun.v)
    rpm_shape = sorted(accelrun.rpm) if sort_rpm else accelrun.rpm
    
    if interval:
        rpmmax = accelrun.revlimit
        rpm, torque = simplify_curve(rpm_shape, torque_shape, rpmmax, interval)
    
    power = torque * rpm
    
    return (np.array(rpm), 
            100*torque/max(torque), 
            100*power/max(power))

import csv
from os.path import exists

#poorly named: does not extend Curve
#Given an array of consecutive rpm/accel points at full throttle and an array
#of consecutive accel points with the clutch disengaged we can derive a torque
#curve and thus a power curve.
#TODO: Do we round revlimit? It is generally above true revlimit.
#At stock, revlimit is a multiple of 100, but upgrades can be things like 3%
#more revs and make it a random number. 
#Appending a single value to an np.array is not efficient
#Consider only working off torque and deriving power later.
class PowerCurve():
    COLUMNS = ['rpm', 'power', 'torque']
    DELIMITER = '\t'
    ENCODING = 'ISO-8859-1' #why not UTF-8?
    def __init__(self, *args, **kwargs):
        if 'filename' in kwargs.keys():
            print("PowerCurve init from file")
            self.init_from_file(*args, **kwargs)
        else:
            print("PowerCurve init from drag")
            self.init_from_drag_fit(*args, **kwargs)

    def init_from_file(self, filename, *args, **kwargs):
        self.load(filename)
    
    def init_from_drag_fit(self, *args, **kwargs):
        accelrun = kwargs.get('accelrun', None)
        if accelrun is None:
            accelrun = args[0]
        result = np_drag_fit(*args, **kwargs)
        self.revlimit = accelrun.revlimit
        self.rpm, self.torque, self.power = result
        
        self.correct_final_point()

    #naively extrapolates power when it is a consequence of torque*rpm
    #The result is close enough though
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

    #TODO: linear interpolation and possibly extrapolation
    def torque_at_rpm(self, target_rpm):
        i = np.argmin(np.abs(self.rpm - target_rpm))
        return self.torque[i]
    
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
    
    #
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
            if name not in self.columns:
                print(f'LOAD: Unexpected column {name} found, loaded anyway')



#convert a packet rate of 60hz to integer milliseconds
def packets_to_ms(val):
    return int(1000*val/60)

#convert integer milliseconds to a packet rate of 60hz
def ms_to_packets(val):
    return int(round(60*int(val)/1000, 0))

#factor is a scalar
def factor_to_percent(val):
    return round(100*val, 1)

#factor is a scalar
def percent_to_factor(val):
    return float(val)/100
# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 10:23:57 2023

@author: RTB
"""

import time
import winsound
import itertools as it
from config import config

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

def get_loops(x, y, max_loop=50):
    ind = list(it.repeat(1, len(x)))
    i = 0
    while i < len(x) - 2:
        for j in range(i+2, min(len(x) - 2, i+max_loop)):
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

#multibeep has a simple sleep in it, which will freeze the UI if called
#we could probably throw this function into the ThreadPool at the cost of
#consistency
def multi_beep(filename=config.sound_file, count=2, delay=0.1):
    winsound.PlaySound(filename,
                       winsound.SND_FILENAME | winsound.SND_NODEFAULT)
    for number in range(count-1):
        time.sleep(delay)
        winsound.PlaySound(filename,
                           winsound.SND_FILENAME | winsound.SND_NODEFAULT)
 
def beep(filename=config.sound_file):
    try:
        winsound.PlaySound(filename,
                           winsound.SND_FILENAME | winsound.SND_ASYNC |
                           winsound.SND_NODEFAULT)
    except:
        print("Sound failed to play")
        
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
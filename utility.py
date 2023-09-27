# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 10:23:57 2023

@author: RTB
"""

import time
import winsound

from config import config

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
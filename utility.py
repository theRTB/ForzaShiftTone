# -*- coding: utf-8 -*-
"""
Created on Wed Sep 13 10:23:57 2023

@author: RTB
"""

import time
import winsound

from config import config

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
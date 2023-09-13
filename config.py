# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:36:24 2023

@author: RTB
"""
import json
from os.path import exists

FILENAME_SETTINGS = 'config.json'

class config():
    ip = '127.0.0.1'
    port = 12350
    packet_format = 'fh4'
    
    sound_file = 'audio/audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav'
    sound_files = {  0:'audio/audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav',
                   -10:'audio/audiocheck.net_sin_1000Hz_-13dBFS_0.1s.wav',
                   -20:'audio/audiocheck.net_sin_1000Hz_-23dBFS_0.1s.wav',
                   -30:'audio/audiocheck.net_sin_1000Hz_-33dBFS_0.1s.wav' }
    
    notification_file = 'audio/audiocheck.net_sin_1500Hz_-13dBFS_0.05s.wav'
    # notification_gear_count = 2
    # notification_gear_delay = 0.02
    notification_power_enabled = True
    notification_power_count = 3
    notification_power_delay = 0.04
    
    volume = -10
    
    window_scalar = 1 #scale window by this factor
    
    #initial revlimit = engine_limit - guess
    #distance between revlimit and engine limit varies between 100 and 2000
    #with the most common value at 500. 750 is the rough average.
    revlimit_guess = 750
    
    beep_counter_max = 30 #minimum number of frames between beeps = 0.33ms
    beep_rpm_pct = 0.75 #counter resets below this percentage of beep rpm
    min_throttle_for_beep = 255 #only test if at or above throttle amount

    tone_offset = 17 #if specified rpm predicted to be hit in x packets: beep
    tone_offset_lower =  9
    tone_offset_upper = 25
    tone_offset_outlier = 30 #discard for dynamic tone if above this distance
    
    revlimit_percent = 0.996 #respected rev limit for trigger revlimit as pct%
    revlimit_percent_lower = 0.950
    revlimit_percent_upper = 0.998
    
    revlimit_offset = 5 #additional buffer in x packets for revlimit
    revlimit_offset_lower = 3
    revlimit_offset_upper = 8
    
    hysteresis = 1
    hysteresis_steps = [0, 1, 5, 25, 50, 100, 250, 500]
    
    log_full_shiftdata = False
    log_basic_shiftdata = True
    we_beep_max = 30 #print previous packets for up to x packets after shift
    
    #as rpm ~ speed, and speed ~ tanh, linear regression + extrapolation 
    #overestimates slope and intercept. Keeping the deque short limits this
    linreg_len_min = 15
    linreg_len_max = 20 
        
    @classmethod
    def get_dict(cls):
        blocklist = ['update', 'get_dict', 'load_from', 'write_to']
        return {k:v for k,v in cls.__dict__.items() 
                                        if k not in blocklist and k[0] != '_'}

    @classmethod
    def load_from(cls, filename):
        if not exists(filename):
            return
        with open(filename) as file:
            file_config = json.load(file)
            for k,v in file_config.items(): 
                if k == 'sound_files': #json saves keys as string, force to int
                    v = {int(key):(value if value[:6] == 'audio/' 
                                   else f'audio/{value}')
                                                  for key, value in v.items()}
                #update old sound location to new audio folder
                if k == 'sound_file' and v[:6] != 'audio/':
                    v = f'audio/{v}'
                    
                setattr(cls, k, v)
    
    @classmethod
    def write_to(cls, filename):
        with open(filename, 'w') as file:
            json.dump(cls.get_dict(), file, indent=4)

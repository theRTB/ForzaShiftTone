# -*- coding: utf-8 -*-
"""
Created on Wed Aug  2 20:36:24 2023

@author: RTB
"""
import json
from os.path import exists

FILENAME_SETTINGS = 'config.json'

class config():
    target_ip = '' #Can be manually set to PS IP to skip automatic detection
    port = 12350 #Exclusive to Forza series
    packet_format = None #Exclusive to Forza series

    #Optional IP-address and port to forward raw packets to
    #TODO: add to GUI Settings
    forward_ipaddress = ''
    forward_port = 33741 #default GT7 port is 33740
    heartbeat_content = 'A' #A or B or ~. Only A works in sports content

    sound_file = 'audio/audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav'
    sound_files = {100:'audio/audiocheck.net_sin_1000Hz_-3dBFS_0.1s.wav',
                    75:'audio/audiocheck.net_sin_1000Hz_-13dBFS_0.1s.wav',
                    50:'audio/audiocheck.net_sin_1000Hz_-23dBFS_0.1s.wav',
                    25:'audio/audiocheck.net_sin_1000Hz_-33dBFS_0.1s.wav' }

    notification_file = 'audio/audiocheck.net_sin_1500Hz_-13dBFS_0.05s.wav'
    notification_file_duration = 0.05 #must equal duration (s) of audio file
    notification_gear_enabled = True
    notification_gear_count = 2
    notification_gear_delay = 0.06
    notification_power_enabled = True
    notification_power_count = 3
    notification_power_delay = 0.08

    volume = 75 #default volume

    #Optional keepalive function. Bluetooth has a tendency to go into power
    #saving when there is no sound being played. Hence we loop a sound to avoid
    #this. If we don't, most beeps don't play or are seriously delayed.
    #duration is the duration of the sound_files, we use this as delay between
    #playing the beep and restarting the keepalive loop
    #delay is the delay between triggers of playing the keepalive sound
    bluetooth_keepalive = False
    bluetooth_keepalive_file = "audio/audiocheck.net_sin_100Hz_-72dBFS_2s.wav"
    bluetooth_keepalive_duration = 0.2
    bluetooth_keepalive_delay = 1.5

    window_scalar = 1 #scale window by this factor
    window_x = None
    window_y = None

    #initial revlimit = engine_limit - guess
    #distance between engine_limit and revlimit has not been investigated for
    #GT7, so disabled due to having little to no benefit anyway
    revlimit_guess = -1

    beep_counter_max = 30 #minimum number of frames between beeps = 0.5ms
    beep_rpm_pct = 0.75 #counter resets below this percentage of beep rpm
    min_throttle_for_beep = 255 #only test if at or above throttle amount

    dynamictoneoffset = 1 #1 is true, 0 is false
    tone_offset = 17 #if specified rpm predicted to be hit in x packets: beep
    tone_offset_lower =  6
    tone_offset_upper = 30
    tone_offset_outlier = 36 #discard for dynamic tone if above this distance

    revlimit_percent = 0.98 #respected rev limit for trigger revlimit as pct%
    revlimit_percent_lower = 0.900
    revlimit_percent_upper = 0.999 #only meant to display the full graph

    revlimit_offset = 6 #additional buffer in x packets for revlimit
    revlimit_offset_lower = 3
    revlimit_offset_upper = 10

    hysteresis_percent = 0.005
    hysteresis_percent_lower = 0.00
    hysteresis_percent_upper = 0.051 #up to 0.05

    #TODO: confirm if shiftdump covers this data as well
    log_full_shiftdata = False
    log_basic_shiftdata = True
    we_beep_max = 30 #print previous packets for up to x packets after shift

    runcollector_minlen = 30
    runcollector_minlen_lock = 180
    #first few points are a ramp up to proper power, so they can negatively
    #affect shift rpm calculations slightly
    runcollector_remove_initial = 5
    #power curve has a minimum boost of 50% of maximum boost
    #points below this will be discarded
    runcollector_pct_lower_limit_boost = .5

    #as rpm ~ speed, and speed ~ tanh, linear regression + extrapolation
    #overestimates slope and intercept. Keeping the deque short limits this
    linreg_len_min = 15
    linreg_len_max = 20

    #draw underfill of >=x% of peak power in the power graph
    graph_power_percentile = 0.9

    #TODO: are these still in use?
    revlimit_round = 50
    revlimit_round_offset = 10

    #round displayed shift RPM in GUI up to nearest x
    shiftrpm_round = 50

    #determine if cars_on_track is considered or not when testing to skip loop
    includereplay = False

    #bop_curve_toggle True is: load Gr. cars, SF19/23, RB2019 curves
    #if stock_curve_toggle True, load non-group cars as well
    #Stock overrules bop
    bop_curve_toggle = True
    stock_curve_toggle = False

    #toggle to place import graph button in GUI
    import_graph_button = False

    #toggle to place speed stats button in GUI and whether loop function runs
    speed_stats_active = False
    speedstats_do_print = 'normal'

    #toggle to place shift stats button in GUI and whether loop function runs
    shift_stats_active = False

    #toggle to place fuel stats button in GUI and whether loop function runs
    fuel_stats_active = False

    #ForzaGUI only: delete curve if user presses the reset button
    delete_curve_on_reset_button = False

    #Allow user to override shift RPM value in GUI
    allow_override_shiftrpm = False

    @classmethod
    def get_dict(cls):
        blocklist = ['update', 'get_dict', 'load_from', 'write_to']
        return {k:v for k,v in cls.__dict__.items()
                                        if k not in blocklist and k[0] != '_'}

    @classmethod
    def load_from(cls, filename):
        if not exists(filename):
            print(f'File {filename} does not exist')
            return
        with open(filename) as file:
            file_config = json.load(file)
            for k,v in file_config.items():
                #json saves keys as string, force to int
                if k in ['sound_files', 'bluetooth_keepalive_sound_files']:
                    v = {int(key):(value if value[:6] == 'audio/'
                                   else f'audio/{value}')
                                                  for key, value in v.items()}
                #update old sound location to new audio folder
                #TODO: remove
                if k == 'sound_file' and v[:6] != 'audio/':
                    v = f'audio/{v}'

                setattr(cls, k, v)

    @classmethod
    def write_to(cls, filename):
        with open(filename, 'w') as file:
            json.dump(cls.get_dict(), file, indent=4)

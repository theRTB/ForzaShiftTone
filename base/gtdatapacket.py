# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 21:21:57 2024

@author: RTB
"""

import struct

from salsa20 import Salsa20_xor

#Alternatives for packet data:
# https://github.com/cybercic/GT7toMoTeC/blob/main/stm/gt7/packet.py
# https://github.com/RaceCrewAI/gt-telem/blob/main/gt_telem/models/telemetry.py
# https://github.com/Bornhall/gt7telemetry/blob/main/gt7telemetry.py
# https://github.com/snipem/gt7dashboard/blob/main/gt7dashboard/gt7communication.py

#For our purposes we only need a small number of variables from the packet
class GTDataPacket():
    FLAGNAMES = ['cars_on_track', 'paused', 'loading', 'in_gear', 'turbo',
                 'overrev', 'handbrake', 'lights_active', 'high_beams', 
                 'low_beams', 'asm_active', 'tcs_active', 
                 'unknown1', 'unknown2', 'unknown3', 'unknown4']
    PROPS = ['position_x', 'position_y', 'position_z', 
             'upshift_rpm', 'engine_max_rpm', 'gear', 'throttle', 'brake', 
             'clutch', 'clutch_in', 'clutch_rpm', 'current_engine_rpm', 'speed', 
             'gears', 'packet_id']
    def __init__(self, data):
        ddata = GTDataPacket.decrypt(data)
        self.ddata = ddata
        if not len(ddata):
            print("Packet did not pass magic number check")
            return
        # print("".join("{:02x}".format(ord(c)) for c in rawdata))

        self.position_x = struct.unpack('f', ddata[0x04:0x04 + 4])[0]  # pos X
        self.position_y = struct.unpack('f', ddata[0x08:0x08 + 4])[0]  # pos Y
        self.position_z = struct.unpack('f', ddata[0x0C:0x0C + 4])[0]  # pos Z
        
        self.current_engine_rpm = struct.unpack('f', ddata[0x3C:0x3C + 4])[0]  # rpm        
        self.speed = struct.unpack('f', ddata[0x4C:0x4C + 4])[0]
        
        self.boost = struct.unpack('f', ddata[0x50:0x50+4])[0] #no -1
        
        self.packet_id = struct.unpack('i', ddata[0x70:0x70 + 4])[0]
            
        self.upshift_rpm = struct.unpack('H', ddata[0x88:0x88 + 2])[0]  # rpm rev warning
        self.engine_max_rpm = struct.unpack('H', ddata[0x8A:0x8A + 2])[0]
        
        flags = struct.unpack('B', ddata[0x8E:0x8E + 1])[0]
        for i, varname in enumerate(self.FLAGNAMES):
            flag = bool(1<<i & flags)
            setattr(self, f'{varname}', flag)
            
        self.gear = struct.unpack('B', ddata[0x90:0x90 + 1])[0] & 0b00001111
        self.throttle = struct.unpack('B', ddata[0x91:0x91 + 1])[0]  # throttle 
        self.brake = struct.unpack('B', ddata[0x92:0x92 + 1])[0] 
        
        self.clutch = struct.unpack('f', ddata[0xF4:0xF4 + 4])[0]  # clutch
        self.clutch_in = struct.unpack('f', ddata[0xF8:0xF8 + 4])[0]  # clutch
        self.clutch_rpm = struct.unpack('f', ddata[0xFC:0xFC + 4])[0]  # clutch
                
        #final gear at 0x100?
        
        #None as gear 0 for a 1:1 mapping for gear number
        gears = list(struct.unpack('8f', ddata[0x104:0x124]))
        self.gears = [None] + [round(g, 3) for g in gears]
        
        self.car_ordinal = struct.unpack('i', ddata[0x124:0x124 + 4])[0]
    
    def print(self):
        print(self.ddata)
    
    def get_props(self):
        # flags = [self.get_flag(name) for name in self.FLAGNAMES]
        # props = [(name, getattr(self, name)) for name in self.PROPS]
        # flagnames = [f'{name}' for name in self.FLAGNAMES]
        return self.FLAGNAMES + self.PROPS
    
    #From https://github.com/snipem/gt7dashboard/blob/main/gt7dashboard/gt7communication.py
    @staticmethod
    def decrypt(dat):
        KEY = b'Simulator Interface Packet GT7 ver 0.0'
        oiv = dat[0x40:0x44]
        iv1 = int.from_bytes(oiv, byteorder='little')
        iv2 = iv1 ^ 0xDEADBEAF 
        IV = bytearray()
        IV.extend(iv2.to_bytes(4, 'little'))
        IV.extend(iv1.to_bytes(4, 'little'))
        ddata = Salsa20_xor(dat, bytes(IV), KEY[0:32])
    
        #check magic number
        magic = int.from_bytes(ddata[0:4], byteorder='little')
        if magic != 0x47375330:
            return bytearray(b'')
        return ddata
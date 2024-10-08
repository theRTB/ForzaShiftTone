#!/usr/env/python
# -*- coding: utf-8 -*-
'''
Python class for Forza Motorsport 7's data stream format.

Copyright (c) 2018 Morten Wang

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
'''

from struct import unpack, pack, calcsize

## Documentation of the packet format is available on
#https://support.forzamotorsport.net/hc/en-us/articles/21742934024211-Forza-Motorsport-Data-Out-Documentation

'''
TODO: update fdp.py with:
First 4bytes of hznUnk is int

    case 11: return “Modern Super Cars”;
    case 12: return “Retro Super Cars”;
    case 13: return “Hyper Cars”;
    case 14: return “Retro Saloons”;
    case 16: return “Vans & Utility”;
    case 17: return “Retro Sports Cars”;
    case 18: return “Modern Sports Cars”;
    case 19: return “Super Saloons”;
    case 20: return “Classic Racers”;
    case 21: return “Cult Cars”;
    case 22: return “Rare Classics”;
    case 25: return “Super Hot Hatch”;
    case 29: return “Rods & Customs”;
    case 30: return “Retro Muscle”;
    case 31: return “Modern Muscle”;
    case 32: return “Retro Rally”;
    case 33: return “Classic Rally”;
    case 34: return “Rally Monsters”;
    case 35: return “Modern Rally”;
    case 36: return “GT Cars”;
    case 37: return “Super GT”;
    case 38: return “Extreme Offroad”;
    case 39: return “Sports Utility Heroes”;
    case 40: return “Offroad”;
    case 41: return “Offroad Buggies”;
    case 42: return “Classic Sports Cars”;
    case 43: return “Track Toys”;
    case 44: return “Vintage Racers”;
    case 45: return “Trucks”;
'''

class ForzaDataPacket:
    ## Class variables are the specification of the format and the names of all
    ## the properties found in the data packet.

    ## Format string that allows unpack to process the data bytestream
    ## for the V1 format called 'sled'
    sled_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiii'

    ## Format string for the V2 format called 'car dash'
    dash_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiifffffffffffffffffHBBBBBBbbb'
    
    ## Format string for the FH4 (to be determined) format
    ## Format string for the FH5 format, final byte is unknown
    ## first int related to car category, two? ints related to hitting objects
    fh4_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiiiiifffffffffffffffffHBBBBBBbbb'
    fh5_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiiiiifffffffffffffffffHBBBBBBbbbb'

    ## Format string for the FM8 format
    ## 20 bytes after the regular dash structure, unknown data
    ## TODO: tire wear FL FR RL RR in float, S32 TrackOrdinal
    fm8_format = '<iIfffffffffffffffffffffffffffffffffffffffffffffffffffiiiiifffffffffffffffffHBBBBBBbbb5i'

    #create lookup table for packet structure detection by packet size
    lookup_format = { calcsize(s):f for s,f in [(sled_format, 'sled'), 
                                                (dash_format, 'dash'), 
                                                (fh4_format, 'fh4'), 
                                                (fh5_format, 'fh5'), 
                                                (fm8_format, 'fm8')] }

    ## Names of the properties in the order they're featured in the packet:
    sled_props = [
        'is_race_on', 'timestamp_ms',
        'engine_max_rpm', 'engine_idle_rpm', 'current_engine_rpm',
        'acceleration_x', 'acceleration_y', 'acceleration_z',
        'velocity_x', 'velocity_y', 'velocity_z',
        'angular_velocity_x', 'angular_velocity_y', 'angular_velocity_z',
        'yaw', 'pitch', 'roll',
        'norm_suspension_travel_FL', 'norm_suspension_travel_FR',
        'norm_suspension_travel_RL', 'norm_suspension_travel_RR',
        'tire_slip_ratio_FL', 'tire_slip_ratio_FR',
        'tire_slip_ratio_RL', 'tire_slip_ratio_RR',
        'wheel_rotation_speed_FL', 'wheel_rotation_speed_FR',
        'wheel_rotation_speed_RL', 'wheel_rotation_speed_RR',
        'wheel_on_rumble_strip_FL', 'wheel_on_rumble_strip_FR',
        'wheel_on_rumble_strip_RL', 'wheel_on_rumble_strip_RR',
        'wheel_in_puddle_FL', 'wheel_in_puddle_FR',
        'wheel_in_puddle_RL', 'wheel_in_puddle_RR',
        'surface_rumble_FL', 'surface_rumble_FR',
        'surface_rumble_RL', 'surface_rumble_RR',
        'tire_slip_angle_FL', 'tire_slip_angle_FR',
        'tire_slip_angle_RL', 'tire_slip_angle_RR',
        'tire_combined_slip_FL', 'tire_combined_slip_FR',
        'tire_combined_slip_RL', 'tire_combined_slip_RR',
        'suspension_travel_meters_FL', 'suspension_travel_meters_FR',
        'suspension_travel_meters_RL', 'suspension_travel_meters_RR',
        'car_ordinal', 'car_class', 'car_performance_index',
        'drivetrain_type', 'num_cylinders'
    ]

    ## The additional props added in the 'car dash' format
    dash_props = ['position_x', 'position_y', 'position_z',
                  'speed', 'power', 'torque',
                  'tire_temp_FL', 'tire_temp_FR',
                  'tire_temp_RL', 'tire_temp_RR',
                  'boost', 'fuel', 'dist_traveled',
                  'best_lap_time', 'last_lap_time',
                  'cur_lap_time', 'cur_race_time',
                  'lap_no', 'race_pos',
                  'accel', 'brake', 'clutch', 'handbrake',
                  'gear', 'steer',
                  'norm_driving_line', 'norm_ai_brake_diff']

    def __init__(self, data, packet_format=None):
        ## The format this data packet was created with, or determine format
        ## through packet size if the format is not defined
        if packet_format is None:
            packet_format = self.lookup_format.get(len(data), 'dash')
        self.packet_format = packet_format

        ## zip makes for convenient flexibility when mapping names to
        ## values in the data packet:
        if packet_format == 'sled':
            for prop_name, prop_value in zip(self.sled_props,
                                             unpack(self.sled_format, data)):
                setattr(self, prop_name, prop_value)
        elif packet_format == 'fh4' or packet_format == 'fh5':
            patched_data = data[:232] + data[244:323]
            for prop_name, prop_value in zip(self.sled_props + self.dash_props,
                                             unpack(self.dash_format,
                                                    patched_data)):
                setattr(self, prop_name, prop_value)
        elif packet_format == 'fm8':
            patched_data = data[:311]
            for prop_name, prop_value in zip(self.sled_props + self.dash_props,
                                             unpack(self.dash_format,
                                                    patched_data)):
                setattr(self, prop_name, prop_value)
        else:
            for prop_name, prop_value in zip(self.sled_props + self.dash_props,
                                             unpack(self.dash_format, data)):
                setattr(self, prop_name, prop_value)

    #convert fdp back into packet
    @classmethod
    def to_packet(cls, fdp):
        props = fdp.to_list(None)
        if fdp.packet_format == 'sled':
            return pack(cls.sled_format, *props)
        elif fdp.packet_format == 'fh4':
            props = (props[:len(cls.sled_props)] + [0] * 3 + 
                                     props[-len(cls.dash_props):])
            return pack(cls.fh4_format, *props)
        else:
            return pack(cls.dash_format, *props)

    @classmethod
    def get_props(cls, packet_format = 'dash'):
        '''
        Return the list of properties in the data packet, in order.

        :param packet_format: which packet format to get properties for,
                              one of either 'sled' or 'dash'
        :type packet_format: str
        '''
        if packet_format == 'sled':
            return(cls.sled_props)

        return(cls.sled_props + cls.dash_props)

    def to_list(self, attributes):
        '''
        Return the values of this data packet, in order. If a list of
        attributes are provided, only return those.

        :param attributes: the attributes to return
        :type attributes: list
        '''
        if attributes:
            return([getattr(self, a) for a in attributes])

        if self.packet_format == 'sled':
            return([getattr(self, prop_name) for prop_name in self.sled_props])

        return([getattr(self, prop_name) for prop_name in \
                self.sled_props + self.dash_props])

    def get_format(self):
        '''
        Return the format this packet was sent with.
        '''
        return(self.packet_format)

    def get_tsv_header(self):
        '''
        Return a tab-separated string with the names of all properties in the order defined in the data packet.
        '''
        if self.packet_format == 'sled':
            return('\t'.join(self.sled_props))

        return('\t'.join(self.sled_props + self.dash_props))

    def to_tsv(self):
        '''
        Return a tab-separated values string with all data in the given order.
        All floating point numbers are defined as such to allow for changing
        the number of significant digits if desired.
        '''
        if self.packet_format == 'sled':
            return('{0.is_race_on}\t{0.timestamp_ms}\t{0.engine_max_rpm:f}\t{0.engine_idle_rpm:f}\t{0.current_engine_rpm:f}\t{0.acceleration_x:f}\t{0.acceleration_y:f}\t{0.acceleration_z:f}\t{0.velocity_x:f}\t{0.velocity_y:f}\t{0.velocity_z:f}\t{0.angular_velocity_x:f}\t{0.angular_velocity_y:f}\t{0.angular_velocity_z:f}\t{0.yaw:f}\t{0.pitch:f}\t{0.roll:f}\t{0.norm_suspension_travel_FL:f}\t{0.norm_suspension_travel_FR:f}\t{0.norm_suspension_travel_RL:f}\t{0.norm_suspension_travel_RR:f}\t{0.tire_slip_ratio_FL:f}\t{0.tire_slip_ratio_FR:f}\t{0.tire_slip_ratio_RL:f}\t{0.tire_slip_ratio_RR:f}\t{0.wheel_rotation_speed_FL:f}\t{0.wheel_rotation_speed_FR:f}\t{0.wheel_rotation_speed_RL:f}\t{0.wheel_rotation_speed_RR:f}\t{0.wheel_on_rumble_strip_FL:f}\t{0.wheel_on_rumble_strip_FR:f}\t{0.wheel_on_rumble_strip_RL:f}\t{0.wheel_on_rumble_strip_RR:f}\t{0.wheel_in_puddle_FL:f}\t{0.wheel_in_puddle_FR:f}\t{0.wheel_in_puddle_RL:f}\t{0.wheel_in_puddle_RR:f}\t{0.surface_rumble_FL:f}\t{0.surface_rumble_FR:f}\t{0.surface_rumble_RL:f}\t{0.surface_rumble_RR:f}\t{0.tire_slip_angle_FL:f}\t{0.tire_slip_angle_FR:f}\t{0.tire_slip_angle_RL:f}\t{0.tire_slip_angle_RR:f}\t{0.tire_combined_slip_FL:f}\t{0.tire_combined_slip_FR:f}\t{0.tire_combined_slip_RL:f}\t{0.tire_combined_slip_RR:f}\t{0.suspension_travel_meters_FL:f}\t{0.suspension_travel_meters_FR:f}\t{0.suspension_travel_meters_RL:f}\t{0.suspension_travel_meters_RR:f}\t{0.car_ordinal}\t{0.car_class}\t{0.car_performance_index}\t{0.drivetrain_type}\t{0.num_cylinders}'.format(self))

        return('{0.is_race_on}\t{0.timestamp_ms}\t{0.engine_max_rpm:f}\t{0.engine_idle_rpm:f}\t{0.current_engine_rpm:f}\t{0.acceleration_x:f}\t{0.acceleration_y:f}\t{0.acceleration_z:f}\t{0.velocity_x:f}\t{0.velocity_y:f}\t{0.velocity_z:f}\t{0.angular_velocity_x:f}\t{0.angular_velocity_y:f}\t{0.angular_velocity_z:f}\t{0.yaw:f}\t{0.pitch:f}\t{0.roll:f}\t{0.norm_suspension_travel_FL:f}\t{0.norm_suspension_travel_FR:f}\t{0.norm_suspension_travel_RL:f}\t{0.norm_suspension_travel_RR:f}\t{0.tire_slip_ratio_FL:f}\t{0.tire_slip_ratio_FR:f}\t{0.tire_slip_ratio_RL:f}\t{0.tire_slip_ratio_RR:f}\t{0.wheel_rotation_speed_FL:f}\t{0.wheel_rotation_speed_FR:f}\t{0.wheel_rotation_speed_RL:f}\t{0.wheel_rotation_speed_RR:f}\t{0.wheel_on_rumble_strip_FL:f}\t{0.wheel_on_rumble_strip_FR:f}\t{0.wheel_on_rumble_strip_RL:f}\t{0.wheel_on_rumble_strip_RR:f}\t{0.wheel_in_puddle_FL:f}\t{0.wheel_in_puddle_FR:f}\t{0.wheel_in_puddle_RL:f}\t{0.wheel_in_puddle_RR:f}\t{0.surface_rumble_FL:f}\t{0.surface_rumble_FR:f}\t{0.surface_rumble_RL:f}\t{0.surface_rumble_RR:f}\t{0.tire_slip_angle_FL:f}\t{0.tire_slip_angle_FR:f}\t{0.tire_slip_angle_RL:f}\t{0.tire_slip_angle_RR:f}\t{0.tire_combined_slip_FL:f}\t{0.tire_combined_slip_FR:f}\t{0.tire_combined_slip_RL:f}\t{0.tire_combined_slip_RR:f}\t{0.suspension_travel_meters_FL:f}\t{0.suspension_travel_meters_FR:f}\t{0.suspension_travel_meters_RL:f}\t{0.suspension_travel_meters_RR:f}\t{0.car_ordinal}\t{0.car_class}\t{0.car_performance_index}\t{0.drivetrain_type}\t{0.num_cylinders}\t{0.position_x}\t{0.position_y}\t{0.position_z}\t{0.speed}\t{0.power}\t{0.torque}\t{0.tire_temp_FL}\t{0.tire_temp_FR}\t{0.tire_temp_RL}\t{0.tire_temp_RR}\t{0.boost}\t{0.fuel}\t{0.dist_traveled}\t{0.best_lap_time}\t{0.last_lap_time}\t{0.cur_lap_time}\t{0.cur_race_time}\t{0.lap_no}\t{0.race_pos}\t{0.accel}\t{0.brake}\t{0.clutch}\t{0.handbrake}\t{0.gear}\t{0.steer}\t{0.norm_driving_line}\t{0.norm_ai_brake_diff}'.format(self))
    
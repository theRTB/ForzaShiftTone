# -*- coding: utf-8 -*-
"""
Created on Sun Jul 21 13:53:13 2024

@author: RTB
"""

import json
from os.path import exists

from utility import Variable

#FM8 car list
#https://forums.forza.net/t/data-out-feature-in-forza-motorsport/651333/2
#https://github.com/bluemanos/forza-motorsport-car-track-ordinal/tree/master/fm8
#ordinals are unique across the Forza games
#TODO: FH car list
    
class CarData():
    FILENAME_CAR = 'database\cars_keys.json'
    
    if exists(FILENAME_CAR):
        with open(FILENAME_CAR) as raw:
            cardata = {int(key):value for key, value in json.load(raw).items()}
    else:
        print(f'file {FILENAME_CAR} not found')
        cardata = {}
    
    @classmethod
    def get_name(cls, car_ordinal):
        car = cls.cardata.get(car_ordinal, None)
        if car is None:
            return f'Unknown car (o{car_ordinal})'
        return f'{car["Make"]} {car["Model"]} {car["Year"]} (id{car_ordinal})'
        
class CarOrdinal(Variable):
    def test(self, value):
        if self.get() != value:
            return True
        return False

    def get_name(self):
        return CarData.get_name(self.get())
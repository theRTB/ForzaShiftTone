# -*- coding: utf-8 -*-
"""
Created on Sun Jul 21 13:53:13 2024

@author: RTB
"""
import csv
from os.path import exists

from utility import Variable

#delimiter is comma
#as_integer array of column names to be converted to integer
#index is the column name to use as key
def load_csv(filename, index, as_integer=[]):
    data = {}
    if not exists(filename):
        print(f'file {filename} does not exist')
        return None
    
    with open(filename, encoding='ISO-8859-1') as rawcsv:
        csvobject = csv.DictReader(rawcsv, delimiter=',')
        for row in csvobject:
            if row[index] == '':
                print(f'missing ordinal: {row}')
                continue
            for k, v in row.items():
                row[k] = int(v) if (k in as_integer and v != '') else v
            data[row[index]] = row
    return data
    
class CarData():
    FILENAME_CAR = 'database\cars.csv'
    FILENAME_MAKER = 'database\maker.csv'
    AS_INTEGER = ['ID', 'Maker']
    INDEX = 'ID'
    
    cardata = load_csv(FILENAME_CAR, INDEX, AS_INTEGER)
    makerdata = load_csv(FILENAME_MAKER, INDEX, AS_INTEGER)
    
    @classmethod
    def get_name(cls, car_ordinal):
        car = cls.cardata.get(car_ordinal, None)
        if car is None:
            return f'Unknown car (o{car_ordinal})'
        name = car['ShortName']
        maker_id = car['Maker']
        maker = cls.makerdata.get(maker_id, {}).get('Name', 'UNKNOWN')
        return f'{maker} {name} (o{car_ordinal})'
        
class CarOrdinal(Variable):
    def test(self, value):
        if self.get() != value:
            return True
        return False
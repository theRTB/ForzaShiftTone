# -*- coding: utf-8 -*-
"""
Created on Sat Jul 20 15:15:00 2024

@author: RTB
"""

from collections import deque

#in ForzaBeep init_vars: self.shiftdump = ShiftDump(self.lookahead)
#in ForzaBeep loop_func funcs:  'loop_shiftdump',        #dump shift data
#in ForzaBeep functions:
    # def loop_shiftdump(self, fdp):
    #     self.shiftdump.update(fdp)

#maxlen preferred even
class ShiftDump():
    fdp_props = ['current_engine_rpm', 'accel', 'clutch', 
                  'boost', 'gear', 'power']
    columns = ['rpm', 'throttle', 'clutch', 'boost', 
               'gear', 'power', 'slope', 'intercept', 'num']
    def __init__(self, lookahead, maxlen=120):
        self.deque = deque(maxlen=maxlen)
        
        self.counter = -1
        self.halfpoint = int(maxlen/2)
        
        self.lookahead = lookahead
    
    def make_point(self, fdp):
        data = {prop:getattr(fdp, prop) for prop in self.fdp_props}
        data['slope'] = self.lookahead.slope
        data['intercept'] = self.lookahead.intercept
        data['power'] /= 1000
        
        for key in ['slope', 'intercept']:
            data[key] = 0 if data[key] is None else data[key]
        for key in ['current_engine_rpm', 'intercept']:
            data[key] = int(data[key])
        for key in ['boost', 'power']:
            data[key] = round(data[key], 1)
        for key in ['clutch', 'slope']:
            data[key] = round(data[key], 2)
        
        return data

    #do not display gear
    def point_tostring(self, point):
        zipped = zip(self.columns, 
                     (self.fdp_props + ['slope', 'intercept']))
        array = [f'{point[p]:>{len(c)+3}}' for c,p in zipped]
        
        return ''.join(array)
    
    def update(self, fdp):
        #If gear number has increased, we have upshifted: start timer
        if (len(self.deque) > 0 and 
            fdp.gear > self.deque[-1]['gear']):
            self.counter = self.halfpoint
            
        #at maximum data point (gear change halfway deque), dump data and reset
        if self.counter == 0:
            self.dump()
            self.reset()
        elif self.counter > 0:
            self.counter -= 1
        
        point = self.make_point(fdp)
        self.deque.append(point)

    def header_tostring(self):
        return ''.join([f'{c:>{len(c)+2}}' for c in self.columns])

    def dump(self):
        print(self.header_tostring())
        for i, point in enumerate(self.deque):
            print(self.point_tostring(point), f'{i:>{3+2}}')
    
    def reset(self):
        self.deque.clear()
        self.counter = -1
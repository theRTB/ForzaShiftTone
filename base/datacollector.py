# -*- coding: utf-8 -*-
"""
Created on Mon Mar 18 21:26:19 2024

@author: RTB
"""
import numpy as np

from utility import rolling_avg, PowerCurve

#can be initialized from a Curve or an array of ForzaDataPacket
#TODO: rename to something like ForzaDPNPArray?
class Curve ():
    def __init__(self, packets):
        if type(packets) == list:
            packets = sorted(packets, key=lambda p: p.packet_id)
            if len(packets) != packets[-1].packet_id - packets[0].packet_id +1:
                print("Curve warning: missing packets")
            self.gear = packets[0].gear
            self.props = packets[0].get_props()
        else:
            self.gear = packets.gear
            self.props = packets.get_props()

        for prop in self.props:
            array = np.array([getattr(p, prop) for p in packets])
            setattr(self, prop, array)

        #aliases
        # self.rpm = self.current_current_engine_rpm #FM8

    def get_props(self):
        return self.props

#Expands on the packet array of Curve by adding a velocity, accel and rpm array
#Class provides a box_pts variable which applies a rolling average to only
#velocity before taking the derivative for acceleration. (multi)_rolling_avg
#can be called to re-apply a different rolling average, or array of
#consecutively applied rolling averages.
#Reason for consecutive is that some cars oscillate heavily every other packet
#such as the Bugatti VGT. The only way to smooth these is to start with a
#rolling average of 3.
#overflow in the case of a dragrun, which has OVERFLOW points past revlimit
#overflow currently non-functional, don't use
#box_pts 1 = no smoothing of v, t and a arrays
class VTACurve(Curve):
    TICRATE = 60 #hardcoded tic rate of 60. This holds for most games.
    def __init__(self, packets, overflow=0, box_pts=1):
        super().__init__(packets)
        self.overflow = overflow

        if overflow > 0:
            print("WARNING: OVERFLOW NOT WORKING ATM")

        self.revlimit = int(max(self.current_engine_rpm))

        #initialize rpm v t and a variables without smoothing
        self.rolling_avg(box_pts)

    #box_pts must be uneven
    def rolling_avg(self, box_pts):
        self.multi_rolling_avg([box_pts])

    #resets v and rpm to default then applies the rolling averages
    def multi_rolling_avg(self, box_pts_array):
        self.v = self.speed.copy()
        self.rpm = self.current_engine_rpm.copy()
        self.time_id = np.array(self.packet_id) - self.packet_id[0]
        for box_pts in box_pts_array:
            self._rolling_avg(box_pts)

        self.derive_ta()

    def _rolling_avg(self, box_pts):
        if box_pts % 2 == 0:
            print(f'rolling_avg box_pts {box_pts} not uneven, adding one')
            box_pts += 1
        cutoff = box_pts//2

        start = cutoff
        end = len(self.v)-max(cutoff, self.overflow)
        self.rpm = self.rpm[start:end]
        self.time_id = self.time_id[start:end]
        self.v = rolling_avg(self.v, box_pts)

    #derive acceleration from v using the packet numbers as time base
    def derive_ta(self):
        self.t = self.time_id / self.TICRATE
        # self.t2 = np.linspace(0, (len(self.v)-1)/60, len(self.v))
        self.a = np.gradient(self.v, self.t)

    # #assumes the signal is cyclical, this does generally not work well
    # def low_pass_filter(self, bandlimit):
    #     cutoff = math.ceil(self.TICRATE / bandlimit)

    #     start = cutoff
    #     end = len(self.speed)-max(cutoff, self.overflow)

    #     #derive acceleration from speed
    #     self.t = np.linspace(0, (len(self.speed)-1)/self.TICRATE,
    #                           len(self.speed))
    #     self.a = low_pass_filter(np.gradient(self.speed, self.t), bandlimit,
    #                               self.TICRATE)[start:end]
    #     self.v = self.speed.copy()[start:end]
    #     self.rpm = self.current_engine_rpm.copy()[start:end]

#Collect data when car is coasting:
# engine rpm must drop initially (implying we go from revlimit to idle)
# handbrake must have been pressed and released, which also disengages the
# clutch until throttle is pressed: We can measure deceleration from drag now
class GTDragCollector():
    def __init__(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1

        self.MIN_DURATION = 5 #seconds

    def update(self, gtdp):
        if self.state == 'WAIT':
            if (gtdp.clutch == 1.0 and self.prev_rpm > gtdp.current_engine_rpm
                    and gtdp.throttle == 0 and gtdp.brake == 0
                    and not gtdp.handbrake):
                self.state = 'RUN'
                self.gear_collected = gtdp.gear
                print("Collecting drag!")

        if self.state == 'RUN':
          #  print(f"RUN {gtdp.current_current_engine_rpm}, {gtdp.power} {gtdp.accel}")
            if gtdp.handbrake or gtdp.brake > 0:
                print("RUN RESET HANDBRAKE/BRAKE")
                self.reset() #back to WAIT
            elif gtdp.clutch < 1 or gtdp.throttle > 4:
                print(f"RUN STOP {gtdp.clutch} or {gtdp.throttle}")
                self.state = 'TEST'
            else:
                self.run.append(gtdp)

        if self.state == 'TEST':
            if len(self.run) < self.MIN_DURATION*60:
                print(f'RUN RESET UNDER {self.MIN_DURATION} seconds')
                self.reset()
            else:
                self.state = 'PRINT'

        if self.state == 'PRINT':
            print("Dragrun done!")
            self.state = 'DONE'

        self.prev_rpm = gtdp.current_engine_rpm

    def is_run_completed(self):
        return self.state == 'DONE'

    def get_run(self):
        return self.run

    def reset(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.gear_collected = -1

#collects an array of packets at full throttle
#if the user lets go of throttle, changes gear: reset
#revlimit is confirmed by:
    #15 consecutive points under the maximum rpm registered at full throttle
class GTAccelCollector():
    MINLEN = 90
    OVERFLOW = 15 #return x points after peak rpm in curve

    def __init__(self, keep_overflow=True):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.peak_rpm = -1
        self.gear_collected = -1
        self.revlimit_counter = 0

        self.keep_overflow = keep_overflow

    def update(self, gtdp):
        if self.state == 'WAIT':
            if (gtdp.throttle == 255 and gtdp.cars_on_track
                    and self.prev_rpm < gtdp.current_engine_rpm):
                self.state = 'RUN'
                self.gear_collected = gtdp.gear
                print("Collecting accel!")

        if self.state == 'RUN':
            # print(f"RUN {gtdp.current_engine_rpm}")
            if gtdp.throttle < 255:
                # print("RUN RESET")
                self.reset() #back to WAIT
            elif gtdp.current_engine_rpm < self.prev_rpm:
                self.state = 'MAYBE_REVLIMIT'
            else:
                self.run.append(gtdp)

        if self.state == 'MAYBE_REVLIMIT':
            # print(f"MAYBE REVLIMIT {gtdp.current_engine_rpm}")
            if gtdp.throttle < 255:
                self.reset()
            elif gtdp.current_engine_rpm <= self.peak_rpm:
                self.revlimit_counter += 1
                self.run.append(gtdp)
            else:
                self.state = 'RUN'
                self.revlimit_counter = 0
                self.run.append(gtdp)
            if self.revlimit_counter >= self.OVERFLOW:
                self.state = 'TEST'
                if not self.keep_overflow:
                    self.run = self.run[0:-self.OVERFLOW]

        if self.state == 'TEST':
            # print("TEST")
            if len(self.run) < self.MINLEN:
                print(f"TEST FAILS MINLEN TEST: {len(self.run)} vs {self.MINLEN}")
                self.reset()
            elif self.peak_rpm < gtdp.upshift_rpm:
                print("TEST PEAK BELOW UPSHIFT RPM")
                self.reset()
            else:
                self.state = 'DONE'
                print(f"Accelrun done! Peak at {self.peak_rpm:.0f}")

        self.prev_rpm = gtdp.current_engine_rpm
        self.peak_rpm = max(self.peak_rpm, gtdp.current_engine_rpm)

    def is_run_completed(self):
        return self.state == 'DONE'

    def get_revlimit_if_done(self):
        if self.state != 'DONE':
            return None
        return self.run[-1].current_engine_rpm

    def get_run(self):
        return self.run

    def reset(self):
        self.run = []
        self.state = 'WAIT'
        self.prev_rpm = -1
        self.peak_rpm = -1
        self.gear_collected = -1
        self.revlimit_counter = 0

#Main class used to collect for both an accel curve and a drag curve to return
#a power curve. This power curve does not contain absolute power numbers as we
#do not have the weight of the car or the size of the wheels and drivetrain
#losses
#test with is_run_completed if data is available, then call get_curve to get
#the power curve
class DataCollector():
    def __init__(self, config, keep_overflow=False, *args, **kwargs):
        self.runcollector = GTAccelCollector(keep_overflow=keep_overflow)
        self.dragcollector = GTDragCollector()

        self.accelrun = None
        self.dragrun = None

    def loop_dragcollector(self, gtdp):
        self.dragcollector.update(gtdp)
        if not self.dragcollector.is_run_completed():
            return
        if self.dragrun is None:
            self.dragrun = VTACurve(self.dragcollector.get_run())
            print("Drag curve collected!")

    def loop_runcollector(self, gtdp):
        self.runcollector.update(gtdp)
        if not self.runcollector.is_run_completed():
            return
        if self.accelrun is None:
            self.accelrun = VTACurve(self.runcollector.get_run())
            print("Accel curve collected!")

    def is_run_completed(self):
        return (self.accelrun is not None and self.dragrun is not None)

    def update(self, gtdp):
        self.loop_runcollector(gtdp)
        self.loop_dragcollector(gtdp)

    def reset(self):
        self.runcollector.reset()
        self.dragcollector.reset()

        self.accelrun = None
        self.dragrun = None

    def get_data(self):
        return {'accelrun':self.accelrun,
                'dragrun': self.dragrun}

    def get_curve(self):
        return PowerCurve(self.accelrun, self.dragrun)
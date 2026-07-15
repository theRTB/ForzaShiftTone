# ForzaShiftTone

**Calibrated audio tone that indicates when to shift for optimal acceleration in Forza Motorsport / Horizon 4/5/6**

![example v0.90 BMW M5 2018](images/sample-BMW-M5-2018-16-1.png)

## TL;DR to calibrate per car

- Per gear: Drive around on flat tarmac until you hear a double beep
  - Maintain fixed speed if it has trouble locking the gear ratio
- On a flat straight: Hold full throttle starting from low rpm until you hear a triple beep
  - Use a gear with low/no wheelspin but able to hit revlimit before the end of the straight
  - Try again if you hit the rev limiter for several consecutive seconds with no triple beep
- Be aware that false positives exist: not every beep is an upshift.

### Enable Data Out in Forza Motorsport / Forza Horizon 4/5/6

To configure Data Out (remote telemetry) in supported Forza games on Steam for this application: 
- Head to **Settings** -> **HUD & Gameplay** -> scroll down to the bottom (**Gameplay & HUD** in Forza Motorsport)
- Set **Data Out** to _On_, enter _127.0.0.1_ as **Data out IP address** and **Data out IP port** _12350_. You may have to restart the game.
- (Forza Motorsport ONLY): The **Data Out Packet Format** should be set to '_Car Dash_' for 
- The Microsoft Store version may require a 3rd party Loopback Utility
- It is unknown whether the Data Out functions on the consoles at all
  - If it works, enter the IP address of your laptop instead of _127.0.0.1_

## Current release
**ForzaShiftTone.vbs**: to launch the application (Preferred)  
**ForzaShiftTone-debug.bat**: to launch the application with an additional commandline window that shows debug information  
**forzabeep.py**: for python users

# Information below this point is not required for using the shift tone

## Implementation

The Tone Offset is dynamic. The program keeps track of the time between a shift tone and an initiated shift, and modifies the running Tone Offset if the tone is early or late.

There are three triggers for the shift tone:
- **Shift RPM**: The RPM value at which power in the current gear becomes lower than the power in the next gear: the ideal time to upshift. If the application predicts shift RPM is reached in the defined tone offset time, trigger a beep
- **Percentage of revlimit**: Uses the tone offset distance as predicted distance to current RPM hitting the listed percentage of rev limit
  - Example: A rev limit of 7500 and a value of 98.0% triggers a tone if it predicts 7350 RPM will be reached in 283 milliseconds
- **Time distance to revlimit**: uses the tone offset value plus the revlimit ms value as predicted distance to current RPM hitting the defined revlimit. Defaults to 100 milliseconds, which leads to a default prediction distance of 383ms

The delay between beep triggers is currently set to 0.5 seconds. This time-out is shared between the three triggers.  
If you choose to not shift and remain above the trigger RPM, the program will not beep again even if revlimit is hit.

### General display values:

- **Revlimit**: The limit on engine RPM by its own power.
- **Power**: At which RPM peak power is hit. This may not match the in-game value exactly.
- **Tach**: The current RPM value as reported by the telemetry. Updates 30 times per second
- **Car ID**: The internal ID of the car.

### Per gear:

- **Target**: The derived shift RPM value.  
- **Rel. Ratio**: The relative ratio of the gear ratios between two consecutive gears.
Say the next gear has a number of 1.35: It is 35% longer. Peak power is reached at a speed 35% higher, revlimit is reached at a speed 35% higher.
- **Ratio**: The gear ratio of the gear
  - Toggle between Ratio and Rel. Ratio by double clicking the "Ratio" or "Rel. Ratio" label text

### General configuration:

- **Tone offset**: Predicted distance between the beep trigger and the trigger RPM value.
  - This should not be taken as reaction time and minimized. It should be regarded as the time you consistently respond to the tone with the least amount of mental effort. Defaults to 283 ms.
- **Volume**: Adjusts the volume of the beep in four steps total. Each step is about half as loud as the previous, where the second loudest is the default. A value of 0 mutes only the shift beep.
- **Reset button**: If pressed, reset revlimit, power curve and all values for all gears. Configuration values are unchanged. If the UI is unresponsive, restart the application.
- **Start/Stop button**: Stops or starts the loop to collect packets. In short, if button says "Stop" it is running, if it says "Start" the program is not tracking the game's packets and will not beep.
- **Shift history**: Displays a table with the last 10 shifts including target RPM, actual shift RPM, gear and measured offset between beep and shift.
- **View Power Graph**: If enabled and pressed, displays a power graph in a separate window.

In **Settings**:  
- **Hysteresis**: Hysteresis may be set as another layer to smooth RPM. An intermediary RPM value is updated only if the change in RPM is larger than the hysteresis value, which is then used for the shift beep tests. Defaults to 0.5% of maximum engine RPM.
- **Revlimit %**: The respected rev limit in percentage of actual rev limit. This is to create a buffer for transients that could cause the engine to cut out due to hitting actual rev limit. Defaults to 98.0%.
- **Revlimit ms**: The minimum predicted distance to actual rev limit. This is to create a buffer for fast changes in RPM that would otherwise lead to hitting actual rev limit, such as in first gear. Defaults to 100ms.
- **Dynamic Tone Offset**: Enables or disables the dynamic updating of the tone offset.
- **Include replays**: Sets the program to function when game is in a paused state.
- **Bluetooth keepalive**: Defaults to off. Bluetooth devices tend to go into power saving and not play the beep in time or at all. This attempts to force the connection to stay alive by playing silence in-between.
- **Reset button deletes curve**: Defaults to off. If enabled, pressing the reset button deletes the power curve data. Useful if it has bad data, or you have upgraded the car.


## Settings are saved to config.json

The settings are saved to _config.json_ on exit. This includes all the settings, Volume, and window location.
Remote telemetry sends data at 60 packets per second. While defined in milliseconds the offset variables Tone offset and revlimit ms) currently use packet counts in the backend.  
There is one packet per 16.667 milliseconds, approximately.

## Notes and known issues
- Assumptions: Stock or BoP, full throttle, not grip limited, instantaneous shifts
- The default values are arbitrarily chosen and may not suit individual cars or track surface
- (Script only) The socket is not always closed cleanly for no apparent reason: requiring a new console on most consecutive launches
- Application will on rare occasions just crash: related to the UI library and cannot be fixed
- Requires at minimum Python 3.10 (statistics linear regression)
- This program _'works for me'_. If you wish to run this script and there are issues, please report them.






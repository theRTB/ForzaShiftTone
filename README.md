# GT7ShiftTone
It beeps, you shift.

**Windows GUI application to provide a shift tone for Gran Turismo 7.**

![example Subaru WRX STI 2014](images/GUIandPower-4.png)

## On first launch
You will need to find and manually set your console IP address into the UI:
- Find the IP address by going to the PS Settings -> Network -> Connection Status -> View Connection Status -> IPv4 address
- Enter this IPv4 address into the PS IP entry box then hit Start
  - After this, GT7ShiftTone will automatically connect to this address and autostart

## Steps
- Load into Special Route X Time Trial, drive past the first tunnel (with the finish line)
- Straighten the car, apply full throttle in a gear that goes from low/medium RPM to revlimit in a few seconds
- When revlimit is hit twice, briefly press handbrake to disengage the clutch
- Let the car roll for several seconds to 10 seconds (finish before the uphill section)
  - Avoid steering inputs as much as possible, controller is preferable
- Press throttle to finish. You can now go to other races with a shift beep.
- Be aware that false positives exist: not every beep is an upshift.

## Current release
Revised first public version. This program is not yet user friendly.

### Launch with:
- gtbeep.py: For Python users  
- ~~**GT7ShiftTone.vbs**: to launch the application (Preferred, requires ZIP download)~~  
- ~~**GT7ShiftTone-debug.bat**: to launch the application with an additional commandline window that shows debug information (requires ZIP download)~~

Changes:  
- Improved algorithm to derive points on the power curve, especially the final point.
- Displayed shift points are now rounded to the nearest 25. The method used in this program probably isn't even accurate enough for that.
- Power curves are now saved based on the Car ID. They can be modified/created through Excel as well (tab separated file). Default save folder: curves\.

## Implementation

The approach is to get consecutive points of acceleration values across a large range of RPMs up to revlimit. These acceleration values include the acceleration from engine torque minus various resistive forces.  
We derive an effective sum of resistive forces by letting the car coast with the clutch engaged and measure how much the car slows based on GPS speed. We add this back to the acceleration curve to cancel out the drag and this gives us the basic torque curve.  
We use the resulting power curve to derive shift points.

The Tone Offset is dynamic. The program keeps track of the time between a shift tone and an initiated shift, and modifies the running Tone Offset if the tone is early or late.

There are three triggers for the shift tone:
- Shift RPM: The RPM value at which power in the current gear becomes lower than the power in the next gear: the ideal time to upshift. If the application predicts shift RPM is reached in the defined tone offset time, trigger a beep
- Percentage of revlimit: Uses the tone offset distance as predicted distance to current RPM hitting the listed percentage of rev limit
  - Example: A rev limit of 7500 and a value of 98.0% triggers a tone if it predicts 7350 RPM will be reached in 283 milliseconds
- Time distance to revlimit: uses the tone offset value plus the revlimit ms value as predicted distance to current RPM hitting the defined revlimit. Defaults to 100 milliseconds, which leads to a default prediction distance of 383ms

The delay between beep triggers is currently set to 0.5 seconds. This time-out is shared between the three triggers.  
If you choose to not shift and remain above the trigger RPM, the program will not beep again even if revlimit is hit.

### General display values:

- **Revlimit**: The limit on engine RPM by its own power. Revlimit is derived upon finishing a full throttle sweep up to revlimit.
- **Revbar**: The range in which the revbar lights up. It begins at 85% and starts blinking at 99% of a predetermined value, generally equal to the upshift line in the Transmission tuning page but not always
- **Power**: A guesstimate on which RPM peak power is hit. If it matches the in-game value, the power curve is probably quite accurate.
- **Tach**: The current RPM value as reported by the telemetry. Updates 30 times per second.
- **Car ID**: The internal ID of the car. The RPM/Power/Torque table is saved with this ID as filename, for example a car with Car ID 432 will have its data saved to _curves\432.tsv_.

### Per gear:

- **Target**: The derived shift RPM value.  
This requires a power curve (revlimit shows a green background)
- **Rel. Ratio**: The relative ratio of the gear ratios between two consecutive gears.  
If gear 2 has a gear ratio of 2.375 and gear 3 has a gear ratio of 1.761, then the relative ratio is 2.375/1.761 ≈ 1.35: third gear is 35% longer than second gear.
- **Ratio**: The gear ratio of the gear
  - Toggle between Ratio and Rel. Ratio by double clicking the "Ratio" or "Rel. Ratio" label text

### General configuration:

- **Tone offset**: Predicted distance between the beep trigger and the trigger RPM value. This should not be taken as reaction time and minimized. It should be regarded as the time you can consistently respond to the tone with the least amount of mental effort. Defaults to 283 ms.
- **Volume**: Adjusts the volume of the beep in four steps total. Each step is about half as loud as the previous, where the second loudest is the default. A value of 0 mutes only the shift beep.
- **Reset button**: If pressed, reset revlimit, power curve and all values for all gears. Configuration values are unchanged. If the UI is unresponsive, restart the application.
- **Start/Stop button**: Stops or starts the loop to collect packets. In short, if button says "Stop" it is running, if it says "Start" the program is not tracking the game's packets and will not beep.
- **Shift history**: Displays a table with the last 10 shifts including target RPM, actual shift RPM, gear and measured offset between beep and shift.
- **View graphs button**: If enabled and pressed, displays a power graph in a separate window. 

In Settings:  
- **Hysteresis**: Hysteresis may be set as another layer to smooth RPM. An intermediary RPM value is updated only if the change in RPM is larger than the hysteresis value, which is then used for the shift beep tests. Defaults to 0.5% of maximum engine RPM.
- **Revlimit %**: The respected rev limit in percentage of actual rev limit. This is to create a buffer for transients that could cause the engine to cut out due to hitting actual rev limit. Defaults to 98.0%.
- **Revlimit ms**: The minimum predicted distance to actual rev limit. This is to create a buffer for fast changes in RPM that would otherwise lead to hitting actual rev limit, such as in first gear. Defaults to 100ms.
- **Dynamic Tone Offset**: Enables or disables the dynamic updating of the tone offset.
- **Include replays**: Sets the program to function during replays: useful primarily to log shift points in a replay.

## Settings are saved to config.json

The settings are saved to _config.json_ on exit. This includes Tone offset, Hysteresis, Revlimit %, Revlimit ms, Volume, Dynamic Tone Offset and Console IP. The gear ratios are not saved.  
Remote telemetry sends data at 60 packets per second. The offset variables (Tone offset, revlimit ms) while defined in milliseconds currently use packet counts in the backend.  
There is one packet per 16.667 milliseconds, approximately.

## Notes and known issues
- Assumptions: not grip limited, shift duration of 0 and no penalty to power after shifting (aka, a turbo)
- Gear 9 and 10 are never filled in even if the car has them: Limitation of the telemetry and implementation.
- FWD cars can't be measured using controller: Handbrake does not disengage the clutch.
- The Power Restrictor for example affects the shape of the curve: adjustments will not match a saved curve.
  - Output adjustment will maintain the overall shape, so is fine to adjust.
- The default values are arbitrarily chosen and may not suit individual cars or track surface.
- ~~Power values in the graph are percentage-based: GT7 only provides acceleration not power/torque. Cannot be fixed.~~
- Due to noise in the acceleration data it is not always possible to derive at which RPM peak power occurs. It can be off by 100 RPM or more.
- The data is smoothed and will not 100% match the ingame curve which is linear interpolation between points
- Some cars have a harsh drop in power and will not hit revlimit at higher gears (Super Formula '23 for example), complicating data gathering
- Revlimit is marginally above the ingame revlimit in by far most runs. We cannot assume it is a multiple of 100 for non-stock cars so rounding down is out.
- ~~Revlimit is an approximation and is equal to the last highest RPM seen on the full throttle run minus the points smoothed out.~~
- On Windows the socket is not closed cleanly for no apparent reason: requiring a new console on most consecutive launches
- Application will on rare occasions crash: related to the UI library and cannot be fixed
- Linux support is untested
- This program _'works for me'_. If you wish to run this script and there are issues, please report them.

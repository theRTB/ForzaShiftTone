# ForzaBeep
It beeps, you shift.

GUI application to provide a shift tone in Forza Horizon 5. This is the first public version.

To enable remote telemetry in Forza Horizon 5 for this application: 
- Head to Settings -> HUD and Gameplay -> scroll down to the bottom
- Set Data Out to On, enter 127.0.0.1 as Data out IP address and Data out IP port 12350. You may have to restart the game.

While it is intended to run in the background without consideration while driving, there are some requirements to having accurate shift tones:
- One consecutive second of data per gear. After this the gear values will lock and the gear ratio derived to a reasonably accurate degree. Road surfaces are far more accurate than dirt/off-road.
- An unobstructed straight acceleration in a medium gear all the way to rev limit. Rev limit should normally be avoided, but must be hit once for accurate data. Avoid impacts.
- Rev limit can be manually entered or derived from the required run. Defaults to maximum engine rpm minus 750.
- The data is not saved for now. Restarting the application results in a blank state including configuration.

'''TBSE Config File'''
# pylint: skip-file

# General
sessionLength = 1   # Length of session in seconds.
virtualSessionLength = 600  # Number of virtual timesteps per sessionLength.
verbose = False     # Adds additional output for debugging.

# Trader Schedule
# Define number of each algorithm used one side of exchange (buyers or sellers).
# Same values will be used to define other side of exchange (buyers = sellers).
numZIC  = 5
numZIP  = 0
numGDX  = 5
numAA   = 0
numGVWY = 5
numSHVR = 0

# Order Schedule
useOffset = True
stepmode = 'fixed'  # Valid values: 'fixed', 'jittered', 'random'
timemode = 'periodic'   # Valid values: 'periodic', 'drip-fixed', 'drip-jitter', 'drip-poisson'
interval = 30   # Virtual seconds between new set of customer orders being generated. 
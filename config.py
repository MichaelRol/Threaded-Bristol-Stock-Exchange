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

supply = dict(              # Define range of values from which supply orders can be taken.
    rangeMax = dict (       # Maximum price a supply order can take.
        rangeHigh = 200,    # RangeMax value is chosen at random from between these two values.
        rangeLow = 100      # For a fixed schedule set rangeHigh = rangeLow.
    ),
    rangeMin = dict (       # Minimum order a supply order can take.
        rangeHigh = 100,    # RangeMax value is chosen at random from between these two values.
        rangeLow = 0        # For a fixed schedule set rangeHigh = rangeLow.
    )
)

### NOTE: If symmetric = True this schedule is ignored and the demand schedule will equal the above supply schedule.
demand = dict(              # Define range of values from which demand orders can be taken.
    rangeMax = dict (       # Maximum price a demand order can take.
        rangeHigh = 200,    # RangeMax value is chosen at random from between these two values.
        rangeLow = 100      # For a fixed schedule set rangeHigh = rangeLow.
    ),
    rangeMin = dict (       # Minimum order a demand order can take.
        rangeHigh = 100,    # RangeMax value is chosen at random from between these two values.
        rangeLow = 0        # For a fixed schedule set rangeHigh = rangeLow.
    )
)

# For single schedule: using config trader schedule, or command-line trader schedule.
numTrials = 50

# For multiple schedules: using input csv file.
numSchedulesPerRatio = 2     # Number of schedules per ratio of traders in csv file.
numTrialsPerSchedule = 5     # Number of trails per schedule.
symmetric = True             # Should range of supply = range of demand?
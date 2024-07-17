# Declaring variables with a global scope

rhoCp = 8.353535 
W_TO_BTUHR = 3.412142
W_TO_BTUMIN = W_TO_BTUHR/60.
W_TO_TONS = 0.000284345
TONS_TO_KBTUHR = 12.
watt_per_gal_recirc_factor = 100 
KWH_TO_BTU = 3412.14
RECIRC_LOSS_MAX_BTUHR = 1080 * (watt_per_gal_recirc_factor * W_TO_BTUHR)

pCompMinimumRunTime = 10./60.
tmCompMinimumRunTime = 20./60.
thermalStorageSF = 1

norm_mean = 0.7052988591269841 # mean of normalized stream data
norm_std = 0.08236427664525116 # standard deviation of normalized stream data

possibleStandardGPDs = ['ca', 'ashLow', 'ashMed', 'ecoMark']

month_to_hour = {
    0: range(0, 744),         # January
    1: range(744, 1416),       # February
    2: range(1416, 2160),      # March
    3: range(2160, 2880),      # April
    4: range(2880, 3624),      # May
    5: range(3624, 4356),      # June
    6: range(4356, 5088),      # July
    7: range(5088, 5832),      # August
    8: range(5832, 6552),      # September
    9: range(6552, 7296),      # October
    10: range(7296, 8016),     # November
    11: range(8016, 8760)      # December
}

month_to_number_days = {
    0: 31,         # January
    1: 28,       # February
    2: 31,      # March
    3: 30,      # April
    4: 31,      # May
    5: 30,      # June
    6: 31,      # July
    7: 31,      # August
    8: 30,      # September
    9: 31,      # October
    10: 30,     # November
    11: 31      # December
}

max_hour_to_month = {
    744: 0,         # January
    1416: 1,       # February
    2160: 2,      # March
    2880: 3,      # April
    3624: 4,      # May
    4356: 5,      # June
    5088: 6,      # July
    5832: 7,      # August
    6552: 8,      # September
    7296: 9,      # October
    8016: 10,     # November
    8760: 11      # December
}

month_names = ["January","February","March","April","May","June","July","August","September","October","November","December"]
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
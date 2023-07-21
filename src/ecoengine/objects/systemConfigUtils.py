import numpy as np

def roundList(a_list, n=3):
    """
    Rounds elements in a python list

    Parameters
    ----------
    a_list : float
        list to round values of.
    n : int
        optional, default = 3. Number of digits to round elements to.

    Returns
    -------
    list
        rounded values.

    """
    return [round(num, n) for num in a_list]

def checkLiqudWater(var_F):
    """
    Checks if the variable has a temperuter with in the range of liquid water at atm pressure

    Args:
        var_F (float): Temperature of water.

    Returns:
        bool: True if liquid, False if solid or gas.

    """
    if var_F < 32. or var_F > 212.:
        return False
    return True

def mixVolume(vol, hotT, coldT, outT):
    """
    Adjusts the volume of water such that the hotT water and outT water have the
    same amount of energy, meaning different volumes. The returned value is the 
    volume at hotT required.

    Parameters
    ----------
    vol : float
        The reference volume (at outT) to convert.
    hotT : float
        The hot water temperature used for mixing.
    coldT : float
        The cold water tempeature used for mixing.
    outT : float
        The out water temperature from mixing.

    Returns
    -------
    float
        The volume at hotT, which, mixed with water at coldT, will produce the needed volume of water at outT.

    """
    fraction = (outT - coldT) / (hotT - coldT)

    return vol * fraction

def hrToMinList(a_list):
    """
    Repeats each element of a_list 60 times to go from hourly to minute.
    Still may need other unit conversions to get data from per hour to per minute

    Parameters
    ----------
    a_list : list
        A list in of values per hour.

    Returns
    -------
    out_list : list
        A list in of values per minute created by repeating values per hour 60 times.

    """
    out_list = []
    for num in a_list:
        out_list += [num]*60
    return out_list

def hrTo15MinList(a_list):
    """
    Repeats each element of a_list 4 times to go from hourly to 15 minute intervals.
    Still may need other unit conversions to get data from per hour to per 15 minute

    Parameters
    ----------
    a_list : list
        A list in of values per hour.

    Returns
    -------
    out_list : list
        A list in of values per 15 minute interval created by repeating values per hour 4 times.

    """
    out_list = []
    for num in a_list:
        out_list += [num]*4
    return out_list

def getPeakIndices(diff1):
    """
    Finds the points of an array where the values go from positive to negative

    Parameters
    ----------
    diff1 : array_like
        A 1 dimensional array.

    Returns
    -------
    ndarray
        Array of indices in which input array changes from positive to negative
    """
    if not isinstance(diff1, np.ndarray):
        diff1 = np.array(diff1)
    diff1 = np.insert(diff1, 0, 0)
    diff1[diff1==0] = .0001 #Got to catch this error in the algorithm. Damn 0s.
    return np.where(np.diff(np.sign(diff1))<0)[0]

def checkHeatHours(heathours):
    """
    Quick check to see if heating hours is a valid number between 1 and 24

    Parameters
    ----------
    heathours (float or numpy.ndarray)
        The number of hours primary heating equipment can run.
    """
    if isinstance(heathours, np.ndarray):
        if any(heathours > 24) or any(heathours <= 0):
            raise Exception("Heat hours is not within 1 - 24 hours")
    else:
        if heathours > 24 or heathours <= 0:
            raise Exception("Heat hours is not within 1 - 24 hours")
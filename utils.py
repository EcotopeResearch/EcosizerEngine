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
    same amount of energy, meaning different volumes.

    Parameters
    ----------
    vol : float
        The reference volume to convert.
    hotT : float
        The hot water temperature used for mixing.
    coldT : float
        The cold water tempeature used for mixing.
    outT : float
        The out water temperature from mixing.

    Returns
    -------
    float
        Temperature adjusted volume.

    """
    fraction = (outT - coldT) / (hotT - coldT)

    return vol * fraction
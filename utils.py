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
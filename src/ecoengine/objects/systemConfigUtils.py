import numpy as np
from plotly.offline import plot
from plotly.graph_objs import Figure, Scatter

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
    Checks if the variable has a temperature with in the range of liquid water at atm pressure

    Args:
        var_F (float): Temperature of water.

    Returns:
        bool: True if liquid, False if solid or gas.

    """
    if var_F < 32. or var_F > 212.:
        return False
    return True

def convertVolume(originalVol, convertToT_F, referenceT_F, convertFromT_F):
    """
    Adjusts the volume of water such that the hotT water and convertFromT water have the
    same amount of energy, meaning different volumes. The returned value is the 
    volume at hotT that has the same energy as the original volume at convertFromT.

    Parameters
    ----------
    originalVol : float
        The original volume (at convertFromT) to convert.
    convertToT_F : float
        The temperature the volume needs to be converted to.
    referenceT_F : float
        The water tempeature used for reference. i.e. The temperature of water when the energy is 0.
    convertFromT_F : float
        The temperature the originalVol needs to be converted from.

    Returns
    -------
    float
        The volume at hotT, which, mixed with water at coldT, will produce the needed volume of water at outT.

    """
    fraction = (convertFromT_F - referenceT_F) / (convertToT_F - referenceT_F)

    return originalVol * fraction


def getMixedTemp(temp1_F, temp2_F, vol1_G, vol2_G):
        """
        Calculates average tank temperature for a tank with vol1_G gallons of water at temp1_F degrees F and
        vol2_G gallons of water at temp2_F degrees F
        Parameters
        ----------
        temp1_F : float
            Temperature (F) of first volume of water 
        temp2_F : float
            Temperature (F) of second volume of water 
        vol1_G : float
            Volume (gallons) of first temperature (temp1_F) of water
        vol2_G : float
            Volume (gallons) of first temperature (temp2_F) of water
        Returns
        ----------
        mixStorageT_F: float
            Average storage temperature calcuated with normal setpoint and load up setpoint.
        """
        totalVol_G = vol1_G + vol2_G
        f1 = vol1_G/totalVol_G
        f2 = vol2_G/totalVol_G

        return (f1 * temp1_F) + (f2 * temp2_F)

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
        
def createSizingCurvePlot(x, y, startind, loadshifting = False):
    """
    Sub - Function to plot the the x and y curve and create a point (secretly creates all the points)
    """
    fig = Figure()
    
    hovertext = 'Storage Volume: %{x:.1f} gallons \nHeating Capacity: %{y:.1f}' if not loadshifting else 'Load Shift Days Captured: %{x:.1f} % \nStorage Volume: %{y:.1f} gallons' 

    fig.add_trace(Scatter(x=x, y=y,
                    visible=True,
                    line=dict(color="#28a745", width=4),
                    hovertemplate=hovertext,
                    opacity=0.8,
                    ))

    # Add traces for the point, one for each slider step
    for ii in range(len(x)):
        fig.add_trace(Scatter(x=[x[ii]], y=[y[ii]], 
                        visible=False,
                        mode='markers', marker_symbol="diamond", 
                        opacity=1, marker_color="#2EA3F2", marker_size=10,
                        name="System Size",
                        hoverlabel = dict(font=dict(color='white'), bordercolor="white")
                        ))

    # Make the 16 hour trace visible
    fig.data[startind+1].visible = True
    fig.update_layout(title="Primary Sizing Curve",
                    xaxis_title="Primary Tank Volume (Gallons) at Storage Temperature" if not loadshifting else "Percent of Load Shift Captured",
                    yaxis_title="Primary Heating Capacity (kBTU/hr)" if not loadshifting else "Primary Tank Volume (Gallons)",
                    showlegend=False)

    return fig

def createERSizingCurvePlot(x, y, startind):
    """
    Sub - Function to plot the the x and y curve and create a point (secretly creates all the points)
    """
    fig = Figure()
    
    hovertext = 'Percent Coverage : %{x:.1f} % \nER Electric Resistance Heating Capacity: %{y:.1f} kW'

    fig.add_trace(Scatter(x=x, y=y,
                    visible=True,
                    line=dict(color="#28a745", width=4),
                    hovertemplate=hovertext,
                    opacity=0.8,
                    ))

    # Add traces for the point, one for each slider step
    for ii in range(len(x)):
        fig.add_trace(Scatter(x=[x[ii]], y=[y[ii]], 
                        visible=False,
                        mode='markers', marker_symbol="diamond", 
                        opacity=1, marker_color="#2EA3F2", marker_size=10,
                        name="System Size",
                        hoverlabel = dict(font=dict(color='white'), bordercolor="white")
                        ))

    # Make the trace visible
    fig.data[startind+1].visible = True
    fig.update_layout(title="Electric Resistance Sizing Curve",
                    xaxis_title='Percent Coverage (%)',
                    yaxis_title="Electric Resistance Heating Capacity (kW)",
                    showlegend=False)

    return fig
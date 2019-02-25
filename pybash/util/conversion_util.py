# Functions for converting variable types
import pybash.util.pybash_helper as pybash_helper
import pybash.util.pipe_util as pipe_util

def shell_data(var):
    """
    Function to convert a python variable to a format compatible with shell commands
        1. If input is None, return None
        2. If input is a file, return the file
        3. For other types, return pybash_helper.to_str(var)

    Args:
        var: Variable to be converted
    Returns:
        Converted variable
    """
    if var is not None:
        if pipe_util.isfile(var):
            shell_data = var
        else:
            shell_data = pybash_helper.to_str(var)
    else:
        shell_data = None

    return shell_data

def autoconvert(s):
    """
    Utility function for automatically converting strings to booleans, integers or floats.

    Args:
        s (str): String to be converted (e.g. 'True', '1234', '3.14159')

    Returns: bool, int or float if the value could be converted, string if no conversion 
        was found.
    """
    for fn in (pipe_util.to_bool, int, float):
        try:
            return fn(s)
        except ValueError:
            pass
    return s


# Functions for manipulating history

import readline

def remove_history_item(line_number, initial_history_length=None):
    """
    Function to remove an item from the readline history 
    since readline.remove_history_item() is not working

    Args:
        line_number (int): History line that will removed
        initial_history_length (int): The history length recorded at the start of the Pybash session,
            used for history management.  If the removed line was prior to the initial history length, 
            then this needs to be adjusted.
    Returns:
        int: If initial_history_length was provided, the adjusted initial history length is returned
            If not, then None is returned
    """
    
    # Get all history items except for the one at line_number
    hist_len = readline.get_current_history_length()
    new_history = [readline.get_history_item(i) for i in range(1, hist_len) if not i == line_number]

    # Replace history
    readline.clear_history()
    for l in new_history:
        readline.add_history(l)
    
    # If initial_history_length was specified, check to see if it needs to be adjusted
    if initial_history_length:
        if line_number < initial_history_length:
            return initial_history_length - 1
        else:
            return initial_history_length
    else:
        return

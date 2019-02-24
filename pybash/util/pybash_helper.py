"""
This file contains helper functions for the pybash interpreter
These functions can be used in a pipeline to facilitagte moving between bash and python
e.g. "find . | to_list" will get the stdout of "find ." and convert each line to an element in a list

This file will be imported within the interpreters "scope" so that the functions are accessible
when using exec('...', self.globals, self.locals)
"""

import yaml
import readline
import sys
import keyword
    

def function_match(s):
    """
    Function used by pybash to determine if a command is a pybash_helper function
    
    Args:
        s (str): Command string which may contain pybash helper functions
    Returns:
        list: List of functions found in input string
    """
    f_list = ['to_list', 'to_dict', 'to_str', 'from_file', 'to_file']
    found = []
    for f in f_list:
        if f in s:
            found.append(f)
    return found


def python_keyword_match(c):
    """
    Function used by pybash to check if a command is a python keyword
    
    Args:
        c (str): Command which is matched against python keywords
    Returns:
        bool
    """
    return keyword.iskeyword(c)


###################################################################################
# TYPE CONVERSION FUNCTIONS 
def to_list(s, ignore_empty_lines=True):
    """
    Function to convert newline-separated string to a python list.
    
    Args:
        s (str): Input string to convert to list
        ignore_empty_lines (bool): If True, then empty text lines are not included in output list
    Returns:
        list
    """
    if ignore_empty_lines:
        return [y for y in (x.strip() for x in s.splitlines()) if y]
    else:
        return [y for y in (x.strip() for x in s.splitlines())]

def to_dict(s):
    """
    Function to convert a yaml-formatted string to a dict
    
    Args:
        s (str): Input string to convert to dict
    Returns:
        dict
    """

    return yaml.load(s)


def to_str(v, single_line=False):
    """
    Function to convert input variable to string, using special formating for dicts and lists.
    TODO: Add support for json
    
    Args:
        v: input variable to convert to string
        single_line (bool): If this flag is True, the variable will be formatted without newlines. 
            1. Dict: converted to string using yaml.dump()
                a) single_line = True: use default_flow_style=True
                b) single_line = False: use default_flow_style=False
            2. List
                a) single_line = True: Use space character to separate elements (used for bash-like formatting)
                b) single_line = False: Use newline character to separate elements (used for writing to file)
            3. Other variable types: Converted to string using str()
            
    Returns:
        String representation of input variable

    """
    
    if type(v) == dict:
        if single_line:
            return yaml.dump(v, default_flow_style=True).strip()
        else:
            return yaml.dump(v, default_flow_style=False)
    elif type(v) == list:
        if single_line:
            return " ".join([str(s) for s in v])
        else:
            return "\n".join([str(s) for s in v])
    else:
        return(str(v))



###################################################################################
# FILE IO FUNCTIONS

def to_file(f_name, d, mode='w'):
    """
    Function to write a python variable to a file
    
    Args: 
        f_name (str): File path to write to
        d: Python variable to write to file, will be automatically converted to a string for writing
        mode (str): Mode to write the file ('w', 'wb', 'a', 'ab'), default = 'w'
    """
    # Remove whitespace left over from shell commands
    f_name = f_name.strip()
    d_out = to_str(d)
    with open(f_name, mode) as f:
        f.write(d_out)


def from_file(f_name, mode='r'):
    """
    Function to read a file and return the contents as a strting
    
    Args: 
        f_name (str): File path to read from
        mode (str): Mode to read the file ('r', 'rb'), default = 'r'
    """
    # Remove whitespace left over from shell commands
    f_name = f_name.strip()
    with open(f_name, mode) as f:
        return f.read()


###################################################################################
# HISTORY FUNCTIONS

def show_history():
    """
    Function to show the pybash histroy. This function is invoked by the pybash_cmd.do_history(),
    allowing the history to be displayed when the user enters the command: 'history'
    """
    
    for i in range(1, readline.get_current_history_length()):
        sys.stdout.write("%i %s\n" % (i, readline.get_history_item(i)))


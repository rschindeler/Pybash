import os, io
import pybash.util.pybash_helper
from collections import deque
import subprocess
import readline
import sys

# Used for checking if variable is a file
if sys.version_info >= (3, 0):
    import _io

def display_std_pipe(std_pipe):
    """
    Helper function display a pipe with different variable types
    Args:
        std_pipe (list): Pybash standard pipe list
    Returns:
        list: Short display representation of each element of std_pipe.  Files, ints or None elements
            are kept as-is, for others the variable type is returned. This allows the std_pipe to be
            printed in debug messages in a short form (especially if some elements of std_pipe are a str)
    """
    return [x if (isfile(x) or type(x) == int or x is None) else type(x) for x in std_pipe]

def expand_std_pipe(std_pipe, stdin, stdout, stderr, use_pipe=False):
    """
    Function to pick either the std_pipe + stdin/stdout/stderr variables, create pipes and 
    process redirects.
    If std_pipe is defined, then it takes precedence over stdin/stdout/stderr. This allows
    functions to accept either a tuple or individual arguments depending on the use case.

    Args:
        std_pipe (tuple): Containing (stdin,stdout,stderr) as one tuple.
        stdin: File-like object, python variable, subprocess.PIPE, positive integer, or None
        stdout: File-like object, python variable, subprocess.PIPE, positive integer, or None
        stderr: File-like object, python variable, subprocess.PIPE, positive integer, or None
            use_pipe (bool): 
                1. If True: an os.pipe() is created and opened, (read,write) file-like objects
                   are returned as a tuple
                2. If False: a collections.deque object is created, which is used instead of pipes 
                   for python commands

    Special cases for stdin, stdout, stderr:
        1. subprocess.PIPE: a new os.pipe or deque is created (depending on the value of use_pipe).
        2. Positive int: this denotes a redirect. 
           If std_pipe = (stdin,stdout,stderr) and std_pipe[i] is >= 0, then, std_pipe[i] is redirected
           to the pipe or deque located at std_pipe[std_pipe[i]].
           For example: std_pipe = (file_a, file_b, 1), then stderr will be redirected to file_b.

    Returns:
        tuple: Returns (stdin,stdout,stderr) which are all either file-like objects (open file, pipes), 
            python variables (stdin only), or collections.deque objects.  
            
    """
    
    # Validate / fill std_pipe if not provided
    if std_pipe:
        if not len(std_pipe) == 3:
            raise ValueError ("std_pipe must be a 3-element list")
    else:
        std_pipe = [stdin, stdout, stderr]

    # Create pipes / deques for each if they are equal to subprocess.PIPE
    for i in range(3):
        # Process subprocess.PIPE
        #    - shell: create os.pipe() + open file-like object for reading
        #    - python: create a FIFO queue
        if std_pipe[i] == subprocess.PIPE:
            if use_pipe:
                std_pipe[i] = open_pipe()
            else:
                std_pipe[i] = deque()

    # Process redirects (denoted by positive integers)
    for i in range(3):
        if type(std_pipe[i]) == int:
            if std_pipe[i] < 0:
                raise ValueError ("Invalid redirect std_pipe index %i cannot be less than 0" % i)
            std_pipe[i] = std_pipe[std_pipe[i]]

    
    return std_pipe


def open_pipe():
    """
    Function that creates an os.pipe and opens the read / write file handles. This mimics
    what subprocess.Popen() does under-the-hood, but in order to support redirects, it is 
    useful to have the pipe opened before calling subprocess.Popen().

    Ref: https://github.com/python/cpython/blob/master/Lib/subprocess.py

    Returns:
        tuple: Contains the (read, write) file-like objects created by opening the pipe. 
    """
    # Create pipe manually so that redirects can be performed before passing to run_shell_cmd()
    # Create new os.pipe()
    r,w = os.pipe()
    # Open each file handel and return
    #  - use os.fdopen() for the read file object in order to get the same type as 
    #    subprocess.Popen().stdout
    file_object_tuple = (os.fdopen(r), io.open(w, 'wb', -1))
    return file_object_tuple


def fd_assign(file_d_index, mode, val, std_pipe):        
    """
    Function to redirect file descriptor in the std_pipe element specified by file_d_index

    Args:
        file_d_index (int): Index of std_pipe that will be assigned
            0 = stdin, 1 = stdout, 2 = stderr
        mode (str): mode to open the file, either 'r', 'w' or 'a'
        val (str): location that the std_pipe element should be redirected to.
            This can be a file path (e.g. 'foo.txt', or a reference to another file 
            descriptor (e.g. '&1'). If the location is a file, the string is replaced
            with an open file-like object (with the mode specified by mode)
        std_pipe (tuple): Contains the current location of (stdin, stdout, stderr)

    """
    
    # Check to see if val refers to another file descriptor
    if type(val) == str and '&' in val:
        _, copy_index = val.split("&")
        val = int(copy_index)
     
    # If this is a string and is a valid file path, open the file
    elif type(val) == str:
        val = open(val, mode)
    
    # If val is a file-like object, integer, subprocess.PIPE or None, the redirect will be
    # handled by run_shell_cmd() / run_python_cmd()

    # Assign the new value to std_pipe
    std_pipe[file_d_index] = val


def read_close_fd(fd):
    """
    Utility function used to read an open file-like object and then close it.
    """
    out = fd.read()
    fd.close()
    return out

def to_bool(s):
    """
    Utility functions for converting string to bool

    Args:
        s (str): either 'True', 'False' (case insensitive)

    Returns:
        bool
    """
    if s.lower() == 'true':
        return True
    if s.lower() == 'false':
        return False
    raise ValueError("String %s cannot be converted to a bool" % s)

def expand_deque_input(dq):
    """
    Function to take a deque (which acts as a pipe for python commands) and 
    expand it to an input variable that is compatible with run_shell_cmd() / run_python_cmd().
    This attempts to replicate the behaviour of shell commands such as 'foo > bar 2>&1'
    
    Args:
        dq (collections.deque): input deque to be converted

    Returns:
        Python variable compatible with run_shell_cmd() / run_python_cmd()
            - If the deque was empty: None
            - If the deque has len == 1: dq[0]
            - If the deque has len > 1, then check the type of elements in the deque. 
              For str, dict and list, pop each deque element and combine into a single variable.
              For other types (or inconsistent types) just convert the deque into a list.
    """
    # If its empty, input is just None
    if len(dq) < 1:
        return None
    # If there is just one element, use it
    elif len(dq) == 1:
        return dq.pop()
    else:
        # Get the first element and enforce same type for all input variables
        new_input = dq.pop()
        input_type = type(new_input)
        # If these are not a string, dict or list, convert deque to list
        if input_type not in [str, dict, list]:
            new_input = [new_input] + list(dq)
        # If they are not all the same type, convert deque to list
        elif len([x for x in dq if (not type(x) == input_type)]) > 0:
            new_input = [new_input] + list(dq)
        # If they are consistent types, combine
        else:
            while len(dq) > 0:
                if input_type in [str, list]:
                    new_input += dq.pop()
                else:
                    new_input.update(dq.pop())
        # Replace input var
        return new_input
                

def isfile(v):
    """
    Function to check if a variable is a file
        * Python 2.x: variable type will be file
        * Python 3.x: variable will be an instance of _io.TextIOWrapper
    """
    if sys.version_info >= (3, 0):
        return isinstance(v, _io.TextIOWrapper)
    else:
        return type(v) == file

import os, io
import pybash_helper
from collections import deque
import subprocess
import readline


# Function to remove an item from the readline history
# since readline.remove_history_item() is not working
def remove_history_item(line_number, initial_history_length=None):
    
    # Get all history items except for the one at line_number
    new_history = [readline.get_history_item(i) for i in range(1, readline.get_current_history_length()) if not i == line_number]

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


# Helper function display a pipe with different variable types
def display_std_pipe(std_pipe):
    return [x if (type(x) == file or type(x) == int or x is None) else type(x) for x in std_pipe]

# Function to convert a python variable to a format compatible with shell commands
def shell_data(var):
    if var is not None:
        if type(var) == file:
            shell_data = var
        else:
            shell_data = pybash_helper.to_str(var)
    else:
        shell_data = None

    return shell_data


# Function to consolidate std_pipe + stdin/stdout/stderr variables, create pipes and process redirects
def expand_std_pipe(std_pipe, stdin, stdout, stderr, use_pipe=False):
    # Validate / fill std_pipe if not provided
    if std_pipe:
        if not len(std_pipe) == 3:
            raise ValueError ("std_pipe must be a 3-element list")
    else:
        std_pipe = [stdin, stdout, stderr]

    for i in range(3):
        # Process subprocess.PIPE
        #    - shell: create os.pipe() + open file-like object for reading
        #    - python: create a FIFO queue
        if std_pipe[i] == subprocess.PIPE:
            if use_pipe:
                std_pipe[i] = open_pipe()
            else:
                std_pipe[i] = deque()
        # Process pybash assignment pipe 
        if std_pipe[i] == -2:
            if use_pipe:
                std_pipe[i] = open_pipe()
            else:
                std_pipe[i] = deque()

    # Process redirects
    for i in range(3):
        if type(std_pipe[i]) == int:
            std_pipe[i] = std_pipe[std_pipe[i]]

    # print("Resulting std_pipe: %s" % std_pipe)
    
    return std_pipe


# If the value is True, create new file-like object
# From subprocess.Popen source code:
# if stdin == PIPE:
#    p2cread, p2cwrite = os.pipe()
# if stdout == PIPE:
#    c2pread, c2pwrite = os.pipe()
# if stderr == PIPE:
#    errread, errwrite = os.pipe()
# self.stdin = io.open(p2cwrite, 'wb', bufsize)
# self.stdout = io.open(c2pread, 'rb', bufsize)
# self.stderr = io.open(errread, 'rb', bufsize)
def open_pipe():
    # Create pipe manually so that redirects can be performed before passing to run_shell_cmd()
    # Create new os.pipe()
    r,w = os.pipe()
    # Open each file handle and return
    file_object_tuple = (os.fdopen(r), io.open(w, 'wb', -1))
    return file_object_tuple


# Each element of std_pipe can be:
#     None: 
#         - stdin: nothing will be passed to python / shell cmd
#         - stdout / stderr: output will be written to sys.stdout/sys.stderr
#     subprocess.PIPE:
#         - shell: an os.pipe() will be opened using pybash_helper.open_pipe()
#             - This creates file objects for the cmd to write to, next cmd to read from
#         - python cmd: return value / error will be added to a deque
#     file-like object:
#         - stdin: cmd will read from this file
#             - shell: pass to subprocess.Popen()
#             - python: read as string and close
#         - stdout / stderr: output will be written to this file
#     str:
#         - a file objected is opened for this file path
#             - shell: binary mode ('rb', 'wb', 'ab')
#             - python: text  mode ('r', 'w', 'a')
#     [0,1,2]:
#         - Used for redirects AFTER other std_pipe elements are processed (e.g. pipe opened) 
#         - e.g. if std_pipe = [None, subprocess.PIPE, 1]:
#             a) nothing passed to cmd input
#             b) pybash_helper.open_pipe() alled for stdout
#             c) write file-object for stdout is copied for stderr
#
# Redirects are parsed BEFORE knowning if it is a shell or python cmd
#    - For this to work, run_bash_cmd() and run_python_cmd() must treat std_pipe the same way
#    - Opening pipes occurs inside these commands since they do so in different ways
#        - shell: pipe = r/w pair of file handles
#        - python: pipe = function return value
#    - Opening files occures before run_bash_cmd() / run_python_cmd() 
#        - Files are opened the same way
#        - The read / write / append mode must be known, these commands are agnostic to this

# Function to assign a file descriptor to std_pipe
def fd_assign(file_d_index, mode, val, std_pipe):        
    # Check to see if val refers to another file descriptor
    if '&' in val:
        _, copy_index = val.split("&")
        val = int(copy_index)
     
    # If this is a string and is a valid file path, open the file
    elif type(val) == str:
        val = open(val, mode)
    
    # If val is a file-like object, integer, subprocess.PIPE or None, the redirect will be
    # handeled by run_shell_cmd() / run_python_cmd()

    # Assign the new value to std_pipe
    std_pipe[file_d_index] = val


def read_close_fd(fd):
    #print("reading fd %s" % fd)
    out = fd.read()
    fd.close()
    #out = ''
    #for line in iter(fd.readline, ''):
    #    out  += line
    #fd.close()
    return out

# Utility functions for converting string to different types automatically
def to_bool(s):
    if s.lower() == 'true':
        return True
    if s.lower() == 'false':
        return False
    raise ValueError("String %s cannot be converted to a bool" % s)

def autoconvert(s):
    for fn in (to_bool, int, float):
        try:
            return fn(s)
        except ValueError:
            pass
    return s

# Function to take a deque (which acts as a pipe for python commands) and 
# expand it to an input variable that is compatible with run_shell_cmd() / run_python_cmd()
def expand_deque_input(dq):
    # If its empty, input is just None
    if len(dq) < 1:
        return None
    # If there is just one element, use it
    elif len(dq) == 1:
        return dq.pop()
    else:
        # Get the first element and enfoce same type for all input variables
        new_input = dq.pop()
        input_type = type(new_input)
        # If these are not a string, dict or list, convert deque to list
        if input_type not in [str, dict, list]:
            new_input = [new_input] + list(dq)
        # If they are not all the same type, convert deque to list
        elif len([x for x in dq if (not type(x) == input_type)]) > 0:
            new_input = [new_input] + list(dq)
        # If they are consisten types, combine
        else:
            while len(dq) > 0:
                if input_type in [str, list]:
                    new_input += dq.pop()
                else:
                    new_input.update(dq.pop())
        # Replace input var
        return new_input
                

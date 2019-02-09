# This file contains helper functions for the pybash interpreter
# These functions can be used in a pipeline to facilitagte moving between bash and python
# e.g. "find . | to_list" will get the stdout of "find ." and convert each line to an element in a list

# This file will be imported within the interpreters "scope" so that the functions are accessible
# when using exec('...', self.globals, self.locals)

import yaml
import readline
import sys
import keyword

# Function used by pybash to determine if a command is a pybash_helper function
def function_match(s):
    f_list = ['to_list', 'to_dict', 'to_str', 'from_file', 'to_file']
    found = []
    for f in f_list:
        if f in s:
            found.append(f)
    return found

# Function used by pybash to check if a command is a python keyword
def python_keyword_match(c):
    return keyword.iskeyword(c)

# Functions for converting strings to dict/list
def to_list(s):
    return [y for y in (x.strip() for x in s.splitlines()) if y]
def to_dict(s):
    return yaml.load(s)

# Function to convert input variable to string, using special formating for certain types
def to_str(v, single_line=False):
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

# Functions to read/write files
def to_file(f_name, d, mode='w'):
    # Remove whitespace left over from shell commands
    f_name = f_name.strip()
    with open(f_name, mode) as f:
        f.write(d)
def from_file(f_name, mode='r'):
    # Remove whitespace left over from shell commands
    f_name = f_name.strip()
    with open(f_name, mode) as f:
        return f.read()


# History functions
def show_history():
    for i in range(1, readline.get_current_history_length()):
        sys.stdout.write("%i %s\n" % (i, readline.get_history_item(i)))

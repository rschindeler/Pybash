from cmd import Cmd
import os
import sys
import readline
import atexit
import traceback
import argparse
import pybash_util

from pybash_io import pybash_io

# The pybash_cmd class forms the basis of the terminal interface 
#    - based on the cmd.Cmd class
#    - custom functions: cd, exit, sudo, set, show
#    - extends pybash_io for stdout / stderr printing functions
class pybash_cmd(Cmd, pybash_io):
    ####################################################################################
    # DEFINITIONS
    ####################################################################################
    banner = "Welcome to pybash! A pythonic way to use your favourite shell"
    prompt_separator = "% "
    user_home = os.path.expanduser("~")
    history_file = os.path.join(user_home, ".pybash")
    
    # Dict to store flags used by the pybash interpreter
    cmd_flags = {'debug': True, 
                 'shell': '/bin/bash', 
                 'shell_source': os.path.join(user_home, '.bashrc'), 
                 'max_autocomplete': 100}
    # Dict to specify which type of variable certain flags should be
    cmd_flag_types = {'debug': bool, 
                      'shell': 'file_exists', 
                      'shell_source': 'file_exists', 
                      'max_autocomplete': int}

    tab_complete_prompt_flag = False

    aliases = {'ls':    {-1: 'ls --color=auto'}, 
               'll':    {0: 'ls -lrt', -1: 'ls -lrt --color=auto'},
               'l':     {0: 'ls -CF',  -1: 'ls -CF --color=auto'},
               'grep':  {-1: 'grep --color=auto'},
               'egrep': {-1: 'egrep --color=auto'},
               'fgrep': {-1: 'fgrep --color=auto'}}

    ####################################################################################
    # OVERRIDE CMD.CMD LOOP FUNCTIONS
    ####################################################################################

    # This function is called when the terminal prompt loop is first entered
    def preloop(self):
        # Initialize interpreter local + global "scope"
        self.locals = {}
        self.globals = {}
        exec('import pybash_helper', self.globals, self.locals)

        # Initialize the list of commands and aliases available in the user's shell
    	self.available_shell_cmds()

        # Initialize environment variables
        self.initialize_environment_variables()

        # Set default prompt
        self.update_prompt()
        
        # Initialize history
        self.stdout_write("history file: %s" % self.history_file)
        if os.path.exists(self.history_file):
            readline.read_history_file(self.history_file)
        self.initial_history_length = readline.get_current_history_length()
        atexit.register(readline.write_history_file, self.history_file)
        
        # Print banner
        self.stdout_write(self.banner)

    # Override emptyline() - by default, an empty line causes cmd.cmd to repeat the last command
    def emptyline(self):
        pass
    
    # Exit on receiving EOF    
    def do_EOF(self, line):
        self.stdout_write("bye")
        return True

    ##############################################################################
    # UTILITY FUNCTIONS
    ##############################################################################

   
    # Function to update the prompt to the current working directory
    def update_prompt(self):
        cwd = os.getcwd()
        self.prompt = cwd + self.prompt_separator

    ##############################################################################
    # PYBASH COMMAND-LINE FUNCTIONS
    ##############################################################################
    
    # Override the cd command - working directory is tracked in python 
    def do_cd(self, line):
        if os.path.isdir(line):
            os.chdir(line)
            self.update_prompt()
        else:
            self.print_error("cd: %s Not a directory" % line)

    # Allow 'exit' or 'exit()' commands to quit pybash
    def do_exit(self, line):
        return self.do_EOF(line)

    # Function to update self.cmd_flags with user input
    def do_set(self, line):
        parts = [s.strip() for s in line.split('=')]
        if len(parts) != 2:
            self.print_error("Invalid set syntax: %s" % line)
        else:
            # Get key and value
            key = parts[0]
            value = parts[1]
            # Attempt to convert
            value = pybash_util.autoconvert(value)
            # Check to see if this variable must be a specific type
            if key in self.cmd_flag_types:
                add_var = False
                # Check special keywords
                if type(self.cmd_flag_types[key]) == str and self.cmd_flag_types[key] == "file_exists":
                    # String that points to a file that exists
                    if os.path.isfile(value):
                        add_var = True
                # todo: elif other special cases
                else: 
                    if type(value) == self.cmd_flag_types[key]:
                        add_var = True
                # Add the value if type identification was successful
                if add_var:
                    self.cmd_flags[key] = value
                    self.stdout_write("Key %s updated to %s %s" % (key, type(value), value))
                else:
                    self.print_error("Key %s must have type %s, got %s %s" % (key, self.cmd_flag_types[key], value, type(value)))
            else:
                self.cmd_flags[key] = value
                self.stdout_write("key %s updated to %s %s" % (key, type(value), value))

    # Function to display self.cmd_flags
    def do_show(self, line):
        for key in line.split():
            if key in self.cmd_flags:
                self.stdout_write("%s = %s %s" % (key, self.cmd_flags[key], type(self.cmd_flags[key])))
            else:
                self.stdout_write("key %s not found" % key)

    # Override shell sudo command
    #   - if 'sudo -i' is used, launch pybash as root
    #   - else, run shell sudo command
    def do_sudo(self, line):
        if line.split()[0] == '-i':
            self.default("sudo python /development/python/pybash/pybash.py")
        else:
            self.default("sudo " + line)

    ##############################################################################
    # PYBASH HISTORY MANAGEMENT 
    ##############################################################################

    # Emulate the bash history command
    def do_history(self, line):
        # Step 1) Build history parser if not already done from a previous history cmd
        if not hasattr(self, 'history_argparser'):
            self.history_argparser = argparse.ArgumentParser(prog='history')
            self.history_argparser.add_argument('-c', '--clear', action="store_true")
            self.history_argparser.add_argument('-d', '--delete', type=int)
            self.history_argparser.add_argument('-a', '--append', nargs='?', const=self.history_file, type=str)
            self.history_argparser.add_argument('-n', '--new', nargs='?', const=self.history_file, type=str)
            self.history_argparser.add_argument('-r', '--read', nargs='?', const=self.history_file, type=str)
            self.history_argparser.add_argument('-w', '--write', nargs='?', const=self.history_file, type=str)
            # TODO: -p, -s

        # Step 2) Parse args in try/catch
        try:
            # If this history command is part of a pipeline, only parse arguments before the first pipe
            if '|' in line:
                parts = line.split('|')
                history_args = parts[0]
                remaining_cmd = '|'.join(parts[1:])
            else:
                history_args = line
                remaining_cmd = None
            # Parse the history arguments
            hist_args = self.history_argparser.parse_args(args=history_args.split())
        except SystemExit as e:
            # Catch parse_args() error, display message but do not exit program!
            self.print_error("invalid history command: %s" % line)
            return
        
        # Step 3) Perform history operations

        # a) Perform history clear
        if hist_args.clear:
            self.write_debug("Clearing history", "do_history")
            # Built-in readline function
            readline.clear_history()
        
        # b) Perform history delete
        if hist_args.delete:
            self.write_debug("Clearing deleting history line %i" % hist_args.delete, "do_history")
            # Delete line and adjust initial_history_length if required
            self.initial_history_length = pybash_util.remove_history_item(hist_args.delete, self.initial_history_length)

        # c) Perform history append
        if hist_args.append:
            # Manual write all history lines to file, starting at the index recorded when session started
            start = self.initial_history_length
            end = readline.get_current_history_length()
            self.write_debug("Appending new history lines %i to %i to file %s" % (start, end, hist_args.append), "do_history")
            with open(self.history_file, 'a') as f:
                for i in range(start, end + 1):
                    f.write(readline.get_history_item(i) + "\n")
            
        # d) Perform history new
        if hist_args.new:
            # Manually read lines in history file, starting at the index recorded (+1) when session started
            self.write_debug("Read new lines %i and above from history file since the begining of this pybash session: %s" % (self.initial_history_length + 1, hist_args.new), "do_history")
            with open(self.history_file, 'r') as f:
                for i, hist_line in enumerate(f):
                    if i > self.initial_history_length:
                        readline.add_history(hist_line.strip())

        # e) Perform history read
        if hist_args.read:
            self.write_debug("Read all lines from history file and append to this session's history: %s" % hist_args.read, "do_history")
            # Built-in readline function
            readline.read_history_file(self.history_file) 
        
        # f) Perform history write
        if hist_args.write:
            self.write_debug("Write current history to this history file, overwriting its contents: %s" % hist_args.read, "do_history")
            # Built-in readline function
            readline.write_history_file(self.history_file)
        
        # g) Display history
        if len(history_args.strip()) == 0:
            self.write_debug("Display history", "do_history")
            # Add the rest of the pipeline if required, then inster the pybash_helper.show_history() function
            #   - this will print history + line numbers to stdout
            #   - the stdout can be redirected as required
            if remaining_cmd:
                full_line = "pybash_helper.show_history() | " + remaining_cmd
            else:
                full_line = "pybash_helper.show_history()"
            # Run the resulting command
            self.default(full_line)
    
    ####################################################################################
    # AUTOCOMPLETE FUNCTIONS
    ####################################################################################
  
    # Function to take autocomplete matches and prompt the user if they want to display a large number
    def within_limits(self, matches, text):
        # If this is a short list, return. If not, prompt user
        if len(matches) < self.cmd_flags['max_autocomplete']:
            return matches
        else:
            # At the completion of each command / completion, this flag is set to False
            if self.tab_complete_prompt_flag is not False:
                if self.tab_complete_prompt_flag == text:
                    self.tab_complete_prompt_flag = False
                    return matches
                else:
                    # Text has changed, reset
                    self.stdout_write("\nHit tab again to display all %s possibilities" % len(matches))
                    self.stdout_write(self.prompt + text, print_line=False)
                    self.tab_complete_prompt_flag = text
                    return []
            else:
                # Prompt user if they want to see all possibilities
                self.stdout_write("\nHit tab again to display all %s possibilities" % len(matches))
                self.stdout_write(self.prompt + text, print_line=False)
                self.tab_complete_prompt_flag = text
                return []


    # Function to perform autocomplete for file paths
    # line: entire line buffer
    # text: text in line between begidx and endidx (current completion context)
    #   - the completion context is determined by readline.get_completer_delims()
    #     which define how line is split to get the start of the word to be considered for completion
    def autocomplete_path(self, text, line, begidx, endidx, require_file=False, require_dir=False):
        try:
            # Get the surounding context for text
            #   e.g. if it is part of a larger file path
            # get all space characters that are before begidx
            spaces = [i for i in range(begidx) if line[i] == ' ']
            if spaces:
                prev_space = spaces[-1]
                context = line[prev_space:begidx].strip()
            else:
                context = ''
            full_text = context + text

            # If full_text is an existing directory and it is explicitly typed (i.e. ends with '/'), look inside
            if os.path.isdir(full_text) and full_text.endswith(os.sep):
               # Look in this dir directly
               #self.write_debug("Searching for contents of %s" % full_text, "autocomplete_path")
               contents = os.listdir(full_text)
               base_dir = full_text
            else:
                # Look in the base directory of this path, filter by remaining text
                base_dir = os.path.dirname(full_text)
                if os.path.isdir(base_dir):
                    # Look for matching files in this directory
                    search_pattern = os.path.basename(full_text)
                else:
                    # Look to see if there are matching files
                    search_pattern = full_text
                    base_dir = os.getcwd()

                # Get dir contents, filter
                if search_pattern:
                    # self.write_debug("Searching for %s in %s" % (search_pattern, base_dir))
                    contents = [c for c in os.listdir(base_dir) if c.startswith(search_pattern)]
                else:
                    # self.write_debug("Searching for everything in %s" % (base_dir))
                    # If there is no search pattern, match everything
                    contents = os.listdir(base_dir)
            
            # Optionally filter by file / dir
            if require_file:
                contents = [f for f in contents if os.path.isfile(os.path.join(base_dir,f))]
            if require_dir:
                contents = [d for d in contents if os.path.isdir(os.path.join(base_dir,d))]
            
            # Filter within limits and return
            return self.within_limits(contents, text)
        except Exception as e:
            self.stderr_write(e)
            self.stderr_write(traceback.format_exc())
            return []



    # Override completedefault() to match against file paths 
    def completedefault(self, text, line, begidx, endidx):
        return self.autocomplete_path(text, line, begidx, endidx)
    
    # For the cd command, require directories
    def complete_cd(self, text, line, begidx, endidx):
        return self.autocomplete_path(text, line, begidx, endidx, require_dir=True)

    # Override completenames() to check against pybash commands and shell commands
    def completenames(self, text, *ignored):
        # Require at least one character be typed before completing names
        if not text:
            return []

        # Get matching pybash functions and shell commands
        pybash_matches = [a[3:] for a in self.get_names() if a.startswith('do_' + text)]
        shell_matches = [a for a in self.shell_cmds if a.startswith(text)]
        matches = list(set(pybash_matches + shell_matches))
        
        # Check limits and display
        return self.within_limits(matches, text) 

import subprocess
import re
import os
import sys
from collections import deque
import traceback
import copy

try:
    # Python 2
    import StringIO
except ImportError:
    # Python 3
    from io import StringIO

# Import pybash helper and utility functions
import pybash.util.pybash_helper as pybash_helper
import pybash.util.pipe_util as pipe_util
import pybash.util.conversion_util as conversion_util

# Import pybash sub-classes
from pybash.command.pybash_cmd import pybash_cmd
from pybash.parsing.parser import parser as pybash_parser
from pybash.util.std_io import pybash_io


#class pybash_runner(pybash_cmd, pybash_parser):
class pybash_runner(pybash_parser, pybash_io):
    """
    Class responsible for running pybash commands 
    """
    
    def run_shell_cmd(self, cmd, std_pipe=None, stdin=None, stdout=None, stderr=None):
        """
        Function to execute a shell command in a subprocess, accepting stdin and returning stdout / stderr.
        The three standard pipe varaibles can be passed individually or together using the std_pipe list. 
        run_shell_cmd() is non-blocking, i.e. it will return before the subprocess finishes executing.
        This allows for proper pipeline streaming.

        Args:
            cmd (str): the shell command to execute (may contain bash-like parameters such as ${var}
            std_pipe (list): list used to pass [std_in, stdout, stderr] if all three
                are available / requried
            stdin: The standard input to pass to the shell command. This may be:
                    1. File-like object (open python file or pipe), passed directly to subprocess.popen()
                    2. Python variable that can be converted to a string with str(). This will written 
                       to using process.stdin.write() after the process is started.
                    3.None: no input is provided to the subprocess.
            stdout: The destination of the standard output that will be returned by the shell 
                command. This may be:
                    1. File-like object (open python file or pipe), passed subprocess.popen()
                    2. subprocess.pipe: a os.pipe() will be created and passed to subprocess.popen()
                    3. tuple: this represents an already-existing pipe (read,write), output written 
                       to stdout[1]
                    4. None: stdout will be written to sys.stdout (i.e. the terminal) 
            stderr: the destination of the standard error that will be returned by the shell command.
                This may be:
                    1. file-like object (open python file or pipe), passed subprocess.popen()
                    2. subprocess.pipe: a os.pipe() will be created and passed to subprocess.popen()
                    3. tuple: this represents an already-existing pipe (read,write), output written 
                       to stderr[1]
                    4. none: stderr will be written to sys.stderr (i.e. the terminal) 
            
    
        Returns:
            tuple: file-like objects for stdout, stderr and the process opened by subprocess.popen()
            (stdout, stderr, process)
                1. if stdout / stderr file-like objects were passed to run_shell_cmd(), 
                   the same objects are returned
                2. if subprocess.PIPE was passed to run_shell_cmd(), the read file handel of the 
                   newly-created os.pipe() is returned.
                3. if none was passed to run_shell_cmd(), then none is returned.
        
        """
        
        # Expand std_pipe, create pipes, handle redirects
        stdin,stdout,stderr = pipe_util.expand_std_pipe(std_pipe, stdin, stdout, stderr, use_pipe=True)
        if std_pipe:
            pipe_display = pipe_util.display_std_pipe([stdin, stdout, stderr])
            self.write_debug("Expanded std_pipe: %s" % pipe_display, "run_shell_cmd")

        # Combine cmd if list and perform parameter subsitution
        if type(cmd) == list:
            cmd = " ".join(cmd)
        cmd = self.parameter_expansion(cmd)
       
        self.write_debug("SHELL: %s" % cmd, "run_shell_cmd")
        self.write_debug("INPUT: %s" % (stdin if pipe_util.isfile(stdin) else type(stdin)), "run_shell_cmd")
        
        # If stdin is a file descriptor, pass directly. If not, we will write stdin as a string
        if stdin:
            if pipe_util.isfile(stdin):
                stdin_var = stdin
                write_stdin = False
            else:
                stdin_var = subprocess.PIPE
                write_stdin = True
        else:
            stdin_var = None
            write_stdin = False
       
        # Possible values for stdout, stderr:
        #    None: stdout / stderr will be writen to the terminal
        #    existing file object: stdout / stderr are redirected to file
        #    subprocess.PIPE: an os.pipe() is created
        #    tuple: this is a pipe, write the stdout[1]
        stdout_var = stdout[1] if stdout and type(stdout) == tuple else stdout
        stderr_var = stderr[1] if stderr and type(stderr) == tuple else stderr

        self.write_debug("shell stdout_var: %s" % stdout_var, "run_shell_cmd")
        self.write_debug("shell stderr_var: %s" % stderr_var, "run_shell_cmd")

        # Open process
        process = subprocess.Popen(cmd, 
            shell=True, 
            executable=self.cmd_flags['shell'], 
            stdout=stdout_var, 
            stderr=stderr_var, 
            stdin=stdin_var)
        
        # Write stdin as string if required
        if write_stdin:
            process.stdin.write(str(stdin))
            process.stdin.close()
        
        # If stdout/stderr were tuples, return the read file object
        # If not, return the process.stdout/stderr
        stdout_ret = stdout[0] if type(stdout) == tuple else process.stdout
        stderr_ret = stderr[0] if type(stderr) == tuple else process.stderr
        self.write_debug("shell stdout_ret: %s" % stdout_ret, "run_shell_cmd")
        self.write_debug("shell stderr_ret: %s" % stderr_ret, "run_shell_cmd")
        
        # Return file descriptors + process
        return stdout_ret, stderr_ret, process
        
    def run_python_cmd(self, cmd, std_pipe=None, input_var=None, stdout=None, stderr=None):
        """
        Function to execute a python command, accepting an input variable and returning:
            1. Result of python command
            2. stdout of python command
            3. stderr of python command

        The python command is executed using exec(cmd, self.globals, self.local) in order to maintain 
        a separate "varable space" from the pybash program.

        Unlike run_shell_cmd(), run_python_cmd() is blocking. A future improvement could be to execute
        the python command in a subprocess, and allow streaming data through std_pipe.
        
        Args:
            cmd (str): the shell command to execute 
            std_pipe (list): list used to pass [input_var, stdout, stderr] if all three
                are available / requried
            input_var: The input variable to the python command, which acts similarily to stdin for
                a shell command. This may be:
                    1. File-like object (open python file or pipe), which will be read and converted 
                       to a string
                    2. Python variable that will be passed directly
                    3. None: no input is provided to the python command
            stdout: The destination of the result(s) of the python command. 
                This may be:
                    1. File-like object (open python file or pipe), result(s) of python command will 
                       be written here
                    2. subprocess.PIPE: a new collections.deque object will be created and result(s)
                       of python command will be written here 
                    3. collections.deque object, result(s) of python command will be written here
                    4. None: stdout will be written to sys.stdout (i.e. the terminal) 
            stderr: The destination of the standard error generated by the python command.
                This may be:
                    1. File-like object (open python file or pipe), stderr of python command will 
                       be written here
                    2. subprocess.PIPE: a new collections.deque object will be created and stderr
                       of python command will be written here 
                    3. collections.deque object, stderr of python command will be written here
                    4. None: stdout will be written to sys.stdout (i.e. the terminal) 
            
    
        Returns:
            tuple: File-like objects for stdout, stderr (stdout, stderr, None)
                
            .. note:: Since run_python_cmd() does not execute in a subprocess, no process is returned by this function.
            stdout and stderr are collections.deque objects, which typically have only one element.  Additional elements
            are added by using redirects. For example, you can redirect the command's stderr to the stdout deque object.

            The stdout deque may contain (one or both): 
                a) the result of evaluating a python statement (e.g. if cmd = '2+4', stdout = 6)
                b) the stdout resulting from executing the python statement (e.g. if cmd = 'print("foo")', stdout = 'foo')
            
            For example, if executing a function that contains a print() statement as well as returning a value, the
            stdout deque will contain both the return value and the printed text.

            The stderr deque will contain the errors generated by the python command (e.g. exception text)

        """
        
        # Expand the std_pipe, handel redirects (create deque objects instead of os.pipe()) 
        input_var,stdout,stderr = pipe_util.expand_std_pipe(std_pipe, input_var, stdout, stderr)
        self.write_debug("Expanded std_pipe: %s" % [type(input_var), stdout, stderr], "run_python_cmd")
       
        ####################################################################
        # Step 1) Get input data, initialize __inputvar__ and __outputvar__ in self.locals
        # If the input_data is a file descriptor, read string
        if input_var and pipe_util.isfile(input_var):
            self.write_debug("Reading file object %s and storing as input_var" % input_var, "run_python_cmd")
            input_var = pipe_util.read_close_fd(input_var) 
        
        # Initialize the special __inputvar__ variable
        #   Python 3.x: Use globals so commands like '[@[f] for f in @] for'
        #   Python 2.x  Use locals since this does not seem to be a problem
        if sys.version_info >= (3, 0):
            self.globals['__inputvar__'] = input_var
        else:   
            self.locals['__inputvar__'] = input_var
        # Initialize __outputvar__ to None in self.locals  - may have been set by a previous cmd
        self.locals['__outputvar__'] = None
        
        ####################################################################
        # Step 2: Compile the command
        # a) Check to see if the command references the input variable
        if '@' in cmd:
            cmd = cmd.replace("@", "__inputvar__")

        # b) Check to see if this is command that can be assigned to a variable
        #  - there is probably a better way to do this without using a try-catch
        # TODO: ugly nested try-catch
        try:
            assignment_cmd = "__outputvar__ = " + cmd
            # self.write_debug("test: %s" % assignment_cmd, "run_python_cmd")
            cmd_c = compile(assignment_cmd, '<pybash>', 'exec')
            cmd = assignment_cmd
            capture_output_var = True
        except (SyntaxError, TypeError) as e:
        # c) Attempt to compile original cmd
            try:
                cmd_c = compile(cmd, '<pybash>', 'exec')
                capture_output_var  = False
            except (SyntaxError, TypeError) as e:
                self.print_error("Could not compile: %s" % cmd)
                self.stderr_write(str(e) + '\n')
                self.stderr_write(traceback.format_exc())
                return None, None, None

        self.write_debug("Sucessfuly compiled python: %s" % (cmd), "run_python_cmd")

        ####################################################################
        # Step 3: Execute the command
        # a) Create StringIO for out/error
        # - after doing this, don't print anything until out/err are restored!
        
        if sys.version_info >= (3, 0):
            out = StringIO()
            err = StringIO()
        else:
            out = StringIO.StringIO()
            err = StringIO.StringIO()
        # Capture out/err
        sys.stdout = out
        sys.stderr = err
        # b) run command in try-catch
        #    - if any errors occur, they will get added to std_pipe[2]
        try:
            exec(cmd_c, self.globals, self.locals)
        except Exception as e:
            sys.stderr.write(str(e) + '\n')
            pass
        
        # c) restore orig out/err
        sys.stdout = sys.__stdout__
        sys.stderr = sys.__stderr__
        # get out/err values and close
        stdout_val = out.getvalue()
        stderr_val = err.getvalue()
        out.close()
        err.close()
        self.write_debug("Restored stdout/stderr", "run_python_cmd")
        
        ####################################################################
        # Step 4: Add output to pipe or print to sys.stdout/sys.stderr
        
        # Define source lists for output + error pipes
        #   - __outputvar__ may not be defined if something went wrong
        try:
            stdout_src_list = [self.locals['__outputvar__'], stdout_val]
        except UnboundLocalError: 
            stdout_src_list = [None, stdout_val]

        stderr_src_list = [stderr_val]
        
        # Define the mappings between the (name, output pipe, output print function, output source list)
        output_mapping =  [("stdout", stdout, self.stdout_write, stdout_src_list), 
                           ("stderr", stderr, self.stderr_write, stderr_src_list)]
        
        # Process each output mapping
        for name, pipe, print_fn, src_list in output_mapping:
            # Process each source in the list
            for src in src_list:
                if not src:
                    continue
                # If pipe is a deque, appendleft
                if type(pipe) == deque:
                    self.write_debug("Adding src to %s queue" % name, "run_python_cmd")
                    pipe.appendleft(src)
                # If pipe is a file-like object, write to file
                elif pipe_util.isfile(pipe):
                    self.write_debug("Writing %s src to file %s" % (name, pipe), "run_python_cmd")
                    pipe.write(pybash_helper.to_str(src))
                # If pipe is None, print using print function
                elif pipe is None:
                    self.write_debug("Printing %s with function %s" % (name, print_fn), "run_python_cmd")
                    print_fn(src)
                # Otherwise, unrecognized pipe type
                else:
                    raise ValueError ("Unrecognized pipe type for %s: %s" % name, type(pipe))
        
        # Close any open file handels and return output
        #    - there is no subprocess for python commands
        output = [stdout, stderr, None]
        for i in range(2):
            if pipe_util.isfile(output[i]):
                if output[i].closed is False:
                    output[i].close()
                # Replace with None so that run_cmd() knows not to expect anything
                output[i] = None

        return output
       

    def run_cmd(self, cmd, std_pipe=None, input_data=None, stdout=None, stderr=None, last_cmd=False):
        """
        Function to execute a single shell or python command and return the output in a pipe.
        .. note:: A "single command" is one that does not contain a pipeline
        
        This function performs the following:
            1. Validate and standardize the input variables 
                a) Combine input variables into std_pipe list
                b) Expand any deque inputs using pipe_util.expand_deque_input()
            2. Sub-in shell aliases if possible
            3. Determine if the command should be executed as a shell command or python command
                a) Commands including pybash helper functions are executed in python
                b) Commands whose first word is a known shell command is executed in a shell subprocess
                c) Any other commands are executed in python

        See run_python_cmd() and run_bash_cmd() for more information on input arguments
        and return types.
        
        Args:
            cmd (str): the shell or python  command to execute
            std_pipe (list): list used to pass [input_data, stdout, stderr] if all three
                are available / requried
            input_data: Either the input_var for run_python_cmd() or the stdin for run_shell_cmd()
            stdout: The destination of the standard output for python / shell commands
            stdout: The destination of the standard error for python / shell commands
        

        Returns:
            tuple: Containing (stdout, stderr, process)
                stdout and stderr are file-like objects (shell) or deque objects (python) 
                generated by the command. process is only used for run_shell_cmd() which
                executes as a subprocess.
        

        """
        ############################################################################
        # Step 1) Validate and standardize input variables
        # If std_pipe was provided, check length
        if std_pipe:
            if len(std_pipe) != 3:
                self.print_error("run_cmd() requires a std_pipe that has exactly 3 elements")
                raise ValueError
        # If not, create using other input variables
        else:
            std_pipe = [input_data, stdout, stderr]
        
        # If input var is a deque, expand
        if type(std_pipe[0]) == deque:
            std_pipe[0] = pipe_util.expand_deque_input(std_pipe[0])
            self.write_debug("Replaced deque with: %s" % std_pipe[0])
        
        ############################################################################
        # Step 2) Prepare the command string
        # Split cmd by space, make sure it has at least one element
        cmd = cmd.strip()
        cmd_parts = cmd.split()
        if len(cmd_parts) < 1:
            return input_data

        # Sub in aliases if possible
        for i in range(len(cmd_parts)):
            if cmd_parts[i] in self.aliases:
                if last_cmd and -1 in self.aliases[cmd_parts[i]]:
                    new_cmd = self.aliases[cmd_parts[i]][-1]
                    self.write_debug("Using alias: '%s' = '%s'" % (cmd_parts[i], new_cmd), "run_cmd")
                    cmd_parts[i] = new_cmd
                elif not last_cmd and 0 in self.aliases[cmd_parts[i]]:
                    new_cmd = self.aliases[cmd_parts[i]][0]
                    self.write_debug("Using alias: '%s' = '%s'" % (cmd_parts[i], new_cmd), "run_cmd")
        # re-join and split now that aliases are in place
        cmd = " ".join(cmd_parts)
        cmd_parts = cmd.split()

        ############################################################################
        # Step 3) Check to see if this is a shell or python command and execute
        # a) Check to see if this command contains known pybash helper functions
        helper_functions = pybash_helper.function_match(cmd)
        if helper_functions:
            for i in range(len(cmd_parts)):
                # This command contains python_helper function(s)
                for fn in helper_functions:
                    if not fn in cmd_parts[i]:
                        continue
                    # Check to see if '(@)' should be added
                    f_call_match = re.match(fn + "\([^\)]*\)", cmd_parts[i])
                    if f_call_match:
                        cmd_parts[i] = cmd_parts[i].replace(fn, "pybash_helper." + fn)
                    else:
                        cmd_parts[i] = cmd_parts[i].replace(fn, "pybash_helper." + fn + "(@)")
                    
                    self.write_debug("Helper function iteration: %s" % cmd_parts[i], "run_cmd")
            cmd = " ".join(cmd_parts)    
            self.write_debug("FULL CALL: %s" % cmd, "run_cmd")
            
            return self.run_python_cmd(cmd, std_pipe=std_pipe)
        
        # b) Check to see if the first element of cmd is a known shell function
        #   - exclude python keywords such as import (which may also be valid shell commands)
        elif cmd_parts[0] in self.shell_cmds and not pybash_helper.python_keyword_match(cmd_parts[0]):
            self.write_debug("First word '%s' matched a shell command and is not a python keyword, executing as shell command" % cmd_parts[0], "run_cmd")
            # If input data is provided, format special variable types for shell compatibility
            std_pipe[0] = conversion_util.shell_data(std_pipe[0])
            return self.run_shell_cmd(cmd, std_pipe=std_pipe) 
        # c) Default to python
        else:
            return self.run_python_cmd(cmd, std_pipe=std_pipe)
    

    def run_pipeline(self, pipeline_cmd):
        """
        Function to execute a combined shell-python command pipeline
        
        Examples:
            * py_var = 5 + 4
            * cat test.txt | grep str | tail -n 5 >> out_file.txt
            * grep -nr str | head -n 5 | py_var
            * py_var = grep -nr str | head -n 5
            * cat test.txt | grep myvar | cut -d '=' -f2 | py_function(@)
        
        This function breaks the pipeline into individual commands, and handels
        the redirects, piping between commands, and assignment to python variables.

        Args:
            pipeline_cmd (str): String containing mixed shell and python syntax,
                using '|' to denote pipes.

        """
        
        #######################################################################
        # Step 1) Setup
        
        # Check for top-level redirects and expansions
        # a) Check for assignment operator
        pipeline_cmd, output_var = self.get_assignment(pipeline_cmd)

        # b) Get each part of the pipeline
        pipeline = [p for p in pipeline_cmd.split("|") if p]

        # c) Inintialize the "location" of [stdin, stdout, stderr] for the pipeline
        #    - For the first iteration, stdin = None
        std_pipe = [None, None, None]
        process = None 
        #######################################################################
        # Step 2) Execute each part of the pipeline, passing output of each stage along
        for i in range(len(pipeline)):
            cmd = pipeline[i]
            self.write_debug("Starting cmd: %s" %cmd, "run_pipeline")

            # a) Initialize std_pipe for this iteration
            # stdin: set by the previous iteration
            # stdout: stage-dependant
            if i == len(pipeline)-1:
                # For the last pipeline command, the stdout value is one of
                #    None: this causes it to be displayed in the terminal
                #    -2: this causes it to be assigned to the output variable
                if output_var:
                    std_pipe[1] = subprocess.PIPE
                else:
                    std_pipe[1] = None
            else:
                # For all other iterations, pipe stdout to the next stage 
                std_pipe[1] = subprocess.PIPE 

            # stderr: all stages start with stderr = None
            std_pipe[2] = None
            
            # b) Get the redirects for this command
            #   - by default, each pipeline stage reads stdin and writes to stdout + stderr
            #   - the "location" of stdin / stdout / stderr are determined by the std_pipe
            cmd = self.redirects(cmd, std_pipe)
            self.write_debug("std_pipe this stage: %s" % pipe_util.display_std_pipe(std_pipe), "run_pipeline")
            
            # c) Run command, get [stdout, stderr, subprocess.Popen() object]
            try:
                process = None
                std_pipe[1], std_pipe[2], process = self.run_cmd(cmd, std_pipe=std_pipe, last_cmd = (i==len(pipeline)-1)) 
            except Exception as e:
                self.print_error("failed to execute: %s" % cmd)
                self.stderr_write(str(e))
                self.write_debug(traceback.format_exc())
                break
            
            # d) Assign stdin for the next iteration
            std_pipe[0] = std_pipe[1]
            
            self.write_debug("Done cmd: %s" % cmd, "run_pipeline")
            self.write_debug("std_pipe for next stage: %s" % pipe_util.display_std_pipe(std_pipe), "run_pipeline")
    
    
        #######################################################################
        # Step 3) Perform post-pipeline activities
        self.write_debug("done pipeline", "run_pipeline")
        # a) If there is a remaining process, wait for it to complete 
        if process:
            self.write_debug("Waiting for process to complete: %s" % process)
            process.wait()
        
        # b) Assign to output variable if required
        if output_var:
            # Read stdout from std_pipe[1] (either a file-like object or deque)
            stdout = std_pipe[1]
            if pipe_util.isfile(stdout):
                if not stdout.closed:
                    self.write_debug("Reading file %s and assigning to output variable %s" % (stdout, output_var), "run_pipeline")
                    stdout_result = pipe_util.read_close_fd(stdout)
                else:
                    self.write_error("Could not process assignemnt, received closed file object")
            elif type(stdout) == deque:
                self.write_debug("Reading deque and assigning to output variable %s" % (output_var), "run_pipeline")
                stdout_result = pipe_util.expand_deque_input(stdout)
           
            # Assign stdout_result to the special __stdout__ variable in self.locals
            # so that it can be assigned 
            self.locals[output_var] = stdout_result 
        
        # c) Read and close any open file handels / python variables for stdout and stderr  
        print_fn = [self.stdout_write, self.stderr_write]
        for i in range(2):
            if std_pipe[1+1] is not None:
                self.write_debug("printing std_pipe[%i]" % (i+1), "run_pipeline") 
                # If this is a file, check to see if open 
                if pipe_util.isfile(std_pipe[i+1]) and std_pipe[i+1].closed is False:
                    for line in iter(std_pipe[i+1].readline, ''):
                        print_fn[i](line, print_line=False)
                    std_pipe[i+1].close()
                # Otherwise, assume python variable and print 
                else:
                    print_fn[i](str(std_pipe[i+1]))
    
    def available_shell_cmds(self):
        """
        Function to get all available shell commands and store them in the 
        searchable dict self.shell_cmds. 

        The shell commands are found by executing:
        
        .. code-blick:: bash
        
            compgen -A function -ack

        and excluding punctuation such as '[', '[['.
        """
        
        # Execute compgen to get all commands
        s, e, p = self.run_shell_cmd("compgen -A function -ack", stdout=subprocess.PIPE)
        cmd_list_str = pipe_util.read_close_fd(s)
        cmd_list = cmd_list_str.split(os.linesep)
       
        # List of characters to exclude
        char_exclude_list = ['[', ']', '{', '}', '(', ')', '!', ':']

        # Store in special hash
        self.shell_cmds = {}
        for c in cmd_list:
            # Check for punctuation
            #  - this can mess things up
            exclude = False
            for e in char_exclude_list:
                if e in c:
                    exclude = True
                    break
            if exclude:
                continue
            # add to hash
            self.shell_cmds[c] = 1
        
        self.write_debug("Loaded %i shell commands" % len(self.shell_cmds), "available_shell_cmds")
    
    def initialize_environment_variables(self):
        """
        Function to load all environment varaibles from default shell
        and store them in the self.locals dict. This allows them to be accessed
        by python commands and shell commands (using ${var} notation)
        """
        
        # Execute printenv to get all environment variables
        s, e, p = self.run_shell_cmd("printenv", stdout=subprocess.PIPE)
        env_list_str = pipe_util.read_close_fd(s)
        env_list = env_list_str.split(os.linesep)
        # Store each in self.locals hash
        for v in env_list:
            # Skip empty lines
            if not v:
                continue
            # Separate into key/value
            parts = v.split('=')
            if not len(parts) >= 2:
                self.write_debug("Failed to load environment line: %s" % v)
                continue
            key = parts[0]
            val = "=".join(parts[1:])
            self.locals[key] = val


    def get_shell_aliases(self):
        """
        Function to get all shell aliases
        TODO: this does not work, can't seem to get ~/.bashrc to source from subshell
        Use config dict instead

        """
        
        # Get the name of the shell script sourced by the default shell
        shell_source = self.cmd_flags['shell_source']
        # Source this script and print all known aliases
        s, e, p = self.run_shell_cmd("source " + shell_source + ";\nalias;", stdout=subprocess.PIPE)
        alias_list_str = pipe_util.read_close_fd(s)
        print(alias_list_str)
        alias_list = alias_list_str.split()

        # Double check formating of each line then add to dict
        shell_aliases = []
        for alias in alias_list:
            m = re.match("alias (.*)='(.*)'", alias)
            if m:
                self.shell_aliases.append([m.groups()[0],  m.groups()[1]])
        for alias in shell_aliases:
            self.stdout_write(alias[0] + ": " + alias[1])
        return shell_aliases



        




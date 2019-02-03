import subprocess
import re
import os
import sys
import StringIO
from collections import deque
import traceback
import copy

# Import pybash helper and utility functions
import pybash_helper, pybash_util

# Import pybash sub-classes
from pybash_cmd import pybash_cmd
from pybash_parser import pybash_parser

# TODO List:
# Bash special variables: https://www.mylinuxplace.com/bash-special-variables/
#
# import statements don't work 


# Future enhancements:
#  - allow "streaming" execution of python commands

#        - if input to python is a deque with len > 1, could process each pop as they come in
#        - would wait for the input deque to be None (same as a file-like object being 'closed')


class pybash(pybash_cmd, pybash_parser):
    


    ####################################################################################
    # COMMAND EXECUTION FUNCTIONS
    ####################################################################################
    
    
    
    # Function to execute a shell command, accepting stdin and returning stdout / stderr
    #    If stdin is not None:
    #        - if type(stdin) == file, then it will be passed to subprocess.Popen()
    #        - if not, it is written to the process's stin after subprocess.Popen() is called 
    #    If stdout_pipe / stderr_pipe are subprocess.PIPE, they are passed to subprocess.Popen
    #        - if not. the subprocess will print its stdout / stderr to terminal
    #
    #    Returns: stdout file handle, stderr file handel, process
    #           - if stdout_pipe / stderr_pipe are None, these file handels are None
    def run_shell_cmd(self, cmd, std_pipe=None, stdin=None, stdout_pipe=None, stderr_pipe=None):
        # Expand std_pipe, create pipes, handle redirects
        stdin,stdout_pipe,stderr_pipe = pybash_util.expand_std_pipe(std_pipe, stdin, stdout_pipe, stderr_pipe, use_pipe=True)
        if std_pipe:
            #pipe_display = [pybash_util.display_std_pipe(p) for p in [stdin, stdout_pipe, stderr_pipe]]
            pipe_display = pybash_util.display_std_pipe([stdin, stdout_pipe, stderr_pipe])
            self.write_debug("Expanded std_pipe: %s" % pipe_display, "run_shell_cmd")

        # Combine cmd if list and perform parameter subsitution
        if type(cmd) == list:
            cmd = " ".join(cmd)
        #cmd = self.parameter_expansion(cmd)
       
        self.write_debug("SHELL: %s" % cmd, "run_shell_cmd")
        self.write_debug("INPUT: %s" % (stdin if type(stdin) == file else type(stdin)), "run_shell_cmd")
        
        # If stdin is a file descriptor, pass directly. If not, we will write stdin as a string
        if stdin:
            if type(stdin) == file:
                stdin_var = stdin
                write_stdin = False
            else:
                stdin_var = subprocess.PIPE
                write_stdin = True
        else:
            stdin_var = None
            write_stdin = False
       
        # Possible values for stdout_pipe, stderr_pipe:
        #    None: stdout / stderr will be writen to the terminal
        #    existing file object: stdout / stderr are redirected to file
        #    subprocess.PIPE: an os.pipe() is created
        #    tuple: this is a pipe, write the stdout_pipe[1]
        stdout_var = stdout_pipe[1] if stdout_pipe and type(stdout_pipe) == tuple else stdout_pipe
        stderr_var = stderr_pipe[1] if stderr_pipe and type(stderr_pipe) == tuple else stderr_pipe

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
        
        # If stdout_pipe/stderr_pipe were tuples, return the read file object
        # If not, return the process.stdout/stderr
        stdout_ret = stdout_pipe[0] if type(stdout_pipe) == tuple else process.stdout
        stderr_ret = stderr_pipe[0] if type(stderr_pipe) == tuple else process.stderr
        self.write_debug("shell stdout_ret: %s" % stdout_ret, "run_shell_cmd")
        self.write_debug("shell stderr_ret: %s" % stderr_ret, "run_shell_cmd")
        
        # Return file descriptors + process
        return stdout_ret, stderr_ret, process
        

    # Function to execute a python command, accepting an input variable and returning and output variable + error 
    def run_python_cmd(self, cmd, std_pipe=None, input_var=None, stdout_pipe=None, stderr_pipe=None):
        # Expand the std_pipe, handel redirects
        input_var,stdout_pipe,stderr_pipe = pybash_util.expand_std_pipe(std_pipe, input_var, stdout_pipe, stderr_pipe)
        self.write_debug("Expanded std_pipe: %s" % [type(input_var), stdout_pipe, stderr_pipe], "run_python_cmd")
       
        ####################################################################
        # Step 1) Get input data, initialize __inputvar__ and __outputvar__ in self.locals
        # If the input_data is a file descriptor, read string
        if input_var and type(input_var) == file:
            self.write_debug("Reading file object %s and storing as input_var" % input_var, "run_python_cmd")
            input_var = pybash_util.read_close_fd(input_var) 
        
        # self.write_debug("input_var: %s" % input_var, "run_python_cmd")
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
                self.stderr_write(e)
                self.stderr_write(traceback.format_exc())
                return None, None, None

        self.write_debug("Sucessfuly compiled python: %s" % (cmd), "run_python_cmd")

        ####################################################################
        # Step 3: Execute the command
        # a) Create StringIO for out/error
        # - after doing this, don't print anything until out/err are restored!
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
            sys.stderr.write(e)
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
        #self.write_debug("stdout_src_list: %s" % stdout_src_list, "run_python_cmd")
        #self.write_debug("stderr_src_list: %s" % stderr_src_list, "run_python_cmd")
        
        # Define the mappings between the (name, output pipe, output print function, output source list)
        output_mapping =  [("stdout", stdout_pipe, self.stdout_write, stdout_src_list), 
                           ("stderr", stderr_pipe, self.stderr_write, stderr_src_list)]
        
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
                elif type(pipe) == file:
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
        output = [stdout_pipe, stderr_pipe, None]
        for i in range(2):
            if type(output[i]) == file:
                if output[i].closed is False:
                    output[i].close()
                # Replace with None so that run_cmd() knows not to expect anything
                output[i] = None

        return output
        

    # Function to execute a single shell or python command 
    # i.e. a command that does not contain a pipeline
    def run_cmd(self, cmd, std_pipe=None, input_data=None, stdout_pipe=None, stderr_pipe=None, last_cmd=False):
        # If std_pipe was provided, check length
        if std_pipe:
            if len(std_pipe) != 3:
                self.print_error("run_cmd() requires a std_pipe that has exactly 3 elements")
                raise ValueError
        # If not, create using other input variables
        else:
            std_pipe = [input_data, stdout_pipe, stderr_pipe]
        
        # If input var is a deque, expand
        if type(std_pipe[0]) == deque:
            std_pipe[0] = pybash_util.expand_deque_input(std_pipe[0])
            self.write_debug("Replaced deque with: %s" % std_pipe[0])
        
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

        # Check to see if this is a shell or python command
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
        elif cmd_parts[0] in self.shell_cmds:
            # If input data is provided, format special variable types for shell compatibility
            std_pipe[0] = pybash_util.shell_data(std_pipe[0])
            return self.run_shell_cmd(cmd, std_pipe=std_pipe) 
        # c) Default to python
        else:
            return self.run_python_cmd(cmd, std_pipe=std_pipe)
    

    # Function to execute a combined shell-python command pipeline
    #    py_var = 5 + 4
    #    cat test.txt | grep str | tail -n 5 >> out_file.txt
    #    grep -nr str | head -n 5 | py_var
    #    py_var = grep -nr str | head -n 5
    #    cat test.txt | grep myvar | cut -d '=' -f2 | py_function(@)
    def run_pipeline(self, pipeline_cmd):
        # Check for top-level redirects and expansions
        # a) Check for assignment operator
        pipeline_cmd, output_var = self.get_assignment(pipeline_cmd)

            
    
        # c) Get each part of the pipeline
        pipeline = [p for p in pipeline_cmd.split("|") if p]

        # Inintialize the "location" of [stdin, stdout, stderr] for the pipeline
        #    - For the first iteration, stdin = None
        std_pipe = [None, None, None]
        
        # Execute each part of the pipeline, passing output of each stage along
        for i in range(len(pipeline)):
            cmd = pipeline[i]
            self.write_debug("Starting cmd: %s" %cmd, "run_pipeline")

            # Step 1) Initialize std_pipe for this iteration
            # a) stdin: set by the previous iteration
            # b) stdout: stage-dependant
            if i == len(pipeline)-1:
                # For the last pipeline command, the stdout value is one of
                #    None: this causes it to be displayed in the terminal
                #    -2: this causes it to be assigned to the output variable
                if output_var:
                    std_pipe[1] = -2
                else:
                    std_pipe[1] = None
            else:
                # For all other iterations, pipe stdout to the next stage 
                std_pipe[1] = subprocess.PIPE 

            # c) stderr: all stages start with stderr = None
            std_pipe[2] = None
            
            # Step 2) Get the redirects for this command
            #   - by default, each pipeline stage reads stdin and writes to stdout + stderr
            #   - the "location" of stdin / stdout / stderr are determined by the std_pipe
            cmd = self.redirects(cmd, std_pipe)
            self.write_debug("std_pipe this stage: %s" % pybash_util.display_std_pipe(std_pipe), "run_pipeline")
            
            # Step 3) Run command, get [stdout, stderr, subprocess.Popen() object]
            try:
                process = None
                std_pipe[1], std_pipe[2], process = self.run_cmd(cmd, std_pipe=std_pipe, last_cmd = (i==len(pipeline)-1)) 
            except Exception as e:
                self.print_error("failed to execute: %s" % cmd)
                self.stderr_write(e)
                self.write_debug(traceback.format_exc())
                break
            
            # Step 4) Assign stdin for the next iteration
            std_pipe[0] = std_pipe[1]
            
            self.write_debug("Done cmd: %s" % cmd, "run_pipeline")
            self.write_debug("std_pipe for next stage: %s" % pybash_util.display_std_pipe(std_pipe), "run_pipeline")
    
    
        #######################################################################
        # Perform post-pipeline activities
        self.write_debug("done pipeline", "run_pipeline")
        # 1) If there is a remaining process, wait for it to complete 
        if process:
            self.write_debug("Waiting for process to complete: %s" % process)
            process.wait()
        
        # 2) Assign to output variable if required
        if output_var:
            # Read stdout from std_pipe[1] (either a file-like object or deque)
            stdout = std_pipe[1]
            if type(stdout) == file:
                if not stdout.closed:
                    self.write_debug("Reading file %s and assigning to output variable %s" % (stdout, output_var), "run_pipeline")
                    stdout_result = pybash_util.read_close_fd(stdout)
                else:
                    self.write_error("Could not process assignemnt, received closed file object")
            elif type(stdout) == deque:
                self.write_debug("Reading deque and assigning to output variable %s" % (output_var), "run_pipeline")
                stdout_result = pybash_util.expand_deque_input(stdout)
           
            # Assign stdout_result to the special __stdout__ variable in self.locals
            # so that it can be assigned 
            self.locals[output_var] = stdout_result 
        
        # 3) Read and close any open file handels / python variables for stdout and stderr  
        print_fn = [self.stdout_write, self.stderr_write]
        for i in range(2):
            if std_pipe[1+1] is not None:
                self.write_debug("printing std_pipe[%i]" % (i+1), "run_pipeline") 
                # If this is a file, check to see if open 
                if type(std_pipe[i+1]) == file and std_pipe[i+1].closed is False:
                    for line in iter(std_pipe[i+1].readline, ''):
                        print_fn[i](line, print_line=False)
                    std_pipe[i+1].close()
                # Otherwise, assume python variable and print 
                else:
                    print_fn[i](str(std_pipe[i+1]))
    
    # Function to get all available shell commands and store them in a searchable hash
    def available_shell_cmds(self):
        s, e, p = self.run_shell_cmd("compgen -A function -ack", stdout_pipe=subprocess.PIPE)
        self.write_debug("reading %s" % s)
        cmd_list_str = pybash_util.read_close_fd(s)
        cmd_list = cmd_list_str.split()
        shell_cmds = {}
        for c in cmd_list:
           shell_cmds[c] = 1
        self.write_debug("Loaded %i shell commands" % len(shell_cmds), "available_shell_cmds")
        return shell_cmds


    # Function to get all shell aliases
    # TODO: this does not work, can't seem to get ~/.bashrc to source from subshell
    # Use config dict instead
    def get_shell_aliases(self):
        # Get the name of the shell script sourced by the default shell
        shell_source = self.cmd_flags['shell_source']
        # Source this script and print all known aliases
        s, e, p = self.run_shell_cmd("source " + shell_source + ";\nalias;", stdout_pipe=subprocess.PIPE)
        alias_list_str = pybash_util.read_close_fd(s)
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



    # This is the cmd.Cmd function that must be declared to parse arbitrary commands
    def default(self, pipeline_cmd):
        self.run_pipeline(pipeline_cmd)
        self.tab_complete_prompt_flag = False
        
    # Perform event designator expansion before parsing line
    def precmd(self, line):
        # b) Check for event and word designator
        try:
            line = self.expand_designators(line)
        except Exception as e:
            self.stderr_write(e)
            self.write_debug(traceback.format_exc())
        return line

if __name__ == "__main__":
    #pb = pybash()
    #pb.preloop()
    #s,e,p = pb.run_shell_cmd("vim")
    #s,e,p = pb.run_cmd("vim")
    #p.wait()
    #pb.default("vim")
    pybash().cmdloop()



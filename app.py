from pybash import pybash

# Future enhancements:
#  - allow "streaming" execution of python commands

#        - if input to python is a deque with len > 1, could process each pop as they come in
#        - would wait for the input deque to be None (same as a file-like object being 'closed')

"""
Pybash
**************************
Pybash is a command-line interpreter written in python. It's goal is to allow the execution 
of any valid shell or python command - as well as combinations of the two! 
Shell-like pipes, file redirects, and pybash helper functions allow you to move back and 
forth between shell and python to make your life easy. 

Examples
=========================
Some examples of commands that can be executed in the pybash interpreter:
1. (pure shell): find . -name "*.xml" | xargs -I % cp % /path/to/dir/%.backup
2. (pure python): foo = [bar['value'] for bar in foo if 'test' in bar and bar['test'] == 2]
3. (shell+python): find . - name "*.yaml" | [s for s in @ if 'test_str' in s] | xargs cat > out.yaml
4. (shell+python): dict_list = find . -name "*.yaml" | [from_file(f) for f in @] | [d for d in @ if 'test_key' in d]

Command Execution Flow
========================
Pybash works by determining which parts of a command should be executed in python, and 
which parts by the shell. Python commands are executed using the built-in exec(), and
shell commands are executed using subprocess.Popen(). 

Each command (which may contain multiple pipeline stages) is evaluated as follows:

1. the cmd.Cmd.precmd() function is executed which will expand bash-like designators
2. cmd.Cmd checks for special pybash commands such as cd, history
3. the cmd.Cmd.default() function is executed if no special commands were found, kicking off
  the main pybash command parsing function: run_pipeline() 
4. run_pipeline() splits the input line by '|' and kicks off the execution of each stage of 
  the pipeline
    - the standard pipe is initiated and managed by this function
    - redirect parsing is done for each stage
5. each stage of the pipeline is processed using the run_cmd() function
    - pre-processes the command (aliases) and input variables
    - run_cmd() will call run_shell_cmd() or run_python_cmd() as appropriate
6. run_pipeline() gets the results fo run_shell_cmd() / run_python_cmd()
    - outputs will be passed to the next stage in the pipeline
    - if this is the last stage, any open file handles are closed and assignment to
      python variables is performed

Pipes and Redirects
======================= 
Pybash handels piping and redirects using the std_pipe variable.  This is a 3-element tuple
which contains the "location" of (stdin, stdout, stderr). The elements of std_pipe will resolve
to either a file-like object (e.g. a file or os.pipe), None, or /dev/null. More details on
std_pipe bellow.

Redirects are perfomed by changing the "location" in std_pipe to either another file-like
object or to reference the location of another element in std_pipe. This allows pybash to
emulate bash-like redirects such as 'cmd > foo' or 'cmd > foo 2>&1'.

Redirects are parsed BEFORE knowning if it is a shell or python cmd
   - For this to work, run_bash_cmd() and run_python_cmd() must treat std_pipe the same way
   - Opening pipes occurs inside these commands since they do so in different ways
       - shell: pipe = r/w pair of file handles
       - python: pipe = collections.deque object
   - Opening files occures before run_bash_cmd() / run_python_cmd() 
       - Files are opened the same way
       - The read / write / append mode must be known, these commands are agnostic to this

Notes on std_pipe
====================================

Each element of std_pipe can be:
    None: 
        - stdin: nothing will be passed to python / shell cmd
        - stdout / stderr: output will be written to sys.stdout/sys.stderr
    subprocess.PIPE:
        - shell: an os.pipe() will be opened using pybash_helper.open_pipe()
            - This creates file objects for the cmd to write to, next cmd to read from
        - python cmd: return value / error will be added to a deque
    file-like object:
        - stdin: cmd will read from this file
            - shell: pass to subprocess.Popen()
            - python: read as string and close
        - stdout / stderr: output will be written to this file
    str:
        - a file objected is opened for this file path
            - shell: binary mode ('rb', 'wb', 'ab')
            - python: text  mode ('r', 'w', 'a')
    [0,1,2]:
        - Used for redirects AFTER other std_pipe elements are processed (e.g. pipe opened) 
        - e.g. if std_pipe = [None, subprocess.PIPE, 1]:
            a) nothing passed to cmd input
            b) pybash_helper.open_pipe() alled for stdout
            c) write file-object for stdout is copied for stderr

"""



# Launch main loop
if __name__ == "__main__":
    pybash().cmdloop()

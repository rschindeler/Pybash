Under The Hood
================================

.. |pybash_runner| replace:: :class:`pybash_runner <pybash.command.pybash_runner.pybash_runner>`
.. |pybash_cmd| replace:: :class:`pybash_cmd <pybash.command.pybash_cmd.pybash_cmd>`
.. |run_pipeline| replace:: :meth:`run_pipeline <pybash.command.pybash_runner.pybash_runner.run_pipeline>`
.. |run_cmd| replace:: :meth:`run_cmd <pybash.command.pybash_runner.pybash_runner.run_cmd>`
.. |run_shell_cmd| replace:: :meth:`run_shell_cmd <pybash.command.pybash_runner.pybash_runner.run_shell_cmd>`
.. |run_python_cmd| replace:: :meth:`run_python_cmd <pybash.command.pybash_runner.pybash_runner.run_python_cmd>`
.. |pybash_helper.open_pipe| replace:: :meth:`pybash_helper.open_pipe <pybash.util.pybash_helper.open_pipe>`
.. |pybash| replace:: :class:`pybash <pybash.pybash.pybash>`


Pybash works by determining which parts of a command should be executed in python, and 
which parts by the shell. 
    * Python commands are executed using the built-in :func:`exec`
    * Shell commands are executed using :class:`subprocess.Popen`

Overview
---------------------------------

The Pybash interpreter is launched by creating an instance of the |pybash| class and calling its
cmdloop() method (see :meth:`cmd.Cmd.cmdloop`). The |pybash| class extends the following:

    * |pybash_cmd|
        * Extends :class:`cmd.Cmd` as the basis for the command-line interface
        * Shell-like commands such as cd , sudo, history, exit
        * Managment of Pybash configuration variables in :attr:`cmd_flags`
        * Shell-like tab autocomplete 
    * |pybash_runner| 
        * Contains methods for executing shell and python commands
        * Splits pipeline commands into their stages and manages the piping between them
        * Handles redirects to files, python variables

Command Execution Flow
---------------------------------

Each command (which may contain multiple pipeline stages) is evaluated as follows:

    1. The :meth:`cmd.Cmd.precmd` method is executed which will expand bash-like designators 
        - For example: !$, !!
    2. :class:`cmd.Cmd` checks for special Pybash commands such as cd, history
    3. The :meth:`cmd.Cmd.default` method is executed if no special commands were found, kicking off
       the main Pybash command parsing method: |run_pipeline|
    4. |run_pipeline| splits the input line by '|' 
       and kicks off the execution of each stage of the pipeline
        - The standard pipe is initiated and managed by this method
        - Redirect parsing is done for each stage
    5. Each stage of the pipeline is processed and executed using the |run_cmd| method
        - Pre-processes the command (aliases) and input variables
        - |run_cmd| will call |run_shell_cmd| or |run_python_cmd| as appropriate
    6. |run_pipeline| gets the results of |run_shell_cmd| / |run_python_cmd|
        - Outputs will be passed to the next stage in the pipeline
        - If this is the last stage, any open file handles are closed and assignment to
          python variables is performed

Pipes and Redirects
---------------------------------
Pybash handles piping and redirects using the std_pipe variable.  This is a 3-element tuple
which contains the "location" of (stdin, stdout, stderr). The std_pipe is created by |run_pipeline|
before executing the first stage of the pipeline, and is passed to each subsequent stage.

The elements of std_pipe will resolve to either a file-like object (e.g. a file or :func:`os.pipe`), 
:const:`None`, or */dev/null*. More details on std_pipe bellow.

Redirects are performed by changing the "location" in std_pipe to either another file-like
object or to reference the location of another element in std_pipe. This allows Pybash to
emulate bash-like redirects such as 'cmd > foo' or 'cmd > foo 2>&1'.

Redirects are parsed BEFORE knowing if it is a shell or python cmd
   - For this to work, |run_shell_cmd| and |run_python_cmd| must treat std_pipe the same way
   - Opening pipes occurs inside these commands since they do so in different ways
       - shell: pipe = r/w pair of file handles
       - python: pipe = collections.deque object
   - Opening files occurs before |run_shell_cmd| / |run_python_cmd| 
       - Files are opened the same way
       - The read / write / append mode must be known, these commands are agnostic to this

Notes on std_pipe
---------------------------------

Each element of std_pipe can be:
    * :const:`None`: 
        - stdin: nothing will be passed to python / shell cmd
        - stdout / stderr: output will be written to sys.stdout/sys.stderr
    * :data:`subprocess.PIPE`:
        - shell: an :func:`os.pipe` will be opened using |pybash_helper.open_pipe|
            - This creates file objects for the cmd to write to, next cmd to read from
        - python cmd: return value / error will be added to a deque
    * file-like object:
        - stdin: cmd will read from this file
            - shell: pass to :class:`subprocess.Popen`
            - python: read as string and close
        - stdout / stderr: output will be written to this file
    * str:
        - a file objected is opened for this file path
            - shell: binary mode ('rb', 'wb', 'ab')
            - python: text  mode ('r', 'w', 'a')
    * int (0, 1, or 2):
        - Used for redirects AFTER other std_pipe elements are processed (e.g. pipe opened) 
        - e.g. if std_pipe = [:const:`None`, :data:`subprocess.PIPE`, 1]:
            a) nothing passed to cmd input
            b) |pybash_helper.open_pipe| called for stdout
            c) write file-object for stdout is copied for stderr

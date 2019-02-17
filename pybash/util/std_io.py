import sys

class pybash_io:
    """
    Class that manages IO functions such as printing to stdout / stderr
    """

    # Functions to write to stdout and stderr
    
    
    def stdout_write(self, msg, print_line=True):
        """
        Function to write string to terminal stdout

        Args:
            msg (str): String to be written
            print_line (bool): If True then a newline will be added to the string (default)
        """
        if msg:
            sys.stdout.write(str(msg))
            if print_line:
                sys.stdout.write("\n")
    
    def stderr_write(self, msg, print_line=True):
        """
        Function to write string to terminal stderr

        Args:
            msg (str): String to be written
            print_line (bool): If True then a newline will be added to the string (default)
        """
        if msg:
            sys.stderr.write(str(msg))
            if print_line:
                sys.stderr.write("\n")

    def print_error(self, text):
        """
        Function to write a pybash error to stderr
        Args:
            text (str): Error text 
        """
        self.stderr_write("-pybash: %s" % text)
    

    def write_debug(self, msg, fn=None):
        """
        Function to write a pybash debug message to stdout
        Args:
            msg (str): Debug message text
            fn (str): Optional string used to print the function generating the debug message
        """
        if self.cmd_flags['debug']:
            fn_str = str(fn) + "() - " if fn else ""
            if type(msg) == list:
                for m in msg:
                    self.stdout_write("[DEBUG] " + fn_str + str(m))
            else:
                self.stdout_write("[DEBUG] " + fn_str + str(msg))

import sys

# Class that manages IO functions such as printing to stdout / stderr
class pybash_io:
    # Functions to write to stdout and stderr
    def stdout_write(self, msg, print_line=True):
        if msg:
            sys.stdout.write(str(msg))
            if print_line:
                sys.stdout.write("\n")
    def stderr_write(self, msg, print_line=True):
        if msg:
            sys.stderr.write(str(msg))
            if print_line:
                sys.stderr.write("\n")
    def print_error(self, text):
        self.stderr_write("-pybash: %s" % text)
    
    def write_debug(self, msg, fn=None):
        if self.cmd_flags['debug']:
            fn_str = str(fn) + "() - " if fn else ""
            if type(msg) == list:
                for m in msg:
                    self.stdout_write("[DEBUG] " + fn_str + str(m))
            else:
                self.stdout_write("[DEBUG] " + fn_str + str(msg))

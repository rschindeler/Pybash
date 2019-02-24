import re

import pybash.util.pipe_util

# Some parsing functions are handeled by subclasses 
from pybash.parsing.designator_parser import designator_parser
from pybash.parsing.parameter_parser import parameter_parser

class parser(designator_parser, parameter_parser):
    """
    Class to manage parsing / expansion of commands:
     1. event and word designators (e.g. !!, !$) (designator_parser class)
     2. parameter expansion (e.g. ${var:4} (parameter_parser class)
     3. file + pipe redirects

    """

    def redirects(self, cmd, std_pipe):
        """
        Function to process all redirects in a command string. Redirects are implemented using 
        the std_pipe variable, which describes the "location" of the command's  stdin/stdout/stderr
        This function will look for '>', '>>', '<' in command, parse the redirect, then return the 
        command with the redirect remove.

        For example: echo foo >> bar 2>&1
        
        Args:
            cmd (str): Command which may contain 0 or more redirect statements
            std_pipe (tuple): pybash std_pipe variable containing "location" of stdin/stdout/stderr

        Returns:
            (str) Command with all redirect text removed
        """

        # All cmds start with these r/w modes by default
        std_modes = ['r', 'w', 'w']
        # TODO: stdin redirect from file   
        # TODO: add support for /dev/null
        cmd_in = cmd
        while '<' in cmd or '>' in cmd:
            self.write_debug("iteration:", "redirects")
            self.write_debug("\tcmd: %s" % cmd, "redirects")
            self.write_debug("\tfds: %s" % [std_modes[i] + ' ' + str(std_pipe[i]) for i in range(3)], "redirects")
            
            ###################################################################
            # Step 1: Look for different types of matches
            matches = [re.match(d['regex'], cmd) for d in self.redirect_definitions]
            self.write_debug("matches: %s" % matches, "redirects")
            
            # Get the location of each match so that we can process them from left to right
            match_loc = [len(m.groups()[0]) if m else None for m in matches]
            self.write_debug("match_loc %s" % match_loc, "redirects")
            
            # Select the match that has the lowest position
            matches_found = [l for l in match_loc if l]
            if len(matches_found) < 1:
                self.write_debug("error: could not parse redirects in cmd %s" % cmd_in, "redirects")
                return

            min_loc = min(matches_found)
            min_loc_index = [i for i in range(len(match_loc)) if match_loc[i] == min_loc]
            if len(min_loc_index) > 0:
                min_loc_index = min_loc_index[0]
            else:
                break
            self.write_debug("min_loc_index: %s" % min_loc_index, "redirects")
            m = matches[min_loc_index]
            
            ###################################################################
            # Step 2: Get the operation definition and execute
            op_def = self.redirect_definitions[min_loc_index]
            
            # Use the op_def['cmd_out'] array to get the indexes that comprise the output cmd 
            self.write_debug("Remaining cmd: %s" % [m.groups()[i] for i in op_def['cmd_out']], "redirects")
            cmd = "".join([m.groups()[i] for i in op_def['cmd_out']])
            # Either use the default descriptor or parse the one specified by op_def['descriptor_index']
            if op_def['default_descriptor']:
                file_d_index =  op_def['default_descriptor']
            else:
                file_d_index = int(m.groups()[op_def['descriptor_index']])
            # Get the value
            value = m.groups()[op_def['value_index']]
            self.write_debug("Executing op %s for fd index %i to %s" % (op_def['name'], file_d_index, value), "redirects")

            pipe_util.fd_assign(file_d_index, op_def['mode'], value, std_pipe)
            self.write_debug("Assigned file descriptor index %i = %s" % (file_d_index, std_pipe[file_d_index]), "redirects")
        
        self.write_debug("cmd_out: %s" % cmd, "redirects")
        return cmd

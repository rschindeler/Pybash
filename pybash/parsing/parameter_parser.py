import re

from pybash.util.std_io import pybash_io
import pybash.util.pybash_helper

class parameter_parser(pybash_io):
    """
    Class to handle the parsing and expansion of bash-like parameters (e.g. ${var:3})
    """

    shell_param_regex = '\$([a-zA-Z0-9_]+)'
    shell_param_brace_regex = '\${([^}^$]+)}'
    # Based on: https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html
    def parameter_expansion(self, cmd):
        """
        Function to perform bash-like parameter expansion 

        Args:
            cmd (str): Command string which may contain bash-like parameters

        Returns:
            (str): Modified command string with expanded parameters

        """
        # Loop until all parameter expansions have been processed
        expansion_limit = 100
        expansion_counter = 0
        while True:
            param_match = re.search(self.shell_param_regex, cmd)
            param_brace_match = re.search(self.shell_param_brace_regex, cmd)
            # If nothing left, break
            if not param_match and not param_brace_match:
                break
            if expansion_counter > expansion_limit:
                self.write_error("Parameter expansion limit reached")
                break
            try:
                # First try parameter expansions in curly braces
                if param_brace_match:
                    start, end = param_brace_match.start(), param_brace_match.end()
                    # Get the full parameter to expand
                    param = param_brace_match.groups()[0]
                    self.write_debug("Performing brace parameter expansion for param %s" % param, "parameter_expansion")
                    
                    shvar_re = '[a-zA-Z0-9\[\]@\*]+?'
                    substitution_re = shvar_re + ':[-=\?\+]' + shvar_re
                    substring_re = shvar_re + ':' + shvar_re
                    substring_re2 = substring_re + ':' + shvar_re
                    # Check for ':' operator for substitution operators
                    if re.match(substitution_re, param):
                        out = self.expand_substitution_operators(param.split(':'))
                    # Check for ':' operator for substring expansion
                    elif re.match(substring_re, param) or re.match(substring_re2, param):
                        out = self.substring_expansion(param.split(':'))
                    # Check for '!' operator
                    elif param.startswith('!'):
                        out = self.existing_var_expansion(param)
                    # Check for '#' operator at start of param
                    elif param.startswith('#'):
                        out = self.length_expansion(param)
                    else:
                        # Default case: ${parameter} or ${paramter[index]}
                        var = self.list_var_expansion(param)
                        if var:
                            out = pybash_helper.to_str(var, single_line=True)
                        else:
                            out = ""
                        
                # Second try simple parameter expansion
                if param_match:
                    start, end = param_match.start(), param_match.end()
                    param = param_match.groups()[0]
                    self.write_debug("Performing simple parameter expansion for param %s" % param, "parameter_expansion")
                    if param in self.locals:
                        val = self.locals[param]
                        if type(val) == list:
                            if len(val) >= 1:
                                out = str(val[0])
                            else:
                                out = ""
                        else:
                            out = pybash_helper.to_str(self.locals[param], single_line=True)
                    else:
                        out = ""
                
                # Perform substitution
                # TODO: this will overwrite any environment variables
                cmd = cmd[0:start] + out + cmd[end:]
            except Exception as e:
               self.print_error('Invalid parameter expansion: %s' % cmd)
               self.stderr_write(e)
               self.stderr_write(traceback.format_exc())
               break

        return cmd


    # Helper function for dealing with list variables
    def list_var_expansion(self, param):
        self.write_debug("Performing list variable expansion '%s'", "list_var_expansion")
        array_indexing_match = re.match('(.*)\[(.*)\]', param)
        # Check if there is array indexing
        if array_indexing_match:
            self.write_debug("param %s contains list indexing" % param, "list_var_expansion")
            # Get the name of the parameter and the indexes used
            name = array_indexing_match.groups()[0]
            index = array_indexing_match.groups()[1]
            # Check to see if this variable is defined
            if name in self.locals:
                val = self.locals[name]
                # If this is a list, apply list indexing
                if type(val) == list:
                    # Check for '@' or '*' index -> use entire list
                    if index == '@' or index == '*':
                        return val
                    # Check for range indexing
                    elif ':' in index:
                        # Split based on ':' and return the list splice
                        index_parts = index.split(':')
                        index_parts = [int(i) for i in index_parts]
                        if len(index_parts) == 2:
                            self.write_debug("Parsing list indexing: %s:%s" % tuple(index_parts), "list_var_expansion")
                            return val[index_parts[0]:index_parts[1]]
                        elif len(index_parts) == 3:
                            self.write_debug("Parsing list indexing: %s:%s:%s" % tuple(index_parts), "list_var_expansion")
                            return val[index_parts[0]:index_parts[1]:index_parts[2]]
                        else:
                            raise ValueError ("Invalid array indexing: '%s'" % index)
                    # Default: use index as integer directly
                    else:
                        return val[int(index)]
                # If this is a dict, return value of this 'key'
                elif type(val) == dict:
                    self.write_debug("Parsing dict indexing: %s" % index, "list_var_expansion")
                    if index in val:
                        return val[index]
                    else:
                        return None
                # Default: return value directly
                else:
                    return val
            else:
                return None
        else:
            self.write_debug("param %s does not contain list indexing" % param, "list_var_expansion")
            # No array indexing, return value if it it is defined
            if param in self.locals:
                val = self.locals[param]
                return val
            else:
                return None
    
    # Length expansion
    def length_expansion(self, param):
        self.write_debug("Performing length expansion '%s'" % param, "length_expansion")
        name = param[1:] 
        val = self.list_var_expansion(name)
        if val:
            if type(val) == list or type(val) == str:
                return str(len(val))
            else:
                return str(len(str(val)))
        else:
            return ""

    # Expands prefix and array indices
    # ${!prefix*} / ${!prefix@}
    # ${!name[@]} / ${!name[*]}
    def existing_var_expansion(self, param):
        self.write_debug("Performing existing variable expansion '%s'" % param, "existing_var_expansion")
        if param.endswith('*') or param.endswith('@'):
            prefix = param[1:-1]
            matches = [key for key in self.locals if key.startswith(prefix)]
            return pybash_helper.to_str(matches, single_line=True)
        elif param.endswith('[@]') or param.endswith('[*]'):
            val = self.list_var_expansion(param[1:])
            if type(val) == list:
                return pybash_helper.to_str([i for i in range(len(val))], single_line=True)
            else:
                return "0"
        else:
            raise ValueError ("Invalid prefix / list index expansion: '%s'" % param)

    def expand_substitution_operators(self, param_parts):
        self.write_debug("Performing substitution expansion '%s'" % param_parts, "expand_substitution_operators")
        # Operation is determined by the first character of the second element
        # case: ${parameter:-word}
        if param_parts[1][0] == '-':
            # If parameter is unset or null, the expansion of word is substituted. Otherwise, the value of parameter is substituted. 
            if param_parts[0] in self.locals:
                return pybash_helper.to_str(self.locals[param_parts[0]], single_line=True)
            else:
                return param_parts[1][1:]
        # case: ${parameter:=word}
        elif param_parts[1][0] == '=':
            # If parameter is unset or null, the expansion of word is assigned to parameter. The value of parameter is then substituted. 
            if param_parts[0] in self.locals:
                return pybash_helper.to_str(self.locals[param_parts[0]], single_line=True)
            else:
                out = param_parts[1][1:]
                self.locals[param_parts[0]] = out
                return out
        # case: ${parameter:?word}
        elif param_parts[1][0] == '?':
            # If parameter is null or unset, the expansion of word (or a message to that effect if word is not present) is written to the standard error and the shell, if it is not interactive, exits. Otherwise, the value of parameter is substituted. 
            # TODO: this will only write to shell stderr
            if param_parts[0] in self.locals:
                return pybash_helper.to_str(self.locals[param_parts[0]], single_line=True)
            else:
                if len(param_parts[1]) > 1:
                    self.stderr_write("pybash: %s: %s" % (param_parts[0], param_parts[1][1:]))
                else:
                    self.stderr_write("pybash: %s: parameter null or not set" % (param_parts[0]))
                return ""
        # case: ${parameter:+word}
        elif param_parts[1][0] == '+':
            # If parameter is null or unset, nothing is substituted, otherwise the expansion of word is substituted. 
            if param_parts[0] in self.locals:
                return param_parts[1][1:]
            else:
                return ""

        # otherwise: This is a Substring Expansion
        #       ${parameter:offset} / ${parameter:offset:length}
        else:
            # - expands to up to "length" characters of the value of "parameter" starting at the character specified by "offset"
            raise ValueError ("Unknown substitution operation %s" % ":".join(param_parts))

    def substring_expansion(self, param_parts):
        self.write_debug("Performing substring expansion '%s'" % param_parts, "substring_expansion")
        # get length, offset and end
        if len(param_parts) == 3:
            # ${parameter:offset:length}
            param = param_parts[0]
            offset = int(param_parts[1])
            length = int(param_parts[2])
            if length >= 0:
                end = offset + length
            else:
                end = length
        elif len(param_parts) == 2:
            # ${parameter:offset}
            param = param_parts[0]
            offset = int(param_parts[1])
            end = None
        else:
            raise ValueError ("Unknown substring expansion %s" % ":".join(param_parts))
        # Get output  
        val = self.list_var_expansion(param)
        if val:
            # For lists, use array indexing
            if type(val) == list:
                out = pybash_helper.to_str(val[offset:end], single_line=True)
            # For other types, convert to string and index using characters
            else:
                out = pybash_helper.to_str(val, single_line=True)[offset:end]
            return out
        else:
            return ""

    
    # This regex will pick up the first assignment (a = b) in a command
    # but exclude other commands with '=' such as 'a == b' or 'a <= b'
    assignment_regex = '^([A-Za-z0-9_]+)[ ]*[^\>\<=]*=[ ]*([^=].*)$'
    def get_assignment(self, cmd):
        """
        Function to parse assignment in a command, returns output variable and cmd to be evaluated
        
        Args:
            cmd (str): Command that may be in the form 'var = expression' where 'var' is the output 
                variable and 'expression' is a valid pybash expression
        Returns:
            tuple: (expression, var) Separated input command if an assignment was detected.  If no 
                assignment was detected, then expression = cmd and var = :const:`None`

        """
        self.write_debug("Checking command for assignment: %s" % cmd)
        assignment_match = re.match(self.assignment_regex, cmd)
        if assignment_match:
            output_var = assignment_match.groups()[0]
            cmd = assignment_match.groups()[1]
            self.write_debug("Detected assignment: %s = %s" % (output_var, cmd))
        else:
            output_var = None
        return cmd, output_var
    
    redirect_definitions = [
            {'name': 'append_specify', 
             'regex': '(.*?)([0-9]+)>>[ ]*([^ ]+)(.*)',
             'cmd_out': [0, 3],
             'default_descriptor': None,
             'descriptor_index': 1,
             'mode': 'a',
             'value_index': 2},
            {'name': 'append_default', 
             'regex': '(.*?[^0-9])>>[ ]*([^>^ ]+)(.*)',
             'cmd_out': [0, 2],
             'default_descriptor': 1,
             'descriptor_index': None,
             'mode': 'a',
             'value_index': 1},
            {'name': 'write_specify', 
             'regex': '(.*?)([0-9]+)>[ ]*([^ ^>]+)(.*)',
             'cmd_out': [0, 3],
             'default_descriptor': None,
             'descriptor_index': 1,
             'mode': 'w',
             'value_index': 2},
            {'name': 'write_default', 
             'regex': '(.*?[^0-9])>[ ]*([^ ^>]+)(.*)',
             'cmd_out': [0, 2],
             'default_descriptor': 1,
             'descriptor_index': None,
             'mode': 'w',
             'value_index': 1}]

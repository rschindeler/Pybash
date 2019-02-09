import subprocess
import re
import os
import sys
import StringIO
from collections import deque
import traceback
import copy
import readline

from pybash_cmd import pybash_cmd
import pybash_helper, pybash_util


def last_matching_char(r, s, i=0):
    k = i
    while k < len(s):
        if not re.match(r, s[k]):
            return k - 1
        k += 1
    return k - 1

class pybash_parser():

    # Function to expand bash-like event and word designators such as !!:3, !$ !!
    # REF: https://www.gnu.org/software/bash/manual/bashref.html#Event-Designators
    def expand_designators(self, cmd):
        # If any expansion is done, replace history line at the end
        expansion_performed = False

        # Loop until there are no more '!' in cmd
        parse_start_index = 0
        while True:
            ###########################################################################
            # Step 1) Find the begining of a history event designator 
            # Starting at parse_start_index, find the first index of '!' in cmd
            loc = -1
            for i in range(parse_start_index, len(cmd)):
                if cmd[i] == '!' or cmd[i] == '^':
                    loc = i
                    break
            if loc < 0:
                break
            
            self.write_debug("Found '!' in cmd at index %i" % loc)
            
            ###########################################################################
            # Step 2) Determine the correct history line index to use
            #   - output: 
            #      - history_line: readline history index
            #      - next_loc: next character location to parse
            #      - parse_word_designator: flag which is set if short-form word designator is found
            history_line, next_loc, parse_word_designator = self.expand_event_designator(cmd, loc)
            self.write_debug("Using history line %s, next character location to parse: %i" % (history_line, next_loc))

            # If nothing found, skip
            if not history_line:
                # Update the parsing start index for the next iteration
                parse_start_index = next_loc
                continue
            else:
                # Set this flag so that history will be updated with the expansion
                expansion_performed = True
            
            ###########################################################################
            # Step 3) Get the history line to replace - special case for !#
            if history_line is True:
                replace_val = cmd[0:loc]
            else:
                # Get the entire history line before processing word designators
                if history_line < 0:
                    history_line = readline.get_current_history_length() + history_line
                replace_val = readline.get_history_item(history_line)
            
            ###########################################################################
            # Step 4) Parse word designators
            # Check for a ':' after the event designator
            #  - Note: The parse_word_designator may have already been set if using a shortform
            if next_loc < len(cmd)-1 and cmd[next_loc] == ':':
                parse_word_designator = True
                next_loc += 1
            if parse_word_designator:
                next_loc, replace_val = self.expand_word_designator(cmd, next_loc, replace_val)
           
            ###########################################################################
            # Step 5) Perform expansion
            if next_loc < len(cmd) - 1:
                cmd = cmd[0:loc] + replace_val + cmd[next_loc:]
            else:
                cmd = cmd[0:loc] + replace_val 
            
            # Update the parsing start index for the next iteration
            parse_start_index = next_loc
        
        # Done parsing - edit history if required
        if expansion_performed:
            # Replace most recent line in history
            last_line = readline.get_current_history_length()
            self.write_debug("Repalcing most recent history line %i" % last_line)
            pybash_util.remove_history_item(last_line)
            readline.add_history(cmd)
            # Print the resulting cmd to stdout (bash does this!)
            sys.stdout.write(cmd + "\n") 
        
        # Done parsing, return modified command
        return cmd
        

    # Function to perform event designator expansion
    # Input:
    #   - cmd: the command being parsed
    #   - loc: the current character index to parsethe event designator
    # Output:
    #   - history_line: the line selected from the history to be substitued
    #   - next_loc: location of the next character in cmd to be parsed
    #   - parse_word_designator: flag that is set if a short-form word designator is detected
    def expand_event_designator(self, cmd, loc):
        # Set this flag to False by default - will be set tyo True if short-form word designator is found
        parse_word_designator = False
        # Set to None for now - if it not set by any of the conditions bellow, this designator will be skipped
        history_line = None

        # Regex definitions
        num_re = '[0-9]'
        alph_re = '[a-zA-Z]'

        # TODO: ^string1^string2^
       
        # Check reference to history line (or relative history line) 
        #   e.g. !100, !-2
        if cmd[loc+1] == '-' or re.match(num_re, cmd[loc+1]): 
            next_loc = last_matching_char(num_re, cmd, loc+2) + 1
            history_line = int(cmd[loc+1:next_loc])
            self.write_debug("Expanding 'previous line' event designator: %i" % history_line, "expand_designators")

        # Check for short-form word designator
        #   e.g. !$, !*
        elif cmd[loc+1] in ['^', '$', '*', '-', '%']:
            next_loc = loc+1
            self.write_debug("Expanding 'short form' word designator '%s'" % cmd[loc+1], "expand_designators")
            history_line = -1
            parse_word_designator = True
        # Check reference to previous command
        #   e.g. !!
        elif cmd[loc+1] == '!':
            next_loc = loc+2
            history_line = -1
            self.write_debug("Expanding 'previous command' event designator", "expand_designators")
        # Check for short form - next character will be a ':'
        elif cmd[loc+1] == ':':
            next_loc = loc+2
            history_line = -1
            parse_word_designator = True
            self.write_debug("Expanding 'previous command' event designator with shortform word designator", "expand_designators")
        # Check for reference to history line starting with a string
        #   e.g. !pattern
        elif re.match(alph_re, cmd[loc+1]):
            next_loc = last_matching_char(alph_re, cmd, loc+1) + 1
            pattern = cmd[loc+1:next_loc]
            self.write_debug("Expanding 'previous line starts with' event designator: '%s'" % pattern, "expand_designators")
            
            # Search for pattern in history (backwards starting with most recent history item)
            for i in range(readline.get_current_history_length() - 2, 0, -1):
                h_line = readline.get_history_item(i)
                if h_line and h_line.startswith(pattern):
                    history_line = i
                    break

        # Check for reference to history line containing a string
        #   e.g. !?pattern[?]
        elif cmd[loc+1] == '?':
            next_loc = last_matching_char('[^\?]', cmd, loc+2) + 1
            pattern = cmd[loc+2:next_loc]
            self.write_debug("Expanding 'previous line search' event designator: '%s'" % pattern, "expand_designators")
            
            # Search for pattern in history (backwards starting with most recent history item)
            history_line = None
            for i in range(readline.get_current_history_length() - 2, 0, -1):
                h_line = readline.get_history_item(i)
                if pattern in h_line:
                    history_line = i
                    # Keep track of the word that was matched: used for '%' word designator
                    matching_words = [w for w in h_line.split() if pattern in w]
                    if len(matching_words) > 0:
                        self.last_matching_history_search = matching_words[-1]
                    break

        # Check for reference to entire command line typed so far
        #   e.g. !#
        elif cmd[loc+1] == '#':
            next_loc = loc+2
            # Set history line to True - this indicates the current line
            history_line = True
            self.write_debug("Expanding 'line so far' event designator", "expand_designators")

        
        return history_line, next_loc, parse_word_designator

    # Function to perform word designator expansion
    # Inputs: 
    #   cmd: the command that is being parsed
    #   next_loc: the next character index to be parsed (after event designator has been parsed)
    #   replace_val: the line of text that was generated by the event designator
    #
    # Output:
    #    next_loc: updated character index after parsing word designator
    #    replace_val: one or more words selected from the input replace_val
    #
    # For example: !!, !$, !!:4-5
    def expand_word_designator(self, cmd, next_loc, replace_val): 
        # Check for "entire command"
        if cmd[next_loc] == '!':
            # no change
            next_loc += 1
        # Check for "last argument" pattern '$'
        elif cmd[next_loc] == '$':
            replace_val = replace_val.split()[-1]
            next_loc += 1
        # Check for "first argument" pattern '^'
        elif cmd[next_loc] == '^':
            parts = replace_val.split()
            next_loc += 1
            if len(parts) > 2:
                replace_val = parts[1]
            else:
                raise ValueError ("bad word specifier: ^")
        # Check for "last match" pattern '%'
        elif cmd[next_loc] == '%':
            next_loc += 1
            if hasattr(self, 'last_matching_history_search'):
                replace_val = self.last_matching_history_search
            else:
                raise ValueError ("bad word specifier: % (no previous history search)")
        # Check for "all arguments" pattern '*'
        elif cmd[next_loc] == '*':
            next_loc += 1
            parts = replace_val.split()
            if len(parts) > 2:
                replace_val = " ".join(parts[1:])
            else:
                raise ValueError ("bad word specifier: ^")
        # Check for numeric pattern (allowing for x-y, x*, x-$)
        elif re.match('[\*$\-0-9]', cmd[next_loc]):
            # Isolate numeric word designator
            start = next_loc
            end = last_matching_char('[\*$\-0-9]', cmd, next_loc) + 1
            word_designator = cmd[start:end]
            self.write_debug("Processing numeric word designator %s" % word_designator)
            next_loc = end
            # Get range of words 
            # Simple case - number only
            if re.match('[0-9]+$', word_designator):
                self.write_debug('Got simple numeric word designator: %s' % (word_designator))
                try:
                    parts = replace_val.split()
                    replace_val = parts[int(word_designator)]
                except Exception as e:
                    self.print_error(e)
                    raise ValueError ("bad word specifier: %s" % word_designator)
            # Check for x-y pattern
            elif re.match('[0-9\$]+-[0-9\$]+$', word_designator):
                start, end = word_designator.split('-')
                self.write_debug('Got start and end numeric word designator: %s to %s' % (start, end))
                try:
                    parts = replace_val.split()
                    # Replace '$'
                    start = len(parts) - 1 if start == '$' else start
                    end = len(parts) - 1 if end == '$' else end
                    # Get range
                    replace_val = " ".join(parts[int(start):int(end)+1])
                except Exception as e:
                    self.print_error(e)
                    raise ValueError ("bad word specifier: %s" % word_designator)
            # Check for '-y' pattern (short for 'x-y')
            elif re.match('-[0-9\$]+$', word_designator):
                start, end = word_designator.split('-')
                start = 0
                try:
                    parts = replace_val.split()
                    # Replace '$'
                    end = len(parts) - 1 if end == '$' else end
                    # Get range
                    replace_val = " ".join(parts[start:int(end)+1])
                except Exception as e:
                    self.print_error(e)
                    raise ValueError ("bad word specifier: %s" % word_designator)
            # Check for 'x*' pattern (short for 'x-$')
            elif re.match('([0-9]+)\*$', word_designator):
                start = word_designator[:-1]
                try:
                    replace_val = " ".join(replace_val.split()[int(start):])
                except Exception as e:
                    self.print_error(e)
                    raise ValueError ("bad word specifier: %s" % word_designator)
            # Check for 'x*' pattern (short for 'x-$')
            elif re.match('([0-9]+)-$', word_designator):
                start = word_designator[:-1]
                try:
                    replace_val = " ".join(replace_val.split()[int(start):-1])
                except Exception as e:
                    self.print_error(e)
                    raise ValueError ("bad word specifier: %s" % word_designator)
            else:
                raise ValueError ("bad word specifier: %s" % word_designator)
        self.write_debug("Word designator result: %s" % (replace_val))
        return next_loc, replace_val

    # Function to perform bash-like parameter expansion
    shell_param_regex = '\$([a-zA-Z0-9_]+)'
    shell_param_brace_regex = '\${([^}^$]+)}'
    # Function to perform bash-like parameter expansion 
    # Based on: https://www.gnu.org/software/bash/manual/html_node/Shell-Parameter-Expansion.html
    def parameter_expansion(self, cmd):
        # Loop untill all parameter expansions have been processed
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
                    # Get the full paramter to expand
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
                        # Default case: ${parameter} or ${paramer[index]}
                        var = self.list_var_expansion(param)
                        if var:
                            out = pybash_helper.to_str(var, single_line=True)
                        else:
                            out = ""
                        
                # Second try simple paramter expansion
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
                # TODO: this will overrite any environemnt variables
                cmd = cmd[0:start] + out + cmd[end:]
            except Exception as e:
               self.print_error('Invalid prarameter expansion: %s' % cmd)
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
            # - expands to up to "length" characters of the value of "parameter" starting at the caracter specified by "offset"
            raise ValueError ("Unknown subsitition operation %s" % ":".join(param_parts))

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

    assignment_regex = "^([A-Za-z0-9_]+)[ ]*=(.*)"
    # Function to parse assignemnt in a command, returns output variable and cmd to be evaluated
    def get_assignment(self, cmd):
        assignment_match = re.match(self.assignment_regex, cmd)
        if assignment_match:
            output_var = assignment_match.groups()[0]
            cmd = assignment_match.groups()[1]
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
         
    # Function to process all redirects in a command string
    #    - Redirects are implemented using the std_pipe variable, which describes the "destination" of the command stdout/stderr + "location" of the stdin
    #    - Look for '>', '>>', '<' in command
    #    - For example: echo foo >> bar 2>&1
    def redirects(self, cmd, std_pipe):
        # All cmds start with these r/w modes by default
        std_modes = ['r', 'w', 'w']
        
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

            pybash_util.fd_assign(file_d_index, op_def['mode'], value, std_pipe)
            self.write_debug("Assigned file descriptor index %i = %s" % (file_d_index, std_pipe[file_d_index]), "redirects")
        
        self.write_debug("cmd_out: %s" % cmd, "redirects")
        return cmd

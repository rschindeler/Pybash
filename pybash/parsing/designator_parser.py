import re
import readline

from pybash.util.std_io import pybash_io
import pybash.util.history_util as history_util

def last_matching_char(r, s, i=0):
    """
    Function to get the index of the last sequential character matching a regex,
    optionally starting at a specific index
    For example, find the last numeric character in a string:

    ::
        last_matching_char('[0-9]', 'asdf1234qwer', 4)
      
    would match '4' at index 7

    Args:
        r (str): regex which matches a single character
        s (str): string representing the character sequence to search in
        i (int): Optional (default = 0) start index to begin searching

    """
    k = i
    while k < len(s):
        if not re.match(r, s[k]):
            return k - 1
        k += 1
    return k - 1

class designator_parser(pybash_io):
    """
    Class to manage parsing bash-like event and word designators
    """

    # REF: https://www.gnu.org/software/bash/manual/bashref.html#Event-Designators
    def expand_designators(self, cmd):
        """
        # Function to expand bash-like event and word designators such as !!:3, !$ !!

        Args:
            cmd (str): Command string which may contain bash-like event and word designators

        Returns:
            (str): Modified command string with all event and word designators expanded    
        """

        # If any expansion is done, replace history line at the end
        expansion_performed = False

        # Loop until there are no more '!' in cmd
        parse_start_index = 0
        while True:
            ###########################################################################
            # Step 1) Find the beginning of a history event designator 
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
            #  - Note: The parse_word_designator may have already been set if using a short form
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
            self.write_debug("Replacing most recent history line %i" % last_line)
            history_util.remove_history_item(last_line)
            readline.add_history(cmd)
            # Print the resulting cmd to stdout (bash does this!)
            self.stdout_write(cmd) 
        
        # Done parsing, return modified command
        return cmd
        

    def expand_event_designator(self, cmd, loc):
        """
        Function to perform event designator expansion
        
        Args:
          - cmd: the command being parsed
          - loc: the current character index to parse the event designator

        Returns:
            (tuple) (history_line, next_loc, parse_word_designator)
         
        Return values:
          - history_line: the line selected from the history to be substituted
          - next_loc: location of the next character in cmd to be parsed
          - parse_word_designator: flag that is set if a short-form word designator is detected

        """
        
        # Set this flag to False by default - will be set to True if short-form word designator is found
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
            self.write_debug("Expanding 'previous command' event designator with short form word designator", "expand_designators")
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

    def expand_word_designator(self, cmd, next_loc, replace_val): 
        """
        Function to perform word designator expansion

        Args: 
            cmd: the command that is being parsed
            next_loc: the next character index to be parsed (after event designator has been parsed)
            replace_val: the line of text that was generated by the event designator

        Returns:
            tuple: (next_loc, replace_val)

        Return values:
            - next_loc: updated character index after parsing word designator
            - replace_val: one or more words selected from the input replace_val
        
        For example: !!, !$, !!:4-5
        """

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

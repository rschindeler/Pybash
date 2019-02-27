from pybash.command.pybash_runner import pybash_runner
from pybash.command.pybash_cmd import pybash_cmd

# Future enhancements:
#  - allow "streaming" execution of python commands

#        - if input to python is a deque with len > 1, could process each pop as they come in
#        - would wait for the input deque to be None (same as a file-like object being 'closed')

"""
Pybash

"""

class pybash(pybash_cmd, pybash_runner):
    """
    Main Pybash application class
    """
    
    def default(self, pipeline_cmd):
        """
        Override the cmd.Cmd function that must be declared to parse arbitrary commands
        """
        self.run_pipeline(pipeline_cmd)
        self.tab_complete_prompt_flag = False

# Launch main loop
if __name__ == "__main__":
    pybash().cmdloop()

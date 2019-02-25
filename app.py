from pybash.command.pybash_runner import pybash_runner
from pybash.command.pybash_cmd import pybash_cmd

# Future enhancements:
#  - allow "streaming" execution of python commands

#        - if input to python is a deque with len > 1, could process each pop as they come in
#        - would wait for the input deque to be None (same as a file-like object being 'closed')

"""
Pybash

TODOs:
    - Python 3 seems to have a different scope when doing list compresions
      This is stopping pybash_helper functions from being used in the "first" part:
       - broken in 3.x: [to_list(f) for f in @] 
       - works in 3.x: [ f for f in to_list(@)]
       - also had to put __inputvar__ in self.globals for python 3.x
"""

class pybash(pybash_cmd, pybash_runner):
    """
    Main pybash application class
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

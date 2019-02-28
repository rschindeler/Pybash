.. _todos-label:

TODO List
=========================
The following are wishlist items and known bugs
    - Python 3 seems to have a different scope when doing list compressions
      This is stopping pybash_helper functions from being used in the "first" part:

       - broken in 3.x: [to_list(f) for f in @] 
       - works in 3.x: [ f for f in to_list(@)]
       - also had to put __inputvar__ in self.globals for python 3.x
    
    - Test and / or implement bash-like execution strings such as:
        - echo `whoami`
        - echo $(whoami)
    - Event designators:
        -  '^string1^string2^'
    - bash-like stdin redirects

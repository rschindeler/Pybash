.. Pybash documentation master file, created by
   sphinx-quickstart on Mon Feb 18 10:30:29 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to Pybash!
==================================

.. toctree::
   :maxdepth: 2
   :caption: Contents:

Pybash is a command-line interpreter written in python. It's goal is to allow the execution 
of any valid shell or python command - as well as combinations of the two! 
Shell-like pipes, file redirects, and Pybash helper functions allow you to move back and 
forth between shell and python to make your life easy. 

Installation and Usage
----------------------------------

Python 2.x
+++++++++++++++++++++++++++++++++
.. code-block:: bash
    :linenos:

    # Pre-requisites 
    sudo apt install python-pip
    pip install pipenv

    # Download the Pybash package

    # Setup virtual environment
    cd path/to/Pybash/
    vim Pipfile
    # Modify the python_version to your version (e.g. python_version = "2.7")
    
    # Install dependencies 
    pipenv install

    # Launch Pybash
    pipenv run python app.py

    

Python 3.x
+++++++++++++++++++++++++++++++++
See :ref:`todos-label`

.. code-block:: bash
    :linenos:

    # Pre-requisites 
    sudo apt install python-pip3
    pip install pipenv

    # Download the Pybash package

    # Setup virtual environment
    cd path/to/Pybash/
    vim Pipfile
    # Modify the python_version to your version (e.g. python_version = "3.6")
    
    # Install dependencies 
    pipenv install

    # Launch Pybash
    pipenv run python app.py



Documentation
----------------------------------
.. toctree::
    :maxdepth: 2
    :titlesonly:

    modules.rst
    examples.rst
    under_the_hood.rst
    todos.rst
    

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

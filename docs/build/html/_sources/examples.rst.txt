
Examples
=========================
Some examples of commands that can be executed in the pybash interpreter:

Pure Shell
-------------------------
You can use the pybash shell just like any regular old linux shell (in fact, you can pick your own shell!)

.. code-block:: bash
    :linenos:

    cd ~/test
    find . -name "\*.xml" | xargs -I % cp % /path/to/dir/%.backup
    tail -n 2000 /var/log/messages | grep -i ERROR > errors.log

Pure Python
-------------------------
You can use the pybash shell just like the standard python shell

.. code-block:: python
    :linenos:

    foo = [{'test': 2}, {'value': 3}, {'test': 2, 'value': 5}]
    foo = [bar['value'] for bar in foo if 'test' in bar and bar['test'] == 2]
    import re
    test = re.match('[A-Z]* ([0-9]*) [A-Z]*', 'ABCD 123456 EFJH')
    print(test)

Python + Shell
-------------------------
You can pipe back and forth between shell and python - it just works!

.. code-block:: python
    :linenos:

    find . - name "\*.yaml" | [s for s in to_list(@) if 'test' in s] | xargs cat > out.yaml
    dict_list = find . -name "\*.yaml" | [to_dict(from_file(f)) for f in to_list(@)] | [d for d in @ if 'test_key' in d]

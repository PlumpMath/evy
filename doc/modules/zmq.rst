:mod:`evy.patched.zmq` -- ØMQ support
========================================

.. automodule:: evy.patched.zmq
    :show-inheritance:

.. currentmodule:: evy.patched.zmq

.. autofunction:: Context

.. autoclass:: _Context
    :show-inheritance:

    .. automethod:: socket

.. autoclass:: Socket
    :show-inheritance:
    :inherited-members:

    .. automethod:: recv

    .. automethod:: send

.. module:: zmq

:mod:`zmq` -- The pyzmq ØMQ python bindings
===========================================

:mod:`pyzmq <zmq>` [1]_ Is a python binding to the C++ ØMQ [2]_ library written in Cython [3]_. The following is
auto generated :mod:`pyzmq's <zmq>` from documentation.

.. autoclass:: zmq.core.context.Context
    :members:

.. autoclass:: zmq.core.socket.Socket

.. autoclass:: zmq.core.poll.Poller
    :members:


.. [1] http://github.com/zeromq/pyzmq
.. [2] http://www.zeromq.com
.. [3] http://www.cython.org

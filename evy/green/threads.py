#
# Evy - a concurrent networking library for Python
#
# Unless otherwise noted, the files in Evy are under the following MIT license:
#
# Copyright (c) 2012, Alvaro Saurin
# Copyright (c) 2008-2010, Eventlet Contributors (see AUTHORS)
# Copyright (c) 2007-2010, Linden Research, Inc.
# Copyright (c) 2005-2006, Bob Ippolito
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#

import sys

from evy import event
from evy import hubs
from evy import timeout

from evy.support import greenlets as greenlet




__all__ = ['getcurrent', 'sleep', 'spawn', 'spawn_n', 'spawn_after', 'spawn_after_local',
           'GreenThread']


getcurrent = greenlet.getcurrent

def switch (coro, result = None, exc = None):
    if exc is not None:
        return coro.throw(exc)
    return coro.switch(result)


def cede():
    """
    Yield control to another eligible coroutine. It is a cooperative yield.
    For example, if one is looping over a large list performing an expensive
    calculation without calling any socket methods, it's a good idea to call ``cede()``
    occasionally; otherwise nothing else will run.
    """
    hub = hubs.get_hub()
    hub.cede()

def sleep (seconds = 0.0):
    """
    Yield control to another eligible coroutine until at least *seconds* have
    elapsed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. Calling :func:`~threads.sleep` with *seconds* of 0 is equivalent
    to invoking :func:`~threads.cede`
    """
    if seconds == 0.0:
        cede()
    else:
        hub = hubs.get_hub()
        current = getcurrent()
        assert hub.greenlet is not current, 'do not call blocking functions from the mainloop'
        timer = hub.schedule_call_global(seconds, current.switch)
        try:
            hub.switch()
        finally:
            timer.cancel()



def spawn (func, *args, **kwargs):
    """
    Create a greenthread to run ``func(*args, **kwargs)``.  Returns a
    :class:`GreenThread` object which you can use to get the results of the 
    call.
    
    Execution control returns immediately to the caller; the created greenthread is merely scheduled
    to be run at the next available opportunity. Use :func:`spawn_after` to  arrange for greenthreads
    to be spawned after a finite delay.
    """
    hub = hubs.get_hub()
    g = GreenThread(hub.greenlet)
    hub.run_callback(g.switch, func, args, kwargs)
    return g


def spawn_n (func, *args, **kwargs):
    """
    Same as :func:`spawn`, but returns a ``greenlet`` object from which it is not possible to
    retrieve either a return value or whether it raised any exceptions.  This is faster than
    :func:`spawn`; it is fastest if there are no keyword arguments.
    
    If an exception is raised in the function, spawn_n prints a stack trace; the print can be
    disabled by calling :func:`evy.debug.hub_exceptions` with False.
    """

    def _run_callback (func, args, kwargs):
        hub = hubs.get_hub()
        g = greenlet.greenlet(func, parent = hub.greenlet)
        hub.run_callback(g.switch, *args, **kwargs)
        return g
    return _run_callback(func, args, kwargs)


def spawn_after (seconds, func, *args, **kwargs):
    """
    Spawns *func* after *seconds* have elapsed.  It runs as scheduled even if
    the current greenthread has completed.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. The *func* will be called with the given *args* and
    keyword arguments *kwargs*, and will be executed within its own greenthread.
    
    The return value of :func:`spawn_after` is a :class:`GreenThread` object,
    which can be used to retrieve the results of the call.
    
    To cancel the spawn and prevent *func* from being called, 
    call :meth:`GreenThread.cancel` on the return value of :func:`spawn_after`.  
    This will not abort the function if it's already started running, which is 
    generally the desired behavior.  If terminating *func* regardless of whether 
    it's started or not is the desired behavior, call :meth:`GreenThread.kill`.
    """
    hub = hubs.get_hub()
    g = GreenThread(hub.greenlet)
    hub.schedule_call_global(seconds, g.switch, func, args, kwargs)
    return g


def spawn_after_local (seconds, func, *args, **kwargs):
    """
    Spawns *func* after *seconds* have elapsed.  The function will NOT be
    called if the current greenthread has exited.

    *seconds* may be specified as an integer, or a float if fractional seconds
    are desired. The *func* will be called with the given *args* and
    keyword arguments *kwargs*, and will be executed within its own greenthread.
    
    The return value of :func:`spawn_after` is a :class:`GreenThread` object,
    which can be used to retrieve the results of the call.
    
    To cancel the spawn and prevent *func* from being called, 
    call :meth:`GreenThread.cancel` on the return value. This will not abort the 
    function if it's already started running.  If terminating *func* regardless 
    of whether it's started or not is the desired behavior, call
    :meth:`GreenThread.kill`.
    """
    hub = hubs.get_hub()
    g = GreenThread(hub.greenlet)
    hub.schedule_call_local(seconds, g.switch, func, args, kwargs)
    return g



# exc_after (seconds, *throw_args): instead of exc_after, which is deprecated, use  Timeout(seconds, exception)

# deprecate, remove
TimeoutError = timeout.Timeout
with_timeout = timeout.with_timeout


class GreenThread(greenlet.greenlet):
    """
    The GreenThread class is a type of Greenlet which has the additional
    property of being able to retrieve the return value of the main function.  
    Do not construct GreenThread objects directly; call :func:`spawn` to get one.
    """

    def __init__ (self, parent):
        greenlet.greenlet.__init__(self, self.main, parent)
        self._exit_event = event.Event()

    def wait (self):
        """
        Returns the result of the main function of this GreenThread.  If the
        result is a normal return value, :meth:`wait` returns it.  If it raised
        an exception, :meth:`wait` will raise the same exception (though the 
        stack trace will unavoidably contain some frames from within the
        greenthread module).
        """
        return self._exit_event.wait()

    def link (self, func, *curried_args, **curried_kwargs):
        """
        Set up a function to be called with the results of the GreenThread.
        
        The function must have the following signature::
        
            def func(gt, [curried args/kwargs]):
          
        When the GreenThread finishes its run, it calls *func* with itself
        and with the `curried arguments <http://en.wikipedia.org/wiki/Currying>`_ supplied at link-time.
        If the function wants to retrieve the result of the GreenThread, it should call wait()
        on its first argument.
        
        Note that *func* is called within execution context of 
        the GreenThread, so it is possible to interfere with other linked 
        functions by doing things like switching explicitly to another 
        greenthread.
        """
        self._exit_funcs = getattr(self, '_exit_funcs', [])
        self._exit_funcs.append((func, curried_args, curried_kwargs))
        if self._exit_event.ready():
            self._resolve_links()

    def main (self, function, args, kwargs):
        try:
            result = function(*args, **kwargs)
        except:
            self._exit_event.send_exception(*sys.exc_info())
            self._resolve_links()
            raise
        else:
            self._exit_event.send(result)
            self._resolve_links()

    def _resolve_links (self):
        # ca and ckw are the curried function arguments
        for f, ca, ckw in getattr(self, '_exit_funcs', []):
            f(self, *ca, **ckw)
        self._exit_funcs = [] # so they don't get called again

    def kill (self, *throw_args):
        """
        Kills the greenthread using :func:`kill`.  After being killed
        all calls to :meth:`wait` will raise *throw_args* (which default 
        to :class:`greenlet.GreenletExit`).
        """
        return kill(self, *throw_args)

    def cancel (self, *throw_args):
        """
        Kills the greenthread using :func:`kill`, but only if it hasn't
        already started running.  After being canceled,
        all calls to :meth:`wait` will raise *throw_args* (which default 
        to :class:`greenlet.GreenletExit`).
        """
        return cancel(self, *throw_args)


def cancel (g, *throw_args):
    """
    Like :func:`kill`, but only terminates the greenthread if it hasn't
    already started execution.  If the grenthread has already started 
    execution, :func:`cancel` has no effect.
    """
    if not g:
        kill(g, *throw_args)


def kill (g, *throw_args):
    """
    Terminates the target greenthread by raising an exception into it.
    Whatever that greenthread might be doing; be it waiting for I/O or another
    primitive, it sees an exception right away.
    
    By default, this exception is GreenletExit, but a specific exception
    may be specified.  *throw_args* should be the same as the arguments to 
    raise; either an exception instance or an exc_info tuple.
    
    Calling :func:`kill` causes the calling greenthread to cooperatively yield.
    """
    if g.dead:
        return
    hub = hubs.get_hub()
    if not g:
        # greenlet hasn't started yet and therefore throw won't work
        # on its own; semantically we want it to be as though the main
        # method never got called
        def just_raise (*a, **kw):
            if throw_args:
                raise throw_args[0], throw_args[1], throw_args[2]
            else:
                raise greenlet.GreenletExit()

        g.run = just_raise
        if isinstance(g, GreenThread):
            # it's a GreenThread object, so we want to call its main
            # method to take advantage of the notification
            try:
                g.main(just_raise, (), {})
            except:
                pass
    current = getcurrent()
    if current is not hub.greenlet:
        # arrange to wake the caller back up immediately
        hub.ensure_greenlet()
        hub.run_callback(current.switch)
    g.throw(*throw_args)


def waitall (*args):
    """
    Waits for ne ore more GreenThreads
    """
    res = []
    for t in args:
        res.append(t.wait())
    return res


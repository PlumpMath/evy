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


import errno
import new

import evy
from evy.io.pipes import GreenPipe
from evy import patcher
from evy.patched import os
from evy.patched import select

patcher.inject('subprocess', globals(), ('select', select))
subprocess_orig = __import__("subprocess")


# This is the meat of this module, the green version of Popen.
class Popen(subprocess_orig.Popen):
    """
    evy-friendly version of subprocess.Popen
    """

    # We do not believe that Windows pipes support non-blocking I/O. At least,
    # the Python file objects stored on our base-class object have no
    # setblocking() method, and the Python fcntl module doesn't exist on
    # Windows. (see evy.io.sockets.set_nonblocking()) As the sole purpose of
    # this __init__() override is to wrap the pipes for evy-friendly
    # non-blocking I/O, don't even bother overriding it on Windows.
    if not subprocess_orig.mswindows:
        def __init__ (self, args, bufsize = 0, *argss, **kwds):
            # Forward the call to base-class constructor
            subprocess_orig.Popen.__init__(self, args, 0, *argss, **kwds)
            # Now wrap the pipes, if any. This logic is loosely borrowed from 
            # evy.processes.Process.run() method.
            for attr in "stdin", "stdout", "stderr":
                pipe = getattr(self, attr)
                if pipe is not None and not type(pipe) == GreenPipe:
                    wrapped_pipe = GreenPipe(pipe, pipe.mode, bufsize)
                    setattr(self, attr, wrapped_pipe)

        __init__.__doc__ = subprocess_orig.Popen.__init__.__doc__

    def wait (self, check_interval = 0.01):
        # Instead of a blocking OS call, this version of wait() uses logic
        # borrowed from the evy 0.2 processes.Process.wait() method.
        try:
            while True:
                status = self.poll()
                if status is not None:
                    return status
                evy.sleep(check_interval)
        except OSError, e:
            if e.errno == errno.ECHILD:
                # no child process, this happens if the child process
                # already died and has been cleaned up
                return -1
            else:
                raise

    wait.__doc__ = subprocess_orig.Popen.wait.__doc__

    if not subprocess_orig.mswindows:
        # don't want to rewrite the original _communicate() method, we
        # just want a version that uses evy.patched.select.select()
        # instead of select.select().
        try:
            _communicate = new.function(subprocess_orig.Popen._communicate.im_func.func_code,
                                        globals())
        except AttributeError:
            # 2.4 only has communicate
            _communicate = new.function(subprocess_orig.Popen.communicate.im_func.func_code,
                                        globals())

            def communicate (self, input = None):
                return self._communicate(input)

# Borrow subprocess.call() and check_call(), but patch them so they reference
# OUR Popen class rather than subprocess.Popen.
call = new.function(subprocess_orig.call.func_code, globals())
try:
    check_call = new.function(subprocess_orig.check_call.func_code, globals())
except AttributeError:
    pass  # check_call added in 2.5



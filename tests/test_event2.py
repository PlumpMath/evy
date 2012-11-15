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


import evy
from evy import event
from tests import LimitedTestCase

class TestEvent(LimitedTestCase):
    def test_waiting_for_event (self):
        evt = event.Event()
        value = 'some stuff'

        def send_to_event ():
            evt.send(value)

        evy.spawn_n(send_to_event)
        self.assertEqual(evt.wait(), value)

    def test_multiple_waiters (self):
        self._test_multiple_waiters(False)

    def test_multiple_waiters_with_exception (self):
        self._test_multiple_waiters(True)

    def _test_multiple_waiters (self, exception):
        evt = event.Event()
        value = 'some stuff'
        results = []

        def wait_on_event (i_am_done):
            evt.wait()
            results.append(True)
            i_am_done.send()
            if exception:
                raise Exception()

        waiters = []
        count = 5
        for i in range(count):
            waiters.append(event.Event())
            evy.spawn_n(wait_on_event, waiters[-1])
        evy.sleep()  # allow spawns to start executing
        evt.send()

        for w in waiters:
            w.wait()

        self.assertEqual(len(results), count)

    def test_reset (self):
        evt = event.Event()

        # calling reset before send should throw
        self.assertRaises(AssertionError, evt.reset)

        value = 'some stuff'

        def send_to_event ():
            evt.send(value)

        evy.spawn_n(send_to_event)
        self.assertEqual(evt.wait(), value)

        # now try it again, and we should get the same exact value,
        # and we shouldn't be allowed to resend without resetting
        value2 = 'second stuff'
        self.assertRaises(AssertionError, evt.send, value2)
        self.assertEqual(evt.wait(), value)

        # reset and everything should be happy
        evt.reset()

        def send_to_event2 ():
            evt.send(value2)

        evy.spawn_n(send_to_event2)
        self.assertEqual(evt.wait(), value2)

    def test_double_exception (self):
        evt = event.Event()
        # send an exception through the event
        evt.send(exc = RuntimeError('from test_double_exception'))
        self.assertRaises(RuntimeError, evt.wait)
        evt.reset()
        # shouldn't see the RuntimeError again
        evy.Timeout(0.001)
        self.assertRaises(evy.Timeout, evt.wait)

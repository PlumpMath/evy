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


from tests import LimitedTestCase, silence_warnings
from unittest import main
import evy
from evy import coros, spawn, sleep
from evy.event import Event


class TestQueue(LimitedTestCase):
    @silence_warnings
    def test_send_first (self):
        q = coros.queue()
        q.send('hi')
        self.assertEquals(q.wait(), 'hi')

    @silence_warnings
    def test_send_exception_first (self):
        q = coros.queue()
        q.send(exc = RuntimeError())
        self.assertRaises(RuntimeError, q.wait)

    @silence_warnings
    def test_send_last (self):
        q = coros.queue()

        def waiter (q):
            timer = evy.Timeout(0.1)
            self.assertEquals(q.wait(), 'hi2')
            timer.cancel()

        spawn(waiter, q)
        sleep(0)
        sleep(0)
        q.send('hi2')

    @silence_warnings
    def test_max_size (self):
        q = coros.queue(2)
        results = []

        def putter (q):
            q.send('a')
            results.append('a')
            q.send('b')
            results.append('b')
            q.send('c')
            results.append('c')

        spawn(putter, q)
        sleep(0)
        self.assertEquals(results, ['a', 'b'])
        self.assertEquals(q.wait(), 'a')
        sleep(0)
        self.assertEquals(results, ['a', 'b', 'c'])
        self.assertEquals(q.wait(), 'b')
        self.assertEquals(q.wait(), 'c')

    @silence_warnings
    def test_zero_max_size (self):
        q = coros.queue(0)

        def sender (evt, q):
            q.send('hi')
            evt.send('done')

        def receiver (evt, q):
            x = q.wait()
            evt.send(x)

        e1 = Event()
        e2 = Event()

        spawn(sender, e1, q)
        sleep(0)
        self.assert_(not e1.ready())
        spawn(receiver, e2, q)
        self.assertEquals(e2.wait(), 'hi')
        self.assertEquals(e1.wait(), 'done')

    @silence_warnings
    def test_multiple_waiters (self):
        # tests that multiple waiters get their results back
        q = coros.queue()

        sendings = ['1', '2', '3', '4']
        gts = [evy.spawn(q.wait)
               for x in sendings]

        evy.sleep(0.01) # get 'em all waiting

        q.send(sendings[0])
        q.send(sendings[1])
        q.send(sendings[2])
        q.send(sendings[3])
        results = set()
        for i, gt in enumerate(gts):
            results.add(gt.wait())
        self.assertEquals(results, set(sendings))

    @silence_warnings
    def test_waiters_that_cancel (self):
        q = coros.queue()

        def do_receive (q, evt):
            evy.Timeout(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')


        evt = Event()
        spawn(do_receive, q, evt)
        self.assertEquals(evt.wait(), 'timed out')

        q.send('hi')
        self.assertEquals(q.wait(), 'hi')

    @silence_warnings
    def test_senders_that_die (self):
        q = coros.queue()

        def do_send (q):
            q.send('sent')

        spawn(do_send, q)
        self.assertEquals(q.wait(), 'sent')

    @silence_warnings
    def test_two_waiters_one_dies (self):
        def waiter (q, evt):
            evt.send(q.wait())

        def do_receive (q, evt):
            evy.Timeout(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')

        q = coros.queue()
        dying_evt = Event()
        waiting_evt = Event()
        spawn(do_receive, q, dying_evt)
        spawn(waiter, q, waiting_evt)
        sleep(0)
        q.send('hi')
        self.assertEquals(dying_evt.wait(), 'timed out')
        self.assertEquals(waiting_evt.wait(), 'hi')

    @silence_warnings
    def test_two_bogus_waiters (self):
        def do_receive (q, evt):
            evy.Timeout(0, RuntimeError())
            try:
                result = q.wait()
                evt.send(result)
            except RuntimeError:
                evt.send('timed out')

        q = coros.queue()
        e1 = Event()
        e2 = Event()
        spawn(do_receive, q, e1)
        spawn(do_receive, q, e2)
        sleep(0)
        q.send('sent')
        self.assertEquals(e1.wait(), 'timed out')
        self.assertEquals(e2.wait(), 'timed out')
        self.assertEquals(q.wait(), 'sent')

    @silence_warnings
    def test_waiting (self):
        def do_wait (q, evt):
            result = q.wait()
            evt.send(result)

        q = coros.queue()
        e1 = Event()
        spawn(do_wait, q, e1)
        sleep(0)
        self.assertEquals(1, q.waiting())
        q.send('hi')
        sleep(0)
        self.assertEquals(0, q.waiting())
        self.assertEquals('hi', e1.wait())
        self.assertEquals(0, q.waiting())


class TestChannel(LimitedTestCase):
    @silence_warnings
    def test_send (self):
        sleep(0.1)
        channel = coros.queue(0)

        events = []

        def another_greenlet ():
            events.append(channel.wait())
            events.append(channel.wait())

        spawn(another_greenlet)

        events.append('sending')
        channel.send('hello')
        events.append('sent hello')
        channel.send('world')
        events.append('sent world')

        self.assertEqual(['sending', 'hello', 'sent hello', 'world', 'sent world'], events)


    @silence_warnings
    def test_wait (self):
        sleep(0.1)
        channel = coros.queue(0)
        events = []

        def another_greenlet ():
            events.append('sending hello')
            channel.send('hello')
            events.append('sending world')
            channel.send('world')
            events.append('sent world')

        spawn(another_greenlet)

        events.append('waiting')
        events.append(channel.wait())
        events.append(channel.wait())

        self.assertEqual(['waiting', 'sending hello', 'hello', 'sending world', 'world'], events)
        sleep(0)
        self.assertEqual(
            ['waiting', 'sending hello', 'hello', 'sending world', 'world', 'sent world'], events)

    @silence_warnings
    def test_waiters (self):
        c = coros.Channel()
        w1 = evy.spawn(c.wait)
        w2 = evy.spawn(c.wait)
        w3 = evy.spawn(c.wait)
        sleep(0)
        self.assertEquals(c.waiting(), 3)
        s1 = evy.spawn(c.send, 1)
        s2 = evy.spawn(c.send, 2)
        s3 = evy.spawn(c.send, 3)
        sleep(0)  # this gets all the sends into a waiting state
        self.assertEquals(c.waiting(), 0)

        s1.wait()
        s2.wait()
        s3.wait()
        # NOTE: we don't guarantee that waiters are served in order
        results = sorted([w1.wait(), w2.wait(), w3.wait()])
        self.assertEquals(results, [1, 2, 3])

if __name__ == '__main__':
    main()

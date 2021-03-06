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


import os
import shutil
import subprocess
import sys
import tempfile

from tests import LimitedTestCase, main


base_module_contents = """
import socket
import urllib
print "base", socket, urllib
"""

patching_module_contents = """
from evy.patched import socket
from evy.patched import urllib
from evy import patcher
print 'patcher', socket, urllib
patcher.inject('base', globals(), ('socket', socket), ('urllib', urllib))
del patcher
"""

import_module_contents = """
import patching
import socket
print "importing", patching, socket, patching.socket, patching.urllib
"""


class ProcessBase(LimitedTestCase):
    TEST_TIMEOUT = 3 # starting processes is time-consuming

    def setUp (self):
        self._saved_syspath = sys.path
        self.tempdir = tempfile.mkdtemp('_patcher_test')

    def tearDown (self):
        sys.path = self._saved_syspath
        shutil.rmtree(self.tempdir)

    def write_to_tempfile (self, name, contents):
        filename = os.path.join(self.tempdir, name + '.py')
        fd = open(filename, "w")
        fd.write(contents)
        fd.close()

    def launch_subprocess (self, filename):
        python_path = os.pathsep.join(sys.path + [self.tempdir])
        new_env = os.environ.copy()
        new_env['PYTHONPATH'] = python_path
        if not filename.endswith('.py'):
            filename = filename + '.py'
        p = subprocess.Popen([sys.executable,
                              os.path.join(self.tempdir, filename)],
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT,
                             env = new_env)
        output, _ = p.communicate()
        lines = output.split("\n")
        return output, lines

    def run_script (self, contents, modname = None):
        if modname is None:
            modname = "testmod"
        self.write_to_tempfile(modname, contents)
        return self.launch_subprocess(modname)


class TestImportPatched(ProcessBase):
    def test_patch_a_module (self):
        self.write_to_tempfile("base", base_module_contents)
        self.write_to_tempfile("patching", patching_module_contents)
        self.write_to_tempfile("importing", import_module_contents)
        output, lines = self.launch_subprocess('importing.py')
        self.assert_(lines[0].startswith('patcher'), repr(output))
        self.assert_(lines[1].startswith('base'), repr(output))
        self.assert_(lines[2].startswith('importing'), repr(output))
        self.assert_('evy.patched.socket' in lines[1], repr(output))
        self.assert_('evy.patched.urllib' in lines[1], repr(output))
        self.assert_('evy.patched.socket' in lines[2], repr(output))
        self.assert_('evy.patched.urllib' in lines[2], repr(output))
        self.assert_('evy.patched.httplib' not in lines[2], repr(output))

    def test_import_patched_defaults (self):
        self.write_to_tempfile("base", base_module_contents)
        new_mod = """
from evy import patcher
base = patcher.import_patched('base')
print "newmod", base, base.socket, base.urllib.socket.socket
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assert_(lines[0].startswith('base'), repr(output))
        self.assert_(lines[1].startswith('newmod'), repr(output))
        self.assert_('evy.patched.socket' in lines[1], repr(output))
        self.assert_('GreenSocket' in lines[1], repr(output))


class TestMonkeyPatch(ProcessBase):
    def test_patched_modules (self):
        new_mod = """
from evy import patcher
patcher.monkey_patch()
import socket
import urllib
print "newmod", socket.socket, urllib.socket.socket
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assert_(lines[0].startswith('newmod'), repr(output))
        self.assertEqual(lines[0].count('GreenSocket'), 2, repr(output))

    def test_early_patching (self):
        new_mod = """
from evy import patcher
patcher.monkey_patch()
import evy
sleep(0.01)
print "newmod"
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assertEqual(len(lines), 2, repr(output))
        self.assert_(lines[0].startswith('newmod'), repr(output))

    def test_late_patching (self):
        new_mod = """
import evy
sleep(0.01)
from evy import patcher
patcher.monkey_patch()
sleep(0.01)
print "newmod"
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assertEqual(len(lines), 2, repr(output))
        self.assert_(lines[0].startswith('newmod'), repr(output))


    def test_typeerror (self):
        new_mod = """
from evy import patcher
patcher.monkey_patch(finagle=True)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assert_(lines[-2].startswith('TypeError'), repr(output))
        self.assert_('finagle' in lines[-2], repr(output))


    def assert_boolean_logic (self, call, expected, not_expected = ''):
        expected_list = ", ".join(['"%s"' % x for x in expected.split(',') if len(x)])
        not_expected_list = ", ".join(['"%s"' % x for x in not_expected.split(',') if len(x)])
        new_mod = """
from evy import patcher
%s
for mod in [%s]:
    assert patcher.is_monkey_patched(mod), mod
for mod in [%s]:
    assert not patcher.is_monkey_patched(mod), mod
print "already_patched", ",".join(sorted(patcher.already_patched.keys()))
""" % (call, expected_list, not_expected_list)
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        ap = 'already_patched'
        self.assert_(lines[0].startswith(ap), repr(output))
        patched_modules = lines[0][len(ap):].strip()
        # psycopg might or might not be patched based on installed modules
        patched_modules = patched_modules.replace("psycopg,", "")
        # ditto for MySQLdb
        patched_modules = patched_modules.replace("MySQLdb,", "")
        self.assertEqual(patched_modules, expected,
                         "Logic:%s\nExpected: %s != %s" % (call, expected,
                                                           patched_modules))

    def test_boolean (self):
        self.assert_boolean_logic("patcher.monkey_patch()",
                                  'os,select,socket,thread,time')

    def test_boolean_all (self):
        self.assert_boolean_logic("patcher.monkey_patch(all=True)",
                                  'os,select,socket,thread,time')

    def test_boolean_all_single (self):
        self.assert_boolean_logic("patcher.monkey_patch(all=True, socket=True)",
                                  'os,select,socket,thread,time')

    def test_boolean_all_negative (self):
        self.assert_boolean_logic("patcher.monkey_patch(all=False, " \
                                  "socket=False, select=True)",
                                  'select')

    def test_boolean_single (self):
        self.assert_boolean_logic("patcher.monkey_patch(socket=True)",
                                  'socket')

    def test_boolean_double (self):
        self.assert_boolean_logic("patcher.monkey_patch(socket=True," \
                                  " select=True)",
                                  'select,socket')

    def test_boolean_negative (self):
        self.assert_boolean_logic("patcher.monkey_patch(socket=False)",
                                  'os,select,thread,time')

    def test_boolean_negative2 (self):
        self.assert_boolean_logic("patcher.monkey_patch(socket=False," \
                                  "time=False)",
                                  'os,select,thread')

    def test_conflicting_specifications (self):
        self.assert_boolean_logic("patcher.monkey_patch(socket=False, " \
                                  "select=True)",
                                  'select')


test_monkey_patch_threading = """
def test_monkey_patch_threading():
    tickcount = [0]
    def tick():
        for i in xrange(1000):
            tickcount[0] += 1
            sleep()

    def do_sleep():
        tpool.execute(time.sleep, 0.5)

    evy.spawn(tick)
    w1 = evy.spawn(do_sleep)
    w1.wait()
    print tickcount[0]
    assert tickcount[0] > 900
    tpool.killall()
"""


class TestTpool(ProcessBase):
    TEST_TIMEOUT = 3

    def test_simple (self):
        new_mod = """
import evy
from evy import patcher
patcher.monkey_patch()
from evy import tpool
print "newmod", tpool.execute(len, "hi")
print "newmod", tpool.execute(len, "hi2")
tpool.killall()
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assertEqual(len(lines), 3, output)
        self.assert_(lines[0].startswith('newmod'), repr(output))
        self.assert_('2' in lines[0], repr(output))
        self.assert_('3' in lines[1], repr(output))

    def test_unpatched_thread (self):
        new_mod = """import evy
evy.monkey_patch(time=False, thread=False)
from evy import tpool
import time
"""
        new_mod += test_monkey_patch_threading
        new_mod += "\ntest_monkey_patch_threading()\n"
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assertEqual(len(lines), 2, lines)

    def test_patched_thread (self):
        new_mod = """import evy
evy.monkey_patch(time=False, thread=True)
from evy import tpool
import time
"""
        new_mod += test_monkey_patch_threading
        new_mod += "\ntest_monkey_patch_threading()\n"
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod.py')
        self.assertEqual(len(lines), 2, "\n".join(lines))


class TestSubprocess(ProcessBase):
    def test_monkeypatched_subprocess (self):
        new_mod = """import evy
evy.monkey_patch()
from evy.patched import subprocess

subprocess.Popen(['/bin/true'], stdin=subprocess.PIPE)
print "done"
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(output, "done\n", output)


class TestThreading(ProcessBase):
    def test_orig_thread (self):
        new_mod = """import evy
evy.monkey_patch()
from evy import patcher
import threading
_threading = patcher.original('threading')
def test():
    print repr(threading.currentThread())
t = _threading.Thread(target=test)
t.start()
t.join()
print len(threading._active)
print len(_threading._active)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 4, "\n".join(lines))
        self.assert_(lines[0].startswith('<Thread'), lines[0])
        self.assertEqual(lines[1], "1", lines[1])
        self.assertEqual(lines[2], "1", lines[2])

    def test_threading (self):
        new_mod = """import evy
evy.monkey_patch()
import threading
def test():
    print repr(threading.currentThread())
t = threading.Thread(target=test)
t.start()
t.join()
print len(threading._active)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assert_(lines[0].startswith('<_MainThread'), lines[0])
        self.assertEqual(lines[1], "1", lines[1])

    def test_tpool (self):
        new_mod = """import evy
evy.monkey_patch()
from evy import tpool
import threading
def test():
    print repr(threading.currentThread())
tpool.execute(test)
print len(threading._active)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assert_(lines[0].startswith('<Thread'), lines[0])
        self.assertEqual(lines[1], "1", lines[1])

    def test_greenlet (self):
        new_mod = """import evy
evy.monkey_patch()
from evy import event
import threading
evt = event.Event()
def test():
    print repr(threading.currentThread())
    evt.send()
spawn_n(test)
evt.wait()
print len(threading._active)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assert_(lines[0].startswith('<_MainThread'), lines[0])
        self.assertEqual(lines[1], "1", lines[1])

    def test_greenthread (self):
        new_mod = """import evy
evy.monkey_patch()
import threading
def test():
    print repr(threading.currentThread())
t = evy.spawn(test)
t.wait()
print len(threading._active)
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assert_(lines[0].startswith('<_GreenThread'), lines[0])
        self.assertEqual(lines[1], "1", lines[1])

    def test_keyerror (self):
        new_mod = """import evy
evy.monkey_patch()
"""
        self.write_to_tempfile("newmod", new_mod)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 1, "\n".join(lines))


class TestGreenThreadWrapper(ProcessBase):
    prologue = """import evy
evy.monkey_patch()
import threading
def test():
    t = threading.currentThread()
"""
    epilogue = """
t = evy.spawn(test)
t.wait()
"""

    def test_join (self):
        self.write_to_tempfile("newmod", self.prologue + """
    def test2():
        global t2
        t2 = threading.currentThread()
    evy.spawn(test2)
""" + self.epilogue + """
print repr(t2)
t2.join()
""")
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 2, "\n".join(lines))
        self.assert_(lines[0].startswith('<_GreenThread'), lines[0])

    def test_name (self):
        self.write_to_tempfile("newmod", self.prologue + """
    print t.name
    print t.getName()
    print t.get_name()
    t.name = 'foo'
    print t.name
    print t.getName()
    print t.get_name()
    t.setName('bar')
    print t.name
    print t.getName()
    print t.get_name()
""" + self.epilogue)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 10, "\n".join(lines))
        for i in xrange(0, 3):
            self.assertEqual(lines[i], "GreenThread-1", lines[i])
        for i in xrange(3, 6):
            self.assertEqual(lines[i], "foo", lines[i])
        for i in xrange(6, 9):
            self.assertEqual(lines[i], "bar", lines[i])

    def test_ident (self):
        self.write_to_tempfile("newmod", self.prologue + """
    print id(t._g)
    print t.ident
""" + self.epilogue)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assertEqual(lines[0], lines[1])

    def test_is_alive (self):
        self.write_to_tempfile("newmod", self.prologue + """
    print t.is_alive()
    print t.isAlive()
""" + self.epilogue)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assertEqual(lines[0], "True", lines[0])
        self.assertEqual(lines[1], "True", lines[1])

    def test_is_daemon (self):
        self.write_to_tempfile("newmod", self.prologue + """
    print t.is_daemon()
    print t.isDaemon()
""" + self.epilogue)
        output, lines = self.launch_subprocess('newmod')
        self.assertEqual(len(lines), 3, "\n".join(lines))
        self.assertEqual(lines[0], "True", lines[0])
        self.assertEqual(lines[1], "True", lines[1])


if __name__ == '__main__':
    main()

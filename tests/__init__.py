# package is named tests, not test, so it won't be confused with test in stdlib


import sys
import os
import errno
import unittest
import warnings

from evy import hubs
from evy.tools import debug

from evy.timeout import Timeout
from evy.patched import socket, thread, threading

from test import test_support

from nose.plugins.attrib import attr




# convenience for importers
main = unittest.main


def s2b (s):
    """portable way to convert string to bytes. In 3.x socket.send and recv require bytes"""
    return s.encode()


def skipped (func):
    """
    Decorator that marks a function as skipped.  Uses nose's SkipTest exception
    if installed.  Without nose, this will count skipped tests as passing tests."""
    try:
        from nose.plugins.skip import SkipTest

        def skipme (*a, **k):
            raise SkipTest()

        skipme.__name__ = func.__name__
        return skipme
    except ImportError:
        # no nose, we'll just skip the test ourselves
        def skipme (*a, **k):
            print "Skipping", func.__name__

        skipme.__name__ = func.__name__
        return skipme


def skip_if (condition, reason = None):
    """
    Decorator that skips a test if the *condition* evaluates True.
    *condition* can be a boolean or a callable that accepts one argument.
    The callable will be called with the function to be decorated, and 
    should return True to skip the test.
    """

    def skipped_wrapper (func):
        def wrapped (*a, **kw):
            if isinstance(condition, bool):
                result = condition
            else:
                result = condition(func)
            if result:
                return skipped(func)(*a, **kw)
            else:
                return func(*a, **kw)

        wrapped.__name__ = func.__name__
        return wrapped

    return skipped_wrapper


def skip_unless (condition, reason = None):
    """
    Decorator that skips a test if the *condition* does not return True.
    *condition* can be a boolean or a callable that accepts one argument.
    The callable will be called with the  function to be decorated, and 
    should return True if the condition is satisfied.
    """

    def skipped_wrapper (func):
        def wrapped (*a, **kw):
            if isinstance(condition, bool):
                result = condition
            else:
                result = condition(func)
            if not result:
                return skipped(func)(*a, **kw)
            else:
                return func(*a, **kw)

        wrapped.__name__ = func.__name__
        return wrapped

    return skipped_wrapper


def using_pyevent (_f):
    from evy.hubs import get_hub

    return 'pyevent' in type(get_hub()).__module__


def skip_on_windows (func):
    """ Decorator that skips a test on Windows."""
    import sys

    return skip_if(sys.platform.startswith('win'))(func)


def skip_if_no_itimer (func):
    """ Decorator that skips a test if the `itimer` module isn't found """
    has_itimer = False
    try:
        import itimer

        has_itimer = True
    except ImportError:
        pass
    return skip_unless(has_itimer)(func)


def skip_if_no_ssl (func):
    """ Decorator that skips a test if SSL is not available."""
    try:
        import evy.patched.ssl
    except ImportError:
        try:
            import evy.patched.OpenSSL
        except ImportError:
            skipped(func)


class TestIsTakingTooLong(Exception):
    """ Custom exception class to be raised when a test's runtime exceeds a limit. """
    pass


class LimitedTestCase(unittest.TestCase):
    """
    Unittest subclass that adds a timeout to all tests.  Subclasses must
    be sure to call the LimitedTestCase setUp and tearDown methods.  The default 
    timeout is 1 second, change it by setting self.TEST_TIMEOUT to the desired
    quantity.
    """

    TEST_TIMEOUT = 1

    def setUp (self):
        self.timer = Timeout(self.TEST_TIMEOUT,
                             TestIsTakingTooLong(self.TEST_TIMEOUT))

    def reset_timeout (self, new_timeout):
        """
        Changes the timeout duration; only has effect during one test case
        """
        self.timer.cancel()
        self.timer = Timeout(new_timeout, TestIsTakingTooLong(new_timeout))

    def tearDown (self):
        self.timer.cancel()
        try:
            hub = hubs.get_hub()
            num_readers = len(hub.get_readers())
            num_writers = len(hub.get_writers())
            assert num_readers == num_writers == 0
        except AssertionError, e:
            print "ERROR: Hub not empty"
            print debug.format_hub_timers()
            print debug.format_hub_listeners()

    def assert_less_than (self, a, b, msg = None):
        if msg:
            self.assert_(a < b, msg)
        else:
            self.assert_(a < b, "%s not less than %s" % (a, b))

    assertLessThan = assert_less_than

    def assert_less_than_equal (self, a, b, msg = None):
        if msg:
            self.assert_(a <= b, msg)
        else:
            self.assert_(a <= b, "%s not less than or equal to %s" % (a, b))

    assertLessThanEqual = assert_less_than_equal


def verify_hub_empty ():
    from evy import hubs

    hub = hubs.get_hub()
    num_readers = len(hub.get_readers())
    num_writers = len(hub.get_writers())
    num_timers = hub.get_timers_count()
    assert num_readers == 0 and num_writers == 0, "Readers: %s Writers: %s" % (
        num_readers, num_writers)


def find_command (command):
    for dir in os.getenv('PATH', '/usr/bin:/usr/sbin').split(os.pathsep):
        p = os.path.join(dir, command)
        if os.access(p, os.X_OK):
            return p
    raise IOError(errno.ENOENT, 'Command not found: %r' % command)


def silence_warnings (func):
    def wrapper (*args, **kw):
        warnings.simplefilter('ignore', DeprecationWarning)
        try:
            return func(*args, **kw)
        finally:
            warnings.simplefilter('default', DeprecationWarning)

    wrapper.__name__ = func.__name__
    return wrapper


def get_database_auth ():
    """Retrieves a dict of connection parameters for connecting to test databases.

    Authentication parameters are highly-machine specific, so
    get_database_auth gets its information from either environment
    variables or a config file.  The environment variable is
    "EVENTLET_DB_TEST_AUTH" and it should contain a json object.  If
    this environment variable is present, it's used and config files
    are ignored.  If it's not present, it looks in the local directory
    (tests) and in the user's home directory for a file named
    ".test_dbauth", which contains a json map of parameters to the
    connect function.
    """
    import os

    retval = {'MySQLdb': {'host': 'localhost', 'user': 'root', 'passwd': ''},
              'psycopg2': {'user': 'test'}}
    try:
        import json
    except ImportError:
        try:
            import simplejson as json
        except ImportError:
            print "No json implementation, using baked-in db credentials."
            return retval

    if 'EVENTLET_DB_TEST_AUTH' in os.environ:
        return json.loads(os.environ.get('EVENTLET_DB_TEST_AUTH'))

    files = [os.path.join(os.path.dirname(__file__), '.test_dbauth'),
             os.path.join(os.path.expanduser('~'), '.test_dbauth')]
    for f in files:
        try:
            auth_utf8 = json.load(open(f))
            # Have to convert unicode objects to str objects because
            # mysqldb is dum. Using a doubly-nested list comprehension
            # because we know that the structure is a two-level dict.
            return dict([(str(modname), dict([(str(k), str(v))
                                              for k, v in connectargs.items()]))
                         for modname, connectargs in auth_utf8.items()])
        except IOError:
            pass
    return retval


certificate_file = os.path.join(os.path.dirname(__file__), 'server.crt')
private_key_file = os.path.join(os.path.dirname(__file__), 'server.key')





class ThreadableTest:
    """
    Threadable Test class

    The ThreadableTest class makes it easy to create a threaded
    client/server pair from an existing unit test. To create a
    new threaded class from an existing unit test, use multiple
    inheritance:

        class NewClass (OldClass, ThreadableTest):
            pass

    This class defines two new fixture functions with obvious
    purposes for overriding:

        clientSetUp ()
        clientTearDown ()

    Any new test functions within the class must then define
    tests in pairs, where the test name is preceeded with a
    '_' to indicate the client portion of the test. Ex:

        def testFoo(self):
            # Server portion

        def _testFoo(self):
            # Client portion

    Any exceptions raised by the clients during their tests
    are caught and transferred to the main thread to alert
    the testing framework.

    Note, the server setup function cannot call any blocking
    functions that rely on the client thread during setup,
    unless serverExplicitReady() is called just before
    the blocking call (such as in setting up a client/server
    connection and performing the accept() in setUp().
    """

    def __init__ (self):
        # Swap the true setup function
        self.__setUp = self.setUp
        self.__tearDown = self.tearDown
        self.setUp = self._setUp
        self.tearDown = self._tearDown

    def serverExplicitReady (self):
        """This method allows the server to explicitly indicate that
        it wants the client thread to proceed. This is useful if the
        server is about to execute a blocking routine that is
        dependent upon the client thread during its setup routine."""
        self.server_ready.set()

    def _setUp (self):
        import Queue

        self.server_ready = threading.Event()
        self.client_ready = threading.Event()
        self.done = threading.Event()
        self.queue = Queue.Queue(1)

        # Do some munging to start the client test.
        methodname = self.id()
        i = methodname.rfind('.')
        methodname = methodname[i + 1:]
        test_method = getattr(self, '_' + methodname)
        self.client_thread = thread.start_new_thread(
            self.clientRun, (test_method,))

        self.__setUp()
        if not self.server_ready.is_set():
            self.server_ready.set()
        self.client_ready.wait()

    def _tearDown (self):
        self.__tearDown()
        self.done.wait()

        if not self.queue.empty():
            msg = self.queue.get()
            self.fail(msg)

    def clientRun (self, test_func):
        self.server_ready.wait()
        self.clientSetUp()
        self.client_ready.set()
        if not callable(test_func):
            raise TypeError("test_func must be a callable function.")
        try:
            test_func()
        except Exception, strerror:
            self.queue.put(strerror)
        self.clientTearDown()

    def clientSetUp (self):
        raise NotImplementedError("clientSetUp must be implemented.")

    def clientTearDown (self):
        self.done.set()
        thread.exit()


class SocketTCPTest(unittest.TestCase):
    def setUp (self):
        self.serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.port = test_support.bind_port(self.serv)
        self.serv.listen(1)

    def tearDown (self):
        self.serv.close()
        self.serv = None


class ThreadedTCPSocketTest(SocketTCPTest, ThreadableTest):
    def __init__ (self, methodName = 'runTest'):
        SocketTCPTest.__init__(self, methodName = methodName)
        ThreadableTest.__init__(self)

    def clientSetUp (self):
        self.cli = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def clientTearDown (self):
        self.cli.close()
        self.cli = None
        ThreadableTest.clientTearDown(self)


class SocketConnectedTest(ThreadedTCPSocketTest):
    def __init__ (self, methodName = 'runTest'):
        ThreadedTCPSocketTest.__init__(self, methodName = methodName)

    def setUp (self):
        ThreadedTCPSocketTest.setUp(self)
        # Indicate explicitly we're ready for the client thread to
        # proceed and then perform the blocking call to accept
        self.serverExplicitReady()
        conn, addr = self.serv.accept()
        self.cli_conn = conn

    def tearDown (self):
        self.cli_conn.close()
        self.cli_conn = None
        ThreadedTCPSocketTest.tearDown(self)

    def clientSetUp (self):
        ThreadedTCPSocketTest.clientSetUp(self)

        from test import test_support
        HOST = test_support.HOST
        self.cli.connect((HOST, self.port))
        self.serv_conn = self.cli

    def clientTearDown (self):
        self.serv_conn.close()
        self.serv_conn = None
        ThreadedTCPSocketTest.clientTearDown(self)

class SocketPairTest(unittest.TestCase, ThreadableTest):
    def __init__ (self, methodName = 'runTest'):
        unittest.TestCase.__init__(self, methodName = methodName)
        ThreadableTest.__init__(self)

    def setUp (self):
        self.serv, self.cli = socket.socketpair()

    def tearDown (self):
        self.serv.close()
        self.serv = None

    def clientSetUp (self):
        pass

    def clientTearDown (self):
        self.cli.close()
        self.cli = None
        ThreadableTest.clientTearDown(self)

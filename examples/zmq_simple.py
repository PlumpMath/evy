from evy.green import zmq
import evy

CTX = zmq.Context(1)

def bob_client (ctx, count):
    print "STARTING BOB"
    bob = zmq.Socket(CTX, zmq.REQ)
    bob.connect("ipc:///tmp/test")

    for i in range(0, count):
        print "BOB SENDING"
        bob.send("HI")
        print "BOB GOT:", bob.recv()


def alice_server (ctx, count):
    print "STARTING ALICE"
    alice = zmq.Socket(CTX, zmq.REP)
    alice.bind("ipc:///tmp/test")

    print "ALICE READY"
    for i in range(0, count):
        print "ALICE GOT:", alice.recv()
        print "ALIC SENDING"
        alice.send("HI BACK")

alice = evy.spawn(alice_server, CTX, 10)
bob = evy.spawn(bob_client, CTX, 10)

bob.wait()
alice.wait()

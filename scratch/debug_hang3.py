import sys
import os
import signal
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from benchmark_scheduler import run_simulation
import traceback

def handler(signum, frame):
    print("ALARM Triggered! Printing stack trace:")
    traceback.print_stack(frame)
    sys.exit(1)

signal.signal(signal.SIGALRM, handler)
signal.alarm(3) # Wait 3 seconds then print stack

print("Running...")
run_simulation((100, 2))
print("Done")

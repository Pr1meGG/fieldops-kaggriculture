import sys
import os
sys.path.insert(0, os.path.abspath("src"))
sys.path.insert(0, os.path.abspath("."))
from kaggle_environments import make
from benchmark_scheduler import run_simulation
import threading

def run():
    print("Starting simulation")
    run_simulation((100, 2))
    print("Done")

t = threading.Thread(target=run)
t.start()
t.join(5)
if t.is_alive():
    print("HUNG! Dumping stack traces...")
    import traceback
    for th in threading.enumerate():
        if th is not threading.current_thread():
            traceback.print_stack(sys._current_frames()[th.ident])

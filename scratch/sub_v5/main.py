import sys
import os

try:
    from fieldops.agent import agent
except ImportError:
    # Fallback for local repository execution where fieldops lives inside src/
    for candidate in [
        os.path.join(os.getcwd(), "src"),
        os.path.abspath(os.path.join(os.path.dirname(__file__ if "__file__" in globals() else os.getcwd()), "src")),
    ]:
        if os.path.exists(candidate) and candidate not in sys.path:
            sys.path.insert(0, candidate)
    from fieldops.agent import agent

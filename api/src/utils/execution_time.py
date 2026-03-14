import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.append(str(ROOT_DIR))

from src.config.settings import Colors


def execution_time_of_a_function(function):
    def wrapper(*args, **kwargs):
        pr = cProfile.Profile()
        pr.enable()
        result = function(*args, **kwargs)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats("cumulative")
        ps.print_stats()
        print(f" FUNCTION: [{Colors.info(str(function.__name__))} ]", s.getvalue())
        return result

    return wrapper

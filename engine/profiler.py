from contextlib import contextmanager
from time import perf_counter

_timings = {}

@contextmanager
def timer(name):
    start = perf_counter()
    try:
        yield
    finally:
        _timings[name] = _timings.get(name, 0) + (perf_counter() - start)


def print_summary():
    print("\n========== PROFILE ==========")

    total = sum(_timings.values())

    for name, seconds in sorted(
        _timings.items(),
        key=lambda x: x[1],
        reverse=True,
    ):
        pct = seconds / total * 100 if total else 0
        print(f"{seconds:8.1f}s   {pct:5.1f}%   {name}")

    print("=============================\n")
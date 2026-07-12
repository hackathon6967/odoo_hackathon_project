"""Load job functions from the importable worker module before starting RQ."""
from worker import run_worker


if __name__ == "__main__":
    run_worker()

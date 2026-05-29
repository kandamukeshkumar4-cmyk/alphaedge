"""Worker entrypoint: python -m app.workers.main"""

from arq import run_worker

from app.workers.tasks import WorkerSettings

if __name__ == "__main__":
    run_worker(WorkerSettings)

# In a real platform, you don't just run random function
# The Manager: Accepts a job (e.g., "Analyze this image").
#
# The Worker Pool: A group of agents ready to work.
#
# The Result Store: Where finished work goes.


import asyncio
import random
import time
from typing import Dict, List

class WorkflowEngine:
    def __init__(self, max_concurrent_agents: int = 3):
        self.queue = asyncio.Queue()
        self.results: Dict[str, str] = {}
        self.is_running = True

        # The Semaphore limits how many agents work AT ONCE
        self.semaphore = asyncio.Semaphore(max_concurrent_agents)
        print(f"⚙️ [INIT] Engine started with {max_concurrent_agents} agent slots.")

    async def add_job(self, job_id: str, complexity: int):
        """Users call this to submit work."""
        print(f"📥 [NEW JOB] Job {job_id} added to queue.")
        await self.queue.put((job_id, complexity))

    async def worker(self, worker_id: int):
        """This is a background worker that runs forever."""
        print(f"   👷 Worker {worker_id} is online and waiting for jobs...")

        while self.is_running:
            # 1. Get a job from the queue (waits here if queue is empty)
            job_id, complexity = await self.queue.get()

            # 2. Use the Semaphore to respect Rate Limits
            async with self.semaphore:
                print(f"   🔵 Worker {worker_id} picked up {job_id}. Processing...")

                # Simulate AI work
                await asyncio.sleep(complexity)

                # Store Result
                self.results[job_id] = f"Completed by Worker {worker_id}"
                print(f"   ✅ Worker {worker_id} FINISHED {job_id}.")

            # 3. Mark job as done in the queue
            self.queue.task_done()

    async def start(self):
        """Boots up the engine and workers."""
        # Create 5 background workers (they sit idle initially)
        workers = [asyncio.create_task(self.worker(i)) for i in range(1, 6)]

        # Keep the engine running (in a real app, this runs forever)
        # For this demo, we will wait until the queue is empty
        await self.queue.join()
        print("🏁 All jobs in queue are processed!")


# ---------------------------------------------------------
# Simulation of your Platform in Action
# ---------------------------------------------------------
async def run_simulation():
    engine = WorkflowEngine(max_concurrent_agents=2)  # Only 2 agents allowed at once!

    # 1. Start the workers in the background
    asyncio.create_task(engine.start())

    # 2. Simulate users submitting jobs over time
    await engine.add_job("Job-A (Research)", 2)
    await engine.add_job("Job-B (Write)", 4)
    await engine.add_job("Job-C (Edit)", 1)

    # Simulate a pause (Maybe no users for a second)
    await asyncio.sleep(1)
    print("--- ⏱️ A new user just arrived! ---")
    await engine.add_job("Job-D (Publish)", 3)

    # Wait for everything to finish
    await engine.queue.join()
    print(f"\nFinal Results: {engine.results}")


if __name__ == "__main__":
    asyncio.run(run_simulation())
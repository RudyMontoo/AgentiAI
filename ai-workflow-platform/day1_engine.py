import asyncio
import time


# ---------------------------------------------------------
# This function represents a single AI Agent doing work.
# It takes a 'name' and a 'duration' (how long the task takes).
# ---------------------------------------------------------
async def agent_task(name: str, duration: int):
    print(f"🔵 [START] Agent '{name}' is starting a {duration}s task...")

    # CRITICAL: 'await asyncio.sleep' simulates waiting for an LLM response.
    # It tells Python: "I am waiting. Go do other work while I wait."
    await asyncio.sleep(duration)

    print(f"🟢 [FINISH] Agent '{name}' completed the task!")
    return f"{name} Output"


# ---------------------------------------------------------
# This is the "Orchestrator" or "Engine"
# ---------------------------------------------------------
async def main():
    print("--- 🚀 Platform Engine Starting ---")
    start_time = time.perf_counter()

    # We schedule 3 agents to run AT THE SAME TIME (concurrently).
    # If this was normal Python, it would take 2 + 5 + 3 = 10 seconds.
    results = await asyncio.gather(
        agent_task("Researcher", 2),  # Takes 2 seconds
        agent_task("Writer", 5),  # Takes 5 seconds
        agent_task("Reviewer", 3)  # Takes 3 seconds
    )

    end_time = time.perf_counter()
    total_time = end_time - start_time

    print("\n--- 🏁 Platform Engine Finished ---")
    print(f"Results: {results}")
    print(f"Total Execution Time: {total_time:.2f} seconds")


# Run the async engine
if __name__ == "__main__":
    asyncio.run(main())
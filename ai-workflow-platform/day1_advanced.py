# Bounded Semaphore Scheduler
import asyncio
import time
import random

# ---------------------------------------------------------
# The "Bouncer" (Semaphore)
# We only allow 3 Agents to access the LLM at the same time.
# ---------------------------------------------------------
MAX_CONCURRENT_AGENTS = 3
semaphore = asyncio.Semaphore(MAX_CONCURRENT_AGENTS)


async def sensitive_agent_task(agent_id):
    print(f"   🚦 Agent {agent_id} is waiting in line...")

    # The 'async with semaphore' block is the critical section.
    # If 3 agents are already inside, the 4th agent WAITS HERE automatically.
    async with semaphore:
        print(f"🔵 [ACCESS GRANTED] Agent {agent_id} is using the API!")

        # Simulate work (1 to 3 seconds)
        processing_time = random.randint(1, 3)
        await asyncio.sleep(processing_time)

        print(f"✅ [FINISHED] Agent {agent_id} done in {processing_time}s. Leaving API.")


async def main():
    print(f"--- 🚀 Starting Platform with Limit: {MAX_CONCURRENT_AGENTS} concurrent agents ---")
    start_time = time.perf_counter()

    # We create 10 agents instantly.
    # Without the Semaphore, all 10 would hit the API at once (and get banned).
    tasks = [sensitive_agent_task(i) for i in range(1, 11)]

    # Run them all
    await asyncio.gather(*tasks)

    end_time = time.perf_counter()
    print(f"\n--- 🏁 All 10 Agents Finished in {end_time - start_time:.2f}s ---")


if __name__ == "__main__":
    asyncio.run(main())
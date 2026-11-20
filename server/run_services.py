import asyncio
import os
import signal
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PYTHON_EXE = sys.executable

SERVICES = [
    {"name": "Auth Service", "dir": BASE_DIR / "services" / "auth", "port": 8001},
    {"name": "Project Service", "dir": BASE_DIR / "services" / "projects", "port": 8002},
    {"name": "AI Service", "dir": BASE_DIR / "services" / "ai", "port": 8003},
    {"name": "API Gateway", "dir": BASE_DIR / "gateway", "port": 5050},
]


async def run_service(service: dict, processes: list):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(service["dir"])

    proc = await asyncio.create_subprocess_exec(
        PYTHON_EXE,
        "-m",
        "uvicorn",
        "main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(service["port"]),
        cwd=str(service["dir"]),
        env=env
    )
    processes.append(proc)
    print(f"🚀 Started {service['name']} on http://127.0.0.1:{service['port']}")
    await proc.wait()


async def main():
    processes = []
    loop = asyncio.get_running_loop()

    def shutdown():
        print("\n🛑 Shutting down all NxtBuild microservices...")
        for p in processes:
            try:
                p.terminate()
            except Exception:
                pass

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, shutdown)
        except NotImplementedError:
            pass

    print("==================================================")
    print("   NxtBuild 4-Service Microservices Orchestrator  ")
    print("==================================================")

    # Start backend services first, then Gateway
    tasks = []
    for s in SERVICES[:-1]:
        tasks.append(asyncio.create_task(run_service(s, processes)))
        await asyncio.sleep(0.5)

    # Start Gateway
    tasks.append(asyncio.create_task(run_service(SERVICES[-1], processes)))

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        pass
    finally:
        shutdown()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

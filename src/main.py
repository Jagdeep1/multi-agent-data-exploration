"""
Entry point for the Multi-Agent Data Exploration System.

Usage:
    python -m src.main                        # interactive loop
    python -m src.main --query "your query"   # single query then exit
"""

import argparse
import os
import sys

from src.agents.supervisor import create_supervisor_agent
from src.config import DATA_DIR, OUTPUT_DIR, S3_BUCKET, S3_ENABLED, S3_PREFIX


def ensure_dirs():
    """Make sure required directories exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_query(supervisor, query: str) -> None:
    """Send a single query to the Supervisor and print the response."""
    print(f"\n[User] {query}")
    print("[Supervisor] Thinking...\n")
    response = supervisor(query)
    print(f"\n[Supervisor]\n{response}\n")


def interactive_loop(supervisor) -> None:
    """Run an interactive REPL until the user exits."""
    print("Multi-Agent Data Exploration System")
    print("Type your query, or 'quit' / 'exit' to stop.\n")
    while True:
        try:
            query = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not query:
            continue
        if query.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        run_query(supervisor, query)


def main() -> None:
    parser = argparse.ArgumentParser(description="Multi-Agent Data Exploration System")
    parser.add_argument(
        "--query",
        type=str,
        default=None,
        help="Run a single query and exit.",
    )
    args = parser.parse_args()

    ensure_dirs()

    if S3_ENABLED:
        print(f"S3 enabled: s3://{S3_BUCKET}/{S3_PREFIX}/")
    else:
        print("S3 disabled (local-only mode)")

    supervisor = create_supervisor_agent()

    if args.query:
        run_query(supervisor, args.query)
    else:
        interactive_loop(supervisor)


if __name__ == "__main__":
    main()

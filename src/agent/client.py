import asyncio
import logging

from langgraph_sdk import get_client

logging.basicConfig(level=logging.INFO)

client = get_client(url="http://localhost:2024")


async def main():
    async for chunk in client.runs.stream(
        None,  # Threadless run
        "agent",  # Name of assistant. Defined in langgraph.json.
        input={
            "messages": [
                {
                    "role": "human",
                    "content": "What is LangGraph?",
                }
            ],
        },
    ):
        logging.info(f"Receiving new event of type: {chunk.event}...")
        logging.info(chunk.data)
        logging.info("\n\n")


asyncio.run(main())

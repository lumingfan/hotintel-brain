"""Runnable RabbitMQ worker for async Brain judge flow."""

from __future__ import annotations

import asyncio
import json

import aio_pika

from src.common.config import get_settings
from src.mq.consumer import BrainJudgeConsumer
from src.mq.messages import BrainJudgeRequestedMessage
from src.mq.publisher import BrainJudgePublisher


async def run_worker() -> None:
    settings = get_settings()
    if not settings.brain_rabbitmq_url:
        raise RuntimeError("BRAIN_RABBITMQ_URL must be set to run the async Brain worker.")

    connection = await aio_pika.connect_robust(settings.brain_rabbitmq_url)
    async with connection:
        channel = await connection.channel()
        requested_queue = await channel.declare_queue("hotintel.judge.requested", durable=True)
        await channel.declare_queue("hotintel.judge.completed", durable=True)

        publisher = BrainJudgePublisher(channel)
        consumer = BrainJudgeConsumer(publisher=publisher)

        async def _handle(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            async with message.process():
                payload = json.loads(message.body.decode("utf-8"))
                requested = BrainJudgeRequestedMessage.model_validate(payload)
                await consumer.handle(requested)

        await requested_queue.consume(_handle)
        await asyncio.Future()


def main() -> None:
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()

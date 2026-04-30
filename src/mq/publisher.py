"""Publish Brain async results."""

from __future__ import annotations

import aio_pika

from src.mq.messages import BrainJudgeCompletedMessage


class BrainJudgePublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel, exchange_name: str = "") -> None:
        self.channel = channel
        self.exchange_name = exchange_name

    async def publish_completed(self, message: BrainJudgeCompletedMessage) -> None:
        body = message.model_dump_json().encode("utf-8")
        exchange = await self.channel.get_exchange(self.exchange_name) if self.exchange_name else self.channel.default_exchange
        await exchange.publish(
            aio_pika.Message(body=body, content_type="application/json"),
            routing_key=message.routing_key,
        )

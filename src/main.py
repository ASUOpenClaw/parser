"""
Parser service — FastStream NATS app.
"""

from __future__ import annotations

import logging

from faststream import FastStream
from faststream.nats import NatsBroker

from .config import settings
from .handlers import create_subscriber
from .transcription_handler import create_transcription_subscriber

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

broker = NatsBroker(settings.nats_url)
app = FastStream(broker)

# Register subscribers
create_subscriber(broker)
create_transcription_subscriber(broker)


@app.on_startup
async def startup() -> None:
    logger.info(
        "Parser starting (TEI=%s, docling=%s, Qdrant=%s, Speaches=%s)",
        settings.tei_url,
        settings.docling_url,
        settings.qdrant_url,
        settings.speaches_url,
    )


if __name__ == "__main__":
    import asyncio
    asyncio.run(app.run())

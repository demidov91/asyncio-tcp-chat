import json
import logging
from asyncio.streams import StreamReader
from typing import Optional


logger = logging.getLogger(__name__)


def encode_json(data: dict) -> bytes:
    payload = json.dumps(data).encode()
    length_encoded = len(payload).to_bytes(length=2, byteorder='big')
    return length_encoded + payload



async def read_json(reader: StreamReader) -> Optional[dict]:
    length = int.from_bytes(await reader.read(2), byteorder='big')
    if not length:
        return None

    raw_data = await reader.read(length)

    try:
        return json.loads(raw_data.decode())
    except Exception as e:
        raise ValueError('Parse error', e)

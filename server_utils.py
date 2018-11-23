import dataclasses
from asyncio.streams import StreamReader, StreamWriter
from typing import Optional

@dataclasses.dataclass
class ClientConnection:
    reader: StreamReader
    writer: StreamWriter
    username: str
    ip: str
    port: int


@dataclasses.dataclass
class PrivateMessage:
    text: str
    send_to: str
    send_from: Optional[str]=None


def parse_for_private_message(text: str) -> Optional[PrivateMessage]:
    if not text.startswith('@'):
        return None

    name_end_index = text.find(' ')
    if name_end_index < 1 or name_end_index == (len(text) - 1):
        return None

    return PrivateMessage(send_to=text[1:name_end_index], text=text[name_end_index:])

import asyncio
import logging
import dataclasses
from asyncio.futures import CancelledError
from asyncio.streams import StreamReader, StreamWriter
from typing import List

from helper import encode_json, read_json


@dataclasses.dataclass
class ClientConnection:
    reader: StreamReader
    writer: StreamWriter
    username: str

connections = []    # type: List[ClientConnection]
logger = logging.getLogger(__name__)

_user_id = 0
def get_next_username():
    global _user_id
    _user_id += 1
    return f'User {_user_id}'


async def server_handler(reader, writer) -> None:
    username = get_next_username()
    current_connection = ClientConnection(reader, writer, username)

    await broadcast_joined(username)
    connections.append(current_connection)

    while True:
        try:
            event = await read_json(reader)
        except ValueError:
            logger.exception('Unexpected client message format.')
            continue

        if event is None:
            break

        if event.get('type') == 'quit':
            break

        if event.get('type') == 'message':
            try:
                await broadcast_message(text=event['data']['text'], username=username)
            except KeyError:
                logger.exception('Unexpected client message format.')
                continue

            except Exception:
                logger.exception('Unexpected exception while broadcasting a message.')
                continue

    connections.remove(current_connection)
    await broadcast_quit(username=username)

    writer.close()


async def broadcast_joined(username: str):
    logger.info('%s joined.', username)
    await asyncio.gather(
        *(
            _send(writer=x.writer, data={
                'type': 'joined',
                'data': {
                    'username': username,
                }
            })
            for x in connections
        )
    )


async def broadcast_quit(username: str):
    logger.info('%s quit.', username)
    await asyncio.gather(
        *(
            _send(writer=x.writer, data={
                'type': 'quit',
                'data': {
                    'username': username,
                }
            }) for x in connections
        )
    )


async def broadcast_message(text: str, *, username: str):
    logger.info('Message (%s): %s', username, text)
    await asyncio.gather(
        *(
            _send(writer=x.writer, data={
                'type': 'message',
                'data': {'text': text, 'sender': username, },
            })
            for x in connections if x.username != username
        )
    )

async def _send(*, writer: StreamWriter, data: dict):
    writer.write(encode_json(data))
    await writer.drain()


async def run():
    server = await asyncio.start_server(server_handler, host='0.0.0.0', port='5555')

    try:
        await server.serve_forever()
    except CancelledError as e:
        logger.info('Server is stopped.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run())

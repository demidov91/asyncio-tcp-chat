#!/usr/bin/python3.7

import asyncio
import logging
import dataclasses
import sys
from asyncio.futures import CancelledError
from asyncio.streams import StreamReader, StreamWriter
from typing import List

from helper import encode_json, read_json


@dataclasses.dataclass
class ClientConnection:
    reader: StreamReader
    writer: StreamWriter
    username: str
    ip: str
    port: int

connections = []    # type: List[ClientConnection]
logger = logging.getLogger(__name__)

_user_id = 0
def get_next_username():
    global _user_id
    _user_id += 1
    return f'user{_user_id}'



class ServerHandler:
    reader = None
    writer = None
    is_stopped = False  # type: bool
    username = None     # type: str
    command_handlers = None     # type: dict
    current_connection = None   # type: ClientConnection

    def __init__(self, reader, writer):
        self.reader = reader
        self.writer = writer

        self.command_handlers = {
            'list': self._process_list,
            'message': self._process_message,
            'quit': self._process_quit,
        }

    async def _process_quit(self, event):
        self.is_stopped = True

    async def _process_list(self, event):
        await _send(writer=self.writer, data={
            'type': 'list',
            'data': {
                'usernames': [x.username for x in connections],
            },
        })

    async def _process_message(self, event):
        try:
            await broadcast_message(text=event['data']['text'], username=self.username)
        except KeyError:
            logger.exception('Unexpected client message format.')
            return

        except Exception:
            logger.exception('Unexpected exception while broadcasting a message.')
            return


    async def initialize(self, strict_ip: bool=False):
        self.username = get_next_username()

        ip, port = self.writer.get_extra_info('peername')

        if strict_ip:
            for x in connections:
                if x.ip == ip:
                    await _send(writer=self.writer, data={
                        'type': 'deny',
                        'data': {'port': x.port}
                    })
                    self.writer.close()
                    await self.writer.wait_closed()
                    return

        self.current_connection = ClientConnection(
            self.reader,
            self.writer,
            username=self.username,
            ip=ip,
            port=port
        )

        await broadcast_joined(self.username)
        connections.append(self.current_connection)

    async def finalize(self):
        connections.remove(self.current_connection)
        await broadcast_quit(username=self.username)
        self.writer.close()


    async def handle(self) -> None:
        while not self.is_stopped:
            try:
                event = await read_json(self.reader)
            except ValueError:
                logger.exception('Unexpected client message format.')
                continue

            if event is None:
                logger.error('Message was not parsed.')
                continue

            event_handler = self.command_handlers.get(event.get('type'))
            if event_handler is None:
                logger.error("Event %s cant be handled.", event.get('type'))
                continue

            await event_handler(event)



async def handler_factory(reader, writer):
    handler_instance = ServerHandler(reader, writer)
    await handler_instance.initialize(strict_ip='--strict-ip' in sys.argv)
    await handler_instance.handle()
    await handler_instance.finalize()


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
    try:
        writer.write(encode_json(data))
        await writer.drain()
    except Exception as e:
        logger.exception('Failed to send %s', data)


async def run():
    server = await asyncio.start_server(
        handler_factory,
        host='0.0.0.0',
        port='5555'
    )

    try:
        await server.serve_forever()
    except CancelledError as e:
        logger.info('Server is stopped.')


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run())

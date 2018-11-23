#!/usr/bin/python3.7

import asyncio
import logging
import sys
from asyncio.futures import CancelledError
from asyncio.streams import StreamReader, StreamWriter
from typing import List, Optional

from constants import ServerEvent
from helper import encode_json, read_json
from server_utils import ClientConnection, PrivateMessage, parse_for_private_message



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
            'type': ServerEvent.LIST.value,
            'data': {
                'usernames': [x.username for x in connections],
            },
        })

    async def _process_message(self, event):
        try:
            text = event['data']['text']
        except KeyError:
            logger.exception('Unexpected client message format.')
            return

        private_message = parse_for_private_message(text)
        if private_message is not None:
            private_message.send_from = self.username
            await _send_private_message(private_message)
            return

        try:
            await _broadcast_message(text=text, username=self.username)
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
                        'type': ServerEvent.DENY.value,
                        'data': {'port': x.port}
                    })
                    self.writer.close()
                    await self.writer.wait_closed()
                    self.is_stopped = True
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
        await _send_text_message(
            message_type=ServerEvent.SYSTEM_MESSAGE,
            connection=self.current_connection,
            text=f"You've been connected as {self.username}."
        )

    async def finalize(self):
        if self.current_connection is not None:
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

            except ConnectionAbortedError:
                logger.info('Connection was closed by client %s.', self.username)
                self.is_stopped = True
                continue

            if event is None:
                logger.error('Message was not parsed.')
                continue

            event_handler = self.command_handlers.get(event.get('type'))
            if event_handler is None:
                logger.error("Event %s cant be handled.", event.get('type'))
                continue

            try:
                await event_handler(event)
            except Exception as e:
                logger.exception("Unexpected exception while handling event %s", event)
                continue


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


async def _broadcast_message(text: str, *, username: str):
    logger.info('Message (%s): %s', username, text)
    await asyncio.gather(
        *(
            _send_text_message(
                message_type=ServerEvent.BROADCAST_MESSAGE,
                connection=x, text=text, sender=username
            )
            for x in connections if x.username != username
        )
    )

def get_connection(username: str) -> Optional[ClientConnection]:
    return next(filter(lambda x: x.username == username, connections), None)

async def _send_private_message(msg: PrivateMessage):
    logger.debug('%s -> %s: %s', msg.send_from, msg.send_to, msg.text)

    connection = get_connection(msg.send_to)

    if connection is None:
        connection = get_connection(msg.send_from)

        if connection is not None:
            await _send_text_message(
                message_type=ServerEvent.SYSTEM_MESSAGE,
                connection=connection,
                text=f'User {msg.send_to} was not found.'
            )
        return

    await _send_text_message(
        message_type=ServerEvent.PRIVATE_MESSAGE,
        connection=connection,
        text=msg.text,
        sender=msg.send_from,
    )

async def _send_text_message(
        *,
        message_type: ServerEvent,
        connection: ClientConnection,
        text: str,
        sender: Optional[str]=None,
):
    await _send(writer=connection.writer, data={
        'type': message_type.value,
        'data': {'text': text, 'sender': sender, },
    })


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

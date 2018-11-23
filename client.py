#!/usr/bin/python3.7

import asyncio
import logging
import sys

from asyncio.streams import StreamReader, StreamWriter, StreamReaderProtocol

from constants import ServerEvent
from helper import read_json, encode_json



logger = logging.getLogger(__name__)


class Client:
    host = '127.0.0.1'
    port = 5555
    is_stopped = False

    async def send(self, message: str):
        pass

    async def start(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)

        await asyncio.gather(
            self.listen(reader),
            self.speak(writer)
        )

    async def listen(self, reader: StreamReader):
        while not self.is_stopped:
            try:
                event = await read_json(reader)
            except ValueError:
                logger.exception('Failed to parse the message.')
                continue

            if event is None:
                break

            try:
                event_type = ServerEvent(event.get('type'))
            except ValueError:
                logger.error(f'Unrecognized format: {event}')
                continue

            await self.MESSAGE_TYPE_TO_HANDLER[event_type](
                self, event.get('data')
            )

    async def speak(self, writer: StreamWriter):
        keyboard_reader = StreamReader()
        keyboard_protocol = StreamReaderProtocol(keyboard_reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda :keyboard_protocol, sys.stdin)

        while True:
            message = (await keyboard_reader.readline()).decode().strip()

            if message == '/q':
                self.is_stopped = True
                await self._send_command('quit', writer=writer)
                break

            if message == '/list':
                await self._send_command('list', writer=writer)
                continue

            await self._send_message(message, writer=writer)

    async def _process_joined_the_channel(self, data: dict):
        print(f"{data['username']} joined the channel")

    async def _process_quit_the_channel(self, data: dict):
        print(f"{data['username']} quit the channel")

    async def _process_broadcast_message(self, data: dict):
        print(f"{data['sender']}: {data['text']}")

    async def _process_private_message(self, data: dict):
        print(f"{data['sender']} (private): {data['text']}")

    async def _process_system_message(self, data: dict):
        print(f"{data['text']}")

    async def _process_deny(self, data: dict):
        self.is_stopped = True
        print(f"There is a client on the same IP and port {data['port']}")

    async def _send_message(self, text, *, writer: StreamWriter):
        writer.write(encode_json({
            'type': 'message',
            'data': {'text': text},
        }))
        await writer.drain()

    async def _send_command(self, command: str, *, writer: StreamWriter):
        writer.write(encode_json({
            'type': command,
        }))
        await writer.drain()

    async def _process_list(self, data: dict):
        usernames = data.get('usernames')
        if not isinstance(usernames, list):
            print('Invalid server response.')
            return

        print("{} users are currently online:\n{}".format(
            len(usernames), ', '.join(usernames)
        ))

    MESSAGE_TYPE_TO_HANDLER = {
        ServerEvent.JOINED: _process_joined_the_channel,
        ServerEvent.QUIT: _process_quit_the_channel,
        ServerEvent.BROADCAST_MESSAGE: _process_broadcast_message,
        ServerEvent.PRIVATE_MESSAGE: _process_private_message,
        ServerEvent.SYSTEM_MESSAGE: _process_system_message,
        ServerEvent.DENY: _process_deny,
        ServerEvent.LIST: _process_list,
    }


async def run():
    await Client().start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run())

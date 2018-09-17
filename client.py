import asyncio
import logging
import sys

from asyncio.streams import StreamReader, StreamWriter, StreamReaderProtocol

from helper import read_json, encode_json



logger = logging.getLogger(__name__)


class Client:
    host = '127.0.0.1'
    port = 5555


    async def send(self, message: str):
        pass

    async def start(self):
        reader, writer = await asyncio.open_connection(self.host, self.port)

        await asyncio.gather(
            self.listen(reader),
            self.speak(writer)
        )

    async def listen(self, reader: StreamReader):
        while True:
            try:
                event = await read_json(reader)
            except ValueError:
                logger.exception('Failed to parse the message.')
                continue

            if event is None:
                break

            if 'type' not in event:
                logger.error(f'Unrecognized format: {event}')
                continue

            await self.MESSAGE_TYPE_TO_HANDLER.get(event['type'])(
                self, event.get('data')
            )

    async def speak(self, writer: StreamWriter):
        keyboard_reader = StreamReader()
        keyboard_protocol = StreamReaderProtocol(keyboard_reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda :keyboard_protocol, sys.stdin)

        while True:
            message = (await keyboard_reader.readline()).decode().strip()

            if message == 'quit':
                await self._send_quit(writer=writer)
                break

            await self._send_message(message, writer=writer)

    async def _process_joined_the_channel(self, data: dict):
        print(f"{data['username']} joined the channel")

    async def _process_quit_the_channel(self, data: dict):
        print(f"{data['username']} quit the channel")

    async def _process_message(self, data: dict):
        print(f"{data['sender']}: {data['text']}")

    async def _send_message(self, text, *, writer: StreamWriter):
        writer.write(encode_json({
            'type': 'message',
            'data': {'text': text},
        }))
        await writer.drain()

    async def _send_quit(self, *, writer: StreamWriter):
        writer.write(encode_json({
            'type': 'quit',
        }))
        await writer.drain()



    MESSAGE_TYPE_TO_HANDLER = {
        'joined': _process_joined_the_channel,
        'quit': _process_quit_the_channel,
        'message': _process_message,
    }


async def run():
    await Client().start()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(run())
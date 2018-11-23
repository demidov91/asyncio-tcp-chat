from enum import Enum


class ServerEvent(Enum):
    BROADCAST_MESSAGE = 'broadcast_message'
    PRIVATE_MESSAGE = 'private_message'
    SYSTEM_MESSAGE = 'system_message'
    DENY = 'deny'
    LIST = 'list'
    QUIT = 'quit'
    JOINED = 'joined'

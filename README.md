# asyncio-tcp-chat

Small study project for a asyncio based tcp chat.

### Server
`python3.7 server.py`

Terminated with `ctrl-c`

Use `--strict-ip` command line argument to enable *one-ip-one-client* policy.

### Client 
`python3.7 client.py`

Available commands:
    
    \q - quit
    \list - list all users which are currently online.
    
*Private message*

* Start your command with `@some-recipient-username` to send a private message.

All other messages are broadcasted for all connected clients.

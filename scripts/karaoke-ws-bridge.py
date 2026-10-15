"""Bounded, same-origin RFC6455 byte relay for the existing FAIO v6 endpoint.

No room controls, new credentials, HTTP polling leases, or generated reports.
Browser masked frames are relayed unchanged to upstream; upstream unmasked
frames are relayed unchanged to the browser. Both ends revalidate normally.
"""
from __future__ import annotations
import base64
import hashlib
import os
import select
import socket
import ssl
import time
from urllib.parse import urlsplit

GUID = '258EAFA5-E914-47DA-95CA-C5AB0DC85B11'


def accept_key(key: str) -> str:
    try:
        if len(base64.b64decode(key, validate=True)) != 16:
            raise ValueError('Invalid WebSocket key')
    except Exception as exc:
        raise ValueError('Invalid WebSocket key') from exc
    return base64.b64encode(hashlib.sha1((key + GUID).encode('ascii')).digest()).decode('ascii')


def connect_upstream(base: str, path: str, cookie: str):
    target = urlsplit(base)
    if target.scheme not in {'http', 'https'} or not target.hostname or target.username or target.password:
        raise ValueError('Invalid upstream origin')
    if any(c in cookie or c in path for c in ('\r', '\n')):
        raise ValueError('Invalid upstream header')
    sock = socket.create_connection((target.hostname, target.port or (443 if target.scheme == 'https' else 80)), timeout=6)
    try:
        if target.scheme == 'https':
            sock = ssl.create_default_context().wrap_socket(sock, server_hostname=target.hostname)
        key = base64.b64encode(os.urandom(16)).decode('ascii')
        headers = [f'GET {path} HTTP/1.1', f'Host: {target.netloc}', f'Origin: {target.scheme}://{target.netloc}',
                   'Upgrade: websocket', 'Connection: Upgrade', f'Sec-WebSocket-Key: {key}',
                   'Sec-WebSocket-Version: 13', f'Cookie: {cookie}', '', '']
        sock.sendall('\r\n'.join(headers).encode('ascii'))
        response = bytearray()
        # Read precisely through headers: never consume the first frame.
        while not response.endswith(b'\r\n\r\n'):
            chunk = sock.recv(1)
            if not chunk or len(response) >= 32768:
                raise OSError('Invalid upstream handshake')
            response.extend(chunk)
        lines = bytes(response).decode('iso-8859-1').split('\r\n')
        status = int(lines[0].split()[1])
        fields = {k.strip().lower(): v.strip() for line in lines[1:] if ':' in line for k,v in [line.split(':',1)]}
        if status != 101 or fields.get('sec-websocket-accept') != accept_key(key):
            raise PermissionError('Upstream rejected WebSocket')
        return sock
    except Exception:
        sock.close()
        raise


def relay(browser, upstream, *, lifetime=1800):
    deadline = time.monotonic() + lifetime if lifetime is not None else float("inf")
    browser.settimeout(6); upstream.settimeout(6)
    while time.monotonic() < deadline:
        ready, _, _ = select.select([browser, upstream], [], [], 2)
        if isinstance(upstream, ssl.SSLSocket) and upstream.pending() and upstream not in ready:
            ready.append(upstream)
        for source in ready:
            data = source.recv(65536)
            if not data:
                return
            (upstream if source is browser else browser).sendall(data)

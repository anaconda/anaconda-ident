from conda.base.context import Context, context

import base64
import getpass
import os
import re
import types
import platform

from logging import getLogger
from os.path import join, expanduser


log = getLogger(__name__)

_client_token_formats = {
    'none': '',
    'random': 'cs',
    'client': 'cs',
    'session': 's',
    'username': 'ucs',
    'hostname': 'hcs',
    'userhost': 'uhcs'
}
_client_token = None
_session_token = None
_full_token = {}

def _random_token(nchar):
    nbytes = (nchar * 6 - 1) // 8 + 1
    return base64.urlsafe_b64encode(os.urandom(nbytes))[:nchar].decode('ascii')


def _get_client_token():
    global _client_token
    if _client_token is not None:
        return _client_token
    cid_file = join(expanduser('~/.conda'), 'client_token')
    if os.path.exists(cid_file):
        try_save = False
        try:
            # Use just the first line of the file, if it exists
            _client_token = ''.join(open(cid_file).read().splitlines()[:1])
            log.debug('Retrieved client token: %s', _client_token)
        except Exception as exc:
            log.debug('Unexpected error reading client token: %s', exc)
    else:
        _client_token = _random_token(8)
        try:
            with open(cid_file, 'w') as fp:
                fp.write(_client_token)
            log.debug('Generated new client token: %s', _client_token)
            log.debug('Client token saved: %s', cid_file)
        except Exception as exc:
            log.debug('Unexpected error writing client token file: %s', exc)
            _client_token = ''
    return _client_token


def _get_session_token():
    global _session_token
    if _session_token is not None:
        return _session_token
    _session_token = _random_token(8)
    log.debug('Session token generated: %s', _session_token)
    return _session_token


def _client_token_value(token_type):
    global _full_token
    if token_type in _full_token:
        return _full_token[token_type]
    parts = []
    fmt = _client_token_formats.get(token_type, token_type)
    for code in fmt:
        value = ''
        if code == 'c':
            value = _get_client_token()
        elif code == 's':
            value = _get_session_token()
        elif code == 'u':
            try:
                value = getpass.getuser()
            except Exception as exc:
                log.debug('getpass.getuser raised an exception: %s' % exc)
        elif code == 'h':
            value = platform.node()
            if not value:
                log.debug('platform.node returned an empty value')
        if value:
            parts.append(code + ':' + value)
    result = ':'.join(parts)
    log.debug('Client token: %s %s', token_type, result)
    _full_token[token_type] = result
    return result


try:
    setattr(Context, '__old_init__', Context.__init__)
    def _new_init(self, *args, **kwargs):
        self.__old_init__(*args, **kwargs)
        fmt = None
        for key, value in self.raw_data.items():
            if 'client_token' in value:
                fmt = value['client_token']._raw_value
        if fmt is None:
            fmt = 'client'
        elif not isinstance(fmt, str):
            log.warning('client_token has an invalid value; defaulting to "client"')
            fmt = 'client'
        self._cache_['__user_agent'] = self.user_agent +' ct/' + _client_token_value(fmt)
    setattr(Context, '__init__', _new_init)
    setattr(context, '__init__', types.MethodType(Context.__init__, context))
    context.__init__((), None)
except Exception as exc:
    print('WARNING: conda_ident failed: %s', exc)
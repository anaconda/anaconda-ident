from conda.base.context import Context, context
from conda.gateways.connection.session import CondaHttpAuth
from conda.auxlib.decorators import memoize

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
    'default': 'cs',
    'random': 'cs',
    'client': 'cs',
    'session': 's',
    'username': 'ucs',
    'hostname': 'hcs',
    'userhost': 'uhcs',
    'org': 'cso'
}


def get_random_token(nchar):
    nbytes = (nchar * 6 - 1) // 8 + 1
    return base64.urlsafe_b64encode(os.urandom(nbytes))[:nchar].decode('ascii')


@memoize
def get_client_token():
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
        _client_token = get_random_token(8)
        try:
            with open(cid_file, 'w') as fp:
                fp.write(_client_token)
            log.debug('Generated new client token: %s', _client_token)
            log.debug('Client token saved: %s', cid_file)
        except Exception as exc:
            log.debug('Unexpected error writing client token file: %s', exc)
            _client_token = ''
    return _client_token


@memoize
def get_session_token():
    _session_token = get_random_token(8)
    log.debug('Session token generated: %s', _session_token)
    return _session_token


@memoize
def get_username():
    try:
        return getpass.getuser()
    except Exception as exc:
        log.debug('getpass.getuser raised an exception: %s' % exc)


@memoize
def get_hostname():
    value = platform.node()
    if not value:
        log.debug('platform.node returned an empty value')
    return value


def get_full_token(token_type):
    fmt_parts = token_type.split(':', 1)
    fmt = _client_token_formats.get(fmt_parts[0], fmt_parts[0])
    if len(fmt_parts) > 1 and 'o' not in fmt:
        log.debug('Adding o flag')
        fmt += 'o'
    if len(fmt_parts) <= 1 and 'o' in fmt:
        fmt = fmt.replace('o', '')
        log.debug('Removing o flag')
    log.debug('Final ident string: %s', fmt)
    parts = []
    for code in fmt:
        if code == 'c':
            value = get_client_token()
        elif code == 's':
            value = get_session_token()
        elif code == 'u':
            value = get_username()
        elif code == 'h':
            value = get_hostname()
        elif code == 'o':
            value = fmt_parts[1]
        else:
            value = None
        if value:
            parts.append(code + '/' + value)
    result = ' '.join(parts)
    log.debug('Client token: %s', result)
    return result


def patch_header():
    CondaHttpAuth._old_apply_basic_auth = CondaHttpAuth._apply_basic_auth
    def _new_apply_basic_auth(request):
        result = CondaHttpAuth._old_apply_basic_auth(request)
        if getattr(Context, '_client_token', None):
            request.headers['X-Conda-Ident'] = Context._client_token
        return result
    CondaHttpAuth._apply_basic_auth = staticmethod(_new_apply_basic_auth)


def patch_context():
    Context._old__init__ = Context.__init__
    Context._client_token_type = Context._client_token = None
    def _new_init(self, *args, **kwargs):
        self._old__init__(*args, **kwargs)
        token = Context._client_token
        token_type = Context._client_token_type
        for key, value in self.raw_data.items():
            if 'client_token' in value:
                token_type = value['client_token']._raw_value
        if token_type is None:
            token_type = 'default'
        if token is None or token_type != Context._client_token_type:
            Context._client_token_type = token_type
            token = Context._client_token = get_full_token(token_type)
        if token:
            new_user_agent = self.user_agent + ' ' + token
            self._cache_['__user_agent'] = new_user_agent
    Context.__init__ = _new_init
    context.__init__ = types.MethodType(_new_init, context)


try:
    patch_context()
    patch_header()
except Exception as exc:
    log.warning('conda_ident failed: %s', exc)
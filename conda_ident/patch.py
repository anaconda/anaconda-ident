import base64
import getpass
import os
import platform
import hashlib

from conda.base.context import Context, context, env_name
from conda.gateways.connection.session import CondaHttpAuth
from conda.auxlib.decorators import memoize, memoizedproperty

from logging import getLogger
from os.path import join, dirname, basename, expanduser, exists


log = getLogger(__name__)

_client_token_formats = {
    'none': '',
    'default': 'cse',
    'username': 'cseu',
    'hostname': 'cseh',
    'environment': 'csen',
    'userenv': 'cseun',
    'userhost': 'cseuh',
    'full': 'cseuhn'
}


def get_random_token(nchar, bytes=None):
    if bytes is None:
        bytes = os.urandom((nchar * 6 - 1) // 8 + 1)
    return base64.urlsafe_b64encode(bytes)[:nchar].decode('ascii')


# Separate this out so it can be called in testing
@memoize
def get_baked_token_config():
    baked_fname = join(dirname(__file__), 'client_token')
    if exists(baked_fname):
        with open(baked_fname, 'r') as fp:
            return fp.read().strip() or None


# Save the raw client and token data as Context class
# attributes to ensure they are passed between subprocesses
def initialize_raw_tokens():
    if hasattr(Context, 'session_token'):
        return
    Context.session_token = get_random_token(8)
    Context.raw_client_token = None
    cid_file = join(expanduser('~/.conda'), 'client_token')
    client_token = ''
    if os.path.exists(cid_file):
        try:
            # Use just the first line of the file, if it exists
            client_token = ''.join(open(cid_file).read().splitlines()[:1])
            log.debug('Retrieved client token: %s', client_token)
        except Exception as exc:
            log.debug('Unexpected error reading client token: %s', exc)
    if len(client_token) < 64:
        if len(client_token) > 0:
            log.debug('Creating longer token for hashing')
        client_token = get_random_token(64)
        try:
            with open(cid_file, 'w') as fp:
                fp.write(client_token)
            log.debug('Generated new client token: %s', client_token)
            log.debug('Client token saved: %s', cid_file)
        except Exception as exc:
            log.debug('Unexpected error writing client token file: %s', exc)
            client_token = ''
    Context.raw_client_token = client_token


def get_environment_token(ctx):
    try:
        value = ctx.target_prefix
    except Exception:
        log.debug('ctx.target_prefix raised an exception')
        return None
    # Do not create an environment token if we don't have
    # enough salt to hash it
    if len(Context.raw_client_token) < 64:
        log.debug('raw_client_token not long enough to hash')
        return None
    # Use the client token as salt for the hash function to
    # ensure the receiver cannot decode the environment name
    hashval = Context.raw_client_token + value
    hash = hashlib.sha1(hashval.encode('utf-8'))
    return get_random_token(8, hash.digest())


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


def get_environment_name(ctx):
    try:
        return basename(env_name(ctx.target_prefix))
    except Exception:
        log.debug('ctx.target_prefix raised an exception')
        return None


def _client_token_type(ctx):
    token_type = get_baked_token_config()
    if token_type:
        log.debug('Hardcoded token config: %s', token_type)
    if token_type is None:
        for key, value in ctx.raw_data.items():
            if 'client_token' in value:
                token_type = value['client_token']._raw_value
                log.debug('Token config from context: %s', token_type)
    if token_type is None:
        log.debug('Selecting default token config')
        token_type = 'default'
    fmt_parts = token_type.split(':', 1)
    fmt = _client_token_formats.get(fmt_parts[0], fmt_parts[0])
    if len(fmt_parts) > 1:
        if not fmt:
            fmt = 'cseo'
        elif 'o' not in fmt:
            fmt += 'o'
    elif fmt == 'o':
        fmt = 'cse'
    elif 'o' in fmt:
        fmt = fmt.replace('o', '')
    fmt_parts[0] = ''.join(c for c in fmt if c in 'csuhoen')
    token_type = ':'.join(fmt_parts)
    log.debug('Final token config: %s', token_type)
    return token_type


def _client_token(ctx):
    parts = []
    fmt_parts = ctx.client_token_type.split(':', 1)
    for code in fmt_parts[0]:
        if code == 'c':
            value = Context.raw_client_token[:8]
        elif code == 's':
            value = Context.session_token
        elif code == 'u':
            value = get_username()
        elif code == 'h':
            value = get_hostname()
        elif code == 'o':
            value = fmt_parts[1]
        elif code == 'e':
            value = get_environment_token(ctx)
        elif code == 'n':
            value = get_environment_name(ctx)
        else:
            log.warning('Unexpected client token code: %s', code)
            value = None
        if value:
            parts.append(code + '/' + value)
    result = ' '.join(parts)
    log.debug('Full client token: %s', result)
    return result


def _user_agent(ctx):
    token = ctx.client_token
    result = ctx._old_user_agent
    return result + ' ' + token if token else result


def _new_apply_basic_auth(request):
    result = CondaHttpAuth._old_apply_basic_auth(request)
    token = context.client_token
    if token:
        request.headers['X-Conda-Ident'] = token
    return result


initialize_raw_tokens()
if not hasattr(Context, 'client_token_type'):
    Context.client_token_type = memoizedproperty(_client_token_type)
if not hasattr(Context, 'client_token'):
    Context.client_token = memoizedproperty(_client_token)
if not hasattr(Context, '_old_user_agent'):
    Context._old_user_agent = Context.user_agent
    # The leading underscore ensures that this is stored in
    # the cache in a different place than the original user agent
    Context.user_agent = memoizedproperty(_user_agent)
if not hasattr(CondaHttpAuth, '_old_apply_basic_auth'):
    CondaHttpAuth._old_apply_basic_auth = CondaHttpAuth._apply_basic_auth
    CondaHttpAuth._apply_basic_auth = staticmethod(_new_apply_basic_auth)

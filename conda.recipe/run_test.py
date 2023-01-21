import os
import sys
import subprocess

from conda_ident import patch


# In theory, test_fields = _client_token_formats[param]
# I'm hardcoding them here so the test doesn't depend on that
# part of the code, with the exception of "baked" test below.
test_patterns = (
    ('none', ''), ('default', 'cs'), ('random', 'cs'),
    ('client', 'cs'), ('session', 's'),
    ('hostname', 'csh'), ('username', 'csu'), ('userhost', 'csuh'), ('org:testme', 'cso'),
    ('full', 'csuhe'),
    ('c', 'c'), ('s', 's'), ('u', 'u'), ('h', 'h'), ('e', 'e'), ('o', 'cs'),
    ('default:org1', 'cso'), ('full:org2', 'csuheo'), ('o:org3', 'o'), (':org4', 'cso')
)
flags = ('', '--disable', '--enable')


# In a "baked" configuration, the client token config is
# hardcoded into the package itself
baked_config = patch.get_baked_token_config()
client_token_env = os.environ.get('CLIENT_TOKEN')
if not client_token_env:
    if baked_config is not None:
        print('Unexpected baked configuration:', baked_config)
        sys.exit(-1)
elif baked_config != client_token_env:
    print('Expected baked configuration %s, found %s:' % (client_token_env, baked_config))
    sys.exit(-1)
else:
    print('Running with baked configuration:', baked_config)
    fmt = baked_config.split(':', 1)[0]
    test_patterns = [(baked_config, patch._client_token_formats.get(fmt, fmt))]
    flags = ('',)
    print('test_patterns:', test_patterns)
    print('')


nfailed = 0
saved_values = {}
all_session_tokens = set()
max_param = max(max(len(x) for x, _ in test_patterns), len('client_token'))
max_field = max(max(len(x) for _, x in test_patterns), len('fields'))
for flag in flags:
    if flag:
        subprocess.run(['python', '-m', 'conda_ident.install', flag])
        value = subprocess.check_output(['python', '-m', 'conda_ident.install', '--status'])
        print('')
        print(value.decode('utf-8').strip())
    is_enabled = flag != '--disable'
    print('{:{w1}} {:{w2}} ?? user-agent'.format(
          'client_token', 'fields', w1=max_param, w2=max_field))
    print('{} {} -- ----------'.format('-' * max_param, '-' * max_field))
    for param, test_fields in test_patterns:
        print('{:{w1}} {:{w2}} '.format(
              param, test_fields, w1=max_param, w2=max_field), end='')
        os.environ['CONDA_CLIENT_TOKEN'] = param
        value = subprocess.check_output(['conda', 'info'])
        user_agent = next(v for v in value.decode('utf-8').splitlines() if 'user-agent' in v)
        user_agent = user_agent.split(' : ', 1)[-1]
        new_values = {token[0]: token for token in user_agent.split(' ') if token[1] == '/'}
        if is_enabled:
            # Confirm that all of the expected tokens are present
            failed = set(new_values) != set(test_fields)
            # Confirm that if the org token, if present, matches the provided value
            if not failed and 'o' in new_values:
                failed = new_values['o'][2:] != param.rsplit(':', 1)[-1]
            # Confirm that the session token, if present, is unique
            if 's' in new_values:
                failed = failed or new_values['s'] in all_session_tokens
                all_session_tokens.add(new_values['s'])
            # Confirm that any values besides session and org do not change from run to run
            if not failed:
                failed = any(v != saved_values.setdefault(k, v)
                             for k, v in new_values.items() if k not in 'so')
        else:
            failed = len(new_values) > 0
        print('XX' if failed else 'OK', user_agent)
        nfailed += failed


print('FAILURES:', nfailed)
sys.exit(nfailed)

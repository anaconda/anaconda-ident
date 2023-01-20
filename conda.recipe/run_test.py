import re
import os
import sys
import subprocess

from conda_ident import patch


# In theory, test_fields = _client_token_formats[param]
# I'm hardcoding them here so the test doesn't depend on that
# part of the code, with the exception of "baked" test below.
test_patterns = (
    ('none', ''), ('default', 'cs'), ('random', 'cs'), ('client', 'cs'), ('session', 's'),
    ('hostname', 'hcs'), ('username', 'ucs'), ('userhost', 'uhcs'), ('org:testme', 'cso'),
    ('c', 'c'), ('s', 's'), ('u', 'u'), ('h', 'h'), ('o:testme', 'o')
)
flags = ('', '--disable', '--enable')


# In a "baked" configuration, the client token config is
# hardcoded into the package itself
baked_config = patch.get_baked_token_config()
client_token_env = os.environ.get('CLIENT_TOKEN')
if client_token_env is None:
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
max_param = max(max(len(x) for x, _ in test_patterns), len('client_token'))
max_field = max(max(len(x) for _, x in test_patterns), len('fields'))
for flag in flags:
    if flag:
        subprocess.run(['python', '-m', 'conda_ident.install', flag])
        value = subprocess.check_output(['python', '-m', 'conda_ident.install', '--status'])
        print('')
        print(value.decode('utf-8').strip())
    is_enabled = flag != '--disable'
    print('{:{w1}} {:{w2}} ?? user-agent'.format('client_token', 'fields', w1=max_param, w2=max_field))
    print('{} {} -- ----------'.format('-' * max_param, '-' * max_field))
    for param, test_fields in test_patterns:
        if test_fields and is_enabled:
            test_re = [c + '/[^ ]+' for c in test_fields]
            test_re_ua = '^.* ' + ' '.join(test_re) + '$'
        else:
            test_re_ua = '^((?! [cso]/).)*$'
        print('{:{w1}} {:{w2}} '.format(param, test_fields, w1=max_param, w2=max_field), end='')
        os.environ['CONDA_CLIENT_TOKEN'] = param
        value = subprocess.check_output(['conda', 'info'])
        user_agent = next(v for v in value.decode('utf-8').splitlines() if 'user-agent' in v)
        user_agent = user_agent.split(' : ', 1)[-1]
        failed = not re.match(test_re_ua, user_agent)
        if failed or is_enabled and 'o' in test_fields and ' o/testme' not in user_agent:
            failed = True
        print('XX' if failed else 'OK', user_agent)
        nfailed += failed


print('FAILURES:', nfailed)
sys.exit(nfailed)

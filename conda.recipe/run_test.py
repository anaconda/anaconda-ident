import re
import os
import sys
import subprocess

nfailed = 0
test_patterns = (
    ('none', ''), ('default', 'cs'), ('random', 'cs'), ('client', 'cs'), ('session', 's'),
    ('hostname', 'hcs'), ('username', 'ucs'), ('userhost', 'uhcs'), ('org:testme', 'cso'),
    ('c', 'c'), ('s', 's'), ('u', 'u'), ('h', 'h'), ('o:testme', 'o')
)
max_param = max(max(len(x) for x, _ in test_patterns), len('client_token'))
max_field = max(max(len(x) for _, x in test_patterns), len('fields'))
for flag in ('', '--disable', '--enable'):
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
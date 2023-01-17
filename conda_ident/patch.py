from conda.base.context import context
try:
    if 'xt/' not in context.user_agent:
        import getpass
        context._cache_['__user_agent'] += ' xt/' + getpass.getuser()
except Exception as exc:
    print('WARNING: conda_ident failed: %s', exc)
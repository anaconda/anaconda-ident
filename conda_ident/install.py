import sysconfig
import sys
import os

pfile = os.path.join(sysconfig.get_paths()['purelib'], 'conda', 'base', 'context.py')

pline = '''
try:
    import conda_ident.patch
except Exception:
    pass
'''.encode('ascii')

try:
    with open(pfile, 'rb') as fp:
        text = fp.read()
    if b'conda_ident' in text[-len(pline):]:
        sys.exit(0)
    wineol = b'\r\n' in text
    if wineol != (b'\r\n' in pline):
        args = (b'\n', b'\r\n') if wineol else (b'\r\n', b'\n')
        pline = pline.replace(*args)
    # We do not append to the original file because this is
    # likely a hard link into the package cache, so doing so
    # would lead to conda flagging package corruption.
    with open(pfile + '.new', 'wb') as fp:
        fp.write(text)
        fp.write(pline)
    os.rename(pfile, pfile + '.orig')
    os.rename(pfile + '.new', pfile)
except Exception as exc:
    print('WARNING: conda_ident activation failed: %s' % exc)

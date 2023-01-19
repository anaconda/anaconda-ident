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
    removing = '--disable' in sys.argv
    status_only = '--status' in sys.argv
    is_present = b'conda_ident' in text[-len(pline):]
    if status_only:
        print('conda_ident status:', 'ENABLED' if is_present else 'DISABLED')
        sys.exit(0)
    if is_present != removing:
        sys.exit(0)
    wineol = b'\r\n' in text
    if wineol != (b'\r\n' in pline):
        args = (b'\n', b'\r\n') if wineol else (b'\r\n', b'\n')
        pline = pline.replace(*args)
    if removing and pline in text:
        text = text.replace(pline, b'')
    # We do not append to the original file because this is
    # likely a hard link into the package cache, so doing so
    # would lead to conda flagging package corruption.
    with open(pfile + '.new', 'wb') as fp:
        fp.write(text)
        if not removing:
            fp.write(pline)
    pfile_orig = pfile + '.orig'
    if os.path.exists(pfile_orig):
        os.unlink(pfile_orig)
    os.rename(pfile, pfile_orig)
    os.rename(pfile + '.new', pfile)
except Exception as exc:
    print('WARNING: conda_ident activation failed: %s' % exc)

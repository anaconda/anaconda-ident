# This patch enables the custom activation heartbeat.
# Future versions of conda will enable this using a
# plugin mechanism.

from conda.activate import _Activator


def _aid_activate(self):
    do_it = _debug = None
    try:
        from anaconda_anon_usage.utils import _debug
        from conda.base.context import context

        # We cannot assume the patch is applied here so
        # we look for the config value in raw data
        for src in context.raw_data.values():
            val = src.get("anaconda_heartbeat")
            if not val:
                continue
            do_it = val._raw_value
            if isinstance(do_it, str):
                do_it = do_it.lower() in ("yes", "true", "t", "1")
        if not do_it:
            return
        _debug("Heartbeat enabled")
        import os
        import sys

        from conda.base.context import locate_prefix_by_name

        from anaconda_ident.heartbeat import attempt_heartbeat

        env = self.env_name_or_prefix
        if env and os.sep not in env:
            env = locate_prefix_by_name(env)
        context.checked_prefix = env or sys.prefix
        attempt_heartbeat("main", "activate", verbose=False, standalone=False)
        _debug("Heartbeat attempted")
    except Exception as exc:
        if _debug:
            _debug("Failed to attempt heartbeat: %s", exc, error=True)
    finally:
        if not do_it and _debug:
            _debug("Heartbeat disabled by %s", "default" if do_it is None else "flag")
        return self._old_activate()


_Activator._old_activate = _Activator.activate
_Activator.activate = _aid_activate

from conda import __version__ as conda_version
from ._version import get_versions

__version__ = get_versions()["version"]
del get_versions

IS_CONDA_23_7_OR_NEWER = tuple(conda_version.split(".")[:2]) >= ("23", "7")

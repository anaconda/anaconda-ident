from setuptools import setup
import versioneer

setup(
    name="conda-ident",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="simple, opt-in user identification for conda clients",
    license="BSD",
    author="Michael C. Grant",
    author_email="mcg@cvxr.com",
    url="https://github.com/mcg1969/conda-ident",
    packages=["conda_ident"],
    install_requires=["conda"],
    keywords=["conda-ident"],
    entry_points={
        "console_scripts": [
            "conda-ident = conda_ident.install:main",
            "conda-keymgr = conda_ident.keymgr:main",
        ]
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)

from setuptools import setup
import versioneer

setup(
    name="anaconda-ident",
    version=versioneer.get_version(),
    cmdclass=versioneer.get_cmdclass(),
    description="simple, opt-in user identification for conda clients",
    license="BSD",
    author="Michael C. Grant",
    author_email="mcg@cvxr.com",
    url="https://github.com/mcg1969/anaconda-ident",
    packages=["anaconda_ident"],
    install_requires=["conda"],
    keywords=["anaconda-ident"],
    entry_points={
        "console_scripts": [
            "anaconda-ident = anaconda_ident.install:main",
            "anaconda-keymgr = anaconda_ident.keymgr:main",
        ],
        "conda": [
            "anaconda-ident-plugin = anaconda_ident.plugin",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
)

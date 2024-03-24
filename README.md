# anaconda-ident

## Simple user identification for conda

The `anaconda-ident` package reconfigures [`conda`](https://docs.conda.io/)
to deliver a configurable amount of additional telemetry data
when requesting indices and packages from a server. This
data is appended to the user agent string, and delivered
to a custom `X-Anaconda-Ident` request header.

In its default mode, this telemetry data is *randomly
generated* to avoid revealing personally identifiable content.
In this mode, use cases include:

- Counting the number of conda clients on a network
- Providing more accurate estimates of package popularity
- Other statistical analyses of conda usage patterns

It may also be *optionally* configured to deliver concrete
identification information such as username, hostname, environment
name, or department. This data enables a variety of additional
use cases, including:

- Counting the number of distinct conda users for compliance purposes
- Implementing a per-departnment chargeback mechanism
- Tracing the distribution of a package that has been flagged for
  security reasons to specific users, machines, or environments

This approach to gathering usage data is more passive and
therefore more convenient for users than, say, requiring that
they authenticate to the package repository.

## Quickstart

### Installation

To use anaconda-ident, simply install it in your base environment:

```
conda install -n base anaconda-ident
```
This package has no additional dependencies other than `conda`
itself. It employs post-link and activation scripts to apply a
small patch into the module `conda.base.context` that enables
the telemetry insertion.

### Default behavior

The easiest way to verify that it is
engaged is by typing `conda info` and examining the `user-agent`
line. The user-agent string will look something like this
(split over two lines for readability):

```
conda/22.11.1 requests/2.28.1 CPython/3.10.4 Darwin/22.2.0
OSX/13.1 c/NIedulQP s/sQPR5moe e/Tfgp_cYz
```

The first five tokens constitute the standard user-agent string
that conda *normally* sends with HTTP requests. The last three tokens,
however, are added by `anaconda-ident`:

- A *client token* `c/NIedulQP` is generated once by the
  conda client and saved in the `~/.conda` directory, so that
  the same value is delivered as long as that
  directory is maintained.
- A *session token* `s/V-X_TsLQ` is generated afresh every time
  `conda` is run.
- An *environment token* `e/Tfgp_cYz` is generated uniquely for
  each separate conda environment (`-n <name>` or `-p <prefix>`).

The same tokens are shipped separately in an additional HTTP header.
Here is an easy way to see precisely what is being shipped to the
upstream server on Unix:

```
conda search -vvv fakepackage 2>&1 | grep -E 'X-Anaconda-Ident|User-Agent'
```

This produces an output like this:

```
> User-Agent: conda/22.11.1 requests/2.28.1 CPython/3.10.4 Darwin/22.2.0 OSX/13.1 c/NIedulQP s/sQPR5moe e/Tfgp_cYz
> X-Anaconda-Ident: c/NIedulQP s/sQPR5moe e/Tfgp_cYz
> User-Agent: conda/22.11.1 requests/2.28.1 CPython/3.10.4 Darwin/22.2.0 OSX/13.1 c/NIedulQP s/sQPR5moe e/Tfgp_cYz
> X-Anaconda-Ident: c/NIedulQP s/sQPR5moe e/Tfgp_cYz
```

### Anonymous token design

These standard three tokens are design to ensure that they do not
reveal identifying information about the user or the host. Specifically:

- The client and session tokens are generated entirely from
  6 bytes of [`os.urandom`](https://docs.python.org/3/library/os.html#os.urandom) data,.
- The environment token is computed from a
  [SHA1 hash](https://docs.python.org/3/library/hashlib.html#hash-algorithms)
  of three components: 1) the full path of your environment,
  2) your client token, and 3) an additional 42 bytes of
  `os.urandom` salt data. The actual hash process produces
  a 20-byte value, which is then truncated to 6 bytes.
- The byte streams are
  [base64-encoded](https://docs.python.org/3/library/base64.html#base64.urlsafe_b64encode)
  to create the tokens themselves.

In short, these tokens were design so that they cannot be used
to recover an underlying username, hostname, or
environment name. The underlying purpose of these tokens is
*disaggregation*: to distinguish between different users,
sessions, and/or environments for analytics purposes. This
works because the probability that two different
users will produce the same tokens is vanishingly small.

Additional tokens are available to be included using optional
configuration, including some that *do* reveal more concrete identifying
information such as username, hostname, and environment name. This
is discussed in the Configuration section below.

### Removing `anaconda-ident`

In order to stop the delivery of the custom tokens entirely,
simply uninstall the package:

```
conda remove -n base anaconda-ident --force
```
The `X-Anaconda-Ident` header will be removed, and the user agent
string will be returned to normal; for instance:

```
user-agent : conda/22.11.1 requests/2.28.1 CPython/3.10.4 Darwin/22.2.0 OSX/13.1
```
The telemetry can also be disabled with a configuration setting;
see below. But removing the package provides the strongest assurance.

## Configuration

The package supports a larger set of tokens

### The token list

All of the tokens produced by `anaconda-ident` take the form
`<character>/<value>`:

- `c`: client token
- `s`: session token
- `e`: environment token
- `u`: username, as determined by the
   [`getpass.getpass`](https://docs.python.org/3/library/getpass.html#getpass.getuser) method.
- `h`: hostname, as determined by the
   [`platform.node`](https://docs.python.org/3/library/platform.html#platform.node) method.
- `n`: environment name. This is the name of the environment
  directory (not the full path), or `base` for the root environment.
- `U`, `H`, and `N`: these are _hashed_ versions of the username, hostname, and environment name (more on this below).
- `o`: organization. This token is an arbitrary string provided
  by the configuration itself, and can be used, for instance,
  to specify the group the user belongs to.

#### Hashed tokens

The _hashed_ username, environment, and hostname tokens provide
a measure of privacy preservation by applying a hash function, salted
with the organization string, to the original values. While
this approach is not cryptographically secure, it would be
expensive for someone to extract the original identifying data
from a hashed token. At the same time, someone with knowledge of
the underlying information (username, environment, hostname, and
organizations string) can readily filter applicable logs for
records that correspond to it.

### The configuration string

A standard configuration string is simply a combination of one
or more of the characters `cseuhnUHN`. To
include an organization string, append it to this configuration
with a leading colon `:`.

Here are some examples:

- `cse`: the default combination of client, session and environment.
- `uh:finance`: username, hostname, and a `finance` organization.
- `cseuhn:eng`: all the tokens, including an `eng` organization.

For convenience, a number of special keywords are also available,
all of which can be combined with the organization string.

- `none`: no tokens. By itself, this keyword effectively disables
  the user-agent telemetry of `anaconda-ident`. If an
  organization string is appended (e.g., `none:myorg`), it
  will be the only token included in the user-agent.
- `default`: equivalent to `cse`.
- `username`: equivalent to `cseu`.
- `hostname`: equivalent to `cseh`.
- `userhost`: equivalent to `cseuh`.
- `userenv`: equivalent to `cseun`.
- `hostenv`: equivalent to `csehn`.
- `full`: equivalent to `cseuhn`.

Here is an example set of tokens for the configuration `full:myorg`:

```
c/NIedulQP s/SsYPna-z e/Tfgp_cYz u/mgrant h/m1mbp.local n/base o/myorg
```

### Local configuration

There are two approaches to setting the configuration for
`anaconda-ident`. The first is to set the `anaconda_ident` parameter using `conda`'s standard configuration mechanisms.
For instance, you can use the `conda config` command:

```
conda config --set anaconda_ident userhost:my_org
```
You can manually edit your `~/.condarc` configuration file and
insert a line; e.g.

```
anaconda_ident: userhost:my_org.
```

### Advanced: configuration package creation

A key feature of the `anaconda_ident` package is the ability
to create a sidecar conda package containing any combination
of the following:

- The `anaconda_ident` configuration string
- A custom `default_channels` value to point conda's `defaults`
  metachannel to an alternative repository
- A standard Conda authentication token for a repository

The typical use case for this is to host this conda package
on an internal package repository, and/or add it into
custom Miniconda / Anaconda installers.

The command to build this package is called `anaconda-keymgr`.
Running `anaconda-keymgr --help` will provide all of the
configuration options. Here is a typical call:

```
anaconda-keymgr \
    --version <VERSION_NUMBER> --build-string <ORGANIZATION> \
    --config-string <CONFIG_STRING> \
    --default-channel <REPO_URL> \
    --repo-token <REPO_TOKEN> \
```

The above command will create a package called

`anaconda-ident-config-<VERSION>-<ORGANIZATION>_0.tar.bz2`.

If this package is installed into a root conda environment,
it will automatically activate `anaconda-ident` and configure
it according to the settings provided.

## Distributing `anaconda-ident`

If you are an Anaconda customer interested in deploying
`anaconda-ident` within your organization, please feel free to
reach out to [Anaconda Support](mailto:support@anaconda.com).
We can offer the following custom builds:

- A set of `anaconda-ident` packages containing your
  preferred configuration.
- A set of `conda` packages with metadata patched to
  include a `anaconda-ident` dependency.
- Builds of the latest Miniconda and Anaconda installers
  with `anaconda-ident` added to them.

By hosting these builds in your internal package repository
and software store, you can greatly simplify the distribution
of this tool throughout your organization.

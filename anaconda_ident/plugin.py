from conda import plugins, __version__ as conda_version

from . import install

subcommand_name = "anaconda-ident"
subcommand_summary = "The anaconda-ident installer."


def configure_parser(parser):
    """
    We're storing the configured parser instance so we can easily
    print the help in the subcommand action
    """
    install._subcommand_parser = parser
    install.configure_parser(parser)


@plugins.hookimpl
def conda_subcommands():
    """
    The conda subcommand plugin hook implementation that works on conda>=22.11.0
    """
    # conda>=23.7.0 has a more advanced subcommand plugin hook
    if tuple(conda_version.split(".")[:2]) >= ("23", "7"):
        yield plugins.CondaSubcommand(
            name=subcommand_name,
            summary=subcommand_summary,
            action=install.execute,
            configure_parser=configure_parser,
        )
    # older versions of conda, just pass pre-parsed args to the action
    else:
        yield plugins.CondaSubcommand(
            name=subcommand_name,
            summary=subcommand_summary,
            action=install.main,
        )

from conda import plugins

from . import install, patch, IS_CONDA_23_7_OR_NEWER

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
    if IS_CONDA_23_7_OR_NEWER:
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


def pre_command_patcher(command):
    # apply the main patch
    patch.monkeypatch()
    # apply the conda.gateways.anaconda_client patch
    patch.monkeypatch_anaconda_client()


if IS_CONDA_23_7_OR_NEWER:
    @plugins.hookimpl
    def conda_pre_commands():
        yield plugins.CondaPreCommand(
            name=subcommand_name,
            action=pre_command_patcher,
            run_for={"install", "create", "uninstall", "env_create", "search"},  # which else?
        )

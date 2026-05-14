"""Typer customizations for dgc."""

import click
from typer.core import TyperGroup


class TLDRGroup(TyperGroup):
    """TyperGroup that renders the epilog via console.print, preserving whitespace."""

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        saved_epilog = self.epilog
        self.epilog = None
        super().format_help(ctx, formatter)
        self.epilog = saved_epilog
        if saved_epilog:
            from dagster_cli.utils.output import console

            console.print(saved_epilog)

"""Local Typer customizations.

Backports the epilog newline-preservation fix from typer PR #1405
(https://github.com/fastapi/typer/pull/1405). Typer's `rich_format_help`
currently collapses single newlines inside `epilog` into spaces, which
destroys indented command examples like the ones in `TLDR_CONTENT`.

Once PR #1405 ships in a Typer release:

  1. Delete this file.
  2. Replace `from dagster_cli.utils.typer_utils import Typer` with
     `from typer import Typer` in every caller.
"""

from __future__ import annotations

import click
import typer
from rich.align import Align
from rich.padding import Padding
from typer.core import TyperGroup
from typer.rich_utils import _make_rich_text


class _FixedEpilogGroup(TyperGroup):
    """TyperGroup that preserves newlines inside `epilog` and hides --help.

    - `format_help` re-renders `epilog` without the `replace("\\n", " ")`
      step Typer applies (backports PR #1405).
    - `get_help_option` returns a hidden `-h`/`--help` option so help stays
      functional but doesn't appear in the rendered Options panel.
    """

    def format_help(self, ctx: click.Context, formatter: click.HelpFormatter) -> None:
        epilog, self.epilog = self.epilog, None
        try:
            super().format_help(ctx, formatter)
        finally:
            self.epilog = epilog
        if not epilog:
            return
        from dagster_cli.utils.output import console

        text = _make_rich_text(text=epilog, markup_mode=self.rich_markup_mode)
        console.print(Padding(Align(text, pad=False), 1))

    def get_help_option(self, ctx: click.Context) -> click.Option | None:
        names = self.get_help_option_names(ctx)
        if not names:
            return None

        def show_help(ctx: click.Context, param: click.Parameter, value: bool) -> None:
            if value and not ctx.resilient_parsing:
                click.echo(ctx.get_help(), color=ctx.color)
                ctx.exit()

        return click.Option(
            names,
            is_flag=True,
            is_eager=True,
            expose_value=False,
            callback=show_help,
            hidden=True,
            help="Show this message and exit.",
        )


class Typer(typer.Typer):
    """Drop-in `typer.Typer` that defaults to `_FixedEpilogGroup`."""

    def __init__(self, *args, **kwargs) -> None:
        kwargs.setdefault("cls", _FixedEpilogGroup)
        kwargs.setdefault("add_help_option", False)
        ctx_settings = kwargs.setdefault("context_settings", {})
        ctx_settings.setdefault("help_option_names", ["-h", "--help"])
        super().__init__(*args, **kwargs)

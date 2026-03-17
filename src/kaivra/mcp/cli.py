"""CLI entrypoint for the local Kaivra MCP server."""

from __future__ import annotations

import json

import click

from kaivra.mcp.server import KaivraMCPServer
from kaivra.mcp.workspace import KaivraWorkspace, format_doctor_report


@click.group(invoke_without_command=True)
@click.pass_context
def main(ctx: click.Context) -> None:
    """Run the local Kaivra MCP server or helper commands."""
    if ctx.invoked_subcommand is None:
        server = KaivraMCPServer()
        server.serve()


@main.command()
@click.option("--json", "as_json", is_flag=True, help="Print the doctor report as JSON.")
def doctor(as_json: bool) -> None:
    """Check the local Kaivra MCP install and print setup instructions."""
    report = KaivraWorkspace().run_doctor()
    if as_json:
        click.echo(json.dumps(report, indent=2))
        return
    click.echo(format_doctor_report(report))


@main.command()
def serve() -> None:
    """Run the stdio MCP server explicitly."""
    KaivraMCPServer().serve()

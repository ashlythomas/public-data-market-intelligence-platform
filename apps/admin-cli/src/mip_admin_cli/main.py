"""Admin CLI."""

import asyncio

import click
from mip_database.session import async_session_factory
from sqlalchemy import text


@click.group()
def cli() -> None:
    """Market Intelligence Platform admin tools."""


@cli.command()
def db_status() -> None:
    """Check database connectivity."""

    async def _check() -> None:
        async with async_session_factory() as session:
            result = await session.execute(text("SELECT 1"))
            assert result.scalar() == 1
            click.echo("Database connection: OK")

    asyncio.run(_check())


@cli.command()
@click.argument("source_id")
def source_info(source_id: str) -> None:
    """Show source information."""

    async def _info() -> None:
        from mip_database.repositories import SourceRepository

        async with async_session_factory() as session:
            repo = SourceRepository(session)
            source = await repo.get_by_id(source_id)
            if not source:
                click.echo(f"Source not found: {source_id}")
                return
            click.echo(f"Source: {source.source_name} ({source.source_id})")
            click.echo(f"  Type: {source.source_type}")
            click.echo(f"  Credibility: {source.credibility_score}")
            click.echo(f"  Licence: {source.licence_type}")

    asyncio.run(_info())

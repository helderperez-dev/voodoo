"""Operational CLI for the local Runtime Store and Voodoo Node fabric."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated

import typer

from voodoo.runtime.identity import (
    AuthenticationEvidence,
    Identity,
    IdentityKind,
    Principal,
)
from voodoo.runtime.membership import NodeAdvertisement, VoodooStoreMembershipStore
from voodoo.runtime.store import RuntimeStore, StoreConfig, VoodooStoreProvider

fabric_app = typer.Typer(help="Inspect and operate the local Voodoo Runtime fabric.")


def _config() -> StoreConfig:
    from voodoo.config import get_config

    return StoreConfig.from_mapping(get_config().store.model_dump())


def _open_runtime() -> RuntimeStore:
    runtime = RuntimeStore(_config())
    runtime.start()
    return runtime


@fabric_app.command("status")
def status() -> None:
    """Show Store health and durable node membership."""
    runtime = _open_runtime()
    try:
        report = runtime.health()
        if report is None:
            typer.echo("Store is disabled", err=True)
            raise typer.Exit(code=1)
        typer.echo(
            f"store={report.provider} path={report.path} "
            f"opened={report.opened} verified={report.verified}"
        )
        membership = VoodooStoreMembershipStore(runtime)
        members = membership.list(include_left=True)
        if not members:
            typer.echo("members=0")
            return
        for member in members:
            typer.echo(
                f"{member.node_id} status={member.status.value} "
                f"location={member.advertisement.location or '-'} "
                f"capabilities={','.join(member.advertisement.capabilities) or '-'}"
            )
    finally:
        runtime.stop()


@fabric_app.command("health")
def health() -> None:
    """Verify the configured application Store and print its health projection."""
    provider = VoodooStoreProvider(_config().path)
    report = provider.health()
    typer.echo(
        f"provider={report.provider} path={report.path} "
        f"verified={report.verified} details={report.details}"
    )
    if not report.verified:
        raise typer.Exit(code=1)


@fabric_app.command("verify")
def verify() -> None:
    """Fail when the configured application Store cannot be verified."""
    health()


@fabric_app.command("join")
def join(
    node_id: Annotated[str, typer.Argument(help="Stable Voodoo Node identity.")],
    capability: Annotated[list[str] | None, typer.Option("--capability", "-c")] = None,
    service: Annotated[list[str] | None, typer.Option("--service", "-s")] = None,
    owner: Annotated[list[str] | None, typer.Option("--owner")] = None,
    location: Annotated[str | None, typer.Option("--location")] = None,
) -> None:
    """Administratively join/update a local node membership record.

    This is a local operator action. Remote nodes still authenticate through the
    Mesh participant resolver before they may become Runtime Principals.
    """
    runtime = _open_runtime()
    try:
        principal = Principal(
            identity=Identity(id=node_id, kind=IdentityKind.NODE),
            evidence=(
                AuthenticationEvidence(
                    method="cli-local", subject=node_id, issuer="voodoo"
                ),
            ),
        )
        member = VoodooStoreMembershipStore(runtime).join(
            principal,
            NodeAdvertisement(
                capabilities=tuple(capability or ()),
                services=tuple(service or ()),
                store_ownership=tuple(owner or ()),
                location=location,
            ),
        )
        typer.echo(f"joined {member.node_id} status={member.status.value}")
    finally:
        runtime.stop()


@fabric_app.command("backup")
def backup(
    destination: Annotated[Path, typer.Argument(help="Destination .vstore path.")],
) -> None:
    """Create a verified cold backup of the configured application Store.

    The command first acquires the Store writer lock. If another Runtime owns the
    Store, acquisition fails rather than copying a live writer unsafely.
    """
    config = _config()
    runtime = RuntimeStore(config)
    runtime.start()
    runtime.stop()
    source = Path(config.path)
    if not source.exists():
        typer.echo(f"Store does not exist: {source}", err=True)
        raise typer.Exit(code=1)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    report = VoodooStoreProvider(destination).health()
    if not report.verified:
        destination.unlink(missing_ok=True)
        typer.echo("Backup verification failed", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"backup={destination} verified=true")

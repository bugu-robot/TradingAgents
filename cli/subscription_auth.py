"""Explicit subscription sign-in/status commands, isolated from analysis."""

import json

import typer

from tradingagents.llm_clients.chatgpt_plan_auth import ChatGPTAuthStore, login
from tradingagents.llm_clients.subscription_errors import USAGE_URL, SubscriptionError
from tradingagents.llm_clients.subscription_registry import (
    preflight_subscription,
    subscription_model_options,
)

app = typer.Typer(help="Manage subscription connections; credentials are never printed.")


@app.command("login")
def sign_in(provider: str = typer.Argument("chatgpt_plan"),
            profile: str | None = typer.Option(None, "--profile"),
            port: int = typer.Option(1455, "--port", min=1, max=65535),
            browser: bool = typer.Option(True, "--browser/--no-browser")):
    """Continue with ChatGPT; approve plan usage in the official sign-in page."""
    if provider != "chatgpt_plan":
        typer.echo("For Google subscription sign-in, run gemini and select Sign in with Google.", err=True)
        raise typer.Exit(1)
    try:
        status = login(ChatGPTAuthStore(profile=profile), port=port, open_browser=browser, announce=typer.echo)
        typer.echo(json.dumps(status))
        if not status["plan_usage_enabled"]:
            typer.echo("Signed in, but plan usage is disabled. Enable it before running analysis.")
        typer.echo(f"Using ChatGPT plan. Manage usage: {USAGE_URL}")
    except (SubscriptionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command("status")
def status(provider: str = typer.Argument("chatgpt_plan")):
    """Read-only authentication preflight; does not consume model quota."""
    try:
        label = preflight_subscription(provider)
        if label is None:
            raise ValueError("Choose a registered subscription provider.")
        if provider == "chatgpt_plan":
            typer.echo(json.dumps(ChatGPTAuthStore().status()))
        else:
            typer.echo(f"{label}: cached Google authentication is configured; live entitlement is not yet verified.")
    except (SubscriptionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command("models")
def models(provider: str = typer.Argument("chatgpt_plan")):
    """Discover the selected account's catalog without guessing entitlement."""
    try:
        options = subscription_model_options(provider)
        if options is None:
            raise ValueError("Choose a registered subscription provider.")
        for display, slug in options:
            typer.echo(f"{slug}\t{display}")
    except (SubscriptionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command("accounts")
def accounts():
    """Show saved connection labels and account status, without credentials."""
    store = ChatGPTAuthStore()
    for path in sorted(store.directory.glob("*.json")):
        if path.stem in {"active", "host"}:
            continue
        typer.echo(json.dumps(ChatGPTAuthStore(profile=path.stem).status()))


@app.command("use")
def use(profile: str):
    """Select a saved ChatGPT connection; each keeps its own client and tokens."""
    try:
        store = ChatGPTAuthStore(profile=profile)
        store.activate()
        typer.echo(json.dumps(store.status()))
    except (SubscriptionError, ValueError) as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from None


@app.command("logout")
def sign_out(profile: str | None = typer.Option(None, "--profile")):
    """Revoke the selected renewable session, then remove its local tokens."""
    confirmed = ChatGPTAuthStore(profile=profile).logout()
    typer.echo("Signed out. Registration retained for later sign-in.")
    if not confirmed:
        typer.echo("Remote revocation was not confirmed. Disconnect TradingAgents in ChatGPT Settings.")

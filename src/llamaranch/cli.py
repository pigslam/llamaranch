import typer

app = typer.Typer(help="LlamaRanch: llama.cpp deployment manager")


@app.command()
def status() -> None:
    """Show LlamaRanch status."""
    print("LlamaRanch status placeholder")


if __name__ == "__main__":
    app()

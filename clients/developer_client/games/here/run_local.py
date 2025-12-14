"""Small helper to run the game server and a client locally for testing.

Usage: run_local.py <host> <port>

This script imports the server and client classes declared in the template
and runs the server in a background thread then runs a client that connects
and exercises the simple ping flow.
"""
import threading
import time
import sys
import importlib
import importlib.util
from pathlib import Path


def run_local(server_module: str, server_class: str, client_module: str, client_class: str):
    def _resolve_module(name: str):
        # Try absolute import first
        try:
            return importlib.import_module(name)
        except Exception:
            pass

        # If it's a relative module (starts with '.'), try importing relative to this package
        if name.startswith('.'):
            pkg = __package__
            if pkg:
                try:
                    return importlib.import_module(name, package=pkg)
                except Exception:
                    pass

        # Fallback: try to load from a file path relative to this file's directory
        try:
            parts = name.lstrip('.').split('.')
            candidate = Path(__file__).resolve().parent.joinpath(*parts).with_suffix('.py')
            if candidate.exists():
                spec = importlib.util.spec_from_file_location(name, str(candidate))
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)  # type: ignore
                return mod
        except Exception:
            pass

        # Last attempt: raise the original import error
        return importlib.import_module(name)

    mod_s = _resolve_module(server_module)
    mod_c = _resolve_module(client_module)
    ServerCls = getattr(mod_s, server_class)
    ClientCls = getattr(mod_c, client_class)

    server = ServerCls(host="127.0.0.1", port=0)

    def start_srv():
        server.start()

    t = threading.Thread(target=start_srv, daemon=True)
    t.start()

    # wait for server to bind
    while getattr(server, "port", 0) == 0:
        time.sleep(0.05)

    host = "127.0.0.1"
    port = server.port
    print(f"Started server on {host}:{port}")

    client = ClientCls(host, port)
    try:
        client.start()
    finally:
        try:
            client.stop()
        except Exception:
            pass
        try:
            server.stop()
        except Exception:
            pass


if __name__ == "__main__":
    # default imports that match the config.json in this template
    # you can call this script with custom import paths if needed
    server_module = "server.server"
    server_class = "GameServer"
    client_module = "client.client"
    client_class = "GameClient"

    if len(sys.argv) >= 5:
        server_module, server_class, client_module, client_class = sys.argv[1:5]

    run_local(server_module, server_class, client_module, client_class)

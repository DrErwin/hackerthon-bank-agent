from importlib import import_module

from fastapi import FastAPI


def test_backend_entry_and_existing_packages_are_importable():
    for package in ("app.contracts", "app.modules.transfer", "app.security"):
        assert import_module(package)

    assert isinstance(import_module("app.main").app, FastAPI)

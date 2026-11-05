"""Hermes plugin entry point, loaded in Hermes' plugin namespace."""


def register(ctx):
    from .sentinel.runtime import register as register_runtime

    register_runtime(ctx)

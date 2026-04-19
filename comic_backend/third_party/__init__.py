import importlib


__all__ = ["external_api", "adapter_factory", "base_adapter", "jmcomic_adapter", "adapter", "legacy"]


def __getattr__(name):
    if name in __all__:
        return importlib.import_module(f"{__name__}.{name}")
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

"""Skeleton smoke test: the package can be imported and exposes its version.

This keeps `pytest` meaningful (and its exit code 0) before the model itself
exists; it is removed once the real test suite covers the package.
"""

import lbo


def test_package_imports_and_has_version() -> None:
    assert lbo.__version__ == "0.1.0"

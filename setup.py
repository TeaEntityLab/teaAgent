from __future__ import annotations

from setuptools import find_packages, setup

GRAPHQLITE_DEPS = ["graphqlite>=0.4.4", "pysqlite3>=0.6.0"]
DEV_DEPS = [*GRAPHQLITE_DEPS, "pytest>=7", "pytest-cov>=4", "ruff>=0.4", "mypy>=1"]


setup(
    name="teaagent",
    version="0.1.0",
    description="Minimal P0 agent harness with governance-first defaults.",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[],
    extras_require={"graphqlite": GRAPHQLITE_DEPS, "dev": DEV_DEPS},
    entry_points={"console_scripts": ["teaagent=teaagent.cli:main"]},
)

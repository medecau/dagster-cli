.PHONY: help fix check test publish

help:			## Show this help.
	@grep '^[^#[:space:]\.].*:' Makefile

fix:			## Run linters and formatters.
	uv run ruff check --fix .
	uv run ruff format .

check:			## Run linters in check mode.
	uv run ruff check .
	uv run ruff format --check .

test: check		## Run tests.
	uv run pytest

publish: test check	## Build and publish to PyPI.
	uv build
	uv publish
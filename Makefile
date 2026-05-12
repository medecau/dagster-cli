.PHONY: help fix check test publish

help:			## Show this help.
	@grep '^[^#[:space:]\.].*:' Makefile

fix:			## Automatically fix most code quality issues
	uv run ruff format .
	uv run ruff check --fix-only .

check:			## Identify code quality issues
	uv run ruff format --check .
	uv run ruff check .
	uv run ty check .

test: check		## Exercute the test suite
	uv run pytest

publish: test	## Build and publish to PyPI
	uv build
	uv publish

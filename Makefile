TEST_OPTIONS=-m unittest discover --start-directory tests --top-level-directory .
CPU_COUNT=$(shell python3 -c "from multiprocessing import cpu_count; print(cpu_count())")

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help           to show this message"
	@echo "  all            to to execute all following targets (except \`test')"
	@echo "  dist           to generate installable Python packages"
	@echo "  dist-clean     to remove generated Python packages"
	@echo "  docs-html      to generate HTML documentation"
	@echo "  docs-clean     to remove documentation"
	@echo "  docs-api       to (re)generate .rst files for the API"
	@echo "  install-dev    to install in editable mode with development dependencies"
	@echo "  lint           to run all linters"
	@echo "  lint-flake8    to run the flake8 linter"
	@echo "  publish        to upload dist/* to PyPi"
	@echo "  test           to run unit tests"
	@echo "  test-coverage  to run unit tests and measure test coverage"

# Edit with caution! Travis CI uses this target. ¶ We run docs-clean before
# docs-html to ensure a complete build. (Warnings are emitted only when a file
# is compiled, and Sphinx does not needlessly recompile.) More broadly, we
# order dependencies by execution time and (anecdotal) likelihood of finding
# issues. ¶ `test-coverage` is a functional superset of `test`. Why keep both?
all: test-coverage pre-commit docs-clean docs-html dist-clean dist

dist:
	./setup.py --quiet sdist bdist_wheel --universal test

dist-clean:
	rm -rf build dist pulp_smash.egg-info

docs-html: docs-api
	@cd docs; $(MAKE) html

docs-clean:
	@cd docs; $(MAKE) clean

docs-api:
	rm -rf docs/api/*
	scripts/gen_api_docs.sh

install-dev:
	pip install --upgrade pip
	pip install -q -e .[dev]

lint: lint-flake

# W504 ignored since it requires line breaks after binary operators.
lint-flake8:
	flake8 . --ignore W504,Q000 --exclude docs/_build

pre-commit:
	@echo "Linting Python files."
	pre-commit run -a
	@echo "Finished."""

publish: dist
	twine upload dist/*

setup-git:
	pre-commit install
	git config branch.autosetuprebase always

test:
	python3 $(TEST_OPTIONS)

test-coverage:
	coverage run --include 'pulp_smash/*' --omit 'pulp_smash/tests/*' $(TEST_OPTIONS)

.PHONY: help all docs-html docs-clean docs-api lint lint-flake8\
    test test-coverage dist-clean publish install-dev

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
	@echo "  lint           to run all linters"
	@echo "  lint-flake8    to run the flake8 linter"
	@echo "  lint-pylint    to run the pylint linter"
	@echo "  publish        to upload dist/* to PyPi"
	@echo "  test           to run unit tests"
	@echo "  test-coverage  to run unit tests and measure test coverage"

# Edit with caution! Travis CI uses this target. ¶ We run docs-clean before
# docs-html to ensure a complete build. (Warnings are emitted only when a file
# is compiled, and Sphinx does not needlessly recompile.) More broadly, we
# order dependencies by execution time and (anecdotal) likelihood of finding
# issues. ¶ `test-coverage` is a functional superset of `test`. Why keep both?
all: test-coverage lint docs-clean docs-html dist-clean dist

dist:
	./setup.py --quiet sdist bdist_wheel --universal

dist-clean:
	rm -rf build dist pulp_smash.egg-info

docs-html:
	@cd docs; $(MAKE) html

docs-clean:
	@cd docs; $(MAKE) clean

# E501 and F401 are ignored because Pylint performs similar checks.
lint-flake8:
	flake8 . --ignore E501,F401 --exclude docs/_build

lint-pylint:
	pylint -j $(CPU_COUNT) --reports=n --disable=I \
		docs/conf.py \
		pulp_smash \
		scripts/run_functional_tests.py \
		setup.py \
		tests

lint: lint-flake8 lint-pylint

publish: dist
	twine upload dist/*

test:
	python3 $(TEST_OPTIONS)

test-coverage:
	coverage run --include 'pulp_smash/*' --omit 'pulp_smash/tests/*' $(TEST_OPTIONS)

.PHONY: help all docs-html docs-clean lint-flake8 lint-pylint lint test \
    test-coverage dist-clean publish

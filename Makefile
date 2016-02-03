TEST_OPTIONS=-m unittest discover --start-directory tests --top-level-directory .
CPU_COUNT=$(shell python -c "from multiprocessing import cpu_count; print(cpu_count())")

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help           to show this message"
	@echo "  docs-html      to generate HTML documentation"
	@echo "  docs-clean     to remove documentation"
	@echo "  lint           to run all linters"
	@echo "  lint-flake8    to run the flake8 linter"
	@echo "  lint-pylint    to run the pylint linter"
	@echo "  test           to run unit tests"
	@echo "  test-coverage  to run unit tests and measure test coverage"
	@echo "  package        to generate installable Python packages"
	@echo "  package-clean  to remove generated Python packages"

docs-html:
	@cd docs; $(MAKE) html

docs-clean:
	@cd docs; $(MAKE) clean

lint-flake8:
	flake8 . --ignore D203

lint-pylint:
	pylint -j $(CPU_COUNT) --reports=n --ignore-imports=y --disable=I \
		docs/conf.py \
		setup.py \
		tests \
		pulp_smash/__init__.py \
		pulp_smash/__main__.py \
		pulp_smash/api.py \
		pulp_smash/cli.py \
		pulp_smash/config.py \
		pulp_smash/constants.py \
		pulp_smash/exceptions.py \
		pulp_smash/selectors.py \
		pulp_smash/utils.py
	pylint -j $(CPU_COUNT) --reports=n --disable=I,duplicate-code pulp_smash/tests/

lint: lint-flake8 lint-pylint

test:
	python $(TEST_OPTIONS)

test-coverage:
	coverage run --source pulp_smash.api,pulp_smash.cli,pulp_smash.config,pulp_smash.exceptions,pulp_smash.selectors,pulp_smash.utils \
	$(TEST_OPTIONS)

package:
	./setup.py sdist bdist_wheel --universal

package-clean:
	rm -rf build dist pulp_smash.egg-info

.PHONY: help docs-html docs-clean lint-flake8 lint-pylint lint test \
    test-coverage package package-clean

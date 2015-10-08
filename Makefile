TEST_OPTIONS=-m unittest discover --start-directory tests --top-level-directory .

help:
	@echo "Please use \`make <target>' where <target> is one of:"
	@echo "  help           to show this message"
	@echo "  docs-html      to generate HTML documentation"
	@echo "  docs-clean     to remove documentation"
	@echo "  lint           to run flake8 and pylint"
	@echo "  test           to run unit tests"
	@echo "  test-coverage  to run unit tests and measure test coverage"
	@echo "  package        to generate installable Python packages"
	@echo "  package-clean  to remove generated Python packages"

docs-html:
	@cd docs; $(MAKE) html

docs-clean:
	@cd docs; $(MAKE) clean

lint:
	flake8 .
	pylint --reports=n --disable=I docs/conf.py pulp_smash tests setup.py

test:
	python $(TEST_OPTIONS)

test-coverage:
	coverage run --source pulp_smash.config $(TEST_OPTIONS)

package:
	./setup.py sdist bdist_wheel --universal

package-clean:
	rm -rf build dist pulp_smash.egg-info

.PHONY: help docs-html docs-clean lint test test-coverage package package-clean

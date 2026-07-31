PYTHON  ?= python3
MAP     ?= maps/easy/01_linear_path.txt

.PHONY: install run visual debug clean lint lint-strict test

install:
	$(PYTHON) -m pip install -r requirements.txt

run:
	$(PYTHON) main.py $(MAP)

visual:
	$(PYTHON) main.py --render $(MAP)

debug:
	$(PYTHON) -m pdb main.py $(MAP)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache .pytest_cache .ruff_cache .coverage htmlcov

lint:
	flake8 . && mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 . && mypy . --strict

test:
	$(PYTHON) -m pytest tests/

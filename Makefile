PYTHON ?= python3

.PHONY: test run

test:
	$(PYTHON) -m compileall -q skywatch tests
	$(PYTHON) -m unittest discover -s tests -t . -b

run:
	set -a; [ -f .env ] && . ./.env; set +a; exec $(PYTHON) -m skywatch

PYTHON ?= python3

.PHONY: test run cycle demo

test:
	$(PYTHON) -m compileall -q skywatch tests
	$(PYTHON) -m unittest discover -s tests -t . -b

# Skywatch loads .env itself (already-set environment variables win).
run:
	exec $(PYTHON) -m skywatch

cycle:
	exec $(PYTHON) -m skywatch cycle

demo:
	$(PYTHON) scripts/demo_digest.py

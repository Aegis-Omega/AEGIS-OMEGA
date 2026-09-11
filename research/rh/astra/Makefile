PYTHON ?= python3
ROOT := $(CURDIR)

.PHONY: doctor pins validate test falsify receipt verify

doctor:
	$(PYTHON) scripts/doctor.py

pins:
	$(PYTHON) scripts/verify_external_pins.py

validate:
	$(PYTHON) scripts/validate_obligations.py --root $(ROOT)

test:
	$(PYTHON) -m pytest -q tests

falsify:
	PYTHONPATH=$(ROOT) $(PYTHON) scripts/run_falsifiers.py

receipt:
	$(PYTHON) scripts/snapshot_receipt.py --root $(ROOT) --output ASTRA_ENV_RECEIPT.json

verify: doctor pins validate test falsify receipt

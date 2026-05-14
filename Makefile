.PHONY: test test-quick test-worker test-web drift eval demo install

install:
	cd worker && python -m venv .venv && . .venv/bin/activate && pip install -e .[dev] && pip install -e ../business_checker
	cd web && pnpm install

test-worker:
	cd worker && pytest -x

test-web:
	cd web && pnpm test --run

test-quick: test-worker test-web

test: test-worker test-web
	@echo "Full suite green"

drift:
	bash scripts/check-drift.sh

eval:
	bash scripts/eval-ci.sh

demo:
	bash scripts/phase0-demo.sh

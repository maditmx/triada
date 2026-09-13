.PHONY: all build test web cli cli-rs clean

all: build test

## regenerate every curriculum file and the web bundle
build:
	python3 tools/gen_typing.py
	python3 tools/gen_nvim.py
	python3 tools/gen_python.py
	python3 tools/gen_meta.py
	python3 tools/build_web.py

## everything: engine unit tests, curriculum validation, JS/Python parity, TUI render
## (the TUI test needs `pip install pyte`; it skips itself if that is missing)
test:
	python3 tests/smoke_vim.py
	python3 tools/validate.py
	node tests/parity.js
	python3 tests/tui_smoke.py
	cd cli-rs && cargo test

## serve the web app (works from file:// too, but a server is nicer)
web:
	@echo "http://localhost:8123 — Ctrl-C to stop"
	@cd web && python3 -m http.server 8123

## run the terminal trainer
cli:
	@./triada

## run the Rust/ratatui port of the terminal trainer
cli-rs:
	@cd cli-rs && cargo run --release

clean:
	find . -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true

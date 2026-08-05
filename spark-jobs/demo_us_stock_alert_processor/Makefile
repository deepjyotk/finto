.PHONY: help setup run lint clean

# Spark 4.0 supports Java 17 and 21 only; the default `java` on this machine may
# be newer, so pin JAVA_HOME to 21 when java_home can find it (macOS).
JAVA_21_HOME := $(shell /usr/libexec/java_home -v 21 2>/dev/null)
ifneq ($(JAVA_21_HOME),)
    export JAVA_HOME := $(JAVA_21_HOME)
endif

help:
	@echo "Available commands:"
	@echo "  make setup - Create the Python 3.12 venv and install dependencies"
	@echo "  make run   - Run the Spark Structured Streaming alert processor"
	@echo "  make lint  - Format and check the job source"
	@echo "  make clean - Remove the venv and streaming checkpoints"

setup:
	@echo "📦 Installing demo_us_stock_alert_processor (Python 3.12)..."
	@uv sync
	@echo "✅ Setup complete!"

run:
	@echo "⚡ JAVA_HOME=$(JAVA_HOME)"
	@uv run python -m demo_us_stock_alert_processor.job

lint:
	@uv run isort src/
	@uv run black src/
	@uv run flake8 src/

clean:
	@rm -rf .venv .checkpoints

.PHONY: setup run-apis run-ui clean lint help

# Detect operating system
ifeq ($(OS),Windows_NT)
    DETECTED_OS := Windows
    VENV_BIN := .venv/Scripts
    PYTHON := python
else
    DETECTED_OS := $(shell uname -s)
    VENV_BIN := .venv/bin
    PYTHON := python3
endif

help:
	@echo "Available commands:"
	@echo "  make setup     - Setup the project (create .venv and install dependencies)"
	@echo "  make run-apis  - Run the FastAPI backend server"
	@echo "  make run-ui    - Run the Gradio UI server"
	@echo "  make lint      - Run code linting and formatting (autoflake, isort, black, flake8)"
	@echo "  make clean     - Clean .venv and uv cache"

setup:
	@echo "🔧 Setting up project for $(DETECTED_OS)..."
	@echo "📦 Creating virtual environment..."
	@uv venv
	@echo "📥 Installing dependencies..."
	@uv sync
	@echo "✅ Setup complete!"
	@echo ""
	@echo "To run the application:"
	@echo "  - Backend API: make run-apis"
	@echo "  - Frontend UI: make run-ui"

run-apis:
	@echo "🚀 Starting FastAPI backend on http://localhost:8000..."
	@uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

run-ui:
	@echo "🎨 Starting Gradio UI on http://localhost:7860..."
	@uv run python -m src.ui.chat_app

lint:
	@echo "🔍 Running code linting and formatting..."
	@echo "🧹 Removing unused imports with autoflake..."
	@uv run autoflake --in-place --remove-all-unused-imports --remove-unused-variables --recursive src/
	@echo "📋 Sorting imports with isort..."
	@uv run isort src/
	@echo "🎨 Formatting code with black..."
	@uv run black src/
	@echo "✅ Running flake8 checks..."
	@uv run flake8 src/
	@echo "✅ Linting complete!"

clean:
	@echo "🧹 Cleaning up..."
	@echo "🗑️  Removing .venv..."
	@rm -rf .venv
	@echo "🗑️  Cleaning uv cache..."
	@uv cache clean
	@echo "✅ Clean complete!"


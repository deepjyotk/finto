.PHONY: setup run-apis run-ui clean lint help render-graph run-evaluation-script create-dataset deploy-tag

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
	@echo "  make render-graph - Render the LangGraph topology image"
	@echo "  make run-evaluation-script dataset_name=<name> - Run LangSmith evaluation on specified dataset"
	@echo "  make create-dataset dataset_name=<name> - Create LangSmith dataset from JSON file"
	@echo "  make deploy-tag - Validate .env vs update-secrets.sh + cloudbuild.yaml, then bump patch semver tag on GitHub (gh)"

setup:
	@echo "🔧 Setting up project for $(DETECTED_OS)..."
	@echo "📦 Creating virtual environment..."
	@uv venv
	@echo "📥 Installing dependencies..."
	@uv sync
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "  1. Copy .env.example to .env and configure your Supabase credentials"
	@echo "  2. Run the application:"
	@echo "     - Backend API: make run-apis"
	@echo "     - Frontend UI: make run-ui"

run-apis:
	@echo "🚀 Starting FastAPI backend on http://localhost:8000..."
	@uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload


docker-build-and-run:
	@echo "🐳 Building Docker image..."
	@docker build -t finto-app:latest .
	@echo "🐳 Starting Docker container..."
	@docker rm -f finto-container >/dev/null 2>&1 || true
	@docker run -d -p 8000:8000 --name finto-container --env-file .env finto-app:latest

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

render-graph:
	@echo "🧭 Rendering LangGraph topology (PNG + Mermaid)..."
	@uv run python scripts/langsmith/render_graph.py --format png --output wiki/artifacts/langgraph.png
	@echo "🖼️  Graph image available at artifacts/langgraph.png"
	@echo "📄  Mermaid file available at wiki/artifacts/langgraph-mermaid.mermaid"

# make run-evaluation-script dataset_name=finto-yf-tools-getBalanceSheet
run-evaluation-script:
	@if [ -z "$(dataset_name)" ]; then \
		echo "❌ Error: dataset_name parameter is required"; \
		echo "Usage: make run-evaluation-script dataset_name=<dataset_name>"; \
		exit 1; \
	fi
	@echo "🔬 Running LangSmith evaluation on dataset: $(dataset_name)..."
	@uv run python scripts/langsmith/evaluators/cot_qa.py --dataset-name $(dataset_name)
	@echo "✅ Evaluation complete!"

#make create-dataset dataset_name=yf-tools-simple-dataset/finto-yf-tools-getBalanceSheet
create-dataset:
	@if [ -z "$(dataset_name)" ]; then \
		echo "❌ Error: dataset_name parameter is required"; \
		echo "Usage: make create-dataset dataset_name=<dataset_name>"; \
		echo "Example: make create-dataset dataset_name=finto-qa-dataset"; \
		exit 1; \
	fi
	@DATASET_FILE="scripts/langsmith/datasets/$(dataset_name).json"; \
	if [ ! -f "$$DATASET_FILE" ]; then \
		echo "❌ Error: Dataset file not found: $$DATASET_FILE"; \
		echo "Please create the file with the following structure:"; \
		echo "{"; \
		echo "    \"dataset_name\": \"$(dataset_name)\","; \
		echo "    \"dataset_description\": \"QA pairs about finto chatbot.\","; \
		echo "    \"examples\": ["; \
		echo "        {"; \
		echo "            \"input\": \"Your question here\","; \
		echo "            \"output\": \"Expected answer here\""; \
		echo "        }"; \
		echo "    ]"; \
		echo "}"; \
		exit 1; \
	fi
	@echo "📦 Creating LangSmith dataset from: scripts/langsmith/datasets/$(dataset_name).json"
	@uv run python scripts/langsmith/datasets/manual_create_dataset.py --dataset-file scripts/langsmith/datasets/$(dataset_name).json
	@echo "✅ Dataset creation complete!"

# Optional: make deploy-tag DEPLOY_TAG_REPO=owner/repo (default deepjyotk/finto)
deploy-tag:
	@DEPLOY_TAG_REPO='$(DEPLOY_TAG_REPO)' bash scripts/deploy-tag.sh

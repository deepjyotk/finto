.PHONY: help install run dev build preview typecheck clean

.DEFAULT_GOAL := help

CYAN := \033[36m
GREEN := \033[32m
RESET := \033[0m

help: ## Show available commands
	@echo "$(CYAN)React concepts — available commands:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-12s$(RESET) %s\n", $$1, $$2}'

install: ## Install npm dependencies
	npm install

run: dev ## Start dev server (alias for dev)

dev: ## Start Vite dev server
	npm run dev

build: ## Production build
	npm run build

preview: ## Preview production build
	npm run preview

typecheck: ## Type-check TSX files
	npm run typecheck

clean: ## Remove build output and node_modules
	rm -rf dist node_modules

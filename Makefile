.PHONY: help install test eval build run deploy clean

SHELL := /bin/bash
IMAGE_NAME ?= cymbal-operations-agent
REGION ?= us-central1
PROJECT_ID ?= $(shell gcloud config get-value project 2>/dev/null || echo "xiaoyj-lab")

help: ## Display help for all targets
	@echo "Cymbal Operations Agent - Makefile Targets"
	@echo "=========================================="
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Setup virtual environment and install dependencies
	uv venv .venv || python3 -m venv .venv
	source .venv/bin/activate && uv pip install -r requirements.txt pytest pytest-mock pytest-asyncio

test: ## Run isolated unit test suite with mocks
	source .venv/bin/activate && pytest -v tests/

eval: ## Run comprehensive live operational verification suite
	source .venv/bin/activate && python run_validation_suite.py

build: ## Build local Docker container image
	docker build -t $(IMAGE_NAME):latest .

run: ## Launch agent locally via ADK Web UI
	source .venv/bin/activate && adk web app

deploy: ## Deploy container to Google Cloud Run
	gcloud builds submit --tag gcr.io/$(PROJECT_ID)/$(IMAGE_NAME):latest
	gcloud run deploy $(IMAGE_NAME) \
		--image gcr.io/$(PROJECT_ID)/$(IMAGE_NAME):latest \
		--region $(REGION) \
		--platform managed \
		--allow-unauthenticated \
		--set-env-vars PROJECT_ID=$(PROJECT_ID),GOOGLE_CLOUD_LOCATION=global,COORDINATOR_MODEL=gemini-3.6-flash

clean: ## Clean up temporary files, pycache, and test artifacts
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.py[cod]" -delete
	rm -rf .pytest_cache

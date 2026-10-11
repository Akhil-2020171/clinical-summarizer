SHELL := /bin/bash
.DEFAULT_GOAL := help

# ---- Settings (override on the command line: make up MODEL_FILE=...) ----
MODEL_REPO ?= Qwen/Qwen2.5-3B-Instruct-GGUF
MODEL_FILE ?= qwen2.5-3b-instruct-q4_k_m.gguf
MODEL_URL  ?= https://huggingface.co/$(MODEL_REPO)/resolve/main/$(MODEL_FILE)
API_PORT   ?= 8000
LLAMA_HOST_PORT ?= 8081

COMPOSE := docker compose

# Make these visible to docker-compose.yml
export MODEL_FILE
export API_PORT
export LLAMA_HOST_PORT

.PHONY: help setup model check-model build up start down restart ps logs logs-api logs-llama \
        health test summary test-fallback shell clean

help: ## Show this help
	@echo "OPD Rx summary generator"
	@echo
	@grep -E '^[a-zA-Z_-]+:.*## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*## "}; {printf "  make %-14s %s\n", $$1, $$2}'
	@echo
	@echo "First time:  make setup model start"

setup: ## Create the models/ folder
	@mkdir -p models
	@echo "models/ is ready."

model: setup ## Download the GGUF model into models/ (resumes if interrupted)
	@if [ -f "models/$(MODEL_FILE)" ]; then \
		echo "models/$(MODEL_FILE) already exists."; \
	else \
		echo "Downloading $(MODEL_FILE) ..."; \
		curl -L --fail -C - -o "models/$(MODEL_FILE)" "$(MODEL_URL)"; \
	fi
	@ls -lh "models/$(MODEL_FILE)"

check-model:
	@test -f "models/$(MODEL_FILE)" || { echo "Model not found: models/$(MODEL_FILE). Run: make model"; exit 1; }

build: ## Build the API image
	$(COMPOSE) build

up: check-model ## Start both containers in the background
	$(COMPOSE) up -d
	@echo "API:  http://localhost:$(API_PORT)   (docs at /docs)"

start: build up ## Build, then start everything

down: ## Stop and remove the containers
	$(COMPOSE) down

restart: ## Restart both containers
	$(COMPOSE) restart

ps: ## Show container status
	$(COMPOSE) ps

logs: ## Follow logs from both containers
	$(COMPOSE) logs -f --tail=100

logs-api: ## Follow API logs (shows "LLM summary accepted/rejected")
	$(COMPOSE) logs -f --tail=100 api

logs-llama: ## Follow llama.cpp server logs
	$(COMPOSE) logs -f --tail=100 llama

health: ## Check the API and the model server
	@echo -n "API:   "; curl -s --max-time 5 http://localhost:$(API_PORT)/health || echo "not reachable"
	@echo
	@echo -n "Model: "; curl -s --max-time 5 http://localhost:$(LLAMA_HOST_PORT)/health || echo "not reachable"
	@echo

test: ## POST samples/sample.json and print the full response
	@time curl -s -X POST http://localhost:$(API_PORT)/summarize \
		-H "Content-Type: application/json" \
		-d @samples/sample.json | python3 -m json.tool

summary: ## POST samples/sample.json and print only the summary
	@time curl -s -X POST http://localhost:$(API_PORT)/summarize \
		-H "Content-Type: application/json" \
		-d @samples/sample.json | python3 -c "import sys, json; print(json.load(sys.stdin)['summary'])"

test-fallback: ## POST a request whose diagnosis the model will alter (expect template summary)
	@curl -s -X POST http://localhost:$(API_PORT)/summarize \
		-H "Content-Type: application/json" \
		-d @samples/sample_fallback.json | python3 -c "import sys, json; print(json.load(sys.stdin)['summary'])"
	@echo
	@echo "Check 'make logs-api' for: LLM summary rejected"

shell: ## Open a shell inside the API container
	$(COMPOSE) exec api bash || $(COMPOSE) exec api sh

clean: ## Remove containers and the locally built API image (keeps models/)
	$(COMPOSE) down --rmi local --remove-orphans

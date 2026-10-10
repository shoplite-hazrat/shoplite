.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down clean ps logs smoke

help: ## Show available targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-8s %s\n", $$1, $$2}'

up: ## Build and start everything, wait until healthy
	$(COMPOSE) up -d --build --wait
	@echo "Shop:  http://localhost:8080"
	@echo "Email: http://localhost:8025"

down: ## Stop everything (keeps data)
	$(COMPOSE) down

clean: ## Stop everything and delete data volumes
	$(COMPOSE) down --volumes --remove-orphans

ps: ## Show container status and health
	$(COMPOSE) ps

logs: ## Follow logs (make logs s=order for one service)
	$(COMPOSE) logs -f $(s)

smoke: ## Run the end-to-end smoke test against the running stack
	./scripts/smoke-test.sh

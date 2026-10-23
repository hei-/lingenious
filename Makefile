# Everything runs in Docker (CadQuery is only in the images).
# Optional build mirrors: APT_MIRROR=<host> PIP_INDEX_URL=<url> make ...
DOCKER := docker
MIRROR_ARGS := $(if $(APT_MIRROR),--build-arg APT_MIRROR=$(APT_MIRROR)) $(if $(PIP_INDEX_URL),--build-arg PIP_INDEX_URL=$(PIP_INDEX_URL))
DEV_IMAGE := lingenious:dev
LANDING_PORT ?= 8080
PLATFORMS ?= linux/amd64,linux/arm64

.DEFAULT_GOAL := help
.PHONY: help web-multiarch setup test cov lint fmt ui-install ui-check ui-build web docker-dev eval-dfm landing-serve lock

help: ## Show this help
	@awk -F':.*## ' '/^[a-zA-Z_-]+:.*## /{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

setup: docker-dev ## Build the dev image and create .env if missing
	@[ -f .env ] || { cp .env.example .env && echo "created .env: fill in DEEPSEEK_API_KEY"; }

docker-dev: ## Build the dev image (lingenious:dev: runtime + pytest/ruff)
	$(DOCKER) build --target dev $(MIRROR_ARGS) -t $(DEV_IMAGE) .

test: docker-dev ## Run pytest in the dev image
	$(DOCKER) run --rm $(DEV_IMAGE) pytest

cov: docker-dev ## pytest with coverage (terminal summary); coverage.xml copied to ./coverage.xml
	-$(DOCKER) rm -f lingenious-cov >/dev/null 2>&1
	$(DOCKER) run --name lingenious-cov $(DEV_IMAGE) pytest --cov --cov-report=term --cov-report=xml; rc=$$?; \
	$(DOCKER) cp lingenious-cov:/app/coverage.xml coverage.xml; $(DOCKER) rm lingenious-cov >/dev/null; exit $$rc

lint: docker-dev ## ruff check + mypy in the dev image
	$(DOCKER) run --rm $(DEV_IMAGE) sh -c 'ruff check . && mypy'

fmt: ## ruff autofix, safe fixes only (runs locally via uvx; no CadQuery needed)
	uvx ruff check --fix .

ui-install: ## npm ci for web/ui (needs local node 22)
	cd web/ui && npm ci

ui-check: ## Typecheck, eslint and unit-test web/ui
	cd web/ui && npx tsc --noEmit && npm run lint && npx vitest run

ui-build: ## Build web/ui into web/ui/dist
	cd web/ui && npm run build

web: ## Build and start the web app at http://localhost:8000
	$(DOCKER) compose up --build

web-multiarch: ## buildx the web image for linux/amd64+arm64 (no push; PUSH=1 TAG=.. to push; see docs)
	$(DOCKER) buildx build --platform $(PLATFORMS) -f web/Dockerfile $(MIRROR_ARGS) \
	  $(if $(filter 1,$(PUSH)),--push -t $(TAG),--output type=cacheonly) .

eval-dfm: docker-dev ## Run the DFM eval set (calls the LLM; needs .env); results copied to eval/results_dfm
	-$(DOCKER) rm -f lingenious-eval-dfm >/dev/null 2>&1
	$(DOCKER) run --name lingenious-eval-dfm --env-file .env $(DEV_IMAGE) python -m eval.runner --taskset dfm --configs A B C --repeat 3 --workers 5
	$(DOCKER) cp lingenious-eval-dfm:/app/eval/results_dfm/. eval/results_dfm/
	$(DOCKER) rm lingenious-eval-dfm

landing-serve: ## Serve web/landing at http://localhost:$(LANDING_PORT)
	cd web/landing && python3 -m http.server $(LANDING_PORT)

lock: ## Regenerate requirements*.lock from pyproject.toml (needs uv)
	uv pip compile pyproject.toml --universal --python-version 3.12 --generate-hashes -o requirements.lock
	uv pip compile pyproject.toml --extra dev -c requirements.lock --universal --python-version 3.12 --generate-hashes -o requirements-dev.lock

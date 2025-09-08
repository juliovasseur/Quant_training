SHELL := /bin/bash

# === Couleurs (pour une sortie plus lisible) ===
RESET := \033[0m
BOLD  := \033[1m
GREEN := \033[32m
BLUE  := \033[34m
YELL  := \033[33m
RED   := \033[31m

# === Réglages simples (modifiable à la volée : make run-lite INPUT=examples/csv) ===
PY      ?= python3
VENV    ?= .venv
PYTHON  := $(VENV)/bin/python
PIP     := $(VENV)/bin/pip
ENTRY   ?= src/lpsolve/cli.py     # ton script principal (mode Lite)
FORMAT  ?= csv                    # csv | txt
OUT     ?= out                    # dossier de sortie
INPUT   ?=                        # chemin d'entrée (fichier ou dossier); vide => mode interactif

.PHONY: help usage install venv run-lite gen-examples clean

help: usage
	@printf "$(BOLD)Cibles utiles :$(RESET)\n"
	@printf "  $(GREEN)make install$(RESET)       : créer la venv (virtual environment) et installer les deps\n"
	@printf "  $(GREEN)make run-lite$(RESET)      : exécuter le solveur en mode Lite\n"
	@printf "  $(GREEN)make clean$(RESET)         : nettoyer les artefacts\n"

usage:
	@printf "$(BOLD)USAGE (CLI — Command-Line Interface) :$(RESET)\n"
	@printf "  $(BLUE)make run-lite INPUT=examples/csv$(RESET)\n"
	@printf "  $(BLUE)make run-lite INPUT=examples/txt"
	@printf "Sans INPUT, le programme passe en mode interactif (tu tapes objectif/contraintes).\n"

# === Setup minimal ===
venv:
	@printf "$(YELL)>> Création venv (virtual environment) dans $(VENV)$(RESET)\n"
	@$(PY) -m venv $(VENV) && printf "$(GREEN)OK$(RESET)\n"

install: venv
	@printf "$(YELL)>> Installation dépendances (PuLP — Python Linear Programming library)$(RESET)\n"
	@if [ -f requirements.txt ]; then \
	  $(PIP) install -r requirements.txt; \
	else \
	  $(PIP) install --upgrade pip >/dev/null; \
	  $(PIP) install pulp click >/dev/null; \
	fi
	@printf "$(GREEN)OK$(RESET)\n"

# === Exécution (mode Lite uniquement) ===
# run-lite: install
# 	@mkdir -p "$(OUT)"
# 	@printf "$(YELL)>> Run (mode=lite format=$(FORMAT) out=$(OUT))$(RESET)\n"
# 	@if [ -n "$(INPUT)" ]; then \
# 	  printf "Input: $(INPUT)\n"; \
# 	  "$(PYTHON)" "$(ENTRY)" --mode lite --format "$(FORMAT)" --out "$(OUT)" "$(INPUT)"; \
# 	else \
# 	  printf "Pas d'INPUT -> mode interactif\n"; \
# 	  "$(PYTHON)" "$(ENTRY)" --mode lite --format "$(FORMAT)" --out "$(OUT)"; \
# 	fi

run:
	@python3 src/lpSolver/lite.py ./data

# === Nettoyage léger ===
clean:
	@printf "$(YELL)>> Nettoyage$(RESET)\n"
	@rm -rf __pycache__ .pytest_cache "$(OUT)"
	@printf "$(GREEN)OK$(RESET)\n"

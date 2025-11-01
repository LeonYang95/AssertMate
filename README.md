# AssertMate

AssertMate is This is an implementation of *Agent-Based Test Assertion Generation via Diverse
Perspective Aggregation* and integration with test-generation tools (EvoSuite and others).

## Highlights
- UTGen_LLM: LLM-based unit test generation pipeline to generate unit tests for public Java methods. Dataset and experimental inputs were constructed from Defects4J.
- DiffOracle: Differential prompting approach for creating LLM-based test oracles.
- Integration tooling and scripts for EvoSuite execution, test running, and data collection.

## Repository layout
Top-level folders and a short description of each:

- `as-gen-integration/` — Integration code for assertion generation and related configuration.
- `DiffOracle/` — Differential prompting and prompt-engineering components for test oracle generation.
- `UTGen_LLM/` — LLM-based unit test generation project with its own README.
- `data/` — Datasets and inputs used by experiments.
- `model/` — Model wrappers, agents and LLM-related utilities.

## Quick start
1. Install Python 3.10 (recommended) and create a virtual environment.
2. Install dependencies:

  pip install -r requirements.txt

## Configuration
- Global or component-specific configuration is stored under each component's `config/` directory and/or `config.py` files. Always copy example configs where indicated and adjust absolute/relative paths before running.

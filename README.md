# agent-playground

Small sample agents built with different agent frameworks, for learning and
trying things out. Each sample is deliberately minimal: one agent, one clear
job, a few hundred lines you can read in one sitting.

| Framework | Sample | What it teaches |
|---|---|---|
| [Google ADK](adk/) | `customer_support_agent` | Agent + instruction + one tool, guardrails in callbacks, basic data leak protection, tests without a model |


## Layout

```
agent-playground/
  README.md            this file
  adk/                 Google ADK samples (one folder per agent)
  <framework>/         one folder per framework, each with its own README,
                       requirements.txt and tests
```

Each framework folder is self-contained: its own virtual environment,
dependencies and run instructions. Nothing is shared between folders on
purpose, so you can read one without knowing the others.

## Ground rules for every sample

- **Secrets never enter the repo.** Keys live in a git-ignored `.env`; each
  sample ships an `.env.example` with placeholders.
- **Rules that must hold go in code, not only in the prompt.** A prompt is a
  suggestion to the model; a callback or a check is a guarantee.
- **Tests run without a model.** A scripted fake stands in for the LLM, so
  `pytest` is fast, free and deterministic.

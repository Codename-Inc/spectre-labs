# SPECTRE Labs

Experimental and power-user features for the [SPECTRE](https://github.com/Codename-Inc/spectre) workflow framework.

## What's Here

### Build Loop

Automated task execution CLI that runs Claude Code in a loop, completing one task per iteration.

```bash
cd build-loop
pipx install -e .
spectre-build --tasks tasks.md --max-iterations 10
```

### Sparks

Knowledge capture plugin for Claude Code. Capture learnings from conversations and automatically recall them when relevant.

```bash
# Add marketplace and install plugin
/plugin marketplace add Codename-Inc/spectre-labs/sparks
/plugin install sparks@spectre-labs
```

## Why Separate?

These features are:
- **Experimental** — APIs may change
- **Power-user oriented** — Require more setup
- **Not core to SPECTRE** — You can use SPECTRE workflow without them

The main [SPECTRE](https://github.com/Codename-Inc/spectre) repo contains the stable workflow framework.

## License

MIT

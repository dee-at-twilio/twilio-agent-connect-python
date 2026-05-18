# TAC Documentation

This directory contains the source for the TAC documentation site.

## Local Development

### Prerequisites

Install dependencies:

```bash
pip install -r docs-requirements.txt
```

Or use the project's uv environment:

```bash
uv pip install mkdocs-material 'mkdocstrings[python]' pymdown-extensions
```

### Build and Serve

Build the docs:

```bash
mkdocs build
```

Serve locally with hot reload:

```bash
mkdocs serve
```

Visit `http://127.0.0.1:8000` to view the docs.

### Project Structure

```
docs/
├── index.md              # Homepage
├── getting-started/      # Installation and setup guides
├── guides/              # In-depth guides
├── examples/            # Code examples
├── api/                 # API reference
└── contributing.md      # Contributing guide
```

### Adding New Pages

1. Create a new `.md` file in the appropriate directory
2. Add it to `nav` in `mkdocs.yml`
3. Build and verify

## Deployment

### GitHub Actions (Automated)

Docs are automatically deployed to GitHub Pages when changes are pushed to `main` via the `.github/workflows/docs.yml` workflow.

You can also trigger manually:
1. Go to: https://github.com/twilio/twilio-agent-connect-python/actions/workflows/docs.yml
2. Click "Run workflow" → Select `main` branch → "Run workflow"

### Enable GitHub Pages (One-time Setup)

1. Go to: https://github.com/twilio/twilio-agent-connect-python/settings/pages
2. **Source**: Deploy from a branch
3. **Branch**: `gh-pages` → `/ (root)`
4. Click **Save**
5. Wait 1-2 minutes for deployment

**Live URL**: https://twilio.github.io/twilio-agent-connect-python/

## Contributing

See [CONTRIBUTING.md](../CONTRIBUTING.md) for contribution guidelines.

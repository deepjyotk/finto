# Finto Chat

AI-powered chat application with FastAPI backend and Gradio UI.

## 🚀 Quick Start

### Setup the project
```bash
make setup
```

This will:
- Create a virtual environment (`.venv`)
- Install all dependencies using `uv`
- Works on both Mac and Windows

### Run the application

**Terminal 1 - Run the FastAPI backend:**
```bash
make run-apis
```
Backend will be available at: http://localhost:8000

**Terminal 2 - Run the Gradio UI:**
```bash
make run-ui
```
UI will be available at: http://localhost:7860

## 📋 Available Commands

- `make setup` - Setup the project (create .venv and install dependencies)
- `make run-apis` - Run the FastAPI backend server
- `make run-ui` - Run the Gradio UI server
- `make help` - Show available commands

## 🏗️ Project Structure

```
finto/
├── src/
│   ├── api/
│   │   └── chat.py       # FastAPI chat endpoint
│   └── ui/
│       └── chat_app.py   # Gradio chat interface
├── Makefile              # Build automation
└── pyproject.toml        # Project dependencies
```


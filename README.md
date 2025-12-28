# Finto Chat

AI-powered chat application with FastAPI backend and Gradio UI.

## 🚀 Quick Start

### 1. Setup the project
```bash
make setup
```

This will:
- Create a virtual environment (`.venv`)
- Install all dependencies using `uv`
- Works on both Mac and Windows

### 2. Configure environment variables

Copy the example environment file and update with your credentials:

```bash
cp .env.example .env
```

Then edit `.env` and set:
- `DATABASE_URL`: Your PostgreSQL connection string (from Supabase Dashboard → Settings → Database → Connection string)
  - Format: `postgresql+asyncpg://postgres:<PASSWORD>@<HOST>:5432/postgres`
  - Example: `postgresql+asyncpg://postgres:yourpassword@db.xxxxx.supabase.co:5432/postgres`
- `SECRET_KEY`: A secure random string for JWT tokens

To generate a secure `SECRET_KEY`:
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Note**: The app now uses direct PostgreSQL connection via SQLAlchemy instead of the Supabase client.

### 3. Run database migrations

Apply database schema using Alembic:

```bash
alembic upgrade head
```

This will create/update all database tables based on your SQLAlchemy models.

### 4. Run the application

**Terminal 1 - Run the FastAPI backend:**
```bash
make run-apis
```
Backend will be available at: http://localhost:8000

## 📋 Available Commands

- `make setup` - Setup the project (create .venv and install dependencies)
- `make run-apis` - Run the FastAPI backend server
- `make run-ui` - Run the Gradio UI server
- `make lint` - Run code linting and formatting
- `make clean` - Clean .venv and uv cache
- `make help` - Show available commands

### Database Migrations (Alembic)

- `alembic revision -m "message" --autogenerate` - Generate new migration
- `alembic upgrade head` - Apply all pending migrations
- `alembic downgrade -1` - Rollback last migration
- `alembic current` - Show current migration version
- `alembic history` - Show migration history

## 🏗️ Project Structure

The project follows a clean architecture pattern: **API → Service → Repository → Database**

```
finto/
├── src/
│   ├── api/              # FastAPI endpoints
│   ├── core/             # Settings, DB, middleware
│   ├── models/           # SQLAlchemy models
│   │   ├── base.py       # Declarative base
│   │   └── user.py       # User model
│   ├── migrations/       # Alembic migrations
│   │   ├── env.py        # Alembic environment
│   │   ├── versions/     # Migration versions
│   │   └── script.py.mako
│   ├── repositories/     # Data access layer
│   ├── services/         # Business logic
│   ├── schemas/          # Pydantic schemas
│   └── main.py           # FastAPI app
├── alembic.ini           # Alembic config
├── Makefile              # Build automation
├── pyproject.toml        # Dependencies
└── .env.example          # Environment template
```

### Architecture Layers

1. **API Layer** (`src/api/`): FastAPI endpoints, depends only on services
2. **Service Layer** (`src/services/`): Business logic, pure classes (no FastAPI)
3. **Repository Layer** (`src/repositories/`): Data access, pure classes (no FastAPI)
4. **Database Layer** (`src/core/db.py`): SQLAlchemy session management
5. **Dependency Injection** (`src/deps/`): Wires together Session → Repo → Service

## 🗄️ Database Migrations

This project uses **Alembic** for database schema management with **SQLAlchemy** models.

### Quick Migration Workflow

1. **Modify/Add a model** in `src/models/`
2. **Generate migration**: `alembic revision -m "add table_name" --autogenerate`
3. **Review** the generated file in `src/migrations/versions/`
4. **Apply**: `alembic upgrade head`

### Adding a New Table

**Example**: Add a `posts` table

1. **Create model** in `src/models/post.py`:
```python
from sqlalchemy import Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from src.models.base import Base

class Post(Base):
    __tablename__ = "posts"
    
    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("f_users.user_id"))
```

2. **Import model** in `src/migrations/env.py`:
```python
from src.models.post import Post  # noqa: F401
```

3. **Generate migration**:
```bash
alembic revision -m "add posts table" --autogenerate
```

4. **Review & apply**:
```bash
# Review: src/migrations/versions/xxxx_add_posts_table.py
alembic upgrade head
```

### Database Schema

**Current Tables:**

#### `f_users`
- `user_id` (UUID, PK)
- `username` (TEXT, unique)
- `email` (TEXT, unique)
- `full_name` (TEXT)
- `password_hash` (TEXT)
- `created_at` (TIMESTAMPTZ)
- `updated_at` (TIMESTAMPTZ)

## 🔒 Authentication

The application uses JWT-based authentication with HTTP-only cookies:

- **Register**: `POST /auth/register` - Create new user account
- **Login**: `POST /auth/login` - Authenticate and receive JWT token
- **Logout**: `POST /auth/logout` - Clear authentication cookie
- **Current User**: `GET /auth/me` - Get authenticated user info

## 🧪 API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

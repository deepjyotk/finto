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

### 3. Initialize the database

Run the database initialization script:

```bash
make init-db
```

This will:
- Display the SQL migration scripts
- Provide instructions to run them in your Supabase Dashboard
- Verify that tables were created successfully

**Note**: Due to Supabase client limitations, you'll need to manually copy the SQL to your Supabase Dashboard's SQL Editor and execute it.

### 4. Run the application

**Terminal 1 - Run the FastAPI backend:**
```bash
make run-apis
```
Backend will be available at: http://localhost:8000

## 📋 Available Commands

- `make setup` - Setup the project (create .venv and install dependencies)
- `make init-db` - Initialize the database (create tables)
- `make run-apis` - Run the FastAPI backend server
- `make run-ui` - Run the Gradio UI server
- `make lint` - Run code linting and formatting
- `make clean` - Clean .venv and uv cache
- `make help` - Show available commands

## 🏗️ Project Structure

The project follows a clean architecture pattern: **API → Service → Repository → Database**

```
finto/
├── src/
│   ├── api/
│   │   ├── auth.py           # Authentication endpoints (API layer)
│   │   └── chat.py           # Chat endpoints
│   ├── core/
│   │   ├── settings.py       # Application settings (pydantic-settings)
│   │   ├── db.py             # Database session management (SQLAlchemy)
│   │   └── middleware.py     # Auth middleware
│   ├── models/
│   │   └── user.py           # SQLAlchemy User model
│   ├── repositories/
│   │   └── user_repo.py      # User repository (data access layer)
│   ├── services/
│   │   └── auth_service.py   # Auth service (business logic layer)
│   ├── deps/
│   │   └── providers.py      # Dependency injection wiring
│   ├── schemas/
│   │   └── auth.py           # Pydantic schemas
│   ├── ui/
│   │   └── chat_app.py       # Gradio chat interface
│   └── main.py               # FastAPI application
├── scripts/
│   └── migrations/
│       └── 001_create_f_users_table.sql  # Database schema
├── init_db.py                # Database initialization script
├── Makefile                  # Build automation
├── pyproject.toml            # Project dependencies
└── .env.example              # Example environment variables
```

### Architecture Layers

1. **API Layer** (`src/api/`): FastAPI endpoints, depends only on services
2. **Service Layer** (`src/services/`): Business logic, pure classes (no FastAPI)
3. **Repository Layer** (`src/repositories/`): Data access, pure classes (no FastAPI)
4. **Database Layer** (`src/core/db.py`): SQLAlchemy session management
5. **Dependency Injection** (`src/deps/`): Wires together Session → Repo → Service

## 🗄️ Database Schema

### `f_users` Table

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | UUID | Primary key |
| `username` | TEXT | Unique username |
| `email` | TEXT | Unique email address |
| `full_name` | TEXT | User's full name |
| `password_hash` | TEXT | Bcrypt hashed password |
| `created_at` | TIMESTAMPTZ | Account creation timestamp |
| `updated_at` | TIMESTAMPTZ | Last update timestamp |

## 🔒 Authentication

The application uses JWT-based authentication with HTTP-only cookies:

- **Register**: `POST /auth/register` - Create new user account
- **Login**: `POST /auth/login` - Authenticate and receive JWT token
- **Logout**: `POST /auth/logout` - Clear authentication cookie
- **Current User**: `GET /auth/me` - Get authenticated user info
- **Verify**: `GET /auth/verify` - Check authentication status

## 🧪 API Documentation

Once the backend is running, visit:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

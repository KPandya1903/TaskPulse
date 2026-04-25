# TaskPulse - Distributed Task Orchestrator

TaskPulse is a distributed task orchestration system built with Python, FastAPI, PostgreSQL, and Redis. It provides a robust platform for scheduling, executing, and monitoring tasks across multiple workers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│                         (Web UI, CLI, API)                                  │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ HTTPS/REST
┌─────────────────────────────────────────────────────────────────────────────┐
│                           FASTAPI APPLICATION                                │
│                                                                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │   Auth API      │  │   Tasks API     │  │     Health API              │  │
│  │  /api/v1/auth   │  │  /api/v1/tasks  │  │     /health                 │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │                      │                           │
          ▼                      ▼                           ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────┐
│   PostgreSQL     │    │      Redis       │    │    Task Workers (N)      │
│  (Primary DB)    │    │   (Task Queue)   │◄───│  (Async Processing)      │
└──────────────────┘    └──────────────────┘    └──────────────────────────┘
```

### Components

- **FastAPI Application**: REST API for authentication and task management
- **PostgreSQL**: Primary database for users, tasks, and tokens
- **Redis**: Task queue using sorted sets for priority-based processing
- **Task Workers**: Distributed workers that process tasks from the queue

### Task Lifecycle

```
PENDING → RUNNING → COMPLETED
                 ↘ FAILED
```

1. **PENDING**: Task created and queued in Redis
2. **RUNNING**: Worker picked up task, execution in progress
3. **COMPLETED**: Task finished successfully
4. **FAILED**: Task execution failed

## Features

- **JWT Authentication**: Secure access with access/refresh token rotation
- **Priority Queue**: Tasks processed by priority (1=highest, 5=lowest)
- **Horizontal Scaling**: Multiple workers for parallel processing
- **RESTful API**: Full CRUD operations with pagination
- **High Test Coverage**: 80%+ coverage target with pytest

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.11+ (for local development)

### Running with Docker

```bash
# Clone the repository
git clone <repository-url>
cd TaskPulse

# Copy environment file
cp .env.example .env

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

The API will be available at `http://localhost:8000`.

### Local Development

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements-dev.txt

# Start PostgreSQL and Redis (via Docker)
docker-compose up -d postgres redis

# Set environment variables
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/taskpulse
export REDIS_URL=redis://localhost:6379/0
export TESTING=1  # For SQLite in tests

# Run migrations
alembic upgrade head

# Start the API server
uvicorn app.main:app --reload

# Start a worker (in another terminal)
python -m app.services.worker
```

## API Documentation

Once running, access the interactive API docs:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Authentication Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register new user |
| POST | `/api/v1/auth/login` | Login (returns JWT) |
| POST | `/api/v1/auth/refresh` | Refresh access token |
| GET | `/api/v1/auth/me` | Get current user |

### Task Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/tasks/` | Create new task |
| GET | `/api/v1/tasks/` | List user's tasks |
| GET | `/api/v1/tasks/{id}` | Get task details |
| PATCH | `/api/v1/tasks/{id}` | Update task |
| DELETE | `/api/v1/tasks/{id}` | Delete/cancel task |

### Example Usage

```bash
# Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "securepass123"}'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -d "username=user@example.com&password=securepass123"

# Create a task (use the access_token from login response)
curl -X POST http://localhost:8000/api/v1/tasks/ \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d '{"title": "Process Data", "description": "Heavy computation", "priority": 1}'

# Check task status
curl http://localhost:8000/api/v1/tasks/<task_id> \
  -H "Authorization: Bearer <access_token>"
```

## Testing

### Run All Tests

```bash
# Set testing environment
export TESTING=1

# Run tests with coverage
pytest --cov=app --cov-report=html --cov-report=term-missing

# Run specific test file
pytest tests/test_auth.py -v

# Run with parallel execution
pytest -n auto
```

### Test Structure

```
tests/
├── conftest.py       # Shared fixtures (DB, client, users)
├── test_auth.py      # Authentication tests (27 tests)
├── test_tasks.py     # Task CRUD tests (20+ tests)
└── test_workers.py   # Worker processing tests
```

### Testing Strategy

1. **Unit Tests**: Individual functions and methods
2. **Integration Tests**: API endpoints with mocked Redis
3. **Lifecycle Tests**: Full task flow (PENDING → COMPLETED)

Redis is mocked in tests to ensure:
- Isolated test execution
- No external dependencies
- Fast test runs

## Project Structure

```
TaskPulse/
├── app/
│   ├── api/
│   │   ├── deps.py           # Dependencies (auth, db)
│   │   └── v1/
│   │       ├── auth.py       # Auth endpoints
│   │       ├── tasks.py      # Task endpoints
│   │       └── router.py     # Router aggregation
│   ├── core/
│   │   ├── config.py         # Settings
│   │   ├── security.py       # JWT, password hashing
│   │   └── redis.py          # Redis client utilities
│   ├── db/
│   │   ├── base.py           # SQLAlchemy base
│   │   └── session.py        # Session management
│   ├── models/
│   │   ├── user.py           # User model
│   │   ├── task.py           # Task model
│   │   └── refresh_token.py  # RefreshToken model
│   ├── schemas/
│   │   ├── user.py           # User schemas
│   │   ├── task.py           # Task schemas
│   │   └── token.py          # Token schemas
│   ├── services/
│   │   └── worker.py         # Task worker service
│   └── main.py               # FastAPI application
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_tasks.py
│   └── test_workers.py
├── alembic/                   # Database migrations
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

## Configuration

Environment variables (see `.env.example`):

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://...` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `SECRET_KEY` | JWT signing key | (change in production!) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access token TTL | `30` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh token TTL | `7` |
| `DEBUG` | Enable debug mode | `false` |

## Scaling Workers

Increase worker replicas for higher throughput:

```yaml
# docker-compose.yml
worker:
  deploy:
    replicas: 4  # Run 4 workers
```

Or run multiple worker processes:

```bash
# Terminal 1
python -m app.services.worker

# Terminal 2
python -m app.services.worker
```

## License

MIT

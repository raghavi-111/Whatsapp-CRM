# WhatsApp CRM

Phase 1 is a minimal project foundation for a future WhatsApp CRM. It includes a React frontend, a Django REST Framework backend, PostgreSQL, Redis, and Docker Compose for local development.

## Architecture

- `frontend/`: React app built with Vite, React Router, and Axios.
- `backend/`: Django project using Django REST Framework and `django-cors-headers`.
- `postgres`: PostgreSQL database service managed by Docker Compose.
- `redis`: Redis service managed by Docker Compose for Channels and Celery.
- `docker-compose.yml`: Runs PostgreSQL, Redis, Django, Celery, and Vite together on one development network.

The frontend calls the backend health endpoint at `GET /api/health/` and displays the backend connection status on the Home page.

Phase 2 adds JWT authentication with email and password:

- `POST /api/auth/register/`
- `POST /api/auth/login/`
- `POST /api/auth/token/refresh/`
- `GET /api/auth/me/`
- `POST /api/auth/logout/`

Phase 3 adds organizations and team roles:

- `GET /api/organizations/`
- `POST /api/organizations/`
- `GET /api/organizations/current/`
- `PATCH /api/organizations/current/`
- `GET /api/organizations/members/`

Phase 4 adds organization-scoped contacts:

- `GET /api/contacts/`
- `POST /api/contacts/`
- `GET /api/contacts/<id>/`
- `PATCH /api/contacts/<id>/`
- `DELETE /api/contacts/<id>/`

Phase 5 adds the local CRM inbox foundation:

- `GET /api/conversations/`
- `POST /api/conversations/`
- `GET /api/conversations/<id>/`
- `PATCH /api/conversations/<id>/`
- `GET /api/conversations/<id>/messages/`
- `POST /api/conversations/<id>/messages/`

Phase 6 adds organization-scoped WhatsApp Business configuration:

- `GET /api/whatsapp/config/`
- `POST /api/whatsapp/config/`
- `PATCH /api/whatsapp/config/`

Phase 7 adds Meta WhatsApp webhook verification and inbound text handling:

- `GET /api/whatsapp/webhook/`
- `POST /api/whatsapp/webhook/`

Phase 8 sends outbound WhatsApp text messages from the Inbox through the existing messages API. Local development defaults to `WHATSAPP_SEND_MODE=mock`; set `WHATSAPP_SEND_MODE=real` and configure valid Meta credentials to call the Graph API.

Phase 9 handles WhatsApp delivery status webhooks. Meta status events update existing outbound messages by `external_message_id` with `sent`, `delivered`, `read`, or `failed`.

Phase 10 adds local WhatsApp message template management. Templates are stored per organization and are not sent to Meta yet.

- `GET /api/templates/`
- `POST /api/templates/`
- `GET /api/templates/<id>/`
- `PATCH /api/templates/<id>/`
- `DELETE /api/templates/<id>/`

Phase 11 sends approved WhatsApp templates through Meta Cloud API or mock mode.

- `POST /api/templates/<id>/send/`

Phase 12 adds tags, contact notes, conversation notes, assignment, and focused status endpoints.

- `GET /api/tags/`
- `POST /api/tags/`
- `PATCH /api/tags/<id>/`
- `DELETE /api/tags/<id>/`
- `GET /api/contacts/<id>/notes/`
- `POST /api/contacts/<id>/notes/`
- `PATCH /api/contacts/<id>/tags/`
- `GET /api/conversations/<id>/notes/`
- `POST /api/conversations/<id>/notes/`
- `PATCH /api/conversations/<id>/assign/`
- `PATCH /api/conversations/<id>/status/`

## Environment Setup

Create the root environment file used by Docker Compose:

```bash
cp .env.example .env
```

Update the values in `.env` for your machine. Do not commit `.env`.

The root `.env` is Compose-oriented. Docker backend containers keep using service hostnames:

```env
DB_HOST=postgres
REDIS_URL=redis://redis:6379/0
```

For local Windows backend and frontend processes, use the local override examples below.

## Docker Development

Start all services:

```bash
docker compose up -d --build
```

Open:

- Frontend: http://localhost:5173
- Backend health check: http://localhost:8000/api/health/
- Uploaded local media: http://localhost:8000/media/ in development

Run Django migrations inside Docker:

```bash
docker compose exec backend python manage.py migrate
```

PostgreSQL is published to `localhost:${POSTGRES_PORT:-5432}` and Redis is published to `localhost:${REDIS_PORT:-6379}` for host-based tools. Docker services still connect to `postgres:5432` and `redis:6379` on the Compose network.

## Local Windows Development With Docker PostgreSQL And Redis

Start only PostgreSQL and Redis in Docker:

```bash
docker compose up -d postgres redis
```

Create local override files:

```powershell
Copy-Item backend\.env.local.example backend\.env.local
Copy-Item frontend\.env.local.example frontend\.env.local
```

The backend local override points Django at the Docker-published host ports:

```env
DB_HOST=localhost
DB_PORT=5432
REDIS_URL=redis://localhost:6379/0
```

If you changed `POSTGRES_PORT` or `REDIS_PORT` in `.env`, update `backend/.env.local` to match those published Windows host ports.

Backend:

```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

For local Vite, `frontend/.env.local` sets `VITE_API_BASE_URL=http://localhost:8000/api` and `VITE_WS_BASE_URL=ws://localhost:8000/ws`.

The default development CORS and CSRF trusted origins include:

- `http://localhost:5173`
- `http://localhost:8000`

After Phase 2, migrations create the custom email-based user table and SimpleJWT token blacklist tables.
After Phase 3, migrations create organization and organization member tables.
After Phase 4, migrations create the contacts table with phone numbers unique per organization.
After Phase 5, migrations create conversation and message tables for local CRM inbox data.
After Phase 6, migrations create secure WhatsApp Business configuration storage. API responses return masked secret values only.
Phase 7 does not add migrations. Webhook POST is public for Meta, but CRM APIs remain JWT protected.
Phase 8 does not add migrations. Outbound sends create `sent` or `failed` messages and never expose WhatsApp access tokens in API responses.
Phase 9 does not add migrations. Repeated status events update the same message safely.
After Phase 10, migrations create the local message templates table.
Phase 11 does not add migrations. Approved template sends create outbound template messages with `sent` or `failed` status.
After Phase 12, migrations create tags, contact notes, conversation notes, and contact tag assignments.
After Phase 16, migrations add message media fields. Uploaded files are stored in the Docker `media_data` volume mounted at `/app/media`.

Phase 13 adds realtime Inbox updates with Django Channels and Redis.

- WebSocket URL: `ws://localhost:8000/ws/inbox/?token=<access_token>`
- Redis is used as the Channels backing store.
- Inbox listens for safe organization-scoped events and refreshes conversation/message data.

Phase 14 adds organization-scoped automation rules and logs.

- `GET /api/automations/`
- `POST /api/automations/`
- `GET /api/automations/<id>/`
- `PATCH /api/automations/<id>/`
- `DELETE /api/automations/<id>/`
- `GET /api/automations/logs/`

Phase 15 moves automation execution to Celery background tasks using Redis as the broker. The `celery_worker` service runs `automations.run_automation_task`; if Celery is unavailable during development, automation enqueue falls back to synchronous execution.

Phase 16 adds local media upload and WhatsApp media message support for images, documents, audio, and video.

- `POST /api/conversations/<id>/messages/media/`
- Multipart fields: `file`, `message_type`, optional `caption`
- Local maximum upload size: 16MB
- In `WHATSAPP_SEND_MODE=mock`, files are saved under Django `MEDIA_ROOT` and fake WhatsApp IDs are generated.
- In `WHATSAPP_SEND_MODE=real`, the backend uploads media to Meta Cloud API, then sends the media message by Meta media ID.
- Inbound media webhooks store Meta media ID, MIME type, filename, and caption without downloading provider media.

Phase 17 adds organization-scoped analytics APIs and dashboard/report UI.

- `GET /api/analytics/summary/`
- `GET /api/analytics/messages/`
- `GET /api/analytics/conversations/`
- `GET /api/analytics/agents/`
- `GET /api/analytics/automations/`

## Local WhatsApp Status Webhook Example

Replace `mock-wamid-example` with an existing outbound message `external_message_id`.

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "changes": [
        {
          "field": "messages",
          "value": {
            "metadata": {
              "phone_number_id": "123456789"
            },
            "statuses": [
              {
                "id": "mock-wamid-example",
                "recipient_id": "15551234567",
                "status": "delivered",
                "timestamp": "1735689700"
              }
            ]
          }
        }
      ]
    }
  ]
}
```

Create a Django superuser if needed:

```bash
docker compose exec backend python manage.py createsuperuser
```

## Testing

Run backend checks and tests locally:

```bash
cd backend
python manage.py check
python manage.py test
```

The test runner defaults to SQLite by setting `USE_SQLITE_FOR_TESTS=true` internally unless you override it. This keeps local tests independent from the Docker PostgreSQL hostname.

Run frontend build verification:

```bash
cd frontend
npm install
npm run build
```

Run verification inside Docker:

```bash
docker compose run --rm backend python manage.py migrate --noinput
docker compose run --rm backend python manage.py check
docker compose build
```

## Production Deployment

Copy the production environment template and fill in real values:

```bash
cp .env.production.example .env.production
```

Production build and startup:

```bash
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d
docker compose -f docker-compose.prod.yml run --rm backend python manage.py migrate --noinput
docker compose -f docker-compose.prod.yml run --rm backend python manage.py createsuperuser
```

Production services:

- `nginx`: public entrypoint on port 80, routes frontend, API, websocket, and media.
- `frontend`: built Vite static assets served by nginx.
- `backend`: Daphne ASGI server for HTTP and WebSockets.
- `celery_worker`: background automation jobs.
- `postgres`: database.
- `redis`: Channels and Celery broker.

Production checklist:

- Set a strong `DJANGO_SECRET_KEY`.
- Set `DJANGO_DEBUG=False`.
- Set `DJANGO_ALLOWED_HOSTS` to your real hostnames.
- Set `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` to your real HTTPS origin.
- Use strong PostgreSQL credentials.
- Use `WHATSAPP_SEND_MODE=real` only after Meta credentials are configured.
- Put TLS in front of nginx or terminate HTTPS at your platform/load balancer.
- Keep `.env.production` out of source control.
- Back up PostgreSQL before upgrades.

## Health And Operations

Health checks:

```bash
curl http://localhost/api/health/
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs --tail=100 backend
docker compose -f docker-compose.prod.yml logs --tail=100 celery_worker
docker compose -f docker-compose.prod.yml logs --tail=100 nginx
```

Development health checks:

```bash
curl http://localhost:8000/api/health/
docker compose ps
docker compose logs --tail=100 backend
docker compose logs --tail=100 celery_worker
```

PostgreSQL backup:

```bash
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > backup.sql
```

PostgreSQL restore:

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U "$POSTGRES_USER" "$POSTGRES_DB" < backup.sql
```

Named volume backup, useful before moving hosts:

```bash
docker run --rm -v whatsapp_crm_postgres_data:/data -v "%cd%":/backup alpine tar czf /backup/postgres_data.tar.gz /data
docker run --rm -v whatsapp_crm_media_data:/data -v "%cd%":/backup alpine tar czf /backup/media_data.tar.gz /data
```

Common troubleshooting:

- Backend cannot start: check `.env.production`, database health, and `docker compose -f docker-compose.prod.yml logs backend`.
- WebSockets do not connect: verify `/ws/` is routed through nginx and `VITE_WS_BASE_URL=/ws`.
- Media does not load: verify `media_data` is mounted and nginx has the `/media/` alias.
- Automations do not run: check Redis health and `celery_worker` logs.
- Meta sends fail: check WhatsApp config, `WHATSAPP_SEND_MODE`, and Meta Graph API permissions.

## Stopping Containers

Stop containers without deleting PostgreSQL data:

```bash
docker compose down
```

This keeps the named `postgres_data` volume.

## Deleting Development Volumes

To intentionally delete containers and development database data:

```bash
docker compose down -v
```

Use this only when you want to remove the PostgreSQL volume and reset local database state.

## Phase 1 Scope

This phase does not include authentication, contacts, inboxes, messages, WhatsApp integration, WebSockets, Redis, Celery, automations, business modules, or custom database models.

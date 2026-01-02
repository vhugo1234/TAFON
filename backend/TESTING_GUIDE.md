# Testing Guide for Startup Shims and Docker Fixes

This guide provides step-by-step instructions for testing the changes made in this PR.

## Prerequisites

- Docker and Docker Compose installed
- curl or similar HTTP client
- (Optional) PostgreSQL client for database inspection

## 1. Build and Start the Backend

```bash
# From the repository root
docker compose up --build backend
```

**Expected Result:**
- Container builds successfully
- No ImportError or ModuleNotFoundError in logs
- Uvicorn starts and listens on port 8000
- Log message: "API SaaS rodando com sucesso!"

## 2. Health Check Endpoints

### Root Endpoint
```bash
curl http://localhost:8000/
```
Expected: `{"message":"API SaaS rodando com sucesso!"}`

### Health Endpoint
```bash
curl http://localhost:8000/health
```
Expected: `{"status":"ok"}`

### Debug Routes (lists all registered routes)
```bash
curl http://localhost:8000/_debug_routes | jq
```
Expected: JSON array with all registered routes

### OpenAPI Documentation
Open in browser:
- http://localhost:8000/docs (Swagger UI)
- http://localhost:8000/redoc (ReDoc)

## 3. Authentication Endpoints

### Test OAuth2 Token Endpoint (form-urlencoded)
```bash
curl -X POST http://localhost:8000/api/v1/auth/token \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=admin@example.com&password=yourpassword"
```

### Test Login Endpoint (JSON)
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"yourpassword"}'
```

**Expected Response (if user exists):**
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "schema_name": "tenant_schema",
  "empresa": "Company Name",
  "logoUrl": "/static/logos/logo.png",
  "nome": "User Name",
  "role": "ADMIN",
  "is_admin": true,
  "email": "admin@example.com",
  "is_superuser": false
}
```

## 4. File Upload Endpoint

```bash
# Create a test file
echo "test" > /tmp/test.txt

# Upload it
curl -X POST http://localhost:8000/api/v1/upload/ \
  -F "file=@/tmp/test.txt"
```

**Expected Response:**
```json
{
  "filename": "uuid-here.txt",
  "path": "/uploads/uuid-here.txt",
  "message": "File uploaded successfully"
}
```

## 5. Password Reset Endpoints (Stubs)

### Request Password Reset
```bash
curl -X POST http://localhost:8000/api/v1/password-reset/request \
  -H "Content-Type: application/json" \
  -d '{"email":"user@example.com"}'
```

### Confirm Password Reset
```bash
curl -X POST http://localhost:8000/api/v1/password-reset/confirm \
  -H "Content-Type: application/json" \
  -d '{"token":"fake-token","new_password":"newpass123"}'
```

## 6. Verify Directory Structure

```bash
# Check directories exist inside container
docker exec tafon_backend ls -la /app/static/imagens
docker exec tafon_backend ls -la /app/static/logos
docker exec tafon_backend ls -la /app/uploads

# Check ownership
docker exec tafon_backend ls -ln /app/static /app/uploads
```

Expected: All directories owned by UID 1000 (appuser)

## 7. Check for Import Errors

```bash
# View startup logs
docker compose logs backend | grep -i "import\|error\|traceback"
```

Expected: No ImportError, ModuleNotFoundError, or Python tracebacks

## 8. Test Placeholder Endpoints

These are temporary and should return stub responses:

```bash
# Legacy endpoints
curl http://localhost:8000/api/v1/items/_placeholder
curl http://localhost:8000/api/v1/asset/_placeholder
curl http://localhost:8000/api/v1/acessorios/_placeholder
curl http://localhost:8000/api/v1/emprestimos/_placeholder

# Results placeholder (if no real implementation)
curl http://localhost:8000/api/v1/taf/results/_placeholder
```

## 9. Database Connection Test

If database is running:

```bash
# Check database connection in logs
docker compose logs backend | grep -i "database\|connection"
```

Expected: "Database connection verified" message

## 10. Security Tests

### Test SQL Injection Prevention
```bash
# Try invalid schema name (should be rejected)
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"pass"}'
```

Check logs for: `[SECURITY] Invalid schema name skipped` (if any invalid schemas exist)

### Test Schema Validation
```bash
# Schema names must match: ^[a-zA-Z0-9_-]+$
# Any schema with special characters like ; ' " should be rejected
```

## 11. Pydantic Compatibility Test

Check which Pydantic version is installed:

```bash
docker exec tafon_backend pip show pydantic
```

Both v1 and v2 should work without warnings.

## Troubleshooting

### Container Fails to Start

1. Check logs: `docker compose logs backend`
2. Look for ImportError or syntax errors
3. Verify all __init__.py files exist
4. Check file permissions

### Authentication Returns 401

1. Verify database has user accounts
2. Check DATABASE_URL environment variable
3. Verify password hash matches
4. Check logs for authentication attempts

### Static Files Not Found

1. Verify directories exist: `docker exec tafon_backend ls -la /app/static`
2. Check Dockerfile created directories
3. Verify ownership: `docker exec tafon_backend ls -ln /app/static`
4. Restart container: `docker compose restart backend`

### Upload Fails

1. Check uploads directory exists and is writable
2. Verify permissions: `docker exec tafon_backend ls -ln /app/uploads`
3. Check logs for specific error messages

## Success Criteria

✅ Container starts without errors
✅ All health endpoints return 200 OK
✅ /docs and /redoc are accessible
✅ No ImportError or ModuleNotFoundError in logs
✅ Static and uploads directories exist with correct permissions
✅ Authentication endpoints return valid responses
✅ File upload works and saves to uploads directory
✅ All placeholder endpoints return stub responses

## Next Steps

After successful testing:

1. Remove temporary shims once proper implementations are ready
2. Implement actual logic for placeholder endpoints
3. Add comprehensive tests
4. Complete Pydantic v2 migration or pin pydantic<2
5. Implement real password reset with email
6. Add file type validation and size limits to upload
7. Security audit of all endpoints

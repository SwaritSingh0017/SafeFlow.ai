# SafeFlow Production Upgrade Plan

## Architecture Summary

- Frontend: static HTML, CSS, and vanilla JavaScript in `frontend/`, with page-specific inline scripts plus shared helpers under `frontend/js/`.
- Backend: FastAPI app in `backend/`, SQLAlchemy ORM models, SQLite by default with optional `DATABASE_URL` override.
- Auth: Firebase Phone Auth on the client, Firebase Admin verification on the backend, then app-issued access/refresh JWTs for API traffic.
- Data: workers, claims, policies, community posts, OTP records, and premium pool state in the relational database.
- External services:
  - Firebase Authentication + Firebase Admin SDK for identity verification.
  - Razorpay for payments and wallet top-ups.
  - OpenWeatherMap and NewsAPI for risk/disruption signals.
- Deployment: one Render blueprint exists, but there is no containerization, CI pipeline, or test suite.

## Current Issues And Risks

### Critical

- The original custom OTP path bypasses the required Firebase identity bridge and is not suitable for production auth.
- The frontend had stale inline Firebase code and separate custom OTP code, creating multiple inconsistent login paths.
- JWT auth uses a single long-lived token with no refresh flow, no rotation, and weak default secret fallback.
- Several worker endpoints expose data by `worker_id` without verifying the caller owns that record.
- Payment verification is not idempotent and can activate duplicate policies or double-credit wallet funds.
- There is no webhook verification path for payment reconciliation.
- `backend/.env` is committed in the repo, indicating secret-handling gaps.

### High

- Frontend profile page calls `saveProfile()` but only `updateProfile()` exists, breaking profile saves.
- Frontend auth/session state relies only on storage; refresh handling is brittle and redirects aggressively on transient failures.
- API responses are inconsistent across routes, making frontend error handling fragile.
- Input validation is minimal; most request models allow weak or malformed values.
- CORS defaults to `*` even when credentials are allowed, which is unsafe for production.
- Logging is basic and unstructured; there is no request correlation or central error middleware.
- SQLite is used by default with no migration path, pooling strategy, or production DB guidance.

### Medium

- HTML pages contain large inline scripts, increasing duplication and making state bugs easier to introduce.
- Public/demo hints are mixed into production login/register UI.
- Weather/news service failures silently downgrade to demo behavior, which is fine for demos but not auditable for prod.
- Tests are absent.
- Deployment docs are outdated and refer to incorrect/local-only flows.

## Implementation Roadmap

### 1. Core Auth, Firebase Bridge, and Session Hardening

- Files affected:
  - `backend/auth_routes.py`
  - `backend/firebase_service.py`
  - `backend/models.py`
  - `backend/main.py`
  - `frontend/js/api.js`
  - `frontend/js/auth.js`
  - `frontend/js/firebase-auth.js`
  - `frontend/login.html`
  - `frontend/register.html`
  - `frontend/profile.html`
  - `frontend/js/profile.js`
- Expected result:
  - Firebase phone verification on the client and Firebase Admin verification on the backend before any app JWT is issued.
  - Access token + refresh token lifecycle with predictable frontend hydration.
  - Broken profile save fixed.
- Verification:
  - Exchange a verified Firebase token, refresh the page, and confirm authenticated state remains valid.
  - Attempt login with a missing/invalid Firebase token and confirm the backend rejects it cleanly.
  - Save profile successfully from the UI and fetch the updated data.

### 2. Secure API Contracts And Error Handling

- Files affected:
  - `backend/main.py`
  - `backend/auth_routes.py`
  - `backend/worker_routes.py`
  - `backend/policy_routes.py`
  - `backend/payment_routes.py`
  - new backend helper modules for security/response utilities
  - `frontend/js/api.js`
- Expected result:
  - Standardized success/error payloads, centralized exception handling, safer auth helpers, and protected worker-scoped endpoints.
- Verification:
  - Call key endpoints with missing/invalid auth and confirm consistent 401/403 responses.
  - Confirm frontend toasts/messages still work on both success and failure.

### 3. Payment Reliability And Idempotency

- Files affected:
  - `backend/payment_routes.py`
  - `backend/models.py`
  - `frontend/js/payment.js`
  - `frontend/js/dashboard.js`
- Expected result:
  - Payment order creation, verification, retry safety, wallet top-up verification, and webhook-based reconciliation all work without duplicate effects.
- Verification:
  - Create order, verify once, then replay the same payload and confirm no duplicate policy or wallet credit is created.
  - Validate wallet top-up success/failure handling in the UI.

### 4. Security Hardening

- Files affected:
  - backend auth/payment/worker modules
  - `.gitignore`
  - `.env.example`
  - docs/config files
- Expected result:
  - Secrets no longer tracked, stronger env validation, stricter CORS, safer HTML rendering patterns, and input validation throughout.
- Verification:
  - Confirm `.env` is ignored, unsafe defaults removed, and invalid request payloads are rejected.

### 5. Observability And Logging

- Files affected:
  - `backend/main.py`
  - logging helper module(s)
- Expected result:
  - Structured logs for requests, auth, OTP, payments, and unhandled exceptions.
- Verification:
  - Start the app and confirm request logs and error traces are readable and consistent.

### 6. Testing

- Files affected:
  - `tests/` new unit and integration tests
  - lightweight test config/helpers
- Expected result:
  - Automated coverage for Firebase exchange, login/logout/refresh, unauthorized access, and payment verification idempotency.
- Verification:
  - Run `pytest` and confirm all tests pass.

### 7. Production Setup

- Files affected:
  - `Dockerfile`
  - `docker-compose.yml`
  - `.github/workflows/ci.yml`
  - `README.md`
  - deployment config files
- Expected result:
  - One-command local startup, reproducible builds, CI validation, and clear deployment targets for frontend and backend.
- Verification:
  - Build containers locally.
  - Run test/build workflow steps successfully.

## Verification Strategy

- After each major change set:
  - run automated tests;
  - run the FastAPI app locally;
  - exercise the affected API flow manually or with scripted requests;
  - fix regressions before moving on.

## Immediate Execution Order

1. Implement the Firebase auth bridge and fix the frontend profile/session breakages.
2. Lock down worker-scoped endpoints and standardize error handling.
3. Make payment verification idempotent and add reconciliation support.
4. Add tests around the repaired flows.
5. Add deployment, Docker, CI, and updated documentation.

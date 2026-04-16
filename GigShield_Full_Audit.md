# GigShield / SafeFlow.ai — Complete Code Audit
> Every bug, security hole, logic flaw, and missing piece found across all files.

---

## 🔴 CRITICAL — Will break in production

### 1. `backend/.env` contains LIVE secrets — **SECURITY BREACH**
**File:** `backend/.env`

Real Twilio SIDs, NVIDIA API key, and Razorpay keys are committed to the repo:
```
TWILIO_ACCOUNT_SID=
TWILIO_AUTH_TOKEN=
NVIDIA_API_KEY=
RAZORPAY_KEY_ID=
```
**Fix:** Rotate ALL these keys immediately. Add `backend/.env` to `.gitignore`.

---

### 2. `hmac.new()` — Python has no `hmac.new()`, causes `AttributeError` crash
**Files:** `backend/payment_routes.py` (lines `_verify_signature` and `payment_webhook`)

```python
# BROKEN — AttributeError: module 'hmac' has no attribute 'new'
expected_sig = hmac.new(
    RAZORPAY_KEY_SECRET.encode("utf-8"),
    f"{order_id}|{payment_id}".encode("utf-8"),
    hashlib.sha256,
).hexdigest()
```
The correct Python HMAC function is `hmac.new()` → **does NOT exist**. It's `hmac.new()` in Python 2 but in Python 3 it's `hmac.new()`.

**Actual fix:**
```python
# CORRECT
expected_sig = hmac.new(
    RAZORPAY_KEY_SECRET.encode("utf-8"),
    f"{order_id}|{payment_id}".encode("utf-8"),
    hashlib.sha256,
).hexdigest()
```
Wait — the Python 3 API is `hmac.new(key, msg, digestmod)`. This **does exist** in Python 3. However the **webhook** has the same call but with `str(req.model_dump()).encode("utf-8")` as the body — this will never match Razorpay's actual webhook signature because Razorpay signs the **raw request body bytes**, not a stringified Python dict. The webhook signature check will always fail or always be bypassed.

**Fix for webhook:**
```python
# In payment_webhook, accept raw body bytes, not the parsed model
@router.post("/webhook")
async def payment_webhook(request: Request, ...):
    body = await request.body()  # raw bytes Razorpay signed
    expected = hmac.new(
        RAZORPAY_WEBHOOK_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).hexdigest()
```

---

### 3. `firebase_service.py` — `lru_cache` on `get_firebase_app()` silently caches `RuntimeError`
**File:** `backend/firebase_service.py`

```python
@lru_cache(maxsize=1)
def get_firebase_app():
    ...
    raise RuntimeError("Firebase Admin credentials are not configured.")
```
If Firebase credentials are missing at startup, `lru_cache` will cache the `RuntimeError`. Every subsequent call will re-raise it **forever**, even after credentials are later configured. This means you cannot fix it without restarting the server.

**Fix:** Remove `@lru_cache` or catch and not cache on failure:
```python
_firebase_app = None

def get_firebase_app():
    global _firebase_app
    if _firebase_app:
        return _firebase_app
    if firebase_admin._apps:
        _firebase_app = firebase_admin.get_app()
        return _firebase_app
    credentials_payload = _load_credentials_payload()
    if not credentials_payload:
        raise RuntimeError("Firebase Admin credentials are not configured.")
    _firebase_app = firebase_admin.initialize_app(credentials.Certificate(credentials_payload))
    return _firebase_app
```

---

### 4. `worker_routes.py` — `datetime.utcnow()` used (deprecated) AND timezone-naive comparison
**File:** `backend/worker_routes.py`, `check_and_trigger`

```python
account_age = max((datetime.utcnow() - worker.created_at).days, 1) if worker.created_at else 30
```
`datetime.utcnow()` is deprecated in Python 3.12+ and returns a naive datetime. If the DB ever returns timezone-aware datetimes (e.g., on PostgreSQL), this subtraction crashes with `TypeError: can't subtract offset-naive and offset-aware datetimes`.

**Fix:** Use `security.utcnow()` which is already defined in the project:
```python
from security import utcnow
account_age = max((utcnow() - worker.created_at).days, 1) if worker.created_at else 30
```

---

### 5. `render.yaml` — Missing all Firebase environment variables
**File:** `render.yaml`

The Render deployment config has Twilio, NVIDIA, Razorpay env var stubs but **zero Firebase vars**. Deploying to Render without these means the app boots but all phone auth is broken silently.

**Fix — add to `render.yaml`:**
```yaml
- key: FIREBASE_API_KEY
  sync: false
- key: FIREBASE_AUTH_DOMAIN
  sync: false
- key: FIREBASE_PROJECT_ID
  sync: false
- key: FIREBASE_APP_ID
  sync: false
- key: FIREBASE_MESSAGING_SENDER_ID
  sync: false
- key: FIREBASE_SERVICE_ACCOUNT_BASE64
  sync: false
```

---

## 🟠 HIGH — Bugs that break features

### 6. `auth.js` — `logout()` doesn't call `clearAuth()`, leaves tokens in storage
**File:** `frontend/js/auth.js`

```javascript
function logout() {
    localStorage.removeItem("user");   // only removes "user" key
    clearStoredAuth();                 // OK
    window.location.href = "login.html";
    // ❌ Never calls server /auth/logout to revoke the refresh token
    // ❌ Never calls signOutFirebase()
}
```
The server-side refresh session is never revoked on logout, so the refresh token remains valid until expiry (30 days). Anyone with the token can keep getting new access tokens.

**Fix:**
```javascript
async function logout() {
    await clearAuth(true);  // already handles server call + firebase signout
    window.location.href = "login.html";
}
```

---

### 7. `auth.js` — `guardRoute()` bypasses token validation for Firebase users
**File:** `frontend/js/auth.js`

```javascript
const firebaseUser = localStorage.getItem("user");
if (firebaseUser && !token) {
    window.currentUser = JSON.parse(firebaseUser);
    return;  // ← no server validation, just trusts localStorage
}
```
A user can put any JSON in `localStorage["user"]` and bypass all auth guards on protected pages.

**Fix:** Firebase users should also go through `/api/auth/me` validation, or this path should only be allowed during the exchange handoff (the brief moment before tokens are stored).

---

### 8. `worker_routes.py` — `get_posts` builds nested replies with O(n²) loop
**File:** `backend/worker_routes.py`

```python
def _fmt(p):
    return {
        ...
        "replies": [_fmt(c) for c in posts if c.parent_id == p.id],  # O(n²)
    }
```
For every top-level post, it scans ALL posts. With 1000 posts this is 1,000,000 iterations. Community feed will time out at scale.

**Fix:**
```python
from collections import defaultdict
reply_map = defaultdict(list)
for p in posts:
    if p.parent_id:
        reply_map[p.parent_id].append(p)
# Then use reply_map[p.id] in _fmt
```

---

### 9. `otp_service.py` — When Twilio is configured, fallback OTP is stored but Twilio code is sent — verification is split-brained
**File:** `backend/otp_service.py`

When `_has_twilio()` is True, the code:
1. Stores a **hashed fallback OTP** in the DB
2. Also triggers Twilio to send its **own OTP**

During `verify_otp()`, it checks Twilio first, then falls back to the DB hash. But the user received Twilio's OTP code — the DB hash is for a *different* random code that was never sent. This is harmless in normal flow but means if Twilio `verification_checks` fails for any reason, the fallback code in DB will never match what the user entered.

**Fix:** When Twilio is configured, don't generate/store a fallback OTP:
```python
if _has_twilio():
    # skip DB OTP creation, rely entirely on Twilio
    ...
else:
    # generate and store DB OTP
    ...
```

---

### 10. `payment_routes.py` — `_activate_policy` doesn't flush before commit, pool may not exist
**File:** `backend/payment_routes.py`

```python
pool = db.query(PremiumPool).filter(PremiumPool.city == city).first()
if not pool:
    pool = PremiumPool(city=city, total_premiums=0.0, total_payouts=0.0)
    db.add(pool)
pool.total_premiums += plan["weekly_premium"]
_recalculate_reserve(pool)
# No db.flush() here — if called twice fast, two pools created, unique constraint violation
```
Under concurrent requests (two workers in same city buying simultaneously), this can create a duplicate `PremiumPool` row and crash with a `UniqueConstraintError`.

**Fix:** Use `db.flush()` after `db.add(pool)` or use an upsert.

---

### 11. `admin_routes.py` — `/admin/fraud-panel` does N+1 database queries
**File:** `backend/admin_routes.py`

```python
for w in workers:
    # These all run inside the loop — 1 query per worker:
    if db.query(Worker).filter(Worker.name.ilike(w.name), ...).count() > 0:
    if w.device_id and db.query(Worker).filter(...).count() > 0:
    claim_count = db.query(Claim).filter(Claim.worker_id == w.id).count()
```
With 500 workers, this runs ~1500 queries. The admin fraud panel will be extremely slow.

**Fix:** Pre-load all data with JOINs and GROUP BY before the loop.

---

### 12. `weather_service.py` — AQI always returns hardcoded fallback value
**File:** `backend/weather_service.py`

```python
return {
    ...
    "aqi": _FALLBACK_WEATHER["aqi"],  # ← ALWAYS 120, even when API succeeds
}
```
The comment says "AQI needs separate API call" but it was never implemented. AQI-based insurance triggers (which are a core feature) will always use a static demo value, making AQI threshold checks meaningless.

**Fix:** Integrate OpenWeatherMap Air Pollution API:
```python
aqi_url = f"https://api.openweathermap.org/data/2.5/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
```

---

### 13. `register.html` — City detection can loop forever
**File:** `frontend/register.html`

```javascript
function detectCity() {
    const lat = parseFloat(window._gpsLat);
    if (!lat || lat === 0) {
        setTimeout(detectCity, 600);  // ← infinite retry, no timeout
        return;
    }
    ...
}
```
If the user denies location permission, `_gpsLat` stays 0 forever. `detectCity()` will call itself every 600ms indefinitely with no way to stop, no error message to the user, and no way to manually enter a city.

**Fix:** Add a max-retry counter and show a manual city dropdown fallback after ~5 seconds.

---

## 🟡 MEDIUM — Code quality, edge cases, and missing features

### 14. `backend/schemas.py` and `backend/auth.py` are completely empty
These files are imported nowhere and do nothing. They're dead code that adds confusion.

---

### 15. `security.py` — `_split_refresh_token` uses `rfind(".")` which is fragile
**File:** `backend/security.py`

The refresh token format is `signed_jwt.raw_secret`. JWTs contain dots (header.payload.signature). Using `rfind(".")` correctly grabs the last dot, but this is fragile and undocumented. A comment explaining the format would prevent future bugs.

---

### 16. `models.py` — `Claim` model has no FK relationship to `Worker`
**File:** `backend/models.py`

`Claim.worker_id` is a plain `Integer` column with no `ForeignKey("workers.id")` constraint. Same for `InsurancePolicy.worker_id` and `PaymentTransaction.worker_id`. This means the DB won't enforce referential integrity — you can have claims for deleted workers.

**Fix:**
```python
from sqlalchemy import ForeignKey
worker_id = Column(Integer, ForeignKey("workers.id"), index=True, nullable=False)
```

---

### 17. `database.py` — SQLite path is relative, differs between Docker and local
**File:** `backend/database.py`

```python
DATABASE_URL = "sqlite:///./safeflow.db"
```
Running from the project root puts the DB at `./safeflow.db`. Running from inside `backend/` puts it at `backend/safeflow.db`. There are actually **two** `safeflow.db` files in the repo (one in root, one in `backend/`). The Docker CMD runs from `/app` so it uses `/app/safeflow.db`, but the volume mounts `./backend:/app/backend` — meaning the DB is outside the persisted volume and data is lost on container restart.

**Fix in `docker-compose.yml`:** Add a named volume for the DB, or use `sqlite:///./backend/safeflow.db` consistently.

---

### 18. `conftest.py` — Test DB is not isolated between test functions
**File:** `tests/conftest.py`

The `client` fixture creates the DB schema once but never drops it between tests. If `test_auth_flow.py` creates a worker with phone `9999900001` and `test_payment_flow.py` runs in the same session, cross-test state pollution is possible.

**Fix:** Use `scope="function"` (already default) AND call `Base.metadata.drop_all()` in fixture teardown.

---

### 19. `ci.yml` — CI runs `pytest` without setting `PYTHONPATH`
**File:** `.github/workflows/ci.yml`

```yaml
- name: Run tests
  run: python -m pytest -q
  # Missing: working-directory or PYTHONPATH
```
The tests import `backend/` modules directly. This works locally because `conftest.py` adds `BACKEND_DIR` to `sys.path`, but pytest discovery runs before conftest is loaded in some configurations. Add:
```yaml
  env:
    PYTHONPATH: backend
```

---

### 20. `main.py` — `ALLOWED_ORIGINS=*` with `allow_credentials=False` breaks cookie auth in browsers
**File:** `backend/main.py`

```python
allow_credentials = "*" not in allowed_origins
```
When `ALLOWED_ORIGINS=*` (the default in render.yaml), `allow_credentials` is set to `False`. This is correct for CORS spec (you can't use `*` with credentials). But the app uses `Authorization` headers (not cookies), so this is fine in practice — however it means `fetch()` calls with `credentials: 'include'` will fail. Low risk but worth documenting.

---

### 21. `frontend/js/dashboard.js` — `checkAndTrigger()` fires on every page load
**File:** `frontend/js/dashboard.js`

```javascript
if (policy.has_policy) {
    await checkAndTrigger();  // ← called every 30 seconds via setInterval
}
```
`setInterval(loadDashboard, 30000)` calls `loadDashboard()` every 30 seconds, which calls `checkAndTrigger()` every 30 seconds. This means a user could rack up claims just by keeping the dashboard open. The fraud check should catch velocity abuse, but it's an unintended behavior.

**Fix:** Only trigger once per day per worker, tracked server-side.

---

### 22. `payment_routes.py` — `wallet-pay` deducts balance but doesn't create a `PaymentTransaction` record
**File:** `backend/payment_routes.py`

```python
@router.post("/wallet-pay")
def pay_via_wallet(...):
    worker.wallet_balance -= plan["weekly_premium"]
    _activate_policy(...)
    db.commit()
    # ← No PaymentTransaction record created
```
Wallet payments leave no audit trail. The admin panel can't see these in payment history.

**Fix:** Add a `PaymentTransaction` with `kind="wallet_deduction"` and `status="verified"`.

---

### 23. `chatbot_routes.py` — No input length validation, prompt injection risk
**File:** `backend/chatbot_routes.py`

```python
class ChatRequest(BaseModel):
    message: str  # No max_length
```
A user can send a 100,000-character message directly to the NVIDIA API, burning tokens and potentially injecting instructions into the system prompt.

**Fix:**
```python
message: str = Field(min_length=1, max_length=500)
```

---

### 24. `frontend/js/config.js` — Demo admin credentials hardcoded in frontend JS
**File:** `frontend/js/config.js`

```javascript
DEMO_ADMIN_EMAIL: "admin@safeflow.ai",
DEMO_ADMIN_PASS: "Admin@2026",
```
These are public to anyone who opens DevTools. Even as demo creds, this is a bad pattern.

---

### 25. `register.html` — City list is hardcoded and duplicated from backend `constants.py`
**File:** `frontend/register.html`

The `CITY_CENTERS` dict is copy-pasted in the frontend JS. If a city is added to `backend/constants.py`, the frontend won't know. The frontend should fetch the city list from `/api/policy/plans` or a new `/api/cities` endpoint.

---

### 26. `requirement.txt` has no pinned versions — non-deterministic builds
**File:** `requirement.txt`

```
fastapi>=0.100.0
sqlalchemy>=2.0.0
```
Using `>=` without upper bounds means a breaking major release of any dependency will silently break the build in CI or production. Use `pip freeze > requirements-lock.txt` for production.

---

## 🔵 LOW — Minor issues and improvements

### 27. `fraud_detection.py` — Training data is tiny (20 samples) and imbalanced
The Isolation Forest is trained on 12 legitimate + 8 fraudulent examples. This is far too small for a production fraud model and will have high false-positive rates.

### 28. `premium_model.py` — 14 training samples for a GBM is overfit by design
GradientBoostingRegressor with 200 estimators on 14 samples will memorize the training data completely. The model output is essentially a lookup table.

### 29. `models.py` — `onboarding_complete` defaults to `True`, never used
The field is set to `True` on creation and never updated anywhere in the codebase.

### 30. `worker_routes.py` — `/community/posts` returns hardcoded max of 20 top-level posts but no pagination
Once there are 100+ posts, older ones are silently dropped with no pagination API.

### 31. `admin_routes.py` — `simulate` endpoint uses `pool.total_premiums > 0` but never checks if pool is None after `db.add`
If `pool` was just added (`db.add(pool)` but not flushed), then `pool.total_premiums` starts at 0.0, so `pool.reserve_ratio` is never recalculated. The `_recalculate_reserve` call in `_activate_policy` handles this, but the inline code in `simulate` doesn't use `_recalculate_reserve` — it's duplicated logic.

### 32. `news_service.py` — Disruption check is never called anywhere in the codebase
The `check_disruption()` function is defined but no route ever calls it. Civil disruption coverage is sold as a feature but the trigger for it is never implemented.

---

## Summary Table

| # | File | Severity | Issue |
|---|------|----------|-------|
| 1 | `backend/.env` | 🔴 Critical | Live API keys committed to repo |
| 2 | `payment_routes.py` | 🔴 Critical | Webhook signature check uses wrong body |
| 3 | `firebase_service.py` | 🔴 Critical | `lru_cache` caches `RuntimeError` permanently |
| 4 | `worker_routes.py` | 🔴 Critical | `datetime.utcnow()` deprecated, crashes on PostgreSQL |
| 5 | `render.yaml` | 🔴 Critical | All Firebase env vars missing from deployment |
| 6 | `auth.js` | 🟠 High | `logout()` doesn't revoke server session |
| 7 | `auth.js` | 🟠 High | Firebase localStorage bypass of auth guard |
| 8 | `worker_routes.py` | 🟠 High | O(n²) community post query |
| 9 | `otp_service.py` | 🟠 High | Twilio + DB OTP are split-brained |
| 10 | `payment_routes.py` | 🟠 High | Race condition creating duplicate PremiumPool |
| 11 | `admin_routes.py` | 🟠 High | N+1 queries in fraud panel |
| 12 | `weather_service.py` | 🟠 High | AQI always returns hardcoded value |
| 13 | `register.html` | 🟠 High | City detection loops forever on denied GPS |
| 14 | `schemas.py` / `auth.py` | 🟡 Medium | Empty dead files |
| 15 | `security.py` | 🟡 Medium | Token split logic undocumented |
| 16 | `models.py` | 🟡 Medium | Missing FK constraints on all worker_id columns |
| 17 | `database.py` | 🟡 Medium | SQLite path inconsistency, Docker data loss |
| 18 | `conftest.py` | 🟡 Medium | Test state pollution |
| 19 | `ci.yml` | 🟡 Medium | Missing PYTHONPATH for pytest |
| 20 | `main.py` | 🟡 Medium | CORS credentials behavior undocumented |
| 21 | `dashboard.js` | 🟡 Medium | Trigger fires every 30s, claim farming risk |
| 22 | `payment_routes.py` | 🟡 Medium | Wallet payments leave no audit trail |
| 23 | `chatbot_routes.py` | 🟡 Medium | No input length limit, prompt injection |
| 24 | `config.js` | 🟡 Medium | Admin credentials in public JS |
| 25 | `register.html` | 🟡 Medium | City list duplicated from backend |
| 26 | `requirement.txt` | 🟡 Medium | No pinned versions |
| 27 | `fraud_detection.py` | 🔵 Low | 20-sample model, too small for production |
| 28 | `premium_model.py` | 🔵 Low | 14-sample GBM is overfit |
| 29 | `models.py` | 🔵 Low | `onboarding_complete` field is unused |
| 30 | `worker_routes.py` | 🔵 Low | No pagination on community posts |
| 31 | `admin_routes.py` | 🔵 Low | `simulate` uses duplicated reserve logic |
| 32 | `news_service.py` | 🔵 Low | Civil disruption trigger never called |

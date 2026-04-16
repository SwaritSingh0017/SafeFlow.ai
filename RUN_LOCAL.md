# Running SafeFlow.ai Locally

This guide will walk you through setting up the SafeFlow.ai application on your local machine for development and testing.

## Prerequisites

1. **Python**: Python 3.9, 3.10, or 3.11 installed. Verify with `python --version` or `python3 --version`.
2. **Pip**: Ensure `pip` is available.
3. **Environment Setup**: A local IDE like VSCode, Cursor, or PyCharm.

## 1. Setup Environment Variables

The application relies on several API keys (Firebase, Razorpay, OpenWeatherMap) to function fully.

1. In the root directory, locate the `.env.example` file.
2. Copy `.env.example` into a new file named `.env` in the exact same directory.
   - On Windows: `copy .env.example .env`
   - On Mac/Linux: `cp .env.example .env`
3. Open `.env` and fill in the required values. If you are just testing the local flow, you only strictly need the `JWT_SECRET` and `ADMIN_PASSWORD` out-of-the-box, but you will need standard API keys for SMS parsing/payments:
   - **Razorpay**: For testing the Add Funds feature. Use your test keys (`rzp_test_...`).
   - **Firebase**: Needed for Phone OTP Authentication. Provide the `FIREBASE_SERVICE_ACCOUNT_JSON` path or base64. Ensure the `FIREBASE_API_KEY` and related web config vars are populated.

## 2. Install Python Dependencies

Open your terminal, navigate to the `gigshield_fixed` root directory where `requirement.txt` is located, and install the libraries:

```bash
pip install -r requirement.txt
```
*(If you are on a Mac/Linux machine you may need to run `pip3 install -r requirement.txt` instead)*

## 3. Start the Backend Server

We use `uvicorn` as the ASGI web server to run our FastAPI backend. The frontend is automatically served statically by the backend server.

Run the following command in the terminal from the root directory:

```bash
uvicorn backend.main:app --reload --port 8000
```

### What this command does:
- `backend.main:app`: Tells Uvicorn where the entry point is (the `app` object in `backend/main.py`).
- `--reload`: Automatically restarts the server if you alter any Python code (useful for development).
- `--port 8000`: Runs the application on port 8000.

You should see logs indicating the server started and that the local `safeflow.db` SQLite database schema was checked and ready.

## 4. Access the Application

Once the server is running successfully:

- **Frontend User View**: Open your web browser and navigate to `http://127.0.0.1:8000`. You will see the main landing page, and can login/register.
- **Backend Swagger API Docs**: Navigate to `http://127.0.0.1:8000/docs`. This gives you an interactive UI to test all backend endpoints (including the new withdrawal system).
- **Admin Panel**: Navigate to `http://127.0.0.1:8000/admin-login.html`. Login with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you configured in your `.env` file to view fraud alerts, pool health, and manage withdrawal requests.

## 5. Troubleshooting Common Issues

- **Database Errors**: SafeFlow.ai uses SQLite by default for easy local development. The database file `safeflow.db` is generated automatically in the `backend/` folder. If you encounter migration or missing column errors, you can safely delete `backend/safeflow.db` and restart the server to recreate a fresh schema.
- **Port In Use**: If you get an error that Port 8000 is in use, you can change the port flag (e.g., `--port 8080`) and then access the site at `http://127.0.0.1:8080`.
- **ModuleNotFoundError: No module named 'fastapi'**: This means your dependencies didn't successfully install, or you installed them in a different environment/terminal than the one running Uvicorn. Ensure you install and run Uvicorn inside the same Python environment (or virtual environment).

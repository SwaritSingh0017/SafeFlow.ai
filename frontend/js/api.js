/**
 * SafeFlow.ai - API utility layer
 * Centralizes auth storage, refresh handling, and UI helpers.
 */

let refreshInFlight = null;

function showToast(message, type = "success") {
    let container = document.getElementById("toast-container");
    if (!container) {
        container = document.createElement("div");
        container.id = "toast-container";
        document.body.appendChild(container);
    }
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.classList.add("fade-out"), 3200);
    setTimeout(() => toast.remove(), 3700);
}

function getDeviceId() {
    let id = localStorage.getItem("gs_device_id");
    if (!id) {
        const raw = [
            navigator.userAgent,
            navigator.language,
            `${screen.width}x${screen.height}`,
            new Date().getTimezoneOffset(),
        ].join("|");
        id = btoa(raw).substring(0, 32);
        localStorage.setItem("gs_device_id", id);
    }
    return id;
}

window._gpsLat = 0;
window._gpsLon = 0;

if (navigator.geolocation) {
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            window._gpsLat = pos.coords.latitude;
            window._gpsLon = pos.coords.longitude;
        },
        () => {},
        { enableHighAccuracy: true, timeout: 8000 }
    );
}

function showLoading() {
    let bar = document.getElementById("global-loader");
    if (!bar) {
        bar = document.createElement("div");
        bar.id = "global-loader";
        bar.style.cssText =
            "position:fixed;top:0;left:0;width:0%;height:3px;background:var(--primary);z-index:10000;transition:width 0.3s ease;";
        document.body.appendChild(bar);
    }
    bar.style.opacity = "1";
    bar.style.width = "35%";
}

function hideLoading() {
    const bar = document.getElementById("global-loader");
    if (!bar) return;
    bar.style.width = "100%";
    setTimeout(() => {
        bar.style.opacity = "0";
        setTimeout(() => {
            bar.style.width = "0%";
        }, 300);
    }, 200);
}

function getStorageBucket() {
    return localStorage.getItem("gs_session_mode") === "session" ? sessionStorage : localStorage;
}

function persistAuth(tokens, rememberMe = true) {
    const storage = rememberMe ? localStorage : sessionStorage;
    const otherStorage = rememberMe ? sessionStorage : localStorage;
    otherStorage.removeItem("gs_access_token");
    otherStorage.removeItem("gs_refresh_token");
    storage.setItem("gs_access_token", tokens.access_token);
    storage.setItem("gs_refresh_token", tokens.refresh_token);
    localStorage.setItem("gs_session_mode", rememberMe ? "local" : "session");
}

function getToken() {
    return localStorage.getItem("gs_access_token") || sessionStorage.getItem("gs_access_token") || null;
}

function getRefreshToken() {
    return localStorage.getItem("gs_refresh_token") || sessionStorage.getItem("gs_refresh_token") || null;
}

function clearStoredAuth() {
    localStorage.removeItem("gs_access_token");
    localStorage.removeItem("gs_refresh_token");
    sessionStorage.removeItem("gs_access_token");
    sessionStorage.removeItem("gs_refresh_token");
    localStorage.removeItem("gs_session_mode");
    localStorage.removeItem("gs_user");
}

function saveCurrentUser(user) {
    localStorage.setItem("gs_user", JSON.stringify(user));
}

function getSavedUser() {
    try {
        const raw = localStorage.getItem("gs_user");
        return raw ? JSON.parse(raw) : null;
    } catch (_) {
        return null;
    }
}

async function refreshAccessToken() {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return false;
    if (!refreshInFlight) {
        refreshInFlight = fetch(`${API_URL}/auth/refresh`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ refresh_token: refreshToken }),
        })
            .then(async (response) => {
                if (!response.ok) {
                    return false;
                }
                const data = await response.json();
                persistAuth(data, localStorage.getItem("gs_session_mode") !== "session");
                return true;
            })
            .catch(() => false)
            .finally(() => {
                refreshInFlight = null;
            });
    }
    return refreshInFlight;
}

async function apiFetch(endpoint, options = {}, retryOnAuth = true) {
    showLoading();
    try {
        const token = getToken();
        const headers = {
            "Content-Type": "application/json",
            ...(token ? { Authorization: `Bearer ${token}` } : {}),
            ...(options.headers || {}),
        };
        const response = await fetch(`${API_URL}${endpoint}`, {
            ...options,
            headers,
        });

        if (response.status === 401 && retryOnAuth && getRefreshToken()) {
            const refreshed = await refreshAccessToken();
            if (refreshed) {
                hideLoading();
                return apiFetch(endpoint, options, false);
            }
            clearStoredAuth();
            if (!window.location.pathname.endsWith("login.html")) {
                window.location.href = "login.html";
            }
            hideLoading();
            return null;
        }

        hideLoading();
        return response;
    } catch (_) {
        hideLoading();
        showToast("Network error - is the backend running?", "error");
        return null;
    }
}

function timeAgo(dateString) {
    if (!dateString) return "";
    const date = new Date(dateString);
    const seconds = Math.floor((Date.now() - date) / 1000);
    if (seconds < 60) return "Just now";
    if (seconds < 3600) return `${Math.floor(seconds / 60)} min ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)} hr ago`;
    return `${Math.floor(seconds / 86400)} days ago`;
}

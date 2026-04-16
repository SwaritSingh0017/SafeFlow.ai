/**
 * SafeFlow.ai - Auth utilities
 */

function saveAuth(tokens, rememberMe = true, user = null) {
    persistAuth(tokens, rememberMe);
    if (user) {
        window.currentUser = user;
        saveCurrentUser(user);
    }
}

async function clearAuth(callLogout = true) {
    const refreshToken = getRefreshToken();
    if (callLogout && refreshToken) {
        try {
            await fetch(`${API_URL}/auth/logout`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ refresh_token: refreshToken }),
            });
        } catch (_) { }
    }
    clearStoredAuth();
    window.currentUser = null;
    if (window.signOutFirebase) {
        try {
            await signOutFirebase();
        } catch (_) {}
    }
}

function redirectByRole(user) {
    window.location.href = user.role === "admin" ? "admin.html" : "dashboard.html";
}

async function guardRoute() {
    const token = getToken();
    const path = window.location.pathname;
    const publicRoutes = ["index.html", "login.html", "admin-login.html", "register.html", "/"];
    const isPublic = publicRoutes.some((route) => path.endsWith(route)) || path === "/";

    if (isPublic && token) {
        try {
            const response = await apiFetch("/auth/me");
            if (!token) return; // skip backend check for firebase users
            if (response && response.ok) {
                const user = await response.json();
                window.currentUser = user;
                saveCurrentUser(user);
                if (path.endsWith("login.html") || path.endsWith("index.html") || path === "/") {
                    redirectByRole(user);
                }
            }
        } catch (_) { }
        return;
    }

    if (isPublic) return;

    const firebaseUser = localStorage.getItem("user");

    if (!token && !firebaseUser) {
        window.location.href = "login.html";
        return;
    }

    // Enforce backend validation even for firebase users
    if (firebaseUser && !token && path.includes("dashboard.html")) {
        // Must wait for token exchange to complete, otherwise they aren't fully authed yet
        window.location.href = "login.html";
        return;
    }

    const cachedUser = getSavedUser();
    if (cachedUser) {
        window.currentUser = cachedUser;
    }

    try {
        const response = await apiFetch("/auth/me");
        if (!response || !response.ok) {
            await clearAuth(false);
            window.location.href = "login.html";
            return;
        }
        const user = await response.json();
        window.currentUser = user;
        saveCurrentUser(user);

        if (path.includes("admin.html") && user.role !== "admin") {
            window.location.href = "dashboard.html";
        } else if (path.includes("dashboard.html") && user.role === "admin") {
            window.location.href = "admin.html";
        }
    } catch (err) {
        console.error("Auth guard error:", err);
    }
}

async function logout() {
    await clearAuth(true);
    window.location.href = "login.html";
}

guardRoute();

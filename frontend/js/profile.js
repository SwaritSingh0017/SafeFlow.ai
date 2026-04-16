/**
 * SafeFlow.ai — Worker Profile Management
 */

async function loadProfile() {
    if (!window.currentUser) { setTimeout(loadProfile, 150); return; }
    const u = window.currentUser;
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    const setText = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };

    set("prof-name",  u.name);
    set("prof-phone", u.phone);
    set("prof-upi",   u.upi || "");

    // Populate city select
    const cityEl = document.getElementById("prof-city");
    if (cityEl) cityEl.value = u.city;

    // Fetch trust score from stats
    try {
        const res = await apiFetch(`/workers/${u.id}/stats`);
        if (res && res.ok) {
            const data = await res.json();
            setText("prof-trust", `${data.trust_score}/100`);
            setText("prof-name-display", u.name);
        }
    } catch (_) {}
}

async function updateProfile() {
    const name = document.getElementById("prof-name").value.trim();
    const city = document.getElementById("prof-city").value;
    const upi  = document.getElementById("prof-upi")  ? document.getElementById("prof-upi").value.trim() : null;

    if (!name) return showToast("Name cannot be empty", "error");

    const res = await apiFetch("/auth/profile", {
        method: "PUT",
        body: JSON.stringify({ name, city, upi }),
    });
    if (res && res.ok) {
        const data = await res.json();
        window.currentUser = { ...window.currentUser, ...data.worker };
        saveCurrentUser(window.currentUser);
        showToast("Profile updated successfully!", "success");
    } else {
        const err = res ? await res.json() : {};
        showToast(err.detail || "Update failed", "error");
    }
}

if (window.location.pathname.includes("profile.html")) {
    window.addEventListener("DOMContentLoaded", loadProfile);
}

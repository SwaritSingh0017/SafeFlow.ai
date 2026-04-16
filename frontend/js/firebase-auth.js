/**
 * SafeFlow.ai - Firebase phone auth bridge helpers.
 */

let firebaseAppInstance = null;
let recaptchaVerifierInstance = null;
let pendingConfirmation = null;
let firebaseConfigPromise = null;
window.__otpMode = "firebase";

async function ensureFirebaseReady() {
    if (!window.firebase || !window.firebase.auth) {
        throw new Error("Firebase SDK not loaded");
    }
    const cfg = await getFirebaseConfig();
    if (!cfg.apiKey || !cfg.authDomain || !cfg.projectId || !cfg.appId) {
        throw new Error("Firebase config is missing. Set the Firebase public env vars on the backend or inject window.__FIREBASE_CONFIG__.");
    }
    if (!firebaseAppInstance) {
        firebaseAppInstance = firebase.apps.length ? firebase.app() : firebase.initializeApp(cfg);
        await firebase.auth().setPersistence(firebase.auth.Auth.Persistence.LOCAL);
    }
    return firebase.auth();
}

async function getFirebaseConfig() {
    const current = APP_CONFIG.FIREBASE || {};
    if (current.apiKey && current.authDomain && current.projectId && current.appId) {
        return current;
    }

    if (!firebaseConfigPromise) {
        firebaseConfigPromise = fetch(`${API_URL}/public-config`)
            .then(async (response) => {
                if (!response.ok) {
                    throw new Error("Unable to load Firebase config");
                }
                const payload = await response.json();
                const firebaseCfg = payload.firebase || {};
                APP_CONFIG.FIREBASE = {
                    apiKey: firebaseCfg.apiKey || "",
                    authDomain: firebaseCfg.authDomain || "",
                    projectId: firebaseCfg.projectId || "",
                    appId: firebaseCfg.appId || "",
                    messagingSenderId: firebaseCfg.messagingSenderId || "",
                };
                return APP_CONFIG.FIREBASE;
            })
            .catch((error) => {
                firebaseConfigPromise = null;
                throw error;
            });
    }

    return firebaseConfigPromise;
}

async function ensureRecaptcha(containerId) {
    const auth = await ensureFirebaseReady();
    if (!recaptchaVerifierInstance) {
        recaptchaVerifierInstance = new firebase.auth.RecaptchaVerifier(
            containerId,
            {
                size: "invisible",
            },
            auth
        );
        await recaptchaVerifierInstance.render();
    }
    return recaptchaVerifierInstance;
}

async function sendFirebaseOtp(phone, recaptchaContainerId) {
    const auth = await ensureFirebaseReady();
    const verifier = await ensureRecaptcha(recaptchaContainerId);
    pendingConfirmation = await auth.signInWithPhoneNumber(`+91${phone}`, verifier);
    return pendingConfirmation;
}

async function confirmFirebaseOtp(otp) {
    if (!pendingConfirmation) {
        throw new Error("OTP request is not active");
    }
    const result = await pendingConfirmation.confirm(otp);
    return result.user.getIdToken(true);
}

async function exchangeFirebaseToken(firebaseToken, profile = null) {
    const body = {
        firebase_token: firebaseToken,
        ...(profile || {}),
    };
    const response = await apiFetch("/auth/firebase/exchange", {
        method: "POST",
        body: JSON.stringify(body),
    }, false);
    if (!response) {
        return null;
    }
    return {
        response,
        data: await response.json(),
    };
}

async function signOutFirebase() {
    if (window.firebase && firebase.apps.length) {
        await firebase.auth().signOut();
    }
    pendingConfirmation = null;
}

async function sendBackendOtp(phone) {
    const response = await apiFetch("/auth/send-otp", {
        method: "POST",
        body: JSON.stringify({ phone }),
    }, false);
    if (!response) {
        throw new Error("Unable to reach backend OTP service");
    }
    const data = await response.json();
    if (!response.ok) {
        throw new Error(data.detail || data.error || "Failed to send OTP");
    }
    window.__otpMode = "backend";
    return data;
}

async function verifyBackendOtp(phone, otp) {
    const response = await apiFetch("/auth/verify-otp", {
        method: "POST",
        body: JSON.stringify({ phone, otp }),
    }, false);
    if (!response) {
        return null;
    }
    return {
        response,
        data: await response.json(),
    };
}

async function registerWithBackendOtp(payload) {
    const response = await apiFetch("/auth/register", {
        method: "POST",
        body: JSON.stringify(payload),
    }, false);
    if (!response) {
        return null;
    }
    return {
        response,
        data: await response.json(),
    };
}

/**
 * SafeFlow.ai - Global frontend runtime configuration.
 */

const Config = {
    API_URL: "/api",
    APP_NAME: "SafeFlow.ai",
    SUPPORT_EMAIL: "support@safeflow.ai",
    DEFAULT_CITY: "Delhi",
    REFRESH_INTERVAL: 30000,
    VERSION: "3.1.0",
    DEMO_ADMIN_EMAIL: "admin@safeflow.ai",
    DEMO_ADMIN_PASS: "Admin@2026",
    FIREBASE: {
        apiKey: window.__FIREBASE_CONFIG__?.apiKey || "",
        authDomain: window.__FIREBASE_CONFIG__?.authDomain || "",
        projectId: window.__FIREBASE_CONFIG__?.projectId || "",
        appId: window.__FIREBASE_CONFIG__?.appId || "",
        messagingSenderId: window.__FIREBASE_CONFIG__?.messagingSenderId || "",
    },
};

window.APP_CONFIG = Config;
const API_URL = Config.API_URL;

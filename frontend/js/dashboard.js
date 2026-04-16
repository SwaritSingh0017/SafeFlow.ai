/**
 * SafeFlow.ai - Dashboard orchestration
 * Fetches live data in parallel, renders cards, auto-polls every 30s.
 */

let lastTriggerCheck = 0;

async function loadDashboard() {
    if (!window.currentUser) {
        setTimeout(loadDashboard, 150);
        return;
    }

    const { id: workerId, city } = window.currentUser;
    document.getElementById("welcome-name").textContent = window.currentUser.name.split(" ")[0];

    setSkeletons(true);

    try {
        const [weatherRes, riskRes, walletRes, statsRes, policyRes] = await Promise.all([
            apiFetch(`/weather?city=${encodeURIComponent(city)}`),
            apiFetch(`/risk?city=${encodeURIComponent(city)}`),
            apiFetch(`/wallet/${workerId}`),
            apiFetch(`/workers/${workerId}/stats`),
            apiFetch("/policy/my-policy"),
        ]);

        const weather = weatherRes && weatherRes.ok ? await weatherRes.json() : {};
        const risk = riskRes && riskRes.ok ? await riskRes.json() : { score: 0, level: "LOW" };
        const wallet = walletRes && walletRes.ok ? await walletRes.json() : { balance: 0 };
        const stats = statsRes && statsRes.ok ? await statsRes.json() : { claims_history: [], trust_score: 85 };
        const policy = policyRes && policyRes.ok ? await policyRes.json() : { has_policy: false };

        setSkeletons(false);
        updateRiskMeter(risk);
        updateWeatherCard(weather);
        updateWalletCard(wallet);
        updateCoverageCard(stats, policy);
        renderClaimsHistory(stats.claims_history || []);

        if (policy.has_policy) {
            const now = Date.now();
            if (now - lastTriggerCheck > 3600000) {
                lastTriggerCheck = now;
                await checkAndTrigger();
            }
        }
    } catch (err) {
        console.error("Dashboard load error:", err);
        setSkeletons(false);
    }
}

async function checkAndTrigger() {
    const res = await apiFetch("/check-and-trigger", {
        method: "POST",
        body: JSON.stringify({ lat: window._gpsLat || null, lon: window._gpsLon || null }),
    });
    if (!res || !res.ok) return;

    const data = await res.json();
    if (data.triggered) {
        showToast(data.message, "success");
        const walletRes = await apiFetch(`/wallet/${window.currentUser.id}`);
        if (walletRes && walletRes.ok) {
            updateWalletCard(await walletRes.json());
        }
    }
}

function updateRiskMeter(risk) {
    const scoreEl = document.getElementById("risk-value");
    const labelEl = document.getElementById("risk-label");
    const card = document.getElementById("risk-card");
    if (!scoreEl) return;

    scoreEl.textContent = `${risk.score}/10`;
    labelEl.textContent = risk.level || "LOW";
    card.classList.remove("animate-pulse-red", "animate-pulse-green");

    if (risk.score >= 7) {
        labelEl.style.color = "var(--danger)";
        card.classList.add("animate-pulse-red");
    } else if (risk.score >= 4) {
        labelEl.style.color = "var(--warning)";
    } else {
        labelEl.style.color = "var(--success)";
    }
}

function updateWeatherCard(data) {
    const set = (id, val) => {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    };

    set("weather-temp", data.temp_celsius != null ? `${data.temp_celsius} C` : "--");
    set("weather-rain", data.rain_mm != null ? `${data.rain_mm} mm` : "--");
    set("weather-wind", data.wind_kmh != null ? `${data.wind_kmh} km/h` : "--");
    set("weather-aqi", data.aqi != null ? data.aqi : "--");
    set("weather-humidity", data.humidity != null ? `${data.humidity}%` : "--");
    set("weather-summary", data.summary || "");
}

function updateWalletCard(wallet) {
    const balEl = document.getElementById("wallet-balance");
    if (!balEl) return;

    const prev = parseFloat(balEl.textContent.replace("Rs", "").replace(",", "")) || 0;
    const next = parseFloat(wallet.balance) || 0;
    if (next > prev && prev !== 0) {
        balEl.parentElement.classList.add("animate-pulse-green");
        setTimeout(() => balEl.parentElement.classList.remove("animate-pulse-green"), 3000);
    }

    balEl.textContent = `Rs${next.toLocaleString("en-IN")}`;
}

function updateCoverageCard(stats, policy) {
    const tsEl = document.getElementById("trust-score-badge");
    if (tsEl) tsEl.textContent = `${stats.trust_score || 85}/100`;

    const planEl = document.getElementById("active-plan-badge");
    if (!planEl) return;

    if (policy && policy.has_policy) {
        planEl.textContent = `${policy.plan_type} Plan Active`;
        planEl.style.color = "var(--success)";
    } else {
        planEl.textContent = "No Active Plan";
        planEl.style.color = "var(--warning)";
    }
}

function renderClaimsHistory(claims) {
    const tbody = document.getElementById("claims-tbody");
    if (!tbody) return;

    if (!claims.length) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted)">No claims yet - you are perfectly safe.</td></tr>';
        return;
    }

    tbody.innerHTML = claims.map((claim) => {
        const statusHtml =
            claim.status === "APPROVED" ? '<span style="color:var(--success)">APPROVED</span>' :
            claim.status === "HOLD" ? '<span style="color:var(--warning)">HOLD</span>' :
            '<span style="color:var(--danger)">REJECTED</span>';

        return `<tr>
            <td>${timeAgo(claim.timestamp)}</td>
            <td>${claim.trigger_type}</td>
            <td>Rs${Number(claim.amount).toLocaleString("en-IN")}</td>
            <td>${statusHtml}</td>
        </tr>`;
    }).join("");
}

function setSkeletons(active) {
    const ids = [
        "risk-value",
        "risk-label",
        "weather-temp",
        "weather-rain",
        "weather-wind",
        "weather-aqi",
        "weather-humidity",
        "wallet-balance",
        "trust-score-badge",
    ];

    ids.forEach((id) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (active) {
            el.classList.add("skeleton");
        } else {
            el.classList.remove("skeleton");
        }
    });
}

function addFundsPrompt() {
    const modal = document.getElementById("fund-modal");
    if (modal) modal.style.display = "flex";
}

function closeFundModal() {
    const modal = document.getElementById("fund-modal");
    if (modal) modal.style.display = "none";
}

// ─── Withdrawal ────────────────────────────────────────────────────────────────

function openWithdrawModal() {
    const modal = document.getElementById("withdraw-modal");
    if (!modal) return;

    // Pre-fill UPI from profile if available
    const upiInput = document.getElementById("withdraw-upi");
    const upiNote  = document.getElementById("withdraw-upi-note");
    if (upiInput && window.currentUser?.upi) {
        upiInput.value = window.currentUser.upi;
        if (upiNote) upiNote.style.display = "block";
    } else if (upiInput) {
        upiInput.value = "";
    }

    // Pre-fill max or a sensible default amount
    const amtInput = document.getElementById("withdraw-amount");
    if (amtInput) {
        const bal = parseFloat(
            document.getElementById("wallet-balance")?.textContent?.replace(/[^0-9.]/g, "") || 0
        );
        amtInput.value = bal > 0 ? Math.min(bal, 10000).toFixed(2) : "";
    }

    modal.style.display = "flex";
}

function closeWithdrawModal() {
    const modal = document.getElementById("withdraw-modal");
    if (modal) modal.style.display = "none";
}

async function submitWithdrawal() {
    const amtRaw = document.getElementById("withdraw-amount")?.value?.trim();
    const upiRaw = document.getElementById("withdraw-upi")?.value?.trim();

    const amount = parseFloat(amtRaw);
    if (!amtRaw || isNaN(amount) || amount < 10) {
        showToast("Minimum withdrawal amount is \u20b910", "error");
        return;
    }
    if (amount > 10000) {
        showToast("Maximum withdrawal per request is \u20b910,000", "error");
        return;
    }
    if (!upiRaw || !upiRaw.includes("@")) {
        showToast("Enter a valid UPI ID (e.g. name@upi)", "error");
        return;
    }

    // Quick client-side balance check
    const displayedBal = parseFloat(
        document.getElementById("wallet-balance")?.textContent?.replace(/[^0-9.]/g, "") || 0
    );
    if (amount > displayedBal + 0.01) {
        showToast(`Insufficient balance. Available: \u20b9${displayedBal.toLocaleString("en-IN")}`, "error");
        return;
    }

    // Disable button to prevent double-submit
    const btn = document.getElementById("withdraw-submit-btn");
    if (btn) { btn.disabled = true; btn.textContent = "Processing..."; }

    closeWithdrawModal();
    showToast("Initiating withdrawal...", "info");

    const res = await apiFetch("/payment/withdraw", {
        method: "POST",
        body: JSON.stringify({ amount, upi_id: upiRaw }),
    });

    if (btn) { btn.disabled = false; btn.textContent = "Withdraw"; }

    if (!res) {
        showToast("Network error. Please try again.", "error");
        return;
    }

    const data = await res.json();
    if (res.ok) {
        showToast(data.message, "success");
        updateWalletCard({ balance: data.new_balance });
        // Persist UPI on the currentUser object so next open pre-fills it
        if (window.currentUser) window.currentUser.upi = upiRaw;
    } else {
        showToast(data.detail || "Withdrawal failed. Please try again.", "error");
        openWithdrawModal(); // re-open so user can correct input
    }
}

async function processAddFunds() {
    const amtInput = document.getElementById("fund-amount");
    const amt = amtInput ? amtInput.value : null;
    const parsedAmount = parseFloat(amt);

    if (!amt || isNaN(amt) || parsedAmount <= 0) {
        showToast("Enter a valid amount", "error");
        return;
    }

    closeFundModal();
    showToast("Opening payment...", "info");

    const orderRes = await apiFetch("/payment/create-wallet-order", {
        method: "POST",
        body: JSON.stringify({ amount: parsedAmount }),
    });
    if (!orderRes || !orderRes.ok) {
        showToast("Failed to create order. Check payment gateway config.", "error");
        return;
    }

    const order = await orderRes.json();
    if (!order.key_id) {
        const fallback = await runLocalPaymentFallback("wallet_topup", { amount: parsedAmount });
        if (fallback) {
            updateWalletCard({ balance: fallback.new_balance });
            return;
        }

        showToast("Razorpay credentials are not configured in the backend.", "error");
        return;
    }

    const options = {
        key: order.key_id,
        amount: order.amount,
        currency: "INR",
        name: "SafeFlow Wallet",
        description: `Wallet Top-up: Rs${parsedAmount}`,
        order_id: order.order_id,
        theme: { color: "#10B981" },
        prefill: {
            name: window.currentUser ? window.currentUser.name : "",
            contact: window.currentUser ? window.currentUser.phone : "",
        },
        handler: async function (response) {
            showToast("Verifying payment...", "info");
            const verifyRes = await apiFetch("/payment/verify-wallet", {
                method: "POST",
                body: JSON.stringify({
                    razorpay_order_id: response.razorpay_order_id,
                    razorpay_payment_id: response.razorpay_payment_id,
                    razorpay_signature: response.razorpay_signature,
                    amount: parsedAmount,
                }),
            });

            if (verifyRes && verifyRes.ok) {
                const data = await verifyRes.json();
                updateWalletCard({ balance: data.new_balance });
                showToast(data.message, "success");
            } else {
                showToast("Payment verification failed", "error");
            }
        },
        modal: {
            ondismiss: () => showToast("Payment cancelled", "error"),
        },
    };

    const result = await openRazorpayCheckout(options, "wallet_topup", { amount: parsedAmount });
    if (result?.usedFallback) {
        updateWalletCard({ balance: result.data.new_balance });
    }
}

if (window.location.pathname.includes("dashboard.html")) {
    window.addEventListener("DOMContentLoaded", loadDashboard);
    setInterval(loadDashboard, Config.REFRESH_INTERVAL);
}

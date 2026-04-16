/**
 * SafeFlow.ai - Payment module
 * Razorpay checkout integration with localhost-safe demo fallback.
 */

let razorpaySdkPromise = null;

function isLocalDemoPaymentAllowed() {
    const host = window.location.hostname;
    const phone = (window.currentUser?.phone || "").trim();
    return ["127.0.0.1", "localhost"].includes(host) &&
        ["9999999999", "+919999999999"].includes(phone);
}

async function ensureRazorpayCheckoutLoaded() {
    if (typeof window.Razorpay === "function") return true;

    if (!razorpaySdkPromise) {
        razorpaySdkPromise = new Promise((resolve) => {
            const existing = document.getElementById("razorpay-checkout-sdk");
            if (existing) {
                existing.addEventListener("load", () => resolve(typeof window.Razorpay === "function"), { once: true });
                existing.addEventListener("error", () => resolve(false), { once: true });
                return;
            }

            const script = document.createElement("script");
            script.id = "razorpay-checkout-sdk";
            script.src = "https://checkout.razorpay.com/v1/checkout.js";
            script.async = true;
            script.onload = () => resolve(typeof window.Razorpay === "function");
            script.onerror = () => resolve(false);
            document.head.appendChild(script);

            setTimeout(() => resolve(typeof window.Razorpay === "function"), 7000);
        }).finally(() => {
            if (typeof window.Razorpay !== "function") {
                razorpaySdkPromise = null;
            }
        });
    }

    return razorpaySdkPromise;
}

async function runLocalPaymentFallback(kind, payload) {
    if (!isLocalDemoPaymentAllowed()) return null;

    const res = await apiFetch("/payment/dev-complete", {
        method: "POST",
        body: JSON.stringify({ kind, ...payload }),
    });
    if (!res) return null;

    const data = await res.json();
    if (!res.ok) {
        showToast(data.detail || "Local demo payment failed", "error");
        return null;
    }

    showToast(data.message, "success");
    return data;
}

async function openRazorpayCheckout(options, fallbackKind, fallbackPayload) {
    const sdkLoaded = await ensureRazorpayCheckoutLoaded();
    if (!sdkLoaded) {
        const fallback = await runLocalPaymentFallback(fallbackKind, fallbackPayload);
        if (fallback) return { usedFallback: true, data: fallback };

        showToast("Razorpay checkout could not load. Disable ad blockers or retry from localhost.", "error");
        return { usedFallback: false };
    }

    try {
        const rzp = new Razorpay(options);
        if (typeof rzp.on === "function") {
            rzp.on("payment.failed", (event) => {
                showToast(event?.error?.description || "Payment failed. Please retry.", "error");
            });
        }
        rzp.open();
        return { usedFallback: false };
    } catch (_) {
        const fallback = await runLocalPaymentFallback(fallbackKind, fallbackPayload);
        if (fallback) return { usedFallback: true, data: fallback };

        showToast("Unable to open Razorpay checkout. Disable browser blockers and try again.", "error");
        return { usedFallback: false };
    }
}

async function purchasePlan(planType) {
    const cfgRes = await apiFetch("/payment/config");
    if (!cfgRes || !cfgRes.ok) {
        showToast("Payment gateway unavailable", "error");
        return;
    }
    const { key_id } = await cfgRes.json();

    if (!key_id) {
        return walletPay(planType);
    }

    showToast("Opening payment...", "info");

    const orderRes = await apiFetch("/payment/create-order", {
        method: "POST",
        body: JSON.stringify({ plan_type: planType }),
    });
    if (!orderRes || !orderRes.ok) {
        const err = orderRes ? await orderRes.json() : {};
        showToast(err.detail || "Failed to create order", "error");
        return;
    }
    const order = await orderRes.json();

    const options = {
        key: key_id,
        amount: order.amount,
        currency: "INR",
        name: "SafeFlow.ai",
        description: `${planType} Insurance Plan - Weekly Premium`,
        order_id: order.order_id,
        theme: { color: "#6366F1" },
        prefill: {
            name: window.currentUser ? window.currentUser.name : "",
            contact: window.currentUser ? window.currentUser.phone : "",
        },
        handler: async function (response) {
            await verifyPayment(response, planType);
        },
        modal: {
            ondismiss: () => showToast("Payment cancelled", "error"),
        },
    };

    const result = await openRazorpayCheckout(options, "policy_purchase", { plan_type: planType });
    if (result?.usedFallback) {
        setTimeout(() => { window.location.href = "dashboard.html"; }, 1200);
    }
}

async function verifyPayment(rzpResponse, planType) {
    showToast("Verifying payment...", "info");
    const res = await apiFetch("/payment/verify", {
        method: "POST",
        body: JSON.stringify({
            razorpay_order_id: rzpResponse.razorpay_order_id,
            razorpay_payment_id: rzpResponse.razorpay_payment_id,
            razorpay_signature: rzpResponse.razorpay_signature,
            plan_type: planType,
        }),
    });
    if (!res) return;

    const data = await res.json();
    if (res.ok) {
        showToast(data.message, "success");
        setTimeout(() => { window.location.href = "dashboard.html"; }, 1200);
    } else {
        showToast(data.detail || "Payment verification failed", "error");
    }
}

async function walletPay(planType) {
    if (!confirm(`Pay for ${planType} plan using your wallet balance?`)) return;

    const res = await apiFetch("/payment/wallet-pay", {
        method: "POST",
        body: JSON.stringify({ plan_type: planType }),
    });
    if (!res) return;

    const data = await res.json();
    if (res.ok) {
        showToast(data.message, "success");
        setTimeout(() => { window.location.href = "dashboard.html"; }, 1200);
    } else {
        showToast(data.detail || "Wallet payment failed", "error");
    }
}

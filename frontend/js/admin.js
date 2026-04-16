/**
 * SafeFlow.ai — Admin Operations Console
 */

async function loadAdmin() {
    try {
        const [overviewRes, fraudRes, poolRes] = await Promise.all([
            apiFetch("/admin/overview"),
            apiFetch("/admin/fraud-panel"),
            apiFetch("/admin/pool-health"),
        ]);

        if (!overviewRes || !overviewRes.ok) { showToast("Admin session expired", "error"); return; }

        const over  = await overviewRes.json();
        const fraud = fraudRes  && fraudRes.ok  ? await fraudRes.json()  : [];
        const pool  = poolRes   && poolRes.ok   ? await poolRes.json()   : [];

        // KPI cards
        const setKPI = (id, val) => { const el = document.getElementById(id); if (el) el.textContent = val; };
        setKPI("stat-workers",  (over.workers        ?? 0).toLocaleString());
        setKPI("stat-policies", (over.active_policies ?? 0).toLocaleString());
        setKPI("stat-claims",   (over.claims_today    ?? 0).toLocaleString());
        setKPI("stat-fraud",    (over.fraud_alerts    ?? 0).toLocaleString());
        setKPI("stat-premiums", `₹${(over.total_premiums ?? 0).toLocaleString("en-IN")}`);
        setKPI("stat-payouts",  `₹${(over.total_payouts  ?? 0).toLocaleString("en-IN")}`);
        setKPI("stat-pool",     `${over.pool_health ?? 2.0}x`);

        const fraudEl = document.getElementById("stat-fraud");
        if (fraudEl && (over.fraud_alerts ?? 0) > 0) {
            fraudEl.parentElement.classList.add("animate-pulse-red");
        }

        renderFraudTable(fraud);
        renderPoolHealth(pool);
        loadWithdrawals();          // ← load withdrawals alongside everything else

    } catch (err) {
        console.error("Admin load error:", err);
    }
}

// ─── Withdrawal Management ────────────────────────────────────────────────────

async function loadWithdrawals() {
    const tbody   = document.getElementById("withdrawals-tbody");
    const summary = document.getElementById("withdrawal-summary");
    if (!tbody) return;

    tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">Loading…</td></tr>';

    const res = await apiFetch("/admin/withdrawals");
    if (!res || !res.ok) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--danger);padding:20px">Failed to load withdrawals.</td></tr>';
        return;
    }

    const withdrawals = await res.json();
    if (!withdrawals.length) {
        tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:20px">No withdrawal requests yet.</td></tr>';
        if (summary) summary.textContent = "";
        return;
    }

    const pending      = withdrawals.filter(w => w.status === "pending");
    const pendingTotal = pending.reduce((s, w) => s + w.amount, 0);

    tbody.innerHTML = withdrawals.map(w => {
        const isPending  = w.status === "pending";
        const statusColor = isPending ? "#F59E0B" : "#10B981";
        const statusLabel = isPending ? "⏳ Pending" : "✅ Completed";
        const date        = w.created_at
            ? new Date(w.created_at).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" })
            : "—";

        return `<tr style="border-bottom:1px solid var(--glass-border)">
          <td style="padding:10px;font-family:'JetBrains Mono',monospace;font-size:0.8rem">${w.ref.slice(0,12)}…</td>
          <td style="padding:10px">
            <div style="font-weight:600">${w.worker_name}</div>
            <div style="font-size:0.78rem;color:var(--text-muted)">${w.worker_phone}</div>
          </td>
          <td style="padding:10px;font-size:0.85rem;color:var(--primary)">${w.upi_id || '<span style="color:var(--text-muted)">—</span>'}</td>
          <td style="padding:10px;text-align:right;font-weight:700">₹${w.amount.toLocaleString("en-IN")}</td>
          <td style="padding:10px"><span style="color:${statusColor};font-weight:600">${statusLabel}</span></td>
          <td style="padding:10px;font-size:0.8rem;color:var(--text-muted)">${date}</td>
          <td style="padding:10px;text-align:center">
            ${isPending
              ? `<button class="btn-primary" style="padding:6px 14px;font-size:0.8rem;background:var(--success);border-color:var(--success)"
                   onclick="approveWithdrawal('${w.ref}')">Mark Paid</button>`
              : `<span style="color:var(--text-muted);font-size:0.8rem">—</span>`
            }
          </td>
        </tr>`;
    }).join("");

    if (summary) {
        if (pending.length > 0) {
            summary.innerHTML = `<span style="color:var(--warning)">⚠️ ${pending.length} pending request${pending.length > 1 ? "s" : ""} totalling <b>₹${pendingTotal.toLocaleString("en-IN")}</b> awaiting payout.</span>`;
        } else {
            summary.innerHTML = `<span style="color:var(--success)">✅ All withdrawal requests have been processed.</span>`;
        }
    }
}

async function approveWithdrawal(ref) {
    if (!confirm(`Mark withdrawal ${ref.slice(0,12)}… as paid? This cannot be undone.`)) return;

    const res = await apiFetch(`/admin/withdrawals/${ref}/approve`, { method: "POST" });
    if (!res) return;
    const data = await res.json();
    if (res.ok) {
        showToast(data.message, "success");
        loadWithdrawals();   // refresh table only (fast)
    } else {
        showToast(data.detail || "Failed to approve withdrawal.", "error");
    }
}

function renderFraudTable(cases) {
    const tbody = document.getElementById("fraud-tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!cases.length) {
        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center;color:var(--text-muted)">No workers registered yet.</td></tr>';
        return;
    }
    cases.forEach(c => {
        const sc     = c.fraud_score;
        const color  = sc >= 7 ? "#EF4444" : sc >= 4 ? "#F59E0B" : "#10B981";
        const partId = c.device_id ? c.device_id.substring(0, 12) + "…" : "—";
        tbody.innerHTML += `
        <tr style="border-left:4px solid ${color}">
          <td>
            <div style="font-weight:600">${c.worker_name}</div>
            <div style="font-size:0.78rem;color:var(--text-muted)">
              ID: ${c.id} | Trust: ${c.trust_score}/100 | Claims: ${c.claim_count ?? 0}<br>
              <span style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;background:rgba(0,0,0,0.06);padding:1px 4px;border-radius:3px">
                Device: ${partId}
              </span>
            </div>
          </td>
          <td>${c.city}</td>
          <td><b style="color:${color}">${sc}/10</b></td>
          <td>${c.flags.map(f => `<span class="badge" style="background:#EEF2FF;color:#0F172A">${f.flag}</span>`).join(" ")}</td>
          <td>
            <button class="btn-ghost" style="padding:4px 10px" onclick="actionClaim('${c.id}','APPROVE')">✓</button>
            ${(c.status === "HOLD" || c.status === "PARTIAL") ?
              `<button class="btn-ghost" style="padding:4px 10px;color:var(--danger);border-color:var(--danger)" onclick="actionClaim('${c.id}','REJECT')">✗</button>` : ""}
          </td>
        </tr>`;
    });
}

function renderPoolHealth(pools) {
    const tbody = document.getElementById("pool-tbody");
    if (!tbody || !pools.length) return;
    tbody.innerHTML = "";
    pools.forEach(p => {
        const color  = p.reserve_ratio >= 1.5 ? "#10B981" : p.reserve_ratio >= 1.0 ? "#F59E0B" : "#EF4444";
        const bar    = Math.min(100, Math.round(p.reserve_ratio * 50));
        tbody.innerHTML += `
        <tr>
          <td>${p.city}</td>
          <td>₹${p.total_premiums.toLocaleString("en-IN")}</td>
          <td>₹${p.total_payouts.toLocaleString("en-IN")}</td>
          <td>
            <div style="display:flex;align-items:center;gap:8px">
              <div style="flex:1;height:6px;background:rgba(0,0,0,0.1);border-radius:3px">
                <div style="width:${bar}%;height:100%;background:${color};border-radius:3px"></div>
              </div>
              <span style="color:${color};font-weight:600">${p.reserve_ratio}x</span>
            </div>
          </td>
          <td><span style="color:${color}">${p.status}</span></td>
        </tr>`;
    });
}

async function actionClaim(id, action) {
    const res = await apiFetch(`/admin/action/${id}`, {
        method: "POST",
        body: JSON.stringify({ action }),
    });
    if (res && res.ok) {
        showToast("Action applied.", "success");
        loadAdmin();
    }
}

async function simulateEvent() {
    const city       = document.getElementById("sim-city").value;
    const disruption = document.getElementById("sim-disruption").value;
    const intensity  = document.getElementById("sim-intensity").value;
    if (!city || !disruption) return showToast("Fill all simulation fields", "error");

    const res = await apiFetch("/admin/simulate", {
        method: "POST",
        body: JSON.stringify({ city, disruption, intensity }),
    });
    if (!res) return;
    const data = await res.json();
    if (res.ok) {
        showToast(`✅ ${data.message}`, "success");
        loadAdmin();
    } else {
        showToast(data.detail || "Simulation failed", "error");
    }
}

if (window.location.pathname.includes("admin.html")) {
    window.addEventListener("DOMContentLoaded", loadAdmin);
}

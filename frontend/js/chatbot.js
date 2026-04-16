/**
 * SafeFlow.ai — AI Chatbot (NVIDIA Mistral via backend)
 */

function toggleChat() {
    const panel = document.getElementById("chat-panel");
    if (!panel) return;
    const isHidden = panel.style.display === "none" || !panel.style.display;
    panel.style.display = isHidden ? "flex" : "none";
    if (isHidden && document.getElementById("chat-body").innerHTML.trim() === "") {
        appendBot("Hi! I'm your SafeFlow.ai assistant. Ask me about your coverage, claims, trust score, or plans. 🛡️");
    }
}

async function sendChat(msg = null) {
    const input = document.getElementById("chat-input");
    const text  = (msg || (input ? input.value : "")).trim();
    if (!text) return;
    if (input) input.value = "";

    appendUser(text);

    const typingId = "typing-" + Date.now();
    appendTyping(typingId);

    try {
        const res = await apiFetch("/chatbot/chat", {
            method: "POST",
            body: JSON.stringify({ message: text }),
        });
        removeTyping(typingId);
        if (res && res.ok) {
            const data = await res.json();
            appendBot(data.reply || "No response received.");
        } else {
            appendBot("Sorry, I couldn't reach the AI right now. Try again shortly.");
        }
    } catch (_) {
        removeTyping(typingId);
        appendBot("Network error. Please check your connection.");
    }
}

function appendUser(text) {
    const body = document.getElementById("chat-body");
    if (!body) return;
    body.innerHTML += `<div style="text-align:right;margin:8px 0">
        <span style="background:var(--primary);color:#fff;padding:6px 12px;border-radius:12px 12px 2px 12px;font-size:0.88rem;display:inline-block">${escapeHtml(text)}</span>
    </div>`;
    body.scrollTop = body.scrollHeight;
}

function appendBot(text) {
    const body = document.getElementById("chat-body");
    if (!body) return;
    body.innerHTML += `<div style="text-align:left;margin:8px 0">
        <span style="background:var(--bg-tertiary);padding:6px 12px;border-radius:12px 12px 12px 2px;font-size:0.88rem;display:inline-block;max-width:90%">${text}</span>
    </div>`;
    body.scrollTop = body.scrollHeight;
}

function appendTyping(id) {
    const body = document.getElementById("chat-body");
    if (!body) return;
    body.innerHTML += `<div id="${id}" style="text-align:left;margin:8px 0;color:var(--text-muted);font-size:0.85rem">SafeFlow.ai is typing…</div>`;
    body.scrollTop = body.scrollHeight;
}

function removeTyping(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
}

function escapeHtml(str) {
    return str.replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

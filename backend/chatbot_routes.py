"""
Chatbot Routes — NVIDIA NIM (Mistral) powered assistant.
Falls back to rule-based responses if API key missing.
"""

import os
import logging
import requests
from fastapi import APIRouter
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()

logger  = logging.getLogger("chatbot_routes")
router  = APIRouter(prefix="/api/chatbot", tags=["chatbot"])

NVIDIA_API_KEY  = os.getenv("NVIDIA_API_KEY", "")
NVIDIA_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
# Model name verified against NVIDIA NIM catalogue
NVIDIA_MODEL    = "mistralai/mistral-7b-instruct-v0.3"

SYSTEM_PROMPT = """You are the SafeFlow.ai assistant — a helpful, empathetic guide for gig delivery workers in India.
You explain parametric insurance, weather-based coverage, trust scores, and instant wallet payouts in simple language.
Respond in 2–3 short sentences. Be warm, practical, and use ₹ for amounts. Switch to Hindi if the user writes in Hindi."""

# Rule-based fallback responses for common queries
_FALLBACK = {
    "claim":    "Your claim is processed automatically when weather crosses your plan threshold — no paperwork needed! Check your wallet for the credited amount.",
    "otp":      "Use phone 9999900001 with OTP 123456 for the demo. For real registration, enter your phone and we'll send an OTP.",
    "plan":     "We offer Basic (₹49/week, ₹500 payout), Standard (₹99/week, ₹1000 payout), and Premium (₹199/week, ₹2000 payout). Choose based on your daily income risk.",
    "rain":     "Your plan triggers automatically when rainfall exceeds your threshold. Premium plan covers ≥25mm, Standard ≥35mm, Basic ≥50mm.",
    "trust":    "Trust score reflects your account credibility. Honest claims improve it; suspicious activity lowers it. A score above 80 is healthy.",
    "wallet":   "Your wallet receives automatic payouts when triggers fire. Add funds via Razorpay to pay your weekly premium.",
    "default":  "I'm here to help with your SafeFlow.ai insurance coverage! Ask me about plans, claims, payouts, or your risk score.",
}


from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=500)


@router.post("/chat")
def chat_with_bot(req: ChatRequest):
    if not NVIDIA_API_KEY:
        return {"reply": _rule_based_reply(req.message)}

    try:
        resp = requests.post(
            NVIDIA_ENDPOINT,
            headers={"Authorization": f"Bearer {NVIDIA_API_KEY}", "Accept": "application/json"},
            json={
                "model":       NVIDIA_MODEL,
                "messages":    [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user",   "content": req.message},
                ],
                "max_tokens":  180,
                "temperature": 0.3,
                "top_p":       0.9,
                "stream":      False,
            },
            timeout=10,
        )
        resp.raise_for_status()
        reply = resp.json()["choices"][0]["message"]["content"]
        return {"reply": reply}

    except Exception as e:
        logger.error(f"[Chatbot] NVIDIA API error: {e}")
        return {"reply": _rule_based_reply(req.message)}


def _rule_based_reply(message: str) -> str:
    msg = message.lower()
    for keyword, response in _FALLBACK.items():
        if keyword in msg:
            return response
    return _FALLBACK["default"]

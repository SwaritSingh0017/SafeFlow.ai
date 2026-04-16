"""
Shared constants for SafeFlow.ai backend.
Single source of truth — no duplication across routes.
"""

CITY_CENTERS = {
    "Mumbai":        {"lat": 19.0760, "lon": 72.8777, "aqi_baseline": 150, "claim_rate": 0.70},
    "Delhi":         {"lat": 28.7041, "lon": 77.1025, "aqi_baseline": 250, "claim_rate": 0.65},
    "Bangalore":     {"lat": 12.9716, "lon": 77.5946, "aqi_baseline": 80,  "claim_rate": 0.40},
    "Chennai":       {"lat": 13.0827, "lon": 80.2707, "aqi_baseline": 90,  "claim_rate": 0.50},
    "Pune":          {"lat": 18.5204, "lon": 73.8567, "aqi_baseline": 100, "claim_rate": 0.42},
    "Hyderabad":     {"lat": 17.3850, "lon": 78.4867, "aqi_baseline": 110, "claim_rate": 0.45},
    "Kolkata":       {"lat": 22.5726, "lon": 88.3639, "aqi_baseline": 180, "claim_rate": 0.65},
    "Ahmedabad":     {"lat": 23.0225, "lon": 72.5714, "aqi_baseline": 130, "claim_rate": 0.48},
    "Surat":         {"lat": 21.1702, "lon": 72.8311, "aqi_baseline": 120, "claim_rate": 0.44},
    "Jaipur":        {"lat": 26.9124, "lon": 75.7873, "aqi_baseline": 140, "claim_rate": 0.47},
    "Lucknow":       {"lat": 26.8467, "lon": 80.9462, "aqi_baseline": 160, "claim_rate": 0.55},
    "Kanpur":        {"lat": 26.4499, "lon": 80.3319, "aqi_baseline": 170, "claim_rate": 0.57},
    "Nagpur":        {"lat": 21.1458, "lon": 79.0882, "aqi_baseline": 110, "claim_rate": 0.43},
    "Indore":        {"lat": 22.7196, "lon": 75.8577, "aqi_baseline": 105, "claim_rate": 0.42},
    "Thane":         {"lat": 19.2183, "lon": 72.9781, "aqi_baseline": 145, "claim_rate": 0.60},
    "Bhopal":        {"lat": 23.2599, "lon": 77.4126, "aqi_baseline": 115, "claim_rate": 0.44},
    "Visakhapatnam": {"lat": 17.6868, "lon": 83.2185, "aqi_baseline": 95,  "claim_rate": 0.41},
    "Patna":         {"lat": 25.5941, "lon": 85.1376, "aqi_baseline": 190, "claim_rate": 0.60},
    "Vadodara":      {"lat": 22.3072, "lon": 73.1812, "aqi_baseline": 115, "claim_rate": 0.43},
    "Ghaziabad":     {"lat": 28.6692, "lon": 77.4538, "aqi_baseline": 220, "claim_rate": 0.62},
    "Ludhiana":      {"lat": 30.9010, "lon": 75.8573, "aqi_baseline": 155, "claim_rate": 0.50},
    "Agra":          {"lat": 27.1767, "lon": 78.0081, "aqi_baseline": 145, "claim_rate": 0.48},
    "Nashik":        {"lat": 19.9975, "lon": 73.7898, "aqi_baseline": 95,  "claim_rate": 0.40},
    "Ranchi":        {"lat": 23.3441, "lon": 85.3096, "aqi_baseline": 100, "claim_rate": 0.41},
    "Bhubaneswar":   {"lat": 20.2961, "lon": 85.8245, "aqi_baseline": 90,  "claim_rate": 0.39},
    "Guwahati":      {"lat": 26.1445, "lon": 91.7362, "aqi_baseline": 100, "claim_rate": 0.42},
    "Chandigarh":    {"lat": 30.7333, "lon": 76.7794, "aqi_baseline": 120, "claim_rate": 0.45},
    "Coimbatore":    {"lat": 11.0168, "lon": 76.9558, "aqi_baseline": 85,  "claim_rate": 0.38},
    "Kochi":         {"lat":  9.9312, "lon": 76.2673, "aqi_baseline": 80,  "claim_rate": 0.45},
    "Dehradun":      {"lat": 30.3165, "lon": 78.0322, "aqi_baseline": 90,  "claim_rate": 0.38},
}

# GPS boundary threshold in degrees-squared (~80km radius)
GPS_BOUNDARY_THRESHOLD = 0.52

# Insurance plan definitions — single source of truth
INSURANCE_PLANS = {
    "Basic": {
        "weekly_premium":  49,
        "max_payout":     500,
        "rain_threshold":  50,   # mm
        "heat_threshold":  43,   # °C
        "aqi_threshold":  300,
        "civil_coverage": False,
        "features": ["Rain coverage", "Basic payout ₹500", "24hr support"]
    },
    "Standard": {
        "weekly_premium":  99,
        "max_payout":    1000,
        "rain_threshold":  35,
        "heat_threshold":  40,
        "aqi_threshold":  200,
        "civil_coverage": True,
        "features": ["Rain + Heat + AQI coverage", "₹1000 payout", "Priority support", "Civil disruption coverage"]
    },
    "Premium": {
        "weekly_premium": 199,
        "max_payout":    2000,
        "rain_threshold":  25,
        "heat_threshold":  38,
        "aqi_threshold":  150,
        "civil_coverage": True,
        "features": ["All coverage", "₹2000 payout", "Instant payout", "Dedicated support", "Flood + Strike coverage"]
    },
}

# Demo bypass phones — always work with OTP 123456
DEMO_PHONES = {
    "9999900001",
    "9999900002",
    "9999900003",
    "9999999999",
    "+919999900001",
    "+919999900002",
    "+919999900003",
    "+919999999999",
}
DEMO_OTP = "123456"

# Admin credentials — loaded from env, these are defaults only
ADMIN_EMAIL_DEFAULT    = "admin@safeflow.ai"
ADMIN_PASSWORD_DEFAULT = "Admin@2026"

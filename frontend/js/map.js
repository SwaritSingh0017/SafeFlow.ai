const CITY_COORDS = {
    "Mumbai": [19.0760, 72.8777], "Delhi": [28.7041, 77.1025],
    "Bangalore": [12.9716, 77.5946], "Chennai": [13.0827, 80.2707],
    "Pune": [18.5204, 73.8567], "Hyderabad": [17.3850, 78.4867],
    "Kolkata": [22.5726, 88.3639]
};

function getRiskColor(score) {
    if (score >= 8) return '#EF4444';
    if (score >= 6) return '#F59E0B';
    if (score >= 4) return '#EA580C';
    return '#10B981';
}

function initAdminRiskMap() {
    const cont = document.getElementById('admin-risk-map');
    if (!cont) return;
    if(window._adminMap) window._adminMap.remove();

    const map = L.map('admin-risk-map').setView([20.5937, 78.9629], 5);
    window._adminMap = map;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; OpenStreetMap'
    }).addTo(map);

    setTimeout(() => map.invalidateSize(), 500);

    apiFetch('/admin/city-risks').then(r => {
        if (!r) return [];
        return r.json();
    }).then(cities => {
        if (!Array.isArray(cities)) return;
        cities.forEach(city => {
            const color = getRiskColor(city.risk_score);
            const size = 20 + (city.active_workers / 50);

            const marker = L.circleMarker([city.lat, city.lon], {
                radius: size, fillColor: color, color: color,
                weight: 2, opacity: 0.9, fillOpacity: 0.35
            }).addTo(map);

            marker.bindPopup(`
                <div class="map-popup">
                    <h4 style="margin:0 0 4px">${city.name}</h4>
                    <span class="badge" style="background:${color};color:white;margin-bottom:8px">Risk: ${city.risk_score}/10</span>
                    <br/>Workers: <b>${city.active_workers}</b>
                    <br/>Claims: <b>${city.claims_today}</b>
                </div>
            `);
        });
    }).catch(err => console.error("Map fetch error:", err));
}

function initWorkerMiniMap(workerCity) {
    const coords = CITY_COORDS[workerCity] || [28.7041, 77.1025];
    const mapCont = document.getElementById('worker-mini-map');
    if (!mapCont) return;

    if (window._miniMap) window._miniMap.remove();
    const map = L.map('worker-mini-map', {
        center: coords, zoom: 11, zoomControl: false, dragging: true, scrollWheelZoom: false
    });
    window._miniMap = map;

    L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', { attribution: false }).addTo(map);

    if (window._gpsLat && window._gpsLat !== "0") {
        L.circleMarker([window._gpsLat, window._gpsLon], {
            radius: 8, color: '#F97316', fillColor: '#F97316', fillOpacity: 0.8
        }).addTo(map);
    }

    apiFetch(`/risk?city=${workerCity}`).then(r => r.json()).then(risk => {
        L.circle(coords, {
            radius: 12000, fillColor: getRiskColor(risk.score),
            fillOpacity: 0.15, color: getRiskColor(risk.score), weight: 1
        }).addTo(map);
    });
}

window.initAdminRiskMap = initAdminRiskMap;
window.initWorkerMiniMap = initWorkerMiniMap;

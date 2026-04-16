/**
 * DISRUPTION SIMULATOR ENGINE
 * This module allows admins to trigger parametric 'weather events' and 'risk surges'.
 * In standalone mode, it updates the global MOCK_STATE to demonstrate reactive UI changes.
 * 
 * Logic:
 * 1. Admin selects a city, event type, and intensity.
 * 2. Payload is sent to the mock /simulate/trigger endpoint.
 * 3. The mock engine updates current weather and risk scores.
 * 4. Dashboards (like the Radar map) reactively show the updated data.
 */
async function triggerSimulation() {
    const btn = document.getElementById('sim-btn');
    if(!btn) return;
    btn.innerText = "Triggering...";
    btn.disabled = true;
    
    const city = document.getElementById('sim-city').value;
    const disruption = document.getElementById('sim-disruption').value;
    const intensity = document.getElementById('sim-intensity').value;

    try {
        const res = await apiFetch('/admin/simulate', {
            method: 'POST',
            body: JSON.stringify({ city, disruption, intensity })
        });
        
        btn.innerText = "Trigger Simulation";
        btn.disabled = false;
        
        if (res && res.ok) {
            const data = await res.json();
            showToast(data.message, "success");
            if (window.loadAdmin) window.loadAdmin();
            if (window.initAdminRiskMap) window.initAdminRiskMap();
        } else {
            showToast("Simulation failed.", "error");
        }
    } catch(err) {
        console.error(err);
        btn.innerText = "Trigger Simulation";
        btn.disabled = false;
    }
}

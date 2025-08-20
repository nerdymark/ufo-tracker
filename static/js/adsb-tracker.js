/**
 * ADSB Flight Tracker - Frontend JavaScript
 * Fetches and displays flight data from local PiAware SkyAware
 */

let adsbTracker = {
    enabled: false,
    lastUpdate: null,
    flights: [],
    updateInterval: null,
    refreshRate: 15000, // 15 seconds
    maxDisplayFlights: 20
};

/**
 * Initialize ADSB flight tracker
 */
function initializeADSBTracker() {
    console.log('Initializing ADSB flight tracker...');
    
    // Test connection first
    testADSBConnection()
        .then(success => {
            if (success) {
                startADSBUpdates();
                showMessage('ADSB flight tracker initialized successfully', 'success');
            } else {
                showMessage('ADSB flight tracker failed to connect to PiAware', 'warning');
            }
        })
        .catch(error => {
            console.error('Error initializing ADSB tracker:', error);
            showMessage('Error initializing ADSB flight tracker', 'error');
        });
}

/**
 * Test connection to PiAware SkyAware
 */
async function testADSBConnection() {
    try {
        const response = await fetch('/api/adsb/test_connection');
        const data = await response.json();
        
        if (data.success) {
            console.log('✅ ADSB Connection OK:', data.message);
            updateADSBConnectionStatus(true, data.message);
            return true;
        } else {
            console.warn('❌ ADSB Connection Failed:', data.error);
            updateADSBConnectionStatus(false, data.error);
            return false;
        }
    } catch (error) {
        console.error('💥 ADSB Connection Error:', error);
        updateADSBConnectionStatus(false, 'Network error: ' + error.message);
        return false;
    }
}

/**
 * Start periodic ADSB updates
 */
function startADSBUpdates() {
    if (adsbTracker.updateInterval) {
        clearInterval(adsbTracker.updateInterval);
    }
    
    // Initial fetch
    fetchADSBFlights();
    
    // Set up periodic updates
    adsbTracker.updateInterval = setInterval(() => {
        fetchADSBFlights();
    }, adsbTracker.refreshRate);
    
    adsbTracker.enabled = true;
    console.log('🛩️ ADSB updates started (every', adsbTracker.refreshRate / 1000, 'seconds)');
}

/**
 * Stop ADSB updates
 */
function stopADSBUpdates() {
    if (adsbTracker.updateInterval) {
        clearInterval(adsbTracker.updateInterval);
        adsbTracker.updateInterval = null;
    }
    
    adsbTracker.enabled = false;
    console.log('🛑 ADSB updates stopped');
}

/**
 * Fetch current flights from API
 */
async function fetchADSBFlights() {
    try {
        const response = await fetch('/api/adsb/flights');
        const data = await response.json();
        
        if (data.success) {
            adsbTracker.flights = data.flights;
            adsbTracker.lastUpdate = new Date().toISOString();
            
            console.log(`🛩️ Updated ADSB data: ${data.flight_count} flights within range`);
            
            // Update UI
            updateADSBFlightDisplay();
            updateADSBStats(data.flight_count);
            
        } else {
            console.warn('Failed to fetch ADSB flights:', data.error);
            showMessage('Failed to fetch flight data: ' + data.error, 'warning');
        }
    } catch (error) {
        console.error('Error fetching ADSB flights:', error);
        showMessage('Error fetching flight data', 'error');
    }
}

/**
 * Update ADSB flight display in UI
 */
function updateADSBFlightDisplay() {
    const container = document.getElementById('adsb-flights-list');
    if (!container) return;
    
    if (adsbTracker.flights.length === 0) {
        container.innerHTML = `
            <div class="adsb-no-flights">
                <p>📡 No flights detected within configured range</p>
                <small>Monitoring ${adsbTracker.flights.length} aircraft</small>
            </div>
        `;
        return;
    }
    
    // Sort flights by distance (closest first)
    const sortedFlights = [...adsbTracker.flights].sort((a, b) => a.distance_miles - b.distance_miles);
    
    // Limit display count
    const displayFlights = sortedFlights.slice(0, adsbTracker.maxDisplayFlights);
    
    const flightsHTML = displayFlights.map(flight => {
        const callsign = flight.flight !== 'N/A' ? flight.flight : 'Unknown';
        const altitude = flight.altitude ? Math.round(flight.altitude).toLocaleString() + ' ft' : 'N/A';
        const speed = flight.ground_speed ? Math.round(flight.ground_speed) + ' kt' : 'N/A';
        const bearing = flight.bearing_degrees ? Math.round(flight.bearing_degrees) + '°' : 'N/A';
        const elevation = flight.elevation_degrees ? Math.round(flight.elevation_degrees * 10) / 10 + '°' : 'N/A';
        
        // Use API-provided unique color
        const flightColor = flight.color || '#FFFF00';
        
        // Color code by distance
        let distanceClass = 'distance-far';
        if (flight.distance_miles < 1) distanceClass = 'distance-close';
        else if (flight.distance_miles < 3) distanceClass = 'distance-medium';
        
        // Create tracking links
        const hexCode = flight.hex.toUpperCase();
        const callsignForUrl = flight.flight && flight.flight !== 'N/A' ? flight.flight.trim() : '';
        
        // FlightRadar24: Use callsign search since direct hex linking format changed
        const flightRadar24Url = callsignForUrl 
            ? `https://www.flightradar24.com/data/flights/${callsignForUrl}`
            : `https://www.flightradar24.com/`;
        
        const flightAwareUrl = `https://flightaware.com/live/modes/${hexCode}`;
        const adsbExchangeUrl = `https://globe.adsbexchange.com/?icao=${hexCode}`;
        
        return `
            <div class="adsb-flight-item ${distanceClass}" style="border-left: 4px solid ${flightColor};">
                <div class="flight-header">
                    <span class="flight-callsign" style="color: ${flightColor};">${callsign}</span>
                    <span class="flight-distance">${flight.distance_miles} mi</span>
                </div>
                <div class="flight-details">
                    <div class="flight-detail">
                        <span class="detail-label">Alt:</span>
                        <span class="detail-value">${altitude}</span>
                    </div>
                    <div class="flight-detail">
                        <span class="detail-label">Speed:</span>
                        <span class="detail-value">${speed}</span>
                    </div>
                    <div class="flight-detail">
                        <span class="detail-label">Bearing:</span>
                        <span class="detail-value">${bearing}</span>
                    </div>
                    <div class="flight-detail">
                        <span class="detail-label">Elevation:</span>
                        <span class="detail-value">${elevation}</span>
                    </div>
                </div>
                <div class="flight-meta">
                    <small>Squawk: ${flight.squawk || 'N/A'} | Hex: ${flight.hex}</small>
                </div>
                <div class="flight-links" style="margin-top: 5px;">
                    <small>
                        ${callsignForUrl 
                            ? `<a href="${flightRadar24Url}" target="_blank" style="color: #17a2b8; margin-right: 10px;">FR24</a>`
                            : `<span style="color: #666; margin-right: 10px;">FR24 (no callsign)</span>`
                        }
                        <a href="${flightAwareUrl}" target="_blank" style="color: #17a2b8; margin-right: 10px;">FlightAware</a>
                        <a href="${adsbExchangeUrl}" target="_blank" style="color: #17a2b8;">ADS-B Exchange</a>
                    </small>
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = flightsHTML;
}

/**
 * Update ADSB connection status in UI
 */
function updateADSBConnectionStatus(connected, message) {
    const statusElement = document.getElementById('adsb-connection-status');
    const messageElement = document.getElementById('adsb-status-message');
    
    if (statusElement) {
        statusElement.textContent = connected ? 'Connected' : 'Disconnected';
        statusElement.className = connected ? 'status-connected' : 'status-disconnected';
    }
    
    if (messageElement) {
        messageElement.textContent = message || '';
    }
}

/**
 * Update ADSB statistics in UI
 */
function updateADSBStats(flightCount) {
    const elements = {
        'adsb-flight-count': flightCount,
        'adsb-last-update': new Date().toLocaleTimeString(),
        'adsb-status': adsbTracker.enabled ? 'Active' : 'Inactive'
    };
    
    Object.entries(elements).forEach(([id, value]) => {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    });
    
    // Update range if we have status info
    fetchADSBStatus().then(status => {
        const rangeElement = document.getElementById('adsb-range');
        if (rangeElement && status.max_distance_miles) {
            rangeElement.textContent = status.max_distance_miles + 'mi';
        }
    }).catch(() => {
        // Ignore errors, use default
    });
}

/**
 * Fetch ADSB status information
 */
async function fetchADSBStatus() {
    const response = await fetch('/api/adsb/status');
    return await response.json();
}

/**
 * Get bearing name from degrees
 */
function getBearingName(degrees) {
    const bearings = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'];
    return bearings[Math.round(degrees / 22.5) % 16];
}

/**
 * Refresh ADSB data manually
 */
function refreshADSBData() {
    showMessage('Refreshing ADSB flight data...', 'info');
    fetchADSBFlights();
}

/**
 * Toggle ADSB tracking on/off
 */
function toggleADSBTracking() {
    const btn = document.getElementById('adsb-toggle-btn');
    if (!btn) return;
    
    if (adsbTracker.enabled) {
        stopADSBUpdates();
        btn.textContent = '▶️ Start ADSB Tracking';
        btn.classList.remove('btn-danger');
        btn.classList.add('btn-success');
        showMessage('ADSB tracking stopped', 'info');
    } else {
        startADSBUpdates();
        btn.textContent = '⏹️ Stop ADSB Tracking';
        btn.classList.remove('btn-success');
        btn.classList.add('btn-danger');
        showMessage('ADSB tracking started', 'success');
    }
}

// Initialize ADSB tracker when page loads
document.addEventListener('DOMContentLoaded', function() {
    // Delay initialization to allow other systems to start
    setTimeout(() => {
        if (document.getElementById('adsb-flights-list')) {
            console.log('Starting ADSB tracker widget initialization...');
            initializeADSBTracker();
        } else {
            console.log('ADSB flights list element not found, skipping initialization');
        }
    }, 2000);
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
    stopADSBUpdates();
});

// Add ADSB CSS styles
const adsbStyles = `
    .adsb-flight-item {
        background: rgba(255,255,255,0.1);
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 8px;
        border-left: 4px solid #17a2b8;
    }
    .distance-close { border-left-color: #dc3545; }
    .distance-medium { border-left-color: #ffc107; }
    .distance-far { border-left-color: #28a745; }
    .flight-header {
        display: flex;
        justify-content: space-between;
        margin-bottom: 8px;
        font-weight: bold;
    }
    .flight-callsign { color: #17a2b8; }
    .flight-distance { color: #ffc107; }
    .flight-details {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 5px;
        margin-bottom: 5px;
    }
    .flight-detail {
        display: flex;
        justify-content: space-between;
        font-size: 0.9em;
    }
    .detail-label { color: #aaa; }
    .detail-value { color: #fff; font-weight: bold; }
    .flight-meta {
        font-size: 0.8em;
        color: #666;
    }
    .status-connected { color: #28a745; }
    .status-disconnected { color: #dc3545; }
    .adsb-no-flights {
        text-align: center;
        padding: 20px;
        color: #666;
    }
`;

// Inject styles
const styleSheet = document.createElement("style");
styleSheet.innerText = adsbStyles;
document.head.appendChild(styleSheet);

console.log('ADSB Tracker JavaScript loaded');
class TrajectoryOverlay {
    constructor(containerId, cameraType = 'ir') {
        this.container = document.getElementById(containerId);
        this.canvas = null;
        this.ctx = null;
        this.trajectories = new Map();
        this.compass = { heading: 0, calibrated: false };
        this.orientation = { pitch: 0, roll: 0, yaw: 0 };
        this.cameraType = cameraType; // 'ir' or 'hq'
        
        // Set camera-specific FOV based on type
        if (cameraType === 'hq') {
            this.fov = { horizontal: 22, vertical: 17 }; // HQ camera: narrower FOV, more zoomed
        } else {
            this.fov = { horizontal: 62, vertical: 48 }; // IR camera: wider field of view
        }
        
        this.showSatellites = true;
        this.showAircraft = true;
        this.projectionEnabled = false;
        this.updateInterval = null;
        
        this.initCanvas();
    }

    initCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.style.position = 'absolute';
        this.canvas.style.top = '0';
        this.canvas.style.left = '0';
        this.canvas.style.pointerEvents = 'none';
        this.canvas.style.zIndex = '1000';
        this.canvas.className = 'trajectory-overlay-canvas';
        
        if (this.container) {
            // Ensure the container has relative positioning
            const currentPosition = window.getComputedStyle(this.container).position;
            if (currentPosition === 'static') {
                this.container.style.position = 'relative';
            }
            
            this.container.appendChild(this.canvas);
            this.resizeCanvas();
        }
        
        this.ctx = this.canvas.getContext('2d');
        
        window.addEventListener('resize', () => this.resizeCanvas());
    }

    resizeCanvas() {
        if (this.container) {
            this.canvas.width = this.container.offsetWidth;
            this.canvas.height = this.container.offsetHeight;
        }
    }

    setCompass(heading, calibrated = true) {
        this.compass.heading = heading;
        this.compass.calibrated = calibrated;
        this.updateProjections();
    }

    setOrientation(pitch, roll, yaw) {
        this.orientation.pitch = pitch;
        this.orientation.roll = roll;
        this.orientation.yaw = yaw;
        this.updateProjections();
    }

    setFOV(horizontal, vertical) {
        this.fov.horizontal = horizontal;
        this.fov.vertical = vertical;
        this.updateProjections();
    }

    enableProjection(enable = true) {
        this.projectionEnabled = enable;
        if (enable) {
            this.startUpdates();
        } else {
            this.stopUpdates();
            this.clear();
        }
    }

    startUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
        }
        
        this.updateProjections();
        this.updateInterval = setInterval(() => {
            this.updateCompassFromSensor();
            this.updateProjections();
        }, 5000);
    }
    
    async updateCompassFromSensor() {
        try {
            const response = await fetch('/api/sensor/mpu9250');
            const data = await response.json();
            
            if (data.success) {
                const sensorData = data.data;
                
                // Update compass heading
                if (sensorData.compass) {
                    this.setCompass(sensorData.compass.true_heading, sensorData.compass.calibrated);
                }
                
                // Update orientation (pitch/roll for tilt compensation)
                if (sensorData.orientation) {
                    this.setOrientation(
                        sensorData.orientation.pitch,
                        sensorData.orientation.roll,
                        sensorData.orientation.yaw
                    );
                }
            }
        } catch (error) {
            console.warn('Could not fetch sensor data from MPU9250:', error);
            // Fallback to compass-only endpoint if MPU9250 is not available
            try {
                const compassResponse = await fetch('/api/sensor/compass');
                const compassData = await compassResponse.json();
                if (compassData.success) {
                    this.setCompass(compassData.data.true_heading, compassData.data.calibrated);
                }
            } catch (compassError) {
                console.warn('Could not fetch compass data either:', compassError);
            }
        }
    }

    stopUpdates() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    async updateProjections() {
        if (!this.projectionEnabled) {
            console.log('Projections disabled, skipping update');
            return;
        }
        
        console.log('Updating trajectory projections...');
        
        try {
            const satellitePromise = this.showSatellites ? this.fetchSatellites() : Promise.resolve([]);
            const aircraftPromise = this.showAircraft ? this.fetchAircraft() : Promise.resolve([]);
            
            const [satellites, aircraft] = await Promise.all([satellitePromise, aircraftPromise]);
            
            console.log('Got data:', { satellites: satellites.length, aircraft: aircraft.length });
            
            this.trajectories.clear();
            
            satellites.forEach(sat => {
                const trajectory = this.projectSatelliteTrajectory(sat);
                console.log(`Satellite ${sat.name}: ${trajectory.length} trajectory points`);
                if (trajectory.length > 0) {
                    this.trajectories.set(`sat_${sat.name}`, {
                        type: 'satellite',
                        data: sat,
                        points: trajectory,
                        color: sat.color || '#00FF00'  // Use API-provided color or default green
                    });
                }
            });
            
            aircraft.forEach(ac => {
                const trajectory = this.projectAircraftTrajectory(ac);
                console.log(`Aircraft ${ac.callsign || ac.icao}: ${trajectory.length} trajectory points`);
                if (trajectory.length > 0) {
                    this.trajectories.set(`ac_${ac.icao}`, {
                        type: 'aircraft',
                        data: ac,
                        points: trajectory,
                        color: ac.color || '#FFFF00'  // Use API-provided color or default yellow
                    });
                }
            });
            
            console.log(`Total trajectories to render: ${this.trajectories.size}`);
            this.render();
            
        } catch (error) {
            console.error('Error updating projections:', error);
        }
    }

    async fetchSatellites() {
        try {
            const response = await fetch('/api/satellites/visible');
            if (response.ok) {
                const data = await response.json();
                console.log('Fetched satellites:', data.satellites?.length || 0);
                return data.satellites || [];
            }
        } catch (error) {
            console.error('Error fetching satellites:', error);
        }
        
        // Return test data if API is not available
        console.log('Using test satellite data');
        return [
            {
                name: 'ISS (TEST)',
                azimuth: 45,
                elevation: 30,
                distance: 400,
                velocity: 17500
            },
            {
                name: 'STARLINK-12345 (TEST)',
                azimuth: 120,
                elevation: 15,
                distance: 550,
                velocity: 27000
            }
        ];
    }

    async fetchAircraft() {
        try {
            const response = await fetch('/api/aircraft');
            if (response.ok) {
                const data = await response.json();
                console.log('Fetched aircraft:', data.aircraft?.length || 0);
                return data.aircraft || [];
            }
        } catch (error) {
            console.error('Error fetching aircraft:', error);
        }
        
        // Return test data if ADSB is not available
        console.log('Using test aircraft data');
        return [
            {
                callsign: 'UAL123 (TEST)',
                icao: 'A12345',
                latitude: 37.7749,
                longitude: -122.4194,
                altitude: 35000,
                heading: 90,
                speed: 450
            }
        ];
    }

    projectSatelliteTrajectory(satellite) {
        const points = [];
        
        // If satellite has a pre-calculated path from the backend, use it
        if (satellite.path && Array.isArray(satellite.path)) {
            satellite.path.forEach((pathPoint, index) => {
                const screenPos = this.projectToScreen(pathPoint.azimuth, pathPoint.elevation);
                if (screenPos) {
                    points.push({
                        x: screenPos.x,
                        y: screenPos.y,
                        time: index * 15, // Approximate time step
                        visible: this.isInView(pathPoint.azimuth, pathPoint.elevation),
                        azimuth: pathPoint.azimuth,
                        elevation: pathPoint.elevation,
                        range_km: pathPoint.range_km
                    });
                }
            });
        } else {
            // Fallback: Calculate a simple great circle path for satellites
            // Satellites typically move in great circles across the sky
            const duration = 300; // 5 minutes
            const steps = 30;
            
            // Estimate angular velocity based on typical LEO satellite speeds
            // LEO satellites cross the sky in about 5-10 minutes (180 degrees)
            const angularVelocity = 0.5; // degrees per second
            
            // Calculate the initial direction of motion based on orbital inclination
            // Most satellites move roughly west to east or in polar orbits
            const motionAzimuth = satellite.azimuth < 180 ? 90 : 270; // Simplified
            
            for (let i = 0; i <= steps; i++) {
                const t = i * (duration / steps);
                
                // Calculate position along great circle path
                // This simulates the satellite moving across the sky
                const distance = angularVelocity * t; // degrees traveled
                
                // Use spherical trigonometry to calculate new position
                const lat1 = (90 - satellite.elevation) * Math.PI / 180;
                const lon1 = satellite.azimuth * Math.PI / 180;
                const bearing = motionAzimuth * Math.PI / 180;
                const angularDistance = distance * Math.PI / 180;
                
                const lat2 = Math.asin(
                    Math.sin(lat1) * Math.cos(angularDistance) +
                    Math.cos(lat1) * Math.sin(angularDistance) * Math.cos(bearing)
                );
                
                const lon2 = lon1 + Math.atan2(
                    Math.sin(bearing) * Math.sin(angularDistance) * Math.cos(lat1),
                    Math.cos(angularDistance) - Math.sin(lat1) * Math.sin(lat2)
                );
                
                const projectedEl = 90 - (lat2 * 180 / Math.PI);
                const projectedAz = ((lon2 * 180 / Math.PI) + 360) % 360;
                
                // Only add points above horizon
                if (projectedEl > 0) {
                    const screenPos = this.projectToScreen(projectedAz, projectedEl);
                    if (screenPos) {
                        points.push({
                            x: screenPos.x,
                            y: screenPos.y,
                            time: t,
                            visible: this.isInView(projectedAz, projectedEl),
                            azimuth: projectedAz,
                            elevation: projectedEl
                        });
                    }
                }
            }
        }
        
        return points;
    }

    projectAircraftTrajectory(aircraft) {
        const points = [];
        
        if (!aircraft.latitude || !aircraft.longitude) return points;
        
        const duration = 300;
        const steps = 10;
        
        for (let i = 0; i <= steps; i++) {
            const t = i * (duration / steps);
            
            const speed_mps = (aircraft.speed || 0) * 0.514444;
            const distance = speed_mps * t;
            
            const projectedLat = aircraft.latitude + 
                (distance / 111000) * Math.cos(Math.PI * (aircraft.heading || 0) / 180);
            const projectedLon = aircraft.longitude + 
                (distance / 111000) * Math.sin(Math.PI * (aircraft.heading || 0) / 180);
            
            const azEl = this.calculateAzimuthElevation(projectedLat, projectedLon, aircraft.altitude || 0);
            
            const screenPos = this.projectToScreen(azEl.azimuth, azEl.elevation);
            if (screenPos) {
                points.push({
                    x: screenPos.x,
                    y: screenPos.y,
                    time: t,
                    visible: this.isInView(azEl.azimuth, azEl.elevation)
                });
            }
        }
        
        return points;
    }

    projectToScreen(azimuth, elevation) {
        // Calculate relative azimuth based on compass heading
        const relativeAz = this.normalizeAngle(azimuth - this.compass.heading);
        
        // Apply pitch compensation to elevation
        // When pitch is 0 (looking at horizon), camera center is at elevation 0°
        // When pitch is 90 (looking straight up), camera center is at elevation 90°
        // The visible elevation range is [pitch - fov.vertical/2, pitch + fov.vertical/2]
        const cameraElevation = this.orientation.pitch;
        const relativeElevation = elevation - cameraElevation;
        
        // Check if object is within camera FOV
        if (Math.abs(relativeAz) > this.fov.horizontal / 2) {
            return null;
        }
        
        if (Math.abs(relativeElevation) > this.fov.vertical / 2) {
            return null;
        }
        
        // Project to screen coordinates with proper FOV scaling
        const x = (relativeAz / (this.fov.horizontal / 2) + 1) * this.canvas.width / 2;
        // Invert Y axis so higher elevations appear at top of screen
        const y = this.canvas.height / 2 - (relativeElevation / (this.fov.vertical / 2)) * this.canvas.height / 2;
        
        return { x, y };
    }

    isInView(azimuth, elevation) {
        const relativeAz = this.normalizeAngle(azimuth - this.compass.heading);
        const cameraElevation = this.orientation.pitch;
        const relativeElevation = elevation - cameraElevation;
        return Math.abs(relativeAz) <= this.fov.horizontal / 2 && 
               Math.abs(relativeElevation) <= this.fov.vertical / 2;
    }

    normalizeAngle(angle) {
        while (angle > 180) angle -= 360;
        while (angle < -180) angle += 360;
        return angle;
    }

    calculateAzimuthElevation(lat, lon, alt) {
        const observerLat = 0;
        const observerLon = 0;
        const observerAlt = 0;
        
        const R = 6371000;
        const dLat = (lat - observerLat) * Math.PI / 180;
        const dLon = (lon - observerLon) * Math.PI / 180;
        
        const azimuth = Math.atan2(
            Math.sin(dLon) * Math.cos(lat * Math.PI / 180),
            Math.cos(observerLat * Math.PI / 180) * Math.sin(lat * Math.PI / 180) -
            Math.sin(observerLat * Math.PI / 180) * Math.cos(lat * Math.PI / 180) * Math.cos(dLon)
        ) * 180 / Math.PI;
        
        const a = Math.sin(dLat/2) * Math.sin(dLat/2) +
                  Math.cos(observerLat * Math.PI / 180) * Math.cos(lat * Math.PI / 180) *
                  Math.sin(dLon/2) * Math.sin(dLon/2);
        const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a));
        const distance = R * c;
        
        const heightDiff = (alt * 0.3048) - observerAlt;
        const elevation = Math.atan2(heightDiff, distance) * 180 / Math.PI;
        
        return {
            azimuth: (azimuth + 360) % 360,
            elevation: elevation
        };
    }

    render() {
        console.log('Rendering trajectories...');
        this.clear();
        
        if (!this.projectionEnabled) {
            console.log('Projections disabled, not rendering');
            return;
        }
        
        if (!this.compass.calibrated) {
            console.log('Compass not calibrated, not rendering');
            // Show a message on the canvas
            this.ctx.fillStyle = '#ff9999';
            this.ctx.font = '14px monospace';
            this.ctx.textAlign = 'center';
            this.ctx.fillText('Compass not calibrated', this.canvas.width / 2, this.canvas.height / 2);
            return;
        }
        
        console.log(`Rendering ${this.trajectories.size} trajectories`);
        
        this.ctx.save();
        
        this.trajectories.forEach(trajectory => {
            console.log(`Drawing trajectory for ${trajectory.data.name || trajectory.data.callsign}`);
            this.drawTrajectory(trajectory);
        });
        
        this.drawCompassIndicator();
        this.drawFOVIndicator();
        
        this.ctx.restore();
    }

    drawTrajectory(trajectory) {
        const points = trajectory.points.filter(p => p.visible);
        if (points.length < 2) return;
        
        // Use the color assigned by the API with transparency
        const baseColor = trajectory.color || (trajectory.type === 'satellite' ? '#00ff00' : '#ffff00');
        const transparentColor = this.addAlphaToColor(baseColor, 0.7); // 70% opacity for tracks
        const textColor = this.addAlphaToColor(baseColor, 0.8); // 80% opacity for text
        
        const label = trajectory.type === 'satellite' ? 
            trajectory.data.name : 
            (trajectory.data.callsign || trajectory.data.icao);
        
        // Draw trajectory line with transparency
        this.ctx.strokeStyle = transparentColor;
        this.ctx.lineWidth = 2;
        
        this.ctx.beginPath();
        this.ctx.moveTo(points[0].x, points[0].y);
        
        for (let i = 1; i < points.length; i++) {
            this.ctx.lineTo(points[i].x, points[i].y);
        }
        
        this.ctx.stroke();
        
        // Draw current position marker with transparency
        this.ctx.fillStyle = transparentColor;
        this.ctx.beginPath();
        this.ctx.arc(points[0].x, points[0].y, 5, 0, 2 * Math.PI);
        this.ctx.fill();
        
        // Draw text labels with transparency
        if (label) {
            this.ctx.fillStyle = textColor;
            this.ctx.font = '12px monospace';
            this.ctx.fillText(label, points[0].x + 10, points[0].y - 5);
            
            const info = trajectory.type === 'satellite' ? 
                `${Math.round(trajectory.data.distance || 0)} mi` :
                `FL${Math.round((trajectory.data.altitude || 0) / 100)}`;
            
            this.ctx.fillText(info, points[0].x + 10, points[0].y + 10);
        }
    }
    
    addAlphaToColor(hexColor, alpha) {
        // Convert hex color to rgba with alpha
        if (hexColor.startsWith('#')) {
            const hex = hexColor.substring(1);
            const r = parseInt(hex.substring(0, 2), 16);
            const g = parseInt(hex.substring(2, 4), 16);
            const b = parseInt(hex.substring(4, 6), 16);
            return `rgba(${r}, ${g}, ${b}, ${alpha})`;
        }
        return hexColor; // Return as-is if not hex
    }

    drawCompassIndicator() {
        const centerX = this.canvas.width / 2;
        const topY = 20;
        
        this.ctx.fillStyle = '#ffffff';
        this.ctx.font = 'bold 14px monospace';
        this.ctx.textAlign = 'center';
        
        const heading = Math.round(this.compass.heading);
        this.ctx.fillText(`${heading}°`, centerX, topY);
        
        const cardinals = [
            { angle: 0, label: 'N' },
            { angle: 90, label: 'E' },
            { angle: 180, label: 'S' },
            { angle: 270, label: 'W' }
        ];
        
        cardinals.forEach(cardinal => {
            const relativeAngle = this.normalizeAngle(cardinal.angle - this.compass.heading);
            if (Math.abs(relativeAngle) <= this.fov.horizontal / 2) {
                const x = (relativeAngle / (this.fov.horizontal / 2) + 1) * this.canvas.width / 2;
                this.ctx.fillStyle = cardinal.angle === 0 ? '#ff0000' : '#888888';
                this.ctx.fillText(cardinal.label, x, topY + 20);
            }
        });
    }

    drawFOVIndicator() {
        const bottomY = this.canvas.height - 10;
        
        this.ctx.fillStyle = '#888888';
        this.ctx.font = '10px monospace';
        this.ctx.textAlign = 'left';
        
        this.ctx.fillText(`FOV: ${this.fov.horizontal}° × ${this.fov.vertical}°`, 10, bottomY);
    }

    clear() {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    }

    destroy() {
        this.stopUpdates();
        if (this.canvas && this.canvas.parentNode) {
            this.canvas.parentNode.removeChild(this.canvas);
        }
    }
}

window.TrajectoryOverlay = TrajectoryOverlay;
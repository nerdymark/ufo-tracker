/**
 * Mood Music Controls for UFO Tracker
 * Browser-based ambient music using Web Audio API
 */

let moodMusicEnabled = false;
let moodMusicPlaying = false;
let currentTrackKey = null;
let continuousPlayback = true;
let shuffleMode = false;
let trackEndTimeout = null;
let useEnhancedEngine = true; // Toggle between original and enhanced engine

// Initialize mood music controls
function initializeMoodMusic() {
    // Load settings from localStorage
    const savedEnabled = localStorage.getItem('moodMusicEnabled');
    if (savedEnabled === 'true') {
        const enableCheckbox = document.getElementById('mood-music-enabled');
        if (enableCheckbox) {
            enableCheckbox.checked = true;
            enableMoodMusic();
        }
    }
    
    // Load engine preference
    const savedEngine = localStorage.getItem('moodMusicEngine');
    if (savedEngine === 'original') {
        useEnhancedEngine = false;
        const toggle = document.getElementById('enhanced-engine-toggle');
        if (toggle) toggle.checked = false;
    }
    
    // Check initial status
    refreshMoodMusicStatus();
}

// Toggle between original and enhanced music engines
function toggleMusicEngine(useEnhanced) {
    useEnhancedEngine = useEnhanced;
    localStorage.setItem('moodMusicEngine', useEnhanced ? 'enhanced' : 'original');
    
    // If music is playing, stop and restart with new engine
    if (moodMusicPlaying) {
        stopMusic();
        setTimeout(() => playRandomTrack(), 500);
    }
    
    showMessage(`Switched to ${useEnhanced ? 'Enhanced' : 'Original'} music engine`, 'info');
}

// Toggle mood music system on/off
function toggleMoodMusic() {
    const checkbox = document.getElementById('mood-music-enabled');
    const controls = document.getElementById('mood-music-controls');
    const status = document.getElementById('mood-music-status');
    
    if (checkbox.checked) {
        enableMoodMusic();
    } else {
        disableMoodMusic();
    }
    
    // Save preference
    localStorage.setItem('moodMusicEnabled', checkbox.checked);
}

function enableMoodMusic() {
    moodMusicEnabled = true;
    const controls = document.getElementById('mood-music-controls');
    const status = document.getElementById('mood-music-status');
    
    if (controls) controls.style.display = 'block';
    if (status) {
        status.textContent = 'Enabled';
        status.style.color = '#4CAF50';
    }
    
    console.log('Mood music system enabled (browser-based)');
    showMessage('Mood music system enabled', 'success');
}

function disableMoodMusic() {
    moodMusicEnabled = false;
    const controls = document.getElementById('mood-music-controls');
    const status = document.getElementById('mood-music-status');
    
    if (controls) controls.style.display = 'none';
    if (status) {
        status.textContent = 'Disabled';
        status.style.color = '#666';
    }
    
    // Stop any playing music
    if (moodMusicPlaying) {
        stopMusic();
    }
    
    console.log('Mood music system disabled');
    showMessage('Mood music system disabled', 'info');
}

// Play a random ambient track
async function playRandomTrack() {
    if (!moodMusicEnabled) {
        showMessage('Please enable mood music first', 'warning');
        return;
    }
    
    const playBtn = document.getElementById('play-btn');
    const trackInfo = document.getElementById('current-track-info');
    
    if (playBtn) playBtn.disabled = true;
    if (trackInfo) trackInfo.textContent = 'Starting random track...';
    
    try {
        // Use selected engine (enhanced or original)
        const engine = useEnhancedEngine ? enhancedMusic : ambientMusic;
        const engineType = useEnhancedEngine ? 'Enhanced' : 'Ambient';
        const success = await engine.playRandomTrack();
        
        if (success) {
            moodMusicPlaying = true;
            const status = engine.getStatus ? engine.getStatus() : { currentKey: engine.currentKey };
            currentTrackKey = status.currentKey || engine.currentKey;
            
            if (trackInfo) {
                trackInfo.textContent = `Playing ${engineType} track in key of ${currentTrackKey}`;
                trackInfo.style.color = '#4CAF50';
            }
            
            showMessage(`Started playing ${engineType} track in key of ${currentTrackKey}`, 'success');
            updatePlaybackControls();
            
            // Monitor playback status
            monitorPlayback();
            
        } else {
            throw new Error('Failed to start ambient music engine');
        }
        
    } catch (error) {
        console.error('Error starting music:', error);
        showMessage('Error starting music: ' + error.message, 'error');
        
        if (trackInfo) {
            trackInfo.textContent = 'Error starting music';
            trackInfo.style.color = '#ff6b6b';
        }
        
        moodMusicPlaying = false;
        
    } finally {
        if (playBtn) playBtn.disabled = false;
    }
}

// Stop currently playing music
function stopMusic() {
    const stopBtn = document.getElementById('stop-btn');
    const trackInfo = document.getElementById('current-track-info');
    
    if (stopBtn) stopBtn.disabled = true;
    
    try {
        // Stop both engines to ensure clean state
        if (typeof ambientMusic !== 'undefined') ambientMusic.stop();
        if (typeof enhancedMusic !== 'undefined') enhancedMusic.stop();
        
        moodMusicPlaying = false;
        currentTrackKey = null;
        
        if (trackInfo) {
            trackInfo.textContent = 'No track playing';
            trackInfo.style.color = '#888';
        }
        
        showMessage('Stopped mood music', 'info');
        updatePlaybackControls();
        
    } catch (error) {
        console.error('Error stopping music:', error);
        showMessage('Error stopping music', 'error');
    } finally {
        if (stopBtn) stopBtn.disabled = false;
    }
}

// Update playback control button states
function updatePlaybackControls() {
    const playBtn = document.getElementById('play-btn');
    const stopBtn = document.getElementById('stop-btn');
    
    if (playBtn && stopBtn) {
        if (moodMusicPlaying) {
            playBtn.textContent = '🔄 Play Different Track';
            stopBtn.disabled = false;
        } else {
            playBtn.textContent = '🎵 Play Random Track';
            stopBtn.disabled = true;
        }
    }
}

// Monitor playback status
function monitorPlayback() {
    const checkStatus = () => {
        const engine = useEnhancedEngine ? enhancedMusic : ambientMusic;
        const engineType = useEnhancedEngine ? 'Enhanced' : 'Ambient';
        const engineStatus = engine.getStatus ? engine.getStatus() : { 
            playing: engine.isPlaying, 
            currentKey: engine.currentKey,
            currentSection: engine.currentSection
        };
        const trackInfo = document.getElementById('current-track-info');
        
        if (engineStatus.playing || engine.isPlaying) {
            moodMusicPlaying = true;
            currentTrackKey = engineStatus.currentKey || engine.currentKey;
            
            if (trackInfo) {
                let statusText = `Playing ${engineType} track in key of ${currentTrackKey}`;
                if (engineStatus.currentSection || engine.currentSection) {
                    statusText += ` (${engineStatus.currentSection || engine.currentSection})`;
                }
                trackInfo.textContent = statusText;
                trackInfo.style.color = '#4CAF50';
            }
            
            // Continue monitoring
            setTimeout(checkStatus, 2000);
            
        } else {
            // Track finished
            moodMusicPlaying = false;
            currentTrackKey = null;
            
            if (trackInfo) {
                trackInfo.textContent = 'Track finished';
                trackInfo.style.color = '#888';
            }
            
            updatePlaybackControls();
        }
    };
    
    checkStatus();
}

// Refresh mood music status (simplified for browser-based system)
function refreshMoodMusicStatus() {
    const status = document.getElementById('mood-music-status');
    const trackInfo = document.getElementById('current-track-info');
    
    // Update UI based on current state
    const checkbox = document.getElementById('mood-music-enabled');
    if (checkbox) checkbox.checked = moodMusicEnabled;
    
    const controls = document.getElementById('mood-music-controls');
    if (controls) {
        controls.style.display = moodMusicEnabled ? 'block' : 'none';
    }
    
    if (status) {
        if (moodMusicEnabled) {
            status.textContent = 'Enabled';
            status.style.color = '#4CAF50';
        } else {
            status.textContent = 'Disabled';
            status.style.color = '#666';
        }
    }
    
    // Update track info if not currently playing
    if (!moodMusicPlaying && trackInfo) {
        trackInfo.textContent = moodMusicEnabled ? 'No track playing' : '';
        trackInfo.style.color = '#888';
    }
    
    updatePlaybackControls();
}

// Auto-refresh status periodically
setInterval(refreshMoodMusicStatus, 5000);

// Status Bar Music Controls
function toggleStatusBarMusic() {
    const toggle = document.getElementById('status-music-toggle');
    
    if (!moodMusicEnabled) {
        // Enable music system
        moodMusicEnabled = true;
        localStorage.setItem('moodMusicEnabled', true);
        console.log('Status bar music enabled');
    }
    
    if (moodMusicPlaying) {
        stopStatusBarMusic();
    } else {
        playStatusBarMusic();
    }
}

async function playStatusBarMusic() {
    const toggle = document.getElementById('status-music-toggle');
    
    try {
        // Use browser-based ambient music engine
        const success = await ambientMusic.playRandomTrack();
        
        if (success) {
            moodMusicPlaying = true;
            const status = ambientMusic.getStatus();
            currentTrackKey = status.currentKey;
            
            if (toggle) {
                toggle.textContent = '⏸️';
                toggle.title = `Playing: ${currentTrackKey}`;
            }
            
            console.log(`Status bar music playing: ${currentTrackKey}`);
            
            // Monitor for track completion and auto-advance
            monitorStatusBarPlayback();
            
        } else {
            throw new Error('Failed to start ambient music engine');
        }
        
    } catch (error) {
        console.error('Error starting status bar music:', error);
        if (toggle) {
            toggle.textContent = '❌';
            toggle.title = 'Music error';
        }
    }
}

function stopStatusBarMusic() {
    const toggle = document.getElementById('status-music-toggle');
    
    try {
        ambientMusic.stop();
        moodMusicPlaying = false;
        currentTrackKey = null;
        
        if (toggle) {
            toggle.textContent = '🎵';
            toggle.title = 'Play music';
        }
        
        // Clear any pending auto-advance
        if (trackEndTimeout) {
            clearTimeout(trackEndTimeout);
            trackEndTimeout = null;
        }
        
        console.log('Status bar music stopped');
        
    } catch (error) {
        console.error('Error stopping status bar music:', error);
    }
}

function nextStatusBarTrack() {
    if (moodMusicPlaying) {
        // Stop current track and start new one
        ambientMusic.stop();
        setTimeout(() => {
            playStatusBarMusic();
        }, 500);
    } else if (moodMusicEnabled) {
        // Just start playing if not already playing
        playStatusBarMusic();
    }
}

function toggleStatusBarShuffle() {
    const shuffleBtn = document.getElementById('status-music-shuffle');
    shuffleMode = !shuffleMode;
    
    if (shuffleBtn) {
        if (shuffleMode) {
            shuffleBtn.textContent = '🔀';
            shuffleBtn.title = 'Shuffle: ON';
            shuffleBtn.style.color = '#4CAF50';
        } else {
            shuffleBtn.textContent = '🔀';
            shuffleBtn.title = 'Shuffle: OFF';
            shuffleBtn.style.color = '';
        }
    }
    
    localStorage.setItem('musicShuffleMode', shuffleMode);
    console.log('Shuffle mode:', shuffleMode ? 'ON' : 'OFF');
}

function monitorStatusBarPlayback() {
    const checkStatus = () => {
        const engineStatus = ambientMusic.getStatus();
        const toggle = document.getElementById('status-music-toggle');
        
        if (engineStatus.playing) {
            moodMusicPlaying = true;
            currentTrackKey = engineStatus.currentKey;
            
            if (toggle) {
                toggle.title = `Playing: ${currentTrackKey} (${engineStatus.currentSection || 'ambient'})`;
            }
            
            // Continue monitoring
            setTimeout(checkStatus, 3000);
            
        } else if (moodMusicPlaying) {
            // Track finished - auto-advance if continuous playback enabled
            moodMusicPlaying = false;
            currentTrackKey = null;
            
            if (toggle) {
                toggle.textContent = '🎵';
                toggle.title = 'Play music';
            }
            
            if (continuousPlayback && moodMusicEnabled) {
                // Auto-advance to next track after a brief pause
                trackEndTimeout = setTimeout(() => {
                    console.log('Auto-advancing to next track...');
                    playStatusBarMusic();
                }, 2000);
            }
        }
    };
    
    checkStatus();
}

// Load saved settings on init
function loadStatusBarMusicSettings() {
    // Load shuffle mode
    const savedShuffle = localStorage.getItem('musicShuffleMode');
    if (savedShuffle === 'true') {
        shuffleMode = true;
        const shuffleBtn = document.getElementById('status-music-shuffle');
        if (shuffleBtn) {
            shuffleBtn.style.color = '#4CAF50';
            shuffleBtn.title = 'Shuffle: ON';
        }
    }
    
    // Load music enabled state
    const savedEnabled = localStorage.getItem('moodMusicEnabled');
    if (savedEnabled === 'true') {
        moodMusicEnabled = true;
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        initializeMoodMusic();
        loadStatusBarMusicSettings();
    }, 1000);
});
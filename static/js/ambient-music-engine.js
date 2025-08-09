/**
 * Ambient Music Engine for UFO Tracker
 * Browser-based ethereal music generator using Web Audio API
 */

class AmbientMusicEngine {
    constructor() {
        this.audioContext = null;
        this.masterGain = null;
        this.isPlaying = false;
        this.currentKey = null;
        this.oscillators = [];
        this.gainNodes = [];
        this.currentSection = null;
        this.sectionTimeout = null;
        this.fadeTimeout = null;
        
        // Musical scales and progressions
        this.keys = {
            'A': { root: 220, name: 'A' },      // A3
            'B': { root: 246.94, name: 'B' },   // B3
            'C': { root: 261.63, name: 'C' },   // C4
            'D': { root: 293.66, name: 'D' },   // D4
            'E': { root: 329.63, name: 'E' },   // E4
            'F': { root: 349.23, name: 'F' },   // F4
            'G': { root: 392.00, name: 'G' }    // G4
        };
        
        // Chord progressions (intervals from root)
        this.progressions = [
            [0, 7, 4, 9],     // I-V-iii-vi (ethereal)
            [0, 4, 7, 2],     // I-iii-V-ii (floating)
            [0, 9, 4, 7],     // I-vi-iii-V (dreamy)
            [0, 2, 9, 7]      // I-ii-vi-V (ambient)
        ];
        
        // Song structure timing (seconds)
        this.structure = {
            intro: 20,
            verse: 40,
            chorus: 30,
            bridge: 25,
            outro: 30
        };
    }
    
    async initialize() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.audioContext.createGain();
            this.masterGain.connect(this.audioContext.destination);
            this.masterGain.gain.value = 0.3; // Keep volume moderate
            
            console.log('Ambient music engine initialized');
            return true;
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            return false;
        }
    }
    
    async playRandomTrack() {
        if (this.isPlaying) {
            this.stop();
        }
        
        if (!this.audioContext) {
            const success = await this.initialize();
            if (!success) return false;
        }
        
        // Resume audio context if suspended (browser autoplay policy)
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        
        // Select random key
        const keyNames = Object.keys(this.keys);
        const randomKey = keyNames[Math.floor(Math.random() * keyNames.length)];
        this.currentKey = randomKey;
        
        console.log(`Starting ambient track in key of ${randomKey}`);
        
        this.isPlaying = true;
        await this.playFullTrack(randomKey);
        
        return true;
    }
    
    async playFullTrack(keyName) {
        const key = this.keys[keyName];
        const progression = this.progressions[Math.floor(Math.random() * this.progressions.length)];
        
        try {
            // Intro - Atmospheric entrance
            this.currentSection = 'intro';
            await this.playSection('intro', key, progression, this.structure.intro);
            
            if (!this.isPlaying) return;
            
            // Verse 1 - Build layers
            this.currentSection = 'verse1';
            await this.playSection('verse', key, progression, this.structure.verse, 1);
            
            if (!this.isPlaying) return;
            
            // Chorus 1 - Full arrangement
            this.currentSection = 'chorus1';
            await this.playSection('chorus', key, progression, this.structure.chorus, 1);
            
            if (!this.isPlaying) return;
            
            // Verse 2 - Variation
            this.currentSection = 'verse2';
            await this.playSection('verse', key, progression, this.structure.verse, 2);
            
            if (!this.isPlaying) return;
            
            // Chorus 2 - Developed
            this.currentSection = 'chorus2';
            await this.playSection('chorus', key, progression, this.structure.chorus, 2);
            
            if (!this.isPlaying) return;
            
            // Bridge - Key change (up a fifth)
            this.currentSection = 'bridge';
            const bridgeKey = { root: key.root * 1.5, name: keyName + ' (bridge)' };
            await this.playSection('bridge', bridgeKey, progression, this.structure.bridge);
            
            if (!this.isPlaying) return;
            
            // Return - Back to original key
            this.currentSection = 'return';
            await this.playSection('chorus', key, progression, this.structure.chorus, 3);
            
            if (!this.isPlaying) return;
            
            // Outro - Fade to atmosphere
            this.currentSection = 'outro';
            await this.playSection('outro', key, progression, this.structure.outro);
            
        } catch (error) {
            console.error('Error during track playback:', error);
        } finally {
            if (this.isPlaying) {
                this.stop();
            }
        }
    }
    
    async playSection(sectionType, key, progression, duration, variation = 1) {
        return new Promise((resolve) => {
            this.clearOscillators();
            
            const layers = this.createSectionLayers(sectionType, key, progression, variation);
            
            // Start all oscillators
            layers.forEach(layer => {
                layer.oscillator.start();
                this.oscillators.push(layer.oscillator);
                this.gainNodes.push(layer.gain);
            });
            
            // Section timeout
            this.sectionTimeout = setTimeout(() => {
                resolve();
            }, duration * 1000);
        });
    }
    
    createSectionLayers(sectionType, key, progression, variation = 1) {
        const layers = [];
        const now = this.audioContext.currentTime;
        
        switch (sectionType) {
            case 'intro':
                // Soft pad entrance
                layers.push(this.createPadLayer(key.root, 0.15, 'sine', now));
                layers.push(this.createPadLayer(key.root * 2, 0.1, 'triangle', now + 5));
                break;
                
            case 'verse':
                // Build layers progressively
                progression.forEach((interval, i) => {
                    const freq = this.getFrequency(key.root, interval);
                    const startTime = now + (i * 2);
                    
                    layers.push(this.createPadLayer(freq, 0.12, 'sine', startTime));
                    if (variation >= 2) {
                        layers.push(this.createPadLayer(freq / 2, 0.08, 'triangle', startTime + 1));
                    }
                });
                break;
                
            case 'chorus':
                // Full arrangement
                progression.forEach((interval, i) => {
                    const freq = this.getFrequency(key.root, interval);
                    const startTime = now + (i * 1.5);
                    
                    // Main pad
                    layers.push(this.createPadLayer(freq, 0.15, 'sine', startTime));
                    // Bass layer
                    layers.push(this.createPadLayer(freq / 2, 0.1, 'triangle', startTime));
                    // High atmosphere
                    if (variation >= 2) {
                        layers.push(this.createPadLayer(freq * 2, 0.08, 'sine', startTime + 0.5));
                    }
                });
                
                // Add melody line in chorus
                if (variation >= 1) {
                    layers.push(this.createMelodyLayer(key.root, now + 2));
                }
                break;
                
            case 'bridge':
                // Lighter texture for contrast
                progression.slice(0, 2).forEach((interval, i) => {
                    const freq = this.getFrequency(key.root, interval);
                    const startTime = now + (i * 3);
                    
                    layers.push(this.createPadLayer(freq, 0.12, 'sine', startTime));
                });
                break;
                
            case 'outro':
                // Fade to simple atmosphere
                layers.push(this.createPadLayer(key.root, 0.1, 'sine', now));
                layers.push(this.createPadLayer(key.root * 2, 0.06, 'triangle', now + 3));
                break;
        }
        
        return layers;
    }
    
    createPadLayer(frequency, volume, waveform, startTime) {
        const oscillator = this.audioContext.createOscillator();
        const gain = this.audioContext.createGain();
        const filter = this.audioContext.createBiquadFilter();
        
        oscillator.type = waveform;
        oscillator.frequency.value = frequency;
        
        // Gentle filtering for warmth
        filter.type = 'lowpass';
        filter.frequency.value = frequency * 3;
        filter.Q.value = 1;
        
        // Slow attack and release
        gain.gain.setValueAtTime(0, startTime);
        gain.gain.linearRampToValueAtTime(volume, startTime + 3);
        
        // Add subtle vibrato
        const lfo = this.audioContext.createOscillator();
        const lfoGain = this.audioContext.createGain();
        lfo.frequency.value = 0.2; // Slow vibrato
        lfoGain.gain.value = frequency * 0.01; // Subtle depth
        
        lfo.connect(lfoGain);
        lfoGain.connect(oscillator.frequency);
        lfo.start(startTime);
        
        oscillator.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        
        return { oscillator, gain, lfo };
    }
    
    createMelodyLayer(rootFreq, startTime) {
        const melody = [0, 2, 4, 7, 9, 7, 4, 2]; // Simple melody intervals
        const noteLength = 2; // 2 seconds per note
        
        const oscillator = this.audioContext.createOscillator();
        const gain = this.audioContext.createGain();
        const filter = this.audioContext.createBiquadFilter();
        
        oscillator.type = 'sine';
        filter.type = 'lowpass';
        filter.frequency.value = rootFreq * 4;
        
        // Create melody by changing frequency
        melody.forEach((interval, i) => {
            const freq = this.getFrequency(rootFreq * 2, interval); // Octave higher
            const noteStart = startTime + (i * noteLength);
            const noteEnd = noteStart + noteLength * 0.8; // Slight gap
            
            oscillator.frequency.setValueAtTime(freq, noteStart);
            gain.gain.setValueAtTime(0, noteStart);
            gain.gain.linearRampToValueAtTime(0.08, noteStart + 0.3);
            gain.gain.linearRampToValueAtTime(0, noteEnd);
        });
        
        oscillator.connect(filter);
        filter.connect(gain);
        gain.connect(this.masterGain);
        
        return { oscillator, gain };
    }
    
    getFrequency(root, semitoneInterval) {
        return root * Math.pow(2, semitoneInterval / 12);
    }
    
    clearOscillators() {
        // Stop existing oscillators
        this.oscillators.forEach(osc => {
            try {
                osc.stop();
            } catch (e) {
                // Oscillator already stopped
            }
        });
        
        this.oscillators = [];
        this.gainNodes = [];
        
        // Clear timeouts
        if (this.sectionTimeout) {
            clearTimeout(this.sectionTimeout);
            this.sectionTimeout = null;
        }
    }
    
    stop() {
        if (!this.isPlaying) return;
        
        this.isPlaying = false;
        this.currentSection = null;
        this.clearOscillators();
        
        // Fade out master gain
        if (this.masterGain) {
            this.masterGain.gain.linearRampToValueAtTime(0, this.audioContext.currentTime + 1);
            setTimeout(() => {
                if (this.masterGain) {
                    this.masterGain.gain.value = 0.3; // Reset for next play
                }
            }, 1100);
        }
        
        console.log('Ambient music stopped');
    }
    
    getStatus() {
        return {
            playing: this.isPlaying,
            currentKey: this.currentKey,
            currentSection: this.currentSection,
            audioContextState: this.audioContext ? this.audioContext.state : 'not initialized'
        };
    }
}

// Global ambient music engine instance
const ambientMusic = new AmbientMusicEngine();
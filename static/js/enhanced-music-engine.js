/**
 * Enhanced Music Engine for UFO Tracker
 * Advanced browser-based music generator with full instrumentation
 */

class EnhancedMusicEngine {
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
        this.bpm = 80; // Slow tempo
        this.beatDuration = 60 / this.bpm;
        
        // Musical scales and progressions
        this.keys = {
            'A': { root: 110, name: 'A', mode: 'minor' },    // A2 minor
            'B': { root: 123.47, name: 'B', mode: 'minor' }, // B2 minor
            'C': { root: 130.81, name: 'C', mode: 'major' }, // C3 major
            'D': { root: 146.83, name: 'D', mode: 'minor' }, // D3 minor
            'E': { root: 164.81, name: 'E', mode: 'minor' }, // E3 minor
            'F': { root: 174.61, name: 'F', mode: 'major' }, // F3 major
            'G': { root: 196.00, name: 'G', mode: 'major' }  // G3 major
        };
        
        // Scale intervals (semitones from root)
        this.scales = {
            major: [0, 2, 4, 5, 7, 9, 11],
            minor: [0, 2, 3, 5, 7, 8, 10],
            pentatonic: [0, 2, 4, 7, 9],
            blues: [0, 3, 5, 6, 7, 10]
        };
        
        // Common bridge melody (in scale degrees)
        this.commonBridgeMelody = [0, 2, 4, 5, 4, 2, 0, -1, 0, 2, 4, 7, 4, 2, 0];
        
        // Unique melodies for each key (in scale degrees)
        this.uniqueMelodies = {
            'A': [0, 2, 3, 5, 3, 2, 0, -2, 0, 3, 5, 7, 5, 3, 0], // Mysterious
            'B': [0, 1, 3, 4, 3, 1, 0, 3, 5, 4, 3, 1, 0, -1, 0], // Dark and wandering
            'C': [0, 2, 4, 5, 7, 5, 4, 2, 0, 4, 7, 9, 7, 4, 0], // Bright and uplifting
            'D': [0, 3, 5, 3, 0, -2, 0, 3, 5, 7, 5, 3, 0, 2, 0], // Melancholic
            'E': [0, 2, 3, 5, 7, 5, 3, 2, 0, -2, 0, 3, 5, 3, 0], // Haunting
            'F': [0, 4, 7, 4, 0, 2, 4, 5, 7, 5, 4, 2, 0, -1, 0], // Peaceful
            'G': [0, 2, 4, 7, 4, 2, 0, 5, 7, 9, 7, 5, 4, 2, 0]  // Hopeful
        };
        
        // Chord progressions (scale degrees)
        this.progressions = {
            major: [
                [0, 3, 4, 0],     // I-IV-V-I
                [0, 5, 3, 4],     // I-vi-IV-V
                [0, 3, 5, 4],     // I-IV-vi-V
                [0, 2, 4, 0]      // I-iii-V-I
            ],
            minor: [
                [0, 3, 4, 0],     // i-iv-v-i
                [0, 5, 3, 6],     // i-VI-iv-VII
                [0, 3, 6, 4],     // i-iv-VII-v
                [0, 6, 3, 4]      // i-VII-iv-v
            ]
        };
        
        // Drum patterns
        this.drumPatterns = {
            kick: [1, 0, 0, 0, 0.5, 0, 0, 0, 1, 0, 0, 0, 0.5, 0, 0, 0],
            snare: [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            hihat: [0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3],
            ride: [1, 0, 0.3, 0, 0.5, 0, 0.3, 0, 1, 0, 0.3, 0, 0.5, 0, 0.3, 0]
        };
        
        // Song structure timing (seconds)
        this.structure = {
            intro: 16,
            verse1: 32,
            chorus1: 24,
            verse2: 32,
            chorus2: 24,
            bridge: 32,
            chorus3: 24,
            outro: 24
        };
    }
    
    async initialize() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.audioContext.createGain();
            this.masterGain.connect(this.audioContext.destination);
            this.masterGain.gain.value = 0.25; // Keep volume moderate
            
            // Create reverb
            this.reverb = await this.createReverb();
            this.reverbGain = this.audioContext.createGain();
            this.reverbGain.gain.value = 0.3;
            this.reverbGain.connect(this.reverb);
            this.reverb.connect(this.masterGain);
            
            // Create delay
            this.delay = this.audioContext.createDelay(1.0);
            this.delay.delayTime.value = 0.375; // Dotted eighth note delay
            this.delayGain = this.audioContext.createGain();
            this.delayGain.gain.value = 0.2;
            this.delay.connect(this.delayGain);
            this.delayGain.connect(this.delay);
            this.delayGain.connect(this.masterGain);
            
            console.log('Enhanced music engine initialized');
            return true;
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            return false;
        }
    }
    
    async createReverb() {
        const convolver = this.audioContext.createConvolver();
        const length = this.audioContext.sampleRate * 3; // 3 second reverb
        const impulse = this.audioContext.createBuffer(2, length, this.audioContext.sampleRate);
        
        for (let channel = 0; channel < 2; channel++) {
            const channelData = impulse.getChannelData(channel);
            for (let i = 0; i < length; i++) {
                channelData[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / length, 2);
            }
        }
        
        convolver.buffer = impulse;
        return convolver;
    }
    
    async playRandomTrack() {
        if (this.isPlaying) {
            this.stop();
        }
        
        if (!this.audioContext) {
            const success = await this.initialize();
            if (!success) return false;
        }
        
        // Resume audio context if suspended
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        
        // Select random key
        const keyNames = Object.keys(this.keys);
        const randomKey = keyNames[Math.floor(Math.random() * keyNames.length)];
        this.currentKey = randomKey;
        
        console.log(`Starting enhanced track in key of ${randomKey} ${this.keys[randomKey].mode}`);
        
        this.isPlaying = true;
        await this.playFullTrack(randomKey);
        
        return true;
    }
    
    async playFullTrack(keyName) {
        const key = this.keys[keyName];
        const mode = key.mode;
        const progressions = this.progressions[mode];
        const progression = progressions[Math.floor(Math.random() * progressions.length)];
        
        try {
            // Intro - Atmospheric entrance with light percussion
            this.currentSection = 'intro';
            await this.playIntro(key, progression);
            
            if (!this.isPlaying) return;
            
            // Verse 1 - Add bass and subtle melody
            this.currentSection = 'verse1';
            await this.playVerse(key, progression, 1);
            
            if (!this.isPlaying) return;
            
            // Chorus 1 - Full instrumentation
            this.currentSection = 'chorus1';
            await this.playChorus(key, progression);
            
            if (!this.isPlaying) return;
            
            // Verse 2 - Variation with different melody
            this.currentSection = 'verse2';
            await this.playVerse(key, progression, 2);
            
            if (!this.isPlaying) return;
            
            // Chorus 2 - Fuller arrangement
            this.currentSection = 'chorus2';
            await this.playChorus(key, progression);
            
            if (!this.isPlaying) return;
            
            // Bridge - Key change with common melody
            this.currentSection = 'bridge';
            await this.playBridge(key);
            
            if (!this.isPlaying) return;
            
            // Chorus 3 - Return to original key
            this.currentSection = 'chorus3';
            await this.playChorus(key, progression);
            
            if (!this.isPlaying) return;
            
            // Outro - Fade out
            this.currentSection = 'outro';
            await this.playOutro(key, progression);
            
            console.log('Track completed');
            this.isPlaying = false;
            
        } catch (error) {
            console.error('Error playing track:', error);
            this.stop();
        }
    }
    
    async playIntro(key, progression) {
        const startTime = this.audioContext.currentTime;
        const duration = this.structure.intro;
        
        // Atmospheric pad
        this.playPadChords(key, progression, startTime, duration, 0.1);
        
        // Light percussion (just hi-hats)
        this.playDrums(startTime + 8, duration - 8, ['hihat']);
        
        // Wait for intro to complete
        await this.wait(duration * 1000);
    }
    
    async playVerse(key, progression, verseNumber) {
        const startTime = this.audioContext.currentTime;
        const duration = verseNumber === 1 ? this.structure.verse1 : this.structure.verse2;
        
        // Chords
        this.playPadChords(key, progression, startTime, duration, 0.15);
        
        // Bass line
        this.playBassLine(key, progression, startTime, duration);
        
        // Drums (kick and hihat)
        this.playDrums(startTime, duration, ['kick', 'hihat']);
        
        // Melody (unique for this key)
        const melody = this.uniqueMelodies[key.name];
        this.playMelody(key, melody, startTime + 4, duration - 8, 0.2);
        
        // Add some variation in verse 2
        if (verseNumber === 2) {
            this.playArpeggio(key, progression, startTime + 16, duration - 16);
        }
        
        await this.wait(duration * 1000);
    }
    
    async playChorus(key, progression) {
        const startTime = this.audioContext.currentTime;
        const duration = this.structure.chorus1;
        
        // Full chords
        this.playPadChords(key, progression, startTime, duration, 0.25);
        
        // Active bass
        this.playBassLine(key, progression, startTime, duration, true);
        
        // Full drums
        this.playDrums(startTime, duration, ['kick', 'snare', 'hihat', 'ride']);
        
        // Strong melody
        const melody = this.uniqueMelodies[key.name];
        this.playMelody(key, melody, startTime, duration, 0.35);
        
        // Harmony line
        this.playHarmony(key, melody, startTime + 8, duration - 8);
        
        await this.wait(duration * 1000);
    }
    
    async playBridge(key) {
        const startTime = this.audioContext.currentTime;
        const duration = this.structure.bridge;
        
        // Modulate up a fifth
        const newRoot = key.root * 1.5; // Perfect fifth
        const modulatedKey = { ...key, root: newRoot };
        
        // Play common bridge melody
        this.playMelody(modulatedKey, this.commonBridgeMelody, startTime, duration / 2, 0.4);
        
        // Transition back to original key
        this.playMelody(key, this.commonBridgeMelody, startTime + duration / 2, duration / 2, 0.3);
        
        // Supporting chords
        const bridgeProgression = [0, 4, 5, 0]; // Simple progression
        this.playPadChords(modulatedKey, bridgeProgression, startTime, duration / 2, 0.2);
        this.playPadChords(key, bridgeProgression, startTime + duration / 2, duration / 2, 0.2);
        
        // Minimal drums
        this.playDrums(startTime, duration, ['kick', 'ride']);
        
        await this.wait(duration * 1000);
    }
    
    async playOutro(key, progression) {
        const startTime = this.audioContext.currentTime;
        const duration = this.structure.outro;
        
        // Fading chords
        this.playPadChords(key, progression, startTime, duration, 0.2, true);
        
        // Sparse drums
        this.playDrums(startTime, duration / 2, ['kick', 'hihat']);
        
        // Final melody phrase
        const melody = this.uniqueMelodies[key.name].slice(0, 8);
        this.playMelody(key, melody, startTime, duration / 2, 0.15);
        
        // Fade master volume
        this.masterGain.gain.exponentialRampToValueAtTime(0.01, startTime + duration);
        
        await this.wait(duration * 1000);
    }
    
    playPadChords(key, progression, startTime, duration, volume, fadeOut = false) {
        const chordDuration = duration / progression.length;
        const scale = this.scales[key.mode];
        
        progression.forEach((degree, index) => {
            const chordTime = startTime + (index * chordDuration);
            const chord = this.getChord(key.root, scale, degree);
            
            chord.forEach((freq, noteIndex) => {
                const osc = this.audioContext.createOscillator();
                const gain = this.audioContext.createGain();
                
                osc.type = 'sine';
                osc.frequency.value = freq;
                
                // Smooth envelope
                gain.gain.setValueAtTime(0, chordTime);
                gain.gain.linearRampToValueAtTime(volume * (0.8 - noteIndex * 0.1), chordTime + 0.5);
                gain.gain.setValueAtTime(volume * (0.8 - noteIndex * 0.1), chordTime + chordDuration - 1);
                
                if (fadeOut && index === progression.length - 1) {
                    gain.gain.exponentialRampToValueAtTime(0.001, chordTime + chordDuration);
                } else {
                    gain.gain.linearRampToValueAtTime(0.001, chordTime + chordDuration);
                }
                
                osc.connect(gain);
                gain.connect(this.masterGain);
                gain.connect(this.reverbGain);
                
                osc.start(chordTime);
                osc.stop(chordTime + chordDuration);
                
                this.oscillators.push(osc);
                this.gainNodes.push(gain);
            });
        });
    }
    
    playBassLine(key, progression, startTime, duration, active = false) {
        const beatDuration = this.beatDuration;
        const scale = this.scales[key.mode];
        const numBeats = Math.floor(duration / beatDuration);
        
        for (let beat = 0; beat < numBeats; beat++) {
            const beatTime = startTime + (beat * beatDuration);
            const chordIndex = Math.floor((beat / numBeats) * progression.length);
            const rootNote = this.getScaleNote(key.root / 2, scale, progression[chordIndex]); // Bass octave
            
            // Create bass pattern
            let playNote = false;
            if (active) {
                // Active bass line - play on most beats
                playNote = beat % 2 === 0 || (beat % 4 === 1);
            } else {
                // Simple bass - play on downbeats
                playNote = beat % 4 === 0;
            }
            
            if (playNote) {
                const osc = this.audioContext.createOscillator();
                const gain = this.audioContext.createGain();
                
                osc.type = 'sawtooth';
                osc.frequency.value = rootNote;
                
                // Bass envelope
                gain.gain.setValueAtTime(0, beatTime);
                gain.gain.linearRampToValueAtTime(0.2, beatTime + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.1, beatTime + 0.1);
                gain.gain.exponentialRampToValueAtTime(0.001, beatTime + beatDuration);
                
                // Add filter for warmth
                const filter = this.audioContext.createBiquadFilter();
                filter.type = 'lowpass';
                filter.frequency.value = 200;
                filter.Q.value = 5;
                
                osc.connect(filter);
                filter.connect(gain);
                gain.connect(this.masterGain);
                
                osc.start(beatTime);
                osc.stop(beatTime + beatDuration);
                
                this.oscillators.push(osc);
                this.gainNodes.push(gain);
            }
        }
    }
    
    playMelody(key, melodyNotes, startTime, duration, volume) {
        const noteDuration = duration / melodyNotes.length;
        const scale = this.scales[key.mode];
        
        melodyNotes.forEach((degree, index) => {
            const noteTime = startTime + (index * noteDuration);
            const freq = this.getScaleNote(key.root * 2, scale, degree); // Melody octave
            
            const osc = this.audioContext.createOscillator();
            const gain = this.audioContext.createGain();
            
            osc.type = 'triangle';
            osc.frequency.value = freq;
            
            // Melody envelope
            gain.gain.setValueAtTime(0, noteTime);
            gain.gain.linearRampToValueAtTime(volume, noteTime + 0.05);
            gain.gain.setValueAtTime(volume, noteTime + noteDuration * 0.8);
            gain.gain.linearRampToValueAtTime(0.001, noteTime + noteDuration);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            gain.connect(this.delayGain); // Add delay to melody
            
            osc.start(noteTime);
            osc.stop(noteTime + noteDuration);
            
            this.oscillators.push(osc);
            this.gainNodes.push(gain);
        });
    }
    
    playHarmony(key, melodyNotes, startTime, duration) {
        const noteDuration = duration / melodyNotes.length;
        const scale = this.scales[key.mode];
        
        melodyNotes.forEach((degree, index) => {
            const noteTime = startTime + (index * noteDuration);
            // Harmony a third above
            const harmonyDegree = degree + 2;
            const freq = this.getScaleNote(key.root * 2, scale, harmonyDegree);
            
            const osc = this.audioContext.createOscillator();
            const gain = this.audioContext.createGain();
            
            osc.type = 'sine';
            osc.frequency.value = freq;
            
            // Softer harmony
            gain.gain.setValueAtTime(0, noteTime);
            gain.gain.linearRampToValueAtTime(0.1, noteTime + 0.05);
            gain.gain.setValueAtTime(0.1, noteTime + noteDuration * 0.8);
            gain.gain.linearRampToValueAtTime(0.001, noteTime + noteDuration);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            gain.connect(this.reverbGain);
            
            osc.start(noteTime);
            osc.stop(noteTime + noteDuration);
            
            this.oscillators.push(osc);
            this.gainNodes.push(gain);
        });
    }
    
    playArpeggio(key, progression, startTime, duration) {
        const noteLength = 0.25; // 16th notes
        const scale = this.scales[key.mode];
        const numNotes = Math.floor(duration / noteLength);
        
        for (let i = 0; i < numNotes; i++) {
            const noteTime = startTime + (i * noteLength);
            const chordIndex = Math.floor((i / numNotes) * progression.length);
            const chord = this.getChord(key.root * 2, scale, progression[chordIndex]);
            const noteIndex = i % chord.length;
            
            const osc = this.audioContext.createOscillator();
            const gain = this.audioContext.createGain();
            
            osc.type = 'sine';
            osc.frequency.value = chord[noteIndex];
            
            // Quick arpeggio notes
            gain.gain.setValueAtTime(0, noteTime);
            gain.gain.linearRampToValueAtTime(0.15, noteTime + 0.01);
            gain.gain.exponentialRampToValueAtTime(0.001, noteTime + noteLength);
            
            osc.connect(gain);
            gain.connect(this.masterGain);
            gain.connect(this.delayGain);
            
            osc.start(noteTime);
            osc.stop(noteTime + noteLength);
            
            this.oscillators.push(osc);
            this.gainNodes.push(gain);
        }
    }
    
    playDrums(startTime, duration, instruments) {
        const beatDuration = this.beatDuration / 4; // 16th note resolution
        const numBeats = Math.floor(duration / beatDuration);
        
        for (let beat = 0; beat < numBeats; beat++) {
            const beatTime = startTime + (beat * beatDuration);
            
            instruments.forEach(instrument => {
                const pattern = this.drumPatterns[instrument];
                const velocity = pattern[beat % pattern.length];
                
                if (velocity > 0) {
                    this.playDrumHit(instrument, beatTime, velocity);
                }
            });
        }
    }
    
    playDrumHit(instrument, time, velocity) {
        const gain = this.audioContext.createGain();
        gain.connect(this.masterGain);
        
        switch(instrument) {
            case 'kick':
                // Sine wave kick drum
                const kickOsc = this.audioContext.createOscillator();
                kickOsc.type = 'sine';
                kickOsc.frequency.setValueAtTime(60, time);
                kickOsc.frequency.exponentialRampToValueAtTime(30, time + 0.1);
                
                gain.gain.setValueAtTime(0, time);
                gain.gain.linearRampToValueAtTime(0.5 * velocity, time + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.2);
                
                kickOsc.connect(gain);
                kickOsc.start(time);
                kickOsc.stop(time + 0.2);
                
                this.oscillators.push(kickOsc);
                break;
                
            case 'snare':
                // Noise snare
                const snareNoise = this.audioContext.createBufferSource();
                const snareBuffer = this.audioContext.createBuffer(1, 0.1 * this.audioContext.sampleRate, this.audioContext.sampleRate);
                const snareData = snareBuffer.getChannelData(0);
                for (let i = 0; i < snareData.length; i++) {
                    snareData[i] = Math.random() * 2 - 1;
                }
                snareNoise.buffer = snareBuffer;
                
                const snareFilter = this.audioContext.createBiquadFilter();
                snareFilter.type = 'highpass';
                snareFilter.frequency.value = 200;
                
                gain.gain.setValueAtTime(0, time);
                gain.gain.linearRampToValueAtTime(0.3 * velocity, time + 0.01);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.1);
                
                snareNoise.connect(snareFilter);
                snareFilter.connect(gain);
                snareNoise.start(time);
                
                break;
                
            case 'hihat':
                // High frequency noise
                const hihatNoise = this.audioContext.createBufferSource();
                const hihatBuffer = this.audioContext.createBuffer(1, 0.05 * this.audioContext.sampleRate, this.audioContext.sampleRate);
                const hihatData = hihatBuffer.getChannelData(0);
                for (let i = 0; i < hihatData.length; i++) {
                    hihatData[i] = Math.random() * 2 - 1;
                }
                hihatNoise.buffer = hihatBuffer;
                
                const hihatFilter = this.audioContext.createBiquadFilter();
                hihatFilter.type = 'highpass';
                hihatFilter.frequency.value = 8000;
                
                gain.gain.setValueAtTime(0, time);
                gain.gain.linearRampToValueAtTime(0.1 * velocity, time + 0.001);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.05);
                
                hihatNoise.connect(hihatFilter);
                hihatFilter.connect(gain);
                hihatNoise.start(time);
                
                break;
                
            case 'ride':
                // Metallic ride cymbal
                const rideOsc = this.audioContext.createOscillator();
                rideOsc.type = 'triangle';
                rideOsc.frequency.value = 4000 + Math.random() * 2000;
                
                const rideFilter = this.audioContext.createBiquadFilter();
                rideFilter.type = 'bandpass';
                rideFilter.frequency.value = 5000;
                rideFilter.Q.value = 2;
                
                gain.gain.setValueAtTime(0, time);
                gain.gain.linearRampToValueAtTime(0.05 * velocity, time + 0.001);
                gain.gain.exponentialRampToValueAtTime(0.001, time + 0.5);
                
                rideOsc.connect(rideFilter);
                rideFilter.connect(gain);
                rideOsc.start(time);
                rideOsc.stop(time + 0.5);
                
                this.oscillators.push(rideOsc);
                break;
        }
        
        this.gainNodes.push(gain);
    }
    
    getChord(root, scale, degree) {
        const chord = [];
        // Build triad (1st, 3rd, 5th)
        chord.push(this.getScaleNote(root, scale, degree));
        chord.push(this.getScaleNote(root, scale, degree + 2));
        chord.push(this.getScaleNote(root, scale, degree + 4));
        // Add 7th for richness
        chord.push(this.getScaleNote(root, scale, degree + 6));
        return chord;
    }
    
    getScaleNote(root, scale, degree) {
        const octaveShift = Math.floor(degree / scale.length);
        const scaleDegree = ((degree % scale.length) + scale.length) % scale.length;
        const semitones = scale[scaleDegree] + (octaveShift * 12);
        return root * Math.pow(2, semitones / 12);
    }
    
    wait(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    stop() {
        this.isPlaying = false;
        
        // Clear timeouts
        if (this.sectionTimeout) {
            clearTimeout(this.sectionTimeout);
            this.sectionTimeout = null;
        }
        
        if (this.fadeTimeout) {
            clearTimeout(this.fadeTimeout);
            this.fadeTimeout = null;
        }
        
        // Stop all oscillators
        this.oscillators.forEach(osc => {
            try {
                osc.stop();
            } catch (e) {
                // Already stopped
            }
        });
        
        // Disconnect all gain nodes
        this.gainNodes.forEach(gain => {
            try {
                gain.disconnect();
            } catch (e) {
                // Already disconnected
            }
        });
        
        // Clear arrays
        this.oscillators = [];
        this.gainNodes = [];
        
        // Reset master volume
        if (this.masterGain) {
            this.masterGain.gain.cancelScheduledValues(this.audioContext.currentTime);
            this.masterGain.gain.setValueAtTime(0.25, this.audioContext.currentTime);
        }
        
        console.log('Music stopped');
    }
    
    setVolume(value) {
        if (this.masterGain) {
            this.masterGain.gain.linearRampToValueAtTime(value * 0.25, this.audioContext.currentTime + 0.1);
        }
    }
    
    getStatus() {
        return {
            playing: this.isPlaying,
            currentKey: this.currentKey,
            currentSection: this.currentSection
        };
    }
}

// Export for use in mood-music.js
window.EnhancedMusicEngine = EnhancedMusicEngine;

// Global enhanced music engine instance
const enhancedMusic = new EnhancedMusicEngine();
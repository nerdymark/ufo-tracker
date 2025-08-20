/**
 * Unified Music Engine for UFO Tracker
 * Combines ambient and enhanced music generation capabilities
 */

class UnifiedMusicEngine {
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
        this.enhancedMode = false;
        
        // Audio effects
        this.effects = {
            reverb: { enabled: true, level: 0.3, roomSize: 0.7 },
            chorus: { enabled: false, level: 0.4, rate: 1.5, depth: 0.002 },
            flanger: { enabled: false, level: 0.3, rate: 0.5, depth: 0.005 },
            delay: { enabled: false, level: 0.2, time: 0.3, feedback: 0.4 },
            filter: { enabled: false, frequency: 800, resonance: 1 }
        };
        
        // Musical scales and progressions
        this.keys = {
            'A': { root: 110, name: 'A', mode: 'minor' },    
            'B': { root: 123.47, name: 'B', mode: 'minor' }, 
            'C': { root: 130.81, name: 'C', mode: 'major' }, 
            'D': { root: 146.83, name: 'D', mode: 'minor' }, 
            'E': { root: 164.81, name: 'E', mode: 'minor' }, 
            'F': { root: 174.61, name: 'F', mode: 'major' }, 
            'G': { root: 196.00, name: 'G', mode: 'major' }  
        };
        
        // Scale intervals (semitones from root)
        this.scales = {
            major: [0, 2, 4, 5, 7, 9, 11],
            minor: [0, 2, 3, 5, 7, 8, 10],
            pentatonic: [0, 2, 4, 7, 9],
            blues: [0, 3, 5, 6, 7, 10]
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
        
        // Drum patterns for enhanced mode
        this.drumPatterns = {
            kick: [1, 0, 0, 0, 0.5, 0, 0, 0, 1, 0, 0, 0, 0.5, 0, 0, 0],
            snare: [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
            hihat: [0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3, 0.5, 0.3],
        };
    }
    
    async initialize() {
        try {
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            this.masterGain = this.audioContext.createGain();
            this.masterGain.connect(this.audioContext.destination);
            this.masterGain.gain.value = 0.25;
            
            // Resume audio context if suspended (browser autoplay policy)
            if (this.audioContext.state === 'suspended') {
                await this.audioContext.resume();
            }
            
            // Create reverb for enhanced mode
            if (this.enhancedMode) {
                await this.setupEffects();
            }
            
            console.log('Unified music engine initialized');
            return true;
        } catch (error) {
            console.error('Failed to initialize audio context:', error);
            return false;
        }
    }
    
    async setupEffects() {
        // Effects chain: Input -> Filter -> Chorus -> Flanger -> Delay -> Reverb -> Output
        this.effectsChain = {
            input: this.audioContext.createGain(),
            filter: this.audioContext.createBiquadFilter(),
            chorus: this.createChorus(),
            flanger: this.createFlanger(),
            delay: this.createDelay(),
            reverb: await this.createReverb(),
            output: this.audioContext.createGain()
        };
        
        // Connect effects chain
        this.effectsChain.input.connect(this.effectsChain.filter);
        this.effectsChain.filter.connect(this.effectsChain.chorus.input);
        this.effectsChain.chorus.output.connect(this.effectsChain.flanger.input);
        this.effectsChain.flanger.output.connect(this.effectsChain.delay.input);
        this.effectsChain.delay.output.connect(this.effectsChain.reverb.input);
        this.effectsChain.reverb.output.connect(this.effectsChain.output);
        this.effectsChain.output.connect(this.masterGain);
        
        // Configure default filter
        this.effectsChain.filter.type = 'lowpass';
        this.effectsChain.filter.frequency.value = this.effects.filter.frequency;
        this.effectsChain.filter.Q.value = this.effects.filter.resonance;
        
        this.updateEffectsBypass();
    }
    
    async createReverb() {
        const input = this.audioContext.createGain();
        const output = this.audioContext.createGain();
        const dry = this.audioContext.createGain();
        const wet = this.audioContext.createGain();
        const convolver = this.audioContext.createConvolver();
        
        // Create impulse response for reverb
        const roomSize = this.effects.reverb.roomSize;
        const length = this.audioContext.sampleRate * (1 + roomSize * 3);
        const impulse = this.audioContext.createBuffer(2, length, this.audioContext.sampleRate);
        
        for (let channel = 0; channel < 2; channel++) {
            const channelData = impulse.getChannelData(channel);
            for (let i = 0; i < length; i++) {
                const decay = Math.pow(1 - i / length, roomSize + 0.5);
                channelData[i] = (Math.random() * 2 - 1) * decay;
            }
        }
        
        convolver.buffer = impulse;
        
        // Set up wet/dry mix
        dry.gain.value = 1 - this.effects.reverb.level;
        wet.gain.value = this.effects.reverb.level;
        
        // Connect reverb
        input.connect(dry);
        input.connect(convolver);
        convolver.connect(wet);
        dry.connect(output);
        wet.connect(output);
        
        return { input, output, convolver, dry, wet };
    }
    
    createChorus() {
        const input = this.audioContext.createGain();
        const output = this.audioContext.createGain();
        const delay = this.audioContext.createDelay(0.02);
        const lfo = this.audioContext.createOscillator();
        const lfoGain = this.audioContext.createGain();
        const dry = this.audioContext.createGain();
        const wet = this.audioContext.createGain();
        
        // Configure chorus
        delay.delayTime.value = 0.005; // Base delay
        lfo.frequency.value = this.effects.chorus.rate;
        lfo.type = 'sine';
        lfoGain.gain.value = this.effects.chorus.depth;
        
        // Set wet/dry mix
        dry.gain.value = 1 - this.effects.chorus.level;
        wet.gain.value = this.effects.chorus.level;
        
        // Connect chorus
        input.connect(dry);
        input.connect(delay);
        delay.connect(wet);
        lfo.connect(lfoGain);
        lfoGain.connect(delay.delayTime);
        dry.connect(output);
        wet.connect(output);
        
        lfo.start();
        
        return { input, output, delay, lfo, lfoGain, dry, wet };
    }
    
    createFlanger() {
        const input = this.audioContext.createGain();
        const output = this.audioContext.createGain();
        const delay = this.audioContext.createDelay(0.02);
        const feedback = this.audioContext.createGain();
        const lfo = this.audioContext.createOscillator();
        const lfoGain = this.audioContext.createGain();
        const dry = this.audioContext.createGain();
        const wet = this.audioContext.createGain();
        
        // Configure flanger
        delay.delayTime.value = 0.001; // Very short base delay
        feedback.gain.value = 0.5;
        lfo.frequency.value = this.effects.flanger.rate;
        lfo.type = 'sine';
        lfoGain.gain.value = this.effects.flanger.depth;
        
        // Set wet/dry mix
        dry.gain.value = 1 - this.effects.flanger.level;
        wet.gain.value = this.effects.flanger.level;
        
        // Connect flanger with feedback
        input.connect(dry);
        input.connect(delay);
        delay.connect(feedback);
        delay.connect(wet);
        feedback.connect(delay);
        lfo.connect(lfoGain);
        lfoGain.connect(delay.delayTime);
        dry.connect(output);
        wet.connect(output);
        
        lfo.start();
        
        return { input, output, delay, feedback, lfo, lfoGain, dry, wet };
    }
    
    createDelay() {
        const input = this.audioContext.createGain();
        const output = this.audioContext.createGain();
        const delay = this.audioContext.createDelay(2.0);
        const feedback = this.audioContext.createGain();
        const dry = this.audioContext.createGain();
        const wet = this.audioContext.createGain();
        
        // Configure delay
        delay.delayTime.value = this.effects.delay.time;
        feedback.gain.value = this.effects.delay.feedback;
        
        // Set wet/dry mix
        dry.gain.value = 1 - this.effects.delay.level;
        wet.gain.value = this.effects.delay.level;
        
        // Connect delay with feedback
        input.connect(dry);
        input.connect(delay);
        delay.connect(feedback);
        delay.connect(wet);
        feedback.connect(delay);
        dry.connect(output);
        wet.connect(output);
        
        return { input, output, delay, feedback, dry, wet };
    }
    
    updateEffectsBypass() {
        if (!this.effectsChain) return;
        
        // Update effect levels based on enabled state
        Object.keys(this.effects).forEach(effectName => {
            const effect = this.effects[effectName];
            const effectNode = this.effectsChain[effectName];
            
            if (effectNode && effectNode.dry && effectNode.wet) {
                if (effect.enabled) {
                    effectNode.dry.gain.value = 1 - effect.level;
                    effectNode.wet.gain.value = effect.level;
                } else {
                    effectNode.dry.gain.value = 1;
                    effectNode.wet.gain.value = 0;
                }
            }
        });
    }
    
    setEffectEnabled(effectName, enabled) {
        if (this.effects[effectName]) {
            this.effects[effectName].enabled = enabled;
            this.updateEffectsBypass();
        }
    }
    
    setEffectParameter(effectName, parameter, value) {
        if (this.effects[effectName] && this.effects[effectName].hasOwnProperty(parameter)) {
            this.effects[effectName][parameter] = value;
            
            // Update audio nodes based on parameter changes
            const effectNode = this.effectsChain[effectName];
            if (effectNode) {
                switch (effectName) {
                    case 'reverb':
                        if (parameter === 'level' && effectNode.dry && effectNode.wet) {
                            effectNode.dry.gain.value = 1 - value;
                            effectNode.wet.gain.value = value;
                        }
                        break;
                    case 'chorus':
                        if (parameter === 'rate' && effectNode.lfo) {
                            effectNode.lfo.frequency.value = value;
                        } else if (parameter === 'depth' && effectNode.lfoGain) {
                            effectNode.lfoGain.gain.value = value;
                        } else if (parameter === 'level' && effectNode.dry && effectNode.wet) {
                            effectNode.dry.gain.value = 1 - value;
                            effectNode.wet.gain.value = value;
                        }
                        break;
                    case 'flanger':
                        if (parameter === 'rate' && effectNode.lfo) {
                            effectNode.lfo.frequency.value = value;
                        } else if (parameter === 'depth' && effectNode.lfoGain) {
                            effectNode.lfoGain.gain.value = value;
                        } else if (parameter === 'level' && effectNode.dry && effectNode.wet) {
                            effectNode.dry.gain.value = 1 - value;
                            effectNode.wet.gain.value = value;
                        }
                        break;
                    case 'delay':
                        if (parameter === 'time' && effectNode.delay) {
                            effectNode.delay.delayTime.value = value;
                        } else if (parameter === 'feedback' && effectNode.feedback) {
                            effectNode.feedback.gain.value = value;
                        } else if (parameter === 'level' && effectNode.dry && effectNode.wet) {
                            effectNode.dry.gain.value = 1 - value;
                            effectNode.wet.gain.value = value;
                        }
                        break;
                    case 'filter':
                        if (parameter === 'frequency' && this.effectsChain.filter) {
                            this.effectsChain.filter.frequency.value = value;
                        } else if (parameter === 'resonance' && this.effectsChain.filter) {
                            this.effectsChain.filter.Q.value = value;
                        }
                        break;
                }
            }
        }
    }
    
    setEnhancedMode(enabled) {
        this.enhancedMode = enabled;
        if (enabled && this.audioContext && !this.effectsChain) {
            this.setupEffects();
        }
        
        // Enable some effects in enhanced mode
        if (enabled) {
            this.setEffectEnabled('reverb', true);
            this.setEffectEnabled('chorus', true);
            this.setEffectParameter('chorus', 'level', 0.3);
        } else {
            this.setEffectEnabled('chorus', false);
            this.setEffectEnabled('flanger', false);
            this.setEffectEnabled('delay', false);
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
        
        // Resume audio context if suspended
        if (this.audioContext.state === 'suspended') {
            await this.audioContext.resume();
        }
        
        // Select random key
        const keyNames = Object.keys(this.keys);
        const randomKey = keyNames[Math.floor(Math.random() * keyNames.length)];
        this.currentKey = randomKey;
        
        console.log(`Starting ${this.enhancedMode ? 'enhanced' : 'ambient'} track in key of ${randomKey}`);
        
        this.isPlaying = true;
        
        if (this.enhancedMode) {
            await this.playEnhancedTrack(randomKey);
        } else {
            await this.playAmbientTrack(randomKey);
        }
        
        return true;
    }
    
    async playAmbientTrack(keyName) {
        const key = this.keys[keyName];
        
        // Play intro
        this.currentSection = 'intro';
        await this.playSection(key, 'intro', this.structure.intro);
        
        // Play verse
        this.currentSection = 'verse';
        await this.playSection(key, 'verse', this.structure.verse);
        
        // Play chorus
        this.currentSection = 'chorus';
        await this.playSection(key, 'chorus', this.structure.chorus);
        
        // Play bridge
        this.currentSection = 'bridge';
        await this.playSection(key, 'bridge', this.structure.bridge);
        
        // Play outro
        this.currentSection = 'outro';
        await this.playSection(key, 'outro', this.structure.outro);
        
        // Track complete
        this.isPlaying = false;
        this.currentSection = null;
    }
    
    async playEnhancedTrack(keyName) {
        const key = this.keys[keyName];
        
        // Enhanced mode with drums and bass
        this.currentSection = 'intro';
        await this.playEnhancedSection(key, 'intro', this.structure.intro);
        
        this.currentSection = 'verse';
        await this.playEnhancedSection(key, 'verse', this.structure.verse);
        
        this.currentSection = 'chorus';
        await this.playEnhancedSection(key, 'chorus', this.structure.chorus);
        
        this.currentSection = 'bridge';
        await this.playEnhancedSection(key, 'bridge', this.structure.bridge);
        
        this.currentSection = 'outro';
        await this.playEnhancedSection(key, 'outro', this.structure.outro);
        
        this.isPlaying = false;
        this.currentSection = null;
    }
    
    async playSection(key, sectionName, duration) {
        const progression = this.progressions[Math.floor(Math.random() * this.progressions.length)];
        const chordDuration = duration / progression.length;
        
        for (let i = 0; i < progression.length && this.isPlaying; i++) {
            const chordRoot = key.root * Math.pow(2, progression[i] / 12);
            this.playChord(chordRoot, chordDuration);
            await this.wait(chordDuration * 1000);
        }
    }
    
    async playEnhancedSection(key, sectionName, duration) {
        const progression = this.progressions[Math.floor(Math.random() * this.progressions.length)];
        const chordDuration = duration / progression.length;
        
        // Start drum pattern if enhanced
        if (this.enhancedMode) {
            this.startDrumPattern(duration);
        }
        
        for (let i = 0; i < progression.length && this.isPlaying; i++) {
            const chordRoot = key.root * Math.pow(2, progression[i] / 12);
            this.playChord(chordRoot, chordDuration);
            
            // Add bass line
            this.playBass(chordRoot, chordDuration);
            
            await this.wait(chordDuration * 1000);
        }
    }
    
    playChord(rootFreq, duration) {
        const frequencies = [
            rootFreq,              // Root
            rootFreq * 1.25,       // Perfect fifth
            rootFreq * 1.5,        // Octave
            rootFreq * 2.0         // Higher octave
        ];
        
        frequencies.forEach((freq, index) => {
            const oscillator = this.audioContext.createOscillator();
            const gainNode = this.audioContext.createGain();
            
            oscillator.type = 'sine';
            oscillator.frequency.value = freq;
            
            // Different volumes for harmonic richness
            const volume = 0.1 / (index + 1);
            gainNode.gain.value = 0;
            gainNode.gain.setValueAtTime(0, this.audioContext.currentTime);
            gainNode.gain.linearRampToValueAtTime(volume, this.audioContext.currentTime + 0.1);
            gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration);
            
            oscillator.connect(gainNode);
            
            // Route through effects chain if available, otherwise direct to master
            if (this.effectsChain) {
                gainNode.connect(this.effectsChain.input);
            } else {
                gainNode.connect(this.masterGain);
            }
            
            oscillator.start();
            oscillator.stop(this.audioContext.currentTime + duration);
            
            this.oscillators.push(oscillator);
            this.gainNodes.push(gainNode);
        });
    }
    
    playBass(rootFreq, duration) {
        const bassFreq = rootFreq / 2; // One octave lower
        
        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();
        
        oscillator.type = 'sawtooth';
        oscillator.frequency.value = bassFreq;
        
        gainNode.gain.value = 0;
        gainNode.gain.setValueAtTime(0, this.audioContext.currentTime);
        gainNode.gain.linearRampToValueAtTime(0.15, this.audioContext.currentTime + 0.05);
        gainNode.gain.exponentialRampToValueAtTime(0.001, this.audioContext.currentTime + duration);
        
        oscillator.connect(gainNode);
        
        // Route bass through effects chain too
        if (this.effectsChain) {
            gainNode.connect(this.effectsChain.input);
        } else {
            gainNode.connect(this.masterGain);
        }
        
        oscillator.start();
        oscillator.stop(this.audioContext.currentTime + duration);
        
        this.oscillators.push(oscillator);
        this.gainNodes.push(gainNode);
    }
    
    startDrumPattern(duration) {
        const beatCount = Math.floor(duration / this.beatDuration);
        
        for (let beat = 0; beat < beatCount && this.isPlaying; beat++) {
            const time = this.audioContext.currentTime + (beat * this.beatDuration);
            const patternIndex = beat % 16;
            
            // Kick drum
            if (this.drumPatterns.kick[patternIndex] > 0) {
                this.playDrum('kick', time, this.drumPatterns.kick[patternIndex]);
            }
            
            // Snare
            if (this.drumPatterns.snare[patternIndex] > 0) {
                this.playDrum('snare', time, this.drumPatterns.snare[patternIndex]);
            }
            
            // Hi-hat
            if (this.drumPatterns.hihat[patternIndex] > 0) {
                this.playDrum('hihat', time, this.drumPatterns.hihat[patternIndex]);
            }
        }
    }
    
    playDrum(type, time, velocity) {
        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();
        
        switch (type) {
            case 'kick':
                oscillator.frequency.value = 60;
                oscillator.type = 'sine';
                break;
            case 'snare':
                oscillator.frequency.value = 200;
                oscillator.type = 'square';
                break;
            case 'hihat':
                oscillator.frequency.value = 8000;
                oscillator.type = 'square';
                break;
        }
        
        const volume = velocity * 0.1;
        gainNode.gain.setValueAtTime(volume, time);
        gainNode.gain.exponentialRampToValueAtTime(0.001, time + 0.1);
        
        oscillator.connect(gainNode);
        
        // Route drums through effects chain too  
        if (this.effectsChain) {
            gainNode.connect(this.effectsChain.input);
        } else {
            gainNode.connect(this.masterGain);
        }
        
        oscillator.start(time);
        oscillator.stop(time + 0.1);
    }
    
    stop() {
        console.log('Stopping music...');
        
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
                // Oscillator may already be stopped
            }
        });
        
        // Clear arrays
        this.oscillators = [];
        this.gainNodes = [];
        
        this.isPlaying = false;
        this.currentKey = null;
        this.currentSection = null;
        
        console.log('Music stopped');
    }
    
    wait(ms) {
        return new Promise(resolve => {
            this.sectionTimeout = setTimeout(resolve, ms);
        });
    }
    
    // Effect presets
    setPresetEffects(presetName) {
        switch (presetName) {
            case 'ambient':
                this.setEffectEnabled('reverb', true);
                this.setEffectParameter('reverb', 'level', 0.4);
                this.setEffectEnabled('chorus', false);
                this.setEffectEnabled('flanger', false);
                this.setEffectEnabled('delay', false);
                break;
            case 'space':
                this.setEffectEnabled('reverb', true);
                this.setEffectParameter('reverb', 'level', 0.6);
                this.setEffectEnabled('delay', true);
                this.setEffectParameter('delay', 'level', 0.3);
                this.setEffectParameter('delay', 'time', 0.5);
                this.setEffectParameter('delay', 'feedback', 0.3);
                this.setEffectEnabled('chorus', false);
                this.setEffectEnabled('flanger', false);
                break;
            case 'ethereal':
                this.setEffectEnabled('reverb', true);
                this.setEffectParameter('reverb', 'level', 0.5);
                this.setEffectEnabled('chorus', true);
                this.setEffectParameter('chorus', 'level', 0.4);
                this.setEffectParameter('chorus', 'rate', 0.8);
                this.setEffectEnabled('flanger', false);
                this.setEffectEnabled('delay', false);
                break;
            case 'dreamy':
                this.setEffectEnabled('reverb', true);
                this.setEffectParameter('reverb', 'level', 0.4);
                this.setEffectEnabled('chorus', true);
                this.setEffectParameter('chorus', 'level', 0.3);
                this.setEffectEnabled('flanger', true);
                this.setEffectParameter('flanger', 'level', 0.2);
                this.setEffectParameter('flanger', 'rate', 0.3);
                this.setEffectEnabled('delay', false);
                break;
            case 'cosmic':
                this.setEffectEnabled('reverb', true);
                this.setEffectParameter('reverb', 'level', 0.7);
                this.setEffectEnabled('delay', true);
                this.setEffectParameter('delay', 'level', 0.4);
                this.setEffectParameter('delay', 'time', 0.75);
                this.setEffectParameter('delay', 'feedback', 0.5);
                this.setEffectEnabled('flanger', true);
                this.setEffectParameter('flanger', 'level', 0.2);
                this.setEffectEnabled('chorus', false);
                break;
        }
    }
    
    getStatus() {
        return {
            playing: this.isPlaying,
            currentKey: this.currentKey,
            currentSection: this.currentSection,
            enhancedMode: this.enhancedMode,
            effects: this.effects,
            audioContextState: this.audioContext ? this.audioContext.state : 'not initialized'
        };
    }
}

// Global unified music engine instance
const unifiedMusic = new UnifiedMusicEngine();
window.unifiedMusic = unifiedMusic;
console.log('Unified music engine loaded successfully');
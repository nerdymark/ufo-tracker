/**
 * Ambient Mood Music Generator for UFO Tracker
 * Creates ethereal, atmospheric music in various keys with structured compositions
 */

import javax.sound.midi.*;
import java.util.Random;
import java.util.concurrent.atomic.AtomicBoolean;

public class MoodMusicGenerator {
    private static final int PPQN = 480; // Pulses per quarter note
    private static final int TEMPO_BPM = 65; // Slow ambient tempo
    
    // Key signatures (root notes)
    private static final int[] KEYS = {
        57, // A3
        59, // B3  
        60, // C4
        62, // D4
        64, // E4
        65, // F4
        67  // G4
    };
    
    private static final String[] KEY_NAMES = {"A", "B", "C", "D", "E", "F", "G"};
    
    // Ambient chord progressions for each key (relative to root)
    private static final int[][] CHORD_PROGRESSIONS = {
        {0, 5, 2, 7}, // vi-IV-ii-V (minor feel)
        {0, 3, 5, 7}, // I-iii-V-vii (ethereal)
        {0, 2, 5, 4}, // I-ii-V-IV (classic ambient)
        {0, 7, 5, 2}  // I-vii-V-ii (floating)
    };
    
    private Sequencer sequencer;
    private Synthesizer synthesizer;
    private MidiChannel[] channels;
    private AtomicBoolean isPlaying = new AtomicBoolean(false);
    private Random random = new Random();
    
    public MoodMusicGenerator() throws MidiUnavailableException {
        // Initialize MIDI system
        sequencer = MidiSystem.getSequencer();
        synthesizer = MidiSystem.getSynthesizer();
        
        if (sequencer == null) {
            throw new MidiUnavailableException("No sequencer available");
        }
        
        sequencer.open();
        synthesizer.open();
        
        // Get MIDI channels
        channels = synthesizer.getChannels();
        
        // Setup instruments
        setupInstruments();
    }
    
    private void setupInstruments() {
        try {
            // Channel assignments for ambient layers
            channels[0].programChange(88); // Pad - New Age
            channels[1].programChange(89); // Pad - Warm
            channels[2].programChange(91); // Pad - Polysynth
            channels[3].programChange(50); // Strings - Slow Strings
            channels[4].programChange(92); // Pad - Choir
            channels[5].programChange(93); // Pad - Bowed Glass
            channels[6].programChange(18); // Organ - Percussive
            channels[7].programChange(40); // Violin (for lead melody)
        } catch (Exception e) {
            System.err.println("Error setting up instruments: " + e.getMessage());
        }
    }
    
    public void playRandomTrack() {
        if (isPlaying.get()) {
            stop();
        }
        
        try {
            int keyIndex = random.nextInt(KEYS.length);
            int rootNote = KEYS[keyIndex];
            String keyName = KEY_NAMES[keyIndex];
            
            System.out.println("Playing ambient track in key of " + keyName);
            
            Sequence sequence = createAmbientTrack(rootNote, keyName);
            sequencer.setSequence(sequence);
            sequencer.setTempoInBPM(TEMPO_BPM);
            sequencer.start();
            isPlaying.set(true);
            
        } catch (Exception e) {
            System.err.println("Error playing track: " + e.getMessage());
        }
    }
    
    private Sequence createAmbientTrack(int rootNote, String keyName) throws InvalidMidiDataException {
        Sequence sequence = new Sequence(Sequence.PPQ, PPQN);
        
        // Create tracks for different layers
        Track padTrack = sequence.createTrack();
        Track bassTrack = sequence.createTrack();
        Track melodyTrack = sequence.createTrack();
        Track atmosphereTrack = sequence.createTrack();
        
        // Song structure timing (in quarter notes)
        int intro = 16;          // 4 measures
        int verseLength = 32;    // 8 measures  
        int chorusLength = 24;   // 6 measures
        int bridgeLength = 16;   // 4 measures
        int outroLength = 24;    // 6 measures
        
        int currentTick = 0;
        
        // Get chord progression
        int[] progression = CHORD_PROGRESSIONS[random.nextInt(CHORD_PROGRESSIONS.length)];
        
        // INTRO - Atmospheric entrance
        currentTick = addIntro(padTrack, atmosphereTrack, rootNote, currentTick, intro);
        
        // VERSE 1 - Build layers
        currentTick = addVerse(padTrack, bassTrack, melodyTrack, rootNote, progression, currentTick, verseLength, 1);
        
        // CHORUS 1 - Full arrangement
        currentTick = addChorus(padTrack, bassTrack, melodyTrack, atmosphereTrack, rootNote, progression, currentTick, chorusLength, 1);
        
        // VERSE 2 - Variation
        currentTick = addVerse(padTrack, bassTrack, melodyTrack, rootNote, progression, currentTick, verseLength, 2);
        
        // CHORUS 2 - Developed
        currentTick = addChorus(padTrack, bassTrack, melodyTrack, atmosphereTrack, rootNote, progression, currentTick, chorusLength, 2);
        
        // BRIDGE - Key change up a fifth
        int bridgeKey = rootNote + 7;
        currentTick = addBridge(padTrack, bassTrack, melodyTrack, bridgeKey, currentTick, bridgeLength);
        
        // RETURN - Back to original key
        currentTick = addChorus(padTrack, bassTrack, melodyTrack, atmosphereTrack, rootNote, progression, currentTick, chorusLength, 3);
        
        // OUTRO - Fade to atmosphere
        currentTick = addOutro(padTrack, atmosphereTrack, rootNote, currentTick, outroLength);
        
        return sequence;
    }
    
    private int addIntro(Track padTrack, Track atmosphereTrack, int rootNote, int startTick, int length) throws InvalidMidiDataException {
        // Soft pad entrance
        addChord(padTrack, 0, rootNote, new int[]{0, 4, 7}, startTick, length * PPQN, 35);
        
        // Atmospheric high notes
        addNote(atmosphereTrack, 5, rootNote + 24, startTick + PPQN * 4, length * PPQN - PPQN * 4, 25);
        addNote(atmosphereTrack, 5, rootNote + 28, startTick + PPQN * 8, length * PPQN - PPQN * 8, 25);
        
        return startTick + length * PPQN;
    }
    
    private int addVerse(Track padTrack, Track bassTrack, Track melodyTrack, int rootNote, int[] progression, int startTick, int length, int verseNum) throws InvalidMidiDataException {
        int chordLength = length / 4; // 4 chords per verse
        int currentTick = startTick;
        
        for (int i = 0; i < 4; i++) {
            int chordRoot = rootNote + progression[i];
            
            // Pad chords
            addChord(padTrack, 0, chordRoot, new int[]{0, 4, 7}, currentTick, chordLength * PPQN, 40);
            
            // Bass notes (lower octave)
            addNote(bassTrack, 1, chordRoot - 12, currentTick, chordLength * PPQN, 35);
            
            // Gentle melody (verse 2 gets more elaborate)
            if (verseNum == 2) {
                addMelodyLine(melodyTrack, 7, rootNote, currentTick, chordLength * PPQN);
            }
            
            currentTick += chordLength * PPQN;
        }
        
        return currentTick;
    }
    
    private int addChorus(Track padTrack, Track bassTrack, Track melodyTrack, Track atmosphereTrack, int rootNote, int[] progression, int startTick, int length, int chorusNum) throws InvalidMidiDataException {
        int chordLength = length / 4;
        int currentTick = startTick;
        
        for (int i = 0; i < 4; i++) {
            int chordRoot = rootNote + progression[i];
            
            // Fuller pad arrangement
            addChord(padTrack, 0, chordRoot, new int[]{0, 4, 7}, currentTick, chordLength * PPQN, 50);
            addChord(padTrack, 2, chordRoot + 12, new int[]{0, 4, 7}, currentTick, chordLength * PPQN, 45);
            
            // Bass
            addNote(bassTrack, 1, chordRoot - 12, currentTick, chordLength * PPQN, 40);
            
            // Melody line
            addMelodyLine(melodyTrack, 7, rootNote + (chorusNum * 2), currentTick, chordLength * PPQN);
            
            // Atmospheric layer
            if (chorusNum >= 2) {
                addNote(atmosphereTrack, 4, chordRoot + 19, currentTick + PPQN, chordLength * PPQN - PPQN, 30);
            }
            
            currentTick += chordLength * PPQN;
        }
        
        return currentTick;
    }
    
    private int addBridge(Track padTrack, Track bassTrack, Track melodyTrack, int rootNote, int startTick, int length) throws InvalidMidiDataException {
        // Simple progression in new key
        int[] bridgeProgression = {0, 5, 4, 7}; // I-V-IV-vii
        int chordLength = length / 4;
        int currentTick = startTick;
        
        for (int i = 0; i < 4; i++) {
            int chordRoot = rootNote + bridgeProgression[i];
            
            // Lighter texture for contrast
            addChord(padTrack, 2, chordRoot, new int[]{0, 4, 7}, currentTick, chordLength * PPQN, 45);
            addNote(bassTrack, 1, chordRoot - 12, currentTick, chordLength * PPQN, 35);
            
            // Different melody character
            addNote(melodyTrack, 7, chordRoot + 7, currentTick + PPQN, chordLength * PPQN - PPQN * 2, 40);
            
            currentTick += chordLength * PPQN;
        }
        
        return currentTick;
    }
    
    private int addOutro(Track padTrack, Track atmosphereTrack, int rootNote, int startTick, int length) throws InvalidMidiDataException {
        // Fade back to simple atmosphere
        addChord(padTrack, 0, rootNote, new int[]{0, 4, 7}, startTick, length * PPQN, 30);
        
        // High atmospheric notes fading in and out
        addNote(atmosphereTrack, 5, rootNote + 24, startTick + PPQN * 2, PPQN * 8, 25);
        addNote(atmosphereTrack, 5, rootNote + 31, startTick + PPQN * 8, PPQN * 8, 20);
        addNote(atmosphereTrack, 5, rootNote + 28, startTick + PPQN * 12, PPQN * 8, 15);
        
        return startTick + length * PPQN;
    }
    
    private void addChord(Track track, int channel, int rootNote, int[] intervals, int startTick, int duration, int velocity) throws InvalidMidiDataException {
        for (int interval : intervals) {
            int note = rootNote + interval;
            if (note >= 0 && note <= 127) {
                addNote(track, channel, note, startTick, duration, velocity);
            }
        }
    }
    
    private void addNote(Track track, int channel, int note, int startTick, int duration, int velocity) throws InvalidMidiDataException {
        // Note on
        ShortMessage noteOn = new ShortMessage();
        noteOn.setMessage(ShortMessage.NOTE_ON, channel, note, velocity);
        track.add(new MidiEvent(noteOn, startTick));
        
        // Note off
        ShortMessage noteOff = new ShortMessage();
        noteOff.setMessage(ShortMessage.NOTE_OFF, channel, note, 0);
        track.add(new MidiEvent(noteOff, startTick + duration));
    }
    
    private void addMelodyLine(Track track, int channel, int rootNote, int startTick, int duration) throws InvalidMidiDataException {
        // Simple ascending and descending melodic phrases
        int[] melodyNotes = {0, 2, 4, 7, 9, 7, 4, 2};
        int noteLength = duration / melodyNotes.length;
        
        for (int i = 0; i < melodyNotes.length; i++) {
            int note = rootNote + melodyNotes[i] + 12; // Octave higher
            int tick = startTick + (i * noteLength);
            addNote(track, channel, note, tick, noteLength - PPQN/4, 35); // Slight gap between notes
        }
    }
    
    public void stop() {
        if (sequencer != null && sequencer.isRunning()) {
            sequencer.stop();
            isPlaying.set(false);
        }
    }
    
    public boolean isPlaying() {
        return isPlaying.get() && sequencer != null && sequencer.isRunning();
    }
    
    public void close() {
        stop();
        if (sequencer != null) {
            sequencer.close();
        }
        if (synthesizer != null) {
            synthesizer.close();
        }
    }
    
    // Test the music generator
    public static void main(String[] args) {
        try {
            MoodMusicGenerator generator = new MoodMusicGenerator();
            System.out.println("Starting ambient mood music...");
            generator.playRandomTrack();
            
            // Keep playing for demo
            Thread.sleep(120000); // 2 minutes
            
            generator.close();
        } catch (Exception e) {
            System.err.println("Error: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
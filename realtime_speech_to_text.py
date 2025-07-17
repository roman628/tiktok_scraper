import os
import sys

def setup_cuda_paths():
    """Set up CUDA paths with priority (always works)"""
    # Define the exact paths that work
    cuda_paths = [
        r"C:\Users\roman\AppData\Roaming\Python\Python313\site-packages\nvidia\cublas\bin",
        r"C:\Users\roman\AppData\Roaming\Python\Python313\site-packages\nvidia\cudnn\bin"
    ]
    
    # Add to PATH with HIGH PRIORITY (at the beginning)
    current_path = os.environ.get('PATH', '')
    
    for cuda_path in cuda_paths:
        if os.path.exists(cuda_path) and cuda_path not in current_path:
            # Add at the BEGINNING of PATH for priority
            os.environ['PATH'] = cuda_path + ';' + os.environ['PATH']
    
    print("✅ CUDA paths set with high priority")

# Setup CUDA before importing faster-whisper
setup_cuda_paths()

import pyaudio
import wave
import threading
import time
import pyperclip
import numpy as np
from faster_whisper import WhisperModel
import queue
import tempfile
import msvcrt

class RealTimeSpeechToText:
    def __init__(self):
        # Audio settings
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 16000
        
        # Initialize model with GPU priority
        print("Loading faster-whisper model...")
        
        try:
            print("🚀 Loading GPU model...")
            self.model = WhisperModel(
                "small.en", 
                device="cuda", 
                compute_type="float16"
            )
            self.device_info = "GPU (RTX 4070 Super)"
            print("🎉 GPU model loaded successfully!")
        except Exception as e:
            print(f"⚠️  GPU failed: {e}")
            print("🔄 Loading CPU model...")
            self.model = WhisperModel("small.en", device="cpu", compute_type="int8")
            self.device_info = "CPU (i7-14700KF)"
            print("✅ CPU model loaded!")
        
        # Audio processing
        self.audio = pyaudio.PyAudio()
        self.audio_queue = queue.Queue()
        self.is_recording = False
        self.is_paused = False
        self.recording_thread = None
        self.processing_thread = None
        self.input_thread = None
        
        # Voice settings (optimized from your tests)
        self.silence_threshold = 50
        self.min_audio_length = 0.8
        
        # Performance tracking
        self.transcription_count = 0
        
        # Force transcribe buffer
        self.current_audio_buffer = []
        self.buffer_lock = threading.Lock()
        
    def get_audio_level(self, data):
        """Calculate RMS audio level"""
        try:
            audio_data = np.frombuffer(data, dtype=np.int16)
            if len(audio_data) == 0:
                return 0
            mean_square = np.mean(audio_data.astype(np.float64) ** 2)
            if mean_square <= 0 or np.isnan(mean_square):
                return 0
            return np.sqrt(mean_square)
        except:
            return 0
    
    def check_for_input(self):
        """Handle keyboard controls"""
        print(f"\n🎤 Real-time Speech-to-Text Ready!")
        print(f"📊 Running on: {self.device_info}")
        print("\nControls:")
        print("  q = Quit")
        print("  p = Pause/Resume") 
        print("  s = Adjust sensitivity")
        print("  t = Test microphone")
        print("  SPACE = Force transcribe current audio")
        print("\n💬 Speak and your text will be copied to clipboard!")
        print("🔄 Listening...\n")
        
        while self.is_recording:
            try:
                if msvcrt.kbhit():
                    key = msvcrt.getch().decode('utf-8').lower()
                    if key == 'q':
                        print("\n🛑 Quitting...")
                        self.is_recording = False
                        break
                    elif key == 'p':
                        self.is_paused = not self.is_paused
                        status = "⏸️  Paused" if self.is_paused else "▶️  Resumed"
                        print(f"\n{status}")
                    elif key == 's':
                        self.adjust_sensitivity()
                    elif key == 't':
                        self.test_microphone()
                    elif key == ' ':  # Spacebar for force transcribe
                        self.force_transcribe()
                time.sleep(0.1)
            except:
                time.sleep(0.1)
    
    def test_microphone(self):
        """Test microphone levels"""
        print("\n🔊 Testing microphone for 3 seconds...")
        print("💬 Speak normally...")
        
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        levels = []
        max_level = 0
        
        for i in range(int(3 * self.RATE / self.CHUNK)):
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                level = self.get_audio_level(data)
                if level > 0:
                    levels.append(level)
                    max_level = max(max_level, level)
                
                indicator = "🔊" if level > self.silence_threshold else "🔇"
                print(f"Level: {level:.0f} {indicator}", end="\r")
                time.sleep(0.1)
            except:
                break
        
        stream.close()
        
        if levels:
            avg_level = sum(levels) / len(levels)
            print(f"\n📊 Max: {max_level:.0f} | Avg: {avg_level:.0f} | Threshold: {self.silence_threshold}")
            
            if max_level > 0:
                recommended = max(10, int(max_level * 0.3))
                print(f"💡 Recommended threshold: {recommended}")
        
        print("Press any key to continue...")
    
    def force_transcribe(self):
        """Force transcribe current audio buffer"""
        with self.buffer_lock:
            if self.current_audio_buffer:
                audio_data = b''.join(self.current_audio_buffer)
                duration = len(audio_data) / (self.RATE * 2)
                if duration > 0.2:  # At least 0.2 seconds
                    print(f"\n⚡ Force transcribing {duration:.1f}s of audio...")
                    self.audio_queue.put(audio_data)
                    self.current_audio_buffer = []
                else:
                    print("\n⚠️  Not enough audio to transcribe")
            else:
                print("\n⚠️  No audio buffer to transcribe")
        """Adjust microphone sensitivity"""
        print(f"\n🔧 Current threshold: {self.silence_threshold}")
        print("💡 Guidelines: 10-30 (sensitive) | 30-60 (normal) | 60+ (less sensitive)")
        
        try:
            new_val = input("New threshold (or Enter to keep): ").strip()
            if new_val:
                self.silence_threshold = max(5, int(new_val))
                print(f"✅ Updated to: {self.silence_threshold}")
        except:
            print("❌ Invalid, keeping current")
    
    def record_audio(self):
        """Record audio continuously"""
        stream = self.audio.open(
            format=self.FORMAT,
            channels=self.CHANNELS,
            rate=self.RATE,
            input=True,
            frames_per_buffer=self.CHUNK
        )
        
        audio_buffer = []
        silence_count = 0
        recording_speech = False
        voice_frames = 0
        
        while self.is_recording:
            if self.is_paused:
                time.sleep(0.1)
                continue
                
            try:
                data = stream.read(self.CHUNK, exception_on_overflow=False)
                level = self.get_audio_level(data)
                
                if level > self.silence_threshold:
                    voice_frames += 1
                    audio_buffer.append(data)
                    with self.buffer_lock:
                        self.current_audio_buffer.append(data)
                    silence_count = 0
                    
                    if not recording_speech and voice_frames >= 3:
                        recording_speech = True
                        print(f"🎤 Recording... (level: {level:.0f})")
                else:
                    voice_frames = 0
                    if recording_speech:
                        silence_count += 1
                        audio_buffer.append(data)
                        
                        if silence_count > 20:  # ~0.5s silence
                            duration = len(audio_buffer) * self.CHUNK / self.RATE
                            if duration >= self.min_audio_length:
                                audio_data = b''.join(audio_buffer)
                                self.audio_queue.put(audio_data)
                                print(f"🔄 Processing {duration:.1f}s...")
                            
                            audio_buffer = []
                            with self.buffer_lock:
                                self.current_audio_buffer = []
                            recording_speech = False
                            silence_count = 0
                
            except Exception as e:
                print(f"❌ Recording error: {e}")
                break
        
        stream.stop_stream()
        stream.close()
    
    def process_audio_queue(self):
        """Process transcription queue"""
        while self.is_recording or not self.audio_queue.empty():
            try:
                if not self.audio_queue.empty():
                    audio_data = self.audio_queue.get(timeout=1)
                    self.transcribe_audio(audio_data)
            except queue.Empty:
                continue
    
    def transcribe_audio(self, audio_data):
        """Transcribe audio to text"""
        try:
            # Create temp WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                
                with wave.open(temp_filename, 'wb') as wf:
                    wf.setnchannels(self.CHANNELS)
                    wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                    wf.setframerate(self.RATE)
                    wf.writeframes(audio_data)
            
            # Transcribe
            start_time = time.time()
            segments, info = self.model.transcribe(
                temp_filename, 
                beam_size=1,
                language="en"
            )
            
            # Extract text
            text = ""
            for segment in segments:
                if segment.text.strip():
                    text += segment.text.strip() + " "
            
            text = text.strip()
            
            if text and len(text) > 2:
                end_time = time.time()
                processing_time = end_time - start_time
                
                # Copy to clipboard
                try:
                    pyperclip.copy(text)
                    clipboard_status = "✅ Copied!"
                except:
                    clipboard_status = "❌ Clipboard failed"
                
                # Performance stats
                audio_duration = len(audio_data) / (self.RATE * 2)
                rt_factor = audio_duration / processing_time if processing_time > 0 else 0
                
                self.transcription_count += 1
                
                print(f"\n📋 [{self.transcription_count}] ({processing_time:.2f}s | {rt_factor:.1f}x RT)")
                print(f"💬 \"{text}\"")
                print(f"{clipboard_status}\n")
            
            # Cleanup
            if os.path.exists(temp_filename):
                os.remove(temp_filename)
                
        except Exception as e:
            print(f"❌ Transcription error: {e}")
            if 'temp_filename' in locals() and os.path.exists(temp_filename):
                os.remove(temp_filename)
    
    def start_listening(self):
        """Start the transcription system"""
        self.is_recording = True
        
        # Start all threads
        self.recording_thread = threading.Thread(target=self.record_audio, daemon=True)
        self.processing_thread = threading.Thread(target=self.process_audio_queue, daemon=True)
        self.input_thread = threading.Thread(target=self.check_for_input, daemon=True)
        
        self.recording_thread.start()
        self.processing_thread.start()
        self.input_thread.start()
        
        # Wait for completion
        try:
            self.input_thread.join()
        except KeyboardInterrupt:
            print("\n🛑 Ctrl+C pressed")
            self.is_recording = False
        
        # Cleanup
        if self.recording_thread and self.recording_thread.is_alive():
            self.recording_thread.join(timeout=2)
        if self.processing_thread and self.processing_thread.is_alive():
            self.processing_thread.join(timeout=2)
    
    def cleanup(self):
        """Clean up resources"""
        if self.audio:
            self.audio.terminate()

def transcribe_mp3_file(file_path, model):
    """Transcribe an MP3 file"""
    if not os.path.exists(file_path):
        print(f"❌ File not found: {file_path}")
        return
    
    print(f"🎵 Transcribing: {os.path.basename(file_path)}")
    start_time = time.time()
    
    try:
        segments, info = model.transcribe(file_path, beam_size=1, language="en")
        
        # Extract text
        full_text = ""
        for segment in segments:
            if segment.text.strip():
                full_text += segment.text.strip() + " "
        
        full_text = full_text.strip()
        
        if full_text:
            end_time = time.time()
            processing_time = end_time - start_time
            
            # Save to text file
            output_file = os.path.splitext(file_path)[0] + "_transcript.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(full_text)
            
            # Copy to clipboard
            try:
                pyperclip.copy(full_text)
                clipboard_status = "✅ Copied to clipboard!"
            except:
                clipboard_status = "❌ Clipboard failed"
            
            print(f"\n📋 Transcription completed in {processing_time:.2f}s")
            print(f"💬 \"{full_text[:100]}{'...' if len(full_text) > 100 else ''}\"")
            print(f"📄 Saved to: {output_file}")
            print(f"{clipboard_status}")
        else:
            print("❌ No speech detected in file")
            
    except Exception as e:
        print(f"❌ Error transcribing file: {e}")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Real-time Speech-to-Text with GPU acceleration')
    parser.add_argument('--file', '-f', type=str, help='Transcribe an MP3 file instead of real-time')
    args = parser.parse_args()
    
    print("=" * 60)
    print("🚀 REAL-TIME SPEECH-TO-TEXT")
    print("=" * 60)
    print("Optimized for RTX 4070 Super + Intel i7-14700KF")
    print()
    
    # Initialize model
    setup_cuda_paths()
    
    try:
        print("Loading faster-whisper model...")
        print("🚀 Loading GPU model...")
        model = WhisperModel("small.en", device="cuda", compute_type="float16")
        device_info = "GPU (RTX 4070 Super)"
        print("🎉 GPU model loaded successfully!")
    except Exception as e:
        print(f"⚠️  GPU failed: {e}")
        print("🔄 Loading CPU model...")
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        device_info = "CPU (i7-14700KF)"
        print("✅ CPU model loaded!")
    
    # Check if file transcription mode
    if args.file:
        transcribe_mp3_file(args.file, model)
        return
    
    # Real-time mode
    recognizer = RealTimeSpeechToText()
    recognizer.model = model
    recognizer.device_info = device_info
    
    try:
        recognizer.start_listening()
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        recognizer.cleanup()
        print("👋 Goodbye!")

if __name__ == "__main__":
    main()
# REMOVE THIS ENTIRE FILE FOR PRODUCTION USE
from datetime import datetime
import os

class WebSocketDebugLogger:
    def __init__(self, log_file="logs/websocket_debug.txt", audio_dump_file="logs/received_audio_bytes.bin"):
        self.log_file = log_file
        self.audio_dump_file = audio_dump_file
        self.audio_chunk_count = 0
        
        # Create/clear the log file
        with open(self.log_file, 'w') as f:
            f.write(f"WebSocket Debug Log Started: {datetime.now()}\n")
            f.write("=" * 60 + "\n")
        
        # Create/clear the audio dump file
        with open(self.audio_dump_file, 'wb') as f:
            pass  # Just create/clear the binary file
    
    def log(self, message):
        """Write a timestamped message to the log file"""
        try:
            with open(self.log_file, 'a') as f:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            pass  # Silent fail to avoid breaking the main app
    
    def log_connection_accepted(self):
        self.log("WebSocket connection accepted")
    
    def log_thread_started(self, thread_name):
        self.log(f"{thread_name} thread started")
    
    def log_waiting_for_message(self):
        self.log("Waiting for WebSocket message...")
    
    def log_message_received(self, byte_count):
        self.log(f"Received WebSocket message: {byte_count} bytes")
    
    def log_processing_chunk(self, byte_count):
        self.log(f"Processing {byte_count}-byte audio chunk")
    
    def log_sent_to_gemini_queue(self, byte_count):
        self.log(f"Sent {byte_count} bytes to Gemini queue")
    
    def log_unexpected_chunk_size(self, received_size, expected_size):
        self.log(f"Unexpected audio chunk size: {received_size} bytes, expected {expected_size}")
    
    def log_error(self, error_context, error):
        self.log(f"ERROR in {error_context}: {error}")
    
    def log_gemini_session_opened(self):
        self.log("Gemini session opened")
    
    def log_connection_closed(self):
        self.log("Audio source closed connection")
    
    def dump_audio_bytes(self, audio_bytes):
        """Dump raw audio bytes to binary file for analysis"""
        try:
            self.audio_chunk_count += 1
            
            # Write raw bytes to binary file
            with open(self.audio_dump_file, 'ab') as f:
                f.write(audio_bytes)
            
            # Log metadata about the audio chunk
            self.log(f"AUDIO DUMP #{self.audio_chunk_count}: {len(audio_bytes)} bytes written to {self.audio_dump_file}")
            
            # Log first 20 bytes as hex for inspection
            hex_preview = ' '.join(f'{b:02x}' for b in audio_bytes[:20])
            self.log(f"  First 20 bytes (hex): {hex_preview}...")
            
            # Log some basic audio analysis
            if len(audio_bytes) >= 2:
                # Interpret as 16-bit little-endian signed integers
                import struct
                samples = []
                for i in range(0, min(len(audio_bytes), 40), 2):  # First 20 samples
                    if i + 1 < len(audio_bytes):
                        sample = struct.unpack('<h', audio_bytes[i:i+2])[0]  # little-endian signed 16-bit
                        samples.append(sample)
                
                if samples:
                    self.log(f"  First 10 samples (16-bit): {samples[:10]}")
                    self.log(f"  Sample range: {min(samples)} to {max(samples)}")
                    
        except Exception as e:
            self.log(f"ERROR dumping audio bytes: {e}")
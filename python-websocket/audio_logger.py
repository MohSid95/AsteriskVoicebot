# REMOVE THIS ENTIRE FILE FOR PRODUCTION USE
import time
import asyncio
from datetime import datetime
import os

class AudioFlowLogger:
    def __init__(self, log_file="logs/audio_debug.txt"):
        self.audio_bytes_sent_to_gemini = 0
        self.audio_bytes_received_from_gemini = 0
        self.audio_chunks_sent_to_go = 0
        self.last_log_time = time.time()
        self.gemini_response_count = 0
        self.last_gemini_response_time = None
        self.is_active = True
        self.log_file = log_file
        
        # Create/clear the log file
        with open(self.log_file, 'w') as f:
            f.write(f"Audio Debug Log Started: {datetime.now()}\n")
            f.write("=" * 60 + "\n")
        
    def log_audio_sent_to_gemini(self, byte_count):
        """Log audio bytes sent to Gemini"""
        self.audio_bytes_sent_to_gemini += byte_count
        self._write_log(f"Sent {byte_count} bytes to Gemini")
        
    def log_audio_received_from_gemini(self, byte_count):
        """Log audio bytes received from Gemini"""
        self.audio_bytes_received_from_gemini += byte_count
        self.last_gemini_response_time = time.time()
        self._write_log(f"Received {byte_count} bytes from Gemini")
        
    def log_audio_chunk_sent_to_go(self):
        """Log audio chunk sent to Go app"""
        self.audio_chunks_sent_to_go += 1
        self._write_log("Sent audio chunk to Go app")
        
    def log_gemini_response(self):
        """Log Gemini response received"""
        self.gemini_response_count += 1
        self.last_gemini_response_time = time.time()
        self._write_log("Gemini response received")
        
    def _write_log(self, message):
        """Write a timestamped message to the log file"""
        try:
            with open(self.log_file, 'a') as f:
                timestamp = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                f.write(f"[{timestamp}] {message}\n")
        except Exception as e:
            pass  # Silent fail to avoid breaking the main app
    
    def stop(self):
        """Stop the logger"""
        self.is_active = False
        self._write_log("Audio logger stopped")
        
    async def start_periodic_logging(self):
        """Start periodic logging every 5 seconds"""
        while self.is_active:
            await asyncio.sleep(5)  # Log every 5 seconds
            current_time = time.time()
            
            # Write to file instead of printing
            with open(self.log_file, 'a') as f:
                f.write(f"\n=== AUDIO FLOW DEBUG ({datetime.now().strftime('%H:%M:%S')}) ===\n")
                f.write(f"Audio bytes sent TO Gemini (last 5s): {self.audio_bytes_sent_to_gemini}\n")
                f.write(f"Audio bytes received FROM Gemini (last 5s): {self.audio_bytes_received_from_gemini}\n")
                f.write(f"Audio chunks sent to Go app (last 5s): {self.audio_chunks_sent_to_go}\n")
                f.write(f"Gemini responses received (last 5s): {self.gemini_response_count}\n")
                
                if self.last_gemini_response_time:
                    seconds_since_response = current_time - self.last_gemini_response_time
                    f.write(f"Time since last Gemini response: {seconds_since_response:.1f}s\n")
                else:
                    f.write("No Gemini responses received yet\n")
                    
                f.write("=" * 50 + "\n")
            
            # Reset counters for next period
            self.audio_bytes_sent_to_gemini = 0
            self.audio_bytes_received_from_gemini = 0
            self.audio_chunks_sent_to_go = 0
            self.gemini_response_count = 0
            self.last_log_time = current_time
# REMOVE THIS ENTIRE FILE FOR PRODUCTION USE
import time
import asyncio
from datetime import datetime

class AudioFlowLogger:
    def __init__(self):
        self.audio_bytes_sent_to_gemini = 0
        self.audio_bytes_received_from_gemini = 0
        self.audio_chunks_sent_to_go = 0
        self.last_log_time = time.time()
        self.gemini_response_count = 0
        self.last_gemini_response_time = None
        self.is_active = True
        
    def log_audio_sent_to_gemini(self, byte_count):
        """Log audio bytes sent to Gemini"""
        self.audio_bytes_sent_to_gemini += byte_count
        
    def log_audio_received_from_gemini(self, byte_count):
        """Log audio bytes received from Gemini"""
        self.audio_bytes_received_from_gemini += byte_count
        self.last_gemini_response_time = time.time()
        
    def log_audio_chunk_sent_to_go(self):
        """Log audio chunk sent to Go app"""
        self.audio_chunks_sent_to_go += 1
        
    def log_gemini_response(self):
        """Log Gemini response received"""
        self.gemini_response_count += 1
        self.last_gemini_response_time = time.time()
        
    def stop(self):
        """Stop the logger"""
        self.is_active = False
        
    async def start_periodic_logging(self):
        """Start periodic logging every 5 seconds"""
        while self.is_active:
            await asyncio.sleep(5)  # Log every 5 seconds
            current_time = time.time()
            
            print(f"\n=== AUDIO FLOW DEBUG ({datetime.now().strftime('%H:%M:%S')}) ===")
            print(f"Audio bytes sent TO Gemini (last 5s): {self.audio_bytes_sent_to_gemini}")
            print(f"Audio bytes received FROM Gemini (last 5s): {self.audio_bytes_received_from_gemini}")
            print(f"Audio chunks sent to Go app (last 5s): {self.audio_chunks_sent_to_go}")
            print(f"Gemini responses received (last 5s): {self.gemini_response_count}")
            
            if self.last_gemini_response_time:
                seconds_since_response = current_time - self.last_gemini_response_time
                print(f"Time since last Gemini response: {seconds_since_response:.1f}s")
            else:
                print("No Gemini responses received yet")
                
            print("=" * 50)
            
            # Reset counters for next period
            self.audio_bytes_sent_to_gemini = 0
            self.audio_bytes_received_from_gemini = 0
            self.audio_chunks_sent_to_go = 0
            self.gemini_response_count = 0
            self.last_log_time = current_time
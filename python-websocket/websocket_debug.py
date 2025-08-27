# REMOVE THIS ENTIRE FILE FOR PRODUCTION USE
from datetime import datetime
import os

class WebSocketDebugLogger:
    def __init__(self, log_file="logs/websocket_debug.txt"):
        self.log_file = log_file
        
        # Create/clear the log file
        with open(self.log_file, 'w') as f:
            f.write(f"WebSocket Debug Log Started: {datetime.now()}\n")
            f.write("=" * 60 + "\n")
    
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
    

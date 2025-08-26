#!/bin/bash

# Development startup script
echo "=== AsteriskVoicebot Development Environment ==="
echo "Starting services with Docker Compose..."

# Create logs and transcripts directories if they don't exist
mkdir -p logs transcripts

# Build and start services
docker-compose up --build -d

echo "Services starting..."
sleep 3

echo ""
echo "=== Service Status ==="
docker-compose ps

echo ""
echo "=== Available endpoints ==="
echo "Python WebSocket: ws://localhost:8080/media"
echo "Go AudioSocket: localhost:9092"

echo ""
echo "=== Useful commands ==="
echo "View Python logs:     docker-compose logs -f python-websocket"
echo "View Go logs:         docker-compose logs -f go-audiosocket"
echo "View all logs:        docker-compose logs -f"
echo "Stop services:        docker-compose down"
echo "Test with Asterisk:   Configure Asterisk to connect to localhost:9092"

echo ""
echo "=== Debug files ==="
echo "Logs directory (./logs/):"
echo "- websocket_debug.txt       (WebSocket message processing)"
echo "- audio_debug.txt           (Audio flow statistics)"  
echo "- received_audio_bytes.bin  (Raw audio data dump)"
echo ""
echo "Python WebSocket directory:"
echo "- live_conversation_transcript.txt  (Real-time conversation)"
echo "- conversation_transcript.txt       (Final transcript on call end)"
#!/bin/bash

# Complete testing workflow script
echo "=== AsteriskVoicebot Testing Workflow ==="

# Function to check if services are ready
check_services() {
    echo "Checking if services are ready..."
    
    # Wait for Python WebSocket
    for i in {1..30}; do
        if curl -s http://localhost:8080 > /dev/null 2>&1; then
            echo "✓ Python WebSocket is ready"
            break
        fi
        if [ $i -eq 30 ]; then
            echo "✗ Python WebSocket failed to start"
            exit 1
        fi
        sleep 1
    done
}

# Start services
echo "1. Starting services..."
./dev-start.sh

# Wait for services to be ready
sleep 5
check_services

echo ""
echo "2. Services are ready for Asterisk connection..."
echo "Configure Asterisk to connect to this VM's IP on port 9092"
echo "Make a test call to verify the audio data flow"
echo ""
echo "Waiting 30 seconds for potential Asterisk connection..."
sleep 30

echo ""
echo "3. Checking debug output..."

# Check if debug files were created
if [ -f "logs/websocket_debug.txt" ]; then
    echo "✓ WebSocket debug file created"
    echo "Last 10 lines of WebSocket debug:"
    tail -10 logs/websocket_debug.txt
else
    echo "✗ WebSocket debug file not found"
fi

if [ -f "logs/audio_debug.txt" ]; then
    echo "✓ Audio debug file created"
    echo "Last 10 lines of audio debug:"
    tail -10 logs/audio_debug.txt
else
    echo "✗ Audio debug file not found"
fi

if [ -f "logs/received_audio_bytes.bin" ]; then
    SIZE=$(stat -f%z logs/received_audio_bytes.bin 2>/dev/null || stat -c%s logs/received_audio_bytes.bin 2>/dev/null)
    echo "✓ Audio bytes file created: $SIZE bytes"
    echo "First 64 bytes (hex):"
    hexdump -C logs/received_audio_bytes.bin | head -4
else
    echo "✗ Audio bytes file not found"
fi

echo ""
echo "4. Service logs (last 20 lines):"
echo "--- Python WebSocket ---"
docker-compose logs --tail=20 python-websocket

echo "--- Go AudioSocket ---"
docker-compose logs --tail=20 go-audiosocket

echo ""
echo "Testing complete!"
echo "To stop services: docker-compose down"
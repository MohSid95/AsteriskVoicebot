# AsteriskVoicebot Deployment Guide

## Prerequisites
- Ubuntu VM with Docker and Docker Compose installed
- Git installed on the VM
- Google Cloud Service Account credentials JSON file
- Asterisk server that can reach the VM's network

## Step-by-Step Deployment

### 1. Clone Repository on Ubuntu VM
```bash
git clone https://github.com/YOUR_USERNAME/AsteriskVoicebot.git
cd AsteriskVoicebot
```

### 2. Setup Google Cloud Credentials

**Option A: Upload credentials file directly**
```bash
# Copy your Google Cloud service account JSON file to the project root
# Name it exactly 'credentials.json'
scp /path/to/your/service-account-key.json user@vm-ip:/path/to/AsteriskVoicebot/credentials.json
```

**Option B: Create credentials file on VM**
```bash
# Create credentials.json file in the project root
nano credentials.json
# Paste your Google Cloud service account JSON content
```

**Verify credentials file:**
```bash
# The file should be in the project root
ls -la credentials.json
# Should show the file exists and has appropriate permissions
```

### 3. Get VM Network Information
```bash
# Find your VM's IP address
ip addr show
# Or
hostname -I

# Note the IP address - this is what Asterisk will connect to
# Example: 192.168.1.100 or 10.0.0.50
```

### 4. Start Services
```bash
# Make scripts executable
chmod +x dev-start.sh test-workflow.sh

# Start all services with Docker
./dev-start.sh
```

### 5. Verify Services Are Running
```bash
# Check service status
docker-compose ps

# Should show both services as "Up"
# go-audiosocket listening on 0.0.0.0:9092
# python-websocket listening on 0.0.0.0:8080

# Check if ports are accessible
sudo netstat -tlnp | grep :9092
sudo netstat -tlnp | grep :8080
```

### 6. Configure Asterisk Connectivity

**Find the exact IP to use:**
```bash
# Method 1: Check VM's main IP
ip route get 8.8.8.8 | awk '{print $7; exit}'

# Method 2: Check all interfaces
ip addr show | grep "inet " | grep -v 127.0.0.1
```

**Configure Asterisk to connect to:**
```
# Use your VM's IP address and port 9092
[your-vm-ip]:9092

# Examples:
# 192.168.1.100:9092
# 10.0.0.50:9092
# 172.16.0.10:9092
```

**Test connectivity from Asterisk server:**
```bash
# From your Asterisk server, test if the port is reachable
telnet [your-vm-ip] 9092
# Should connect successfully

# Or use nc (netcat)
nc -zv [your-vm-ip] 9092
# Should show "Connection to [ip] 9092 port [tcp] succeeded!"
```

## Network Troubleshooting

### If Asterisk can't connect to VM:

**Check firewall on Ubuntu VM:**
```bash
# Check if UFW is blocking the port
sudo ufw status

# Allow port 9092 if needed
sudo ufw allow 9092/tcp

# For iptables
sudo iptables -I INPUT -p tcp --dport 9092 -j ACCEPT
```

**Check Docker port binding:**
```bash
# Verify Docker is binding to all interfaces (0.0.0.0)
docker-compose ps
netstat -tlnp | grep :9092
# Should show: 0.0.0.0:9092, not 127.0.0.1:9092
```

**Test from VM itself:**
```bash
# Test if service responds locally
telnet localhost 9092
# Should connect to Go audiosocket service
```

## Monitoring and Debugging

### Real-time monitoring:
```bash
# Monitor all logs
docker-compose logs -f

# Monitor specific services
docker-compose logs -f go-audiosocket     # Shows Asterisk connections
docker-compose logs -f python-websocket  # Shows Gemini processing

# Monitor debug files
tail -f logs/websocket_debug.txt          # WebSocket message flow
tail -f live_conversation_transcript.txt  # Live conversation
```

### Check Google Cloud credentials:
```bash
# Verify credentials are mounted correctly in container
docker-compose exec python-websocket ls -la /app/credentials.json
docker-compose exec python-websocket echo $GOOGLE_APPLICATION_CREDENTIALS

# Test credentials work (should show no permission errors in logs)
docker-compose logs python-websocket | grep -i "credential\|auth\|permission"
```

## Service Endpoints Summary

- **Go AudioSocket** (for Asterisk): `[VM-IP]:9092`
- **Python WebSocket** (internal only): `localhost:8080/media`
- **Debug logs**: `./logs/` directory
- **Live transcript**: `./live_conversation_transcript.txt`

## Stopping Services
```bash
# Stop all containers
docker-compose down

# Stop and remove volumes/networks
docker-compose down -v
```

## Common Issues

1. **"Permission denied" for credentials**: Check file permissions on `credentials.json`
2. **Asterisk can't connect**: Check VM firewall and network connectivity
3. **No audio processing**: Check if credentials are properly loaded
4. **Container won't start**: Check Docker logs with `docker-compose logs [service-name]`
# Asterisk AudioSocket Voicebot

Simple Go application that reads and prints audio byte streams from Asterisk using AudioSocket.

## Setup Instructions

### 1. Build and Run the Go Application

```bash
go mod tidy
go build -o audiosocket-server main.go
./audiosocket-server
```

The server will listen on port 9092.

### 2. Verify AudioSocket Module is Available

First, check if AudioSocket is compiled in your Asterisk installation:

```bash
sudo asterisk -rx "module show like audiosocket"
```

If nothing shows, AudioSocket may not be compiled. Install it:

```bash
# On CentOS/RHEL/FreePBX Distro
sudo yum install asterisk-audiosocket
# or build from source if not available
```

### 3. Configure Asterisk Modules

1. Edit `/etc/asterisk/modules.conf`:
```bash
sudo nano /etc/asterisk/modules.conf
```

2. Ensure AudioSocket is loaded (add this line in the modules section):
```
load => app_audiosocket.so
```

3. Reload modules:
```bash
sudo asterisk -rx "module load app_audiosocket.so"
```

4. Verify it's loaded:
```bash
sudo asterisk -rx "module show like audiosocket"
```

### 4. Network and Firewall Configuration

1. **Open firewall port** (if firewall is enabled):
```bash
# For firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-port=9092/tcp
sudo firewall-cmd --reload

# For iptables
sudo iptables -I INPUT -p tcp --dport 9092 -j ACCEPT
sudo service iptables save
```

2. **Test network connectivity** from Asterisk server to Go server:
```bash
telnet YOUR_GO_SERVER_IP 9092
```

### 5. FreePBX16 Dialplan Configuration

#### Method 1: Direct Extensions_custom.conf Edit

1. **SSH into FreePBX server** as root
2. **Backup current config**:
```bash
cp /etc/asterisk/extensions_custom.conf /etc/asterisk/extensions_custom.conf.backup
```

3. **Edit extensions_custom.conf**:
```bash
nano /etc/asterisk/extensions_custom.conf
```

4. **Add this complete dialplan context**:
```
[audiosocket-test]
exten => s,1,NoOp(=== AudioSocket Test Started ===)
 same => n,Answer()
 same => n,Wait(1)
 same => n,Playback(hello-world)
 same => n,Wait(1)
 same => n,NoOp(Connecting to AudioSocket at YOUR_SERVER_IP:9092)
 same => n,AudioSocket(YOUR_SERVER_IP:9092,in)
 same => n,NoOp(AudioSocket connection ended)
 same => n,Playback(goodbye)
 same => n,Hangup()

; Create extension 8888 to access the test
exten => 8888,1,NoOp(=== Calling AudioSocket Test ===)
 same => n,Goto(audiosocket-test,s,1)

; Alternative bidirectional test (both directions)
exten => 8889,1,NoOp(=== AudioSocket Bidirectional Test ===)
 same => n,Answer()
 same => n,AudioSocket(YOUR_SERVER_IP:9092,in,out)
 same => n,Hangup()
```

5. **Replace YOUR_SERVER_IP** with actual IP address of your Go server

6. **Reload dialplan**:
```bash
asterisk -rx "dialplan reload"
```

7. **Verify extension was added**:
```bash
asterisk -rx "dialplan show audiosocket-test"
```

#### Method 2: Using FreePBX GUI + Manual Edit

1. **Create an Inbound Route** in FreePBX GUI:
   - Go to **Connectivity > Inbound Routes**
   - Add new route with DID Number: 8888
   - Set Destination to "Terminate Call - Hangup"
   - Submit and Apply Config

2. **Find the generated context** in extensions_additional.conf:
```bash
grep -A 10 "8888" /etc/asterisk/extensions_additional.conf
```

3. **Modify the context** to add AudioSocket before hangup

### 6. Create Test Extension in FreePBX

1. **Go to Applications > Extensions**
2. **Add Extension**: Generic SIP Device
3. **Extension**: 9999
4. **Display Name**: AudioSocket Test
5. **Submit and Apply Config**

### 7. Testing and Verification

#### Start Your Go Server
```bash
cd /path/to/your/go/app
./audiosocket-server
```

#### Test the Connection

1. **From Asterisk CLI**, monitor the connection:
```bash
sudo asterisk -rvvv
```

2. **Call extension 8888** from any phone connected to FreePBX

3. **Watch for these log messages**:
   - "AudioSocket Test Started"
   - "Connecting to AudioSocket at ..."
   - Connection establishment messages

4. **In your Go application**, you should see:
   - "New connection from [asterisk-ip]"
   - "Connection ID: [unique-id]"  
   - "Audio data received: [bytes]"
   - "Received hangup message"

#### Alternative CLI Test
```bash
# From Asterisk CLI
originate Local/8888@from-internal extension s@audiosocket-test
```

## Common Issues and Troubleshooting

### AudioSocket Module Issues

**Problem**: Module not found
```bash
# Check if compiled with AudioSocket support
asterisk -rx "core show applications" | grep -i audio
```

**Solution**: If missing, you may need to:
1. Install development packages: `yum install asterisk-devel`
2. Compile AudioSocket from source:
```bash
git clone https://github.com/CyCoreSystems/audiosocket
cd audiosocket
make install
```

### Connection Issues

**Problem**: "Connection refused" errors

**Debug steps**:
1. **Check if Go server is running**:
```bash
netstat -tlnp | grep 9092
```

2. **Test from Asterisk server**:
```bash
telnet YOUR_GO_SERVER_IP 9092
```

3. **Check Asterisk logs**:
```bash
tail -f /var/log/asterisk/full | grep -i audiosocket
```

4. **Verify dialplan syntax**:
```bash
asterisk -rx "dialplan show 8888@from-internal"
```

### FreePBX Configuration Issues

**Problem**: Extension 8888 not working

**Debug steps**:
1. **Check if extension exists**:
```bash
asterisk -rx "dialplan show" | grep 8888
```

2. **Verify context is loaded**:
```bash
asterisk -rx "dialplan show audiosocket-test"
```

3. **Test dialplan manually**:
```bash
asterisk -rx "originate Local/8888@from-internal application playback hello-world"
```

### Audio Issues

**Problem**: No audio data in Go application

**Check**:
1. **Verify audio path**: Use `in` parameter for receiving audio from caller
2. **Check codec**: AudioSocket uses signed linear (slin) - may need transcoding
3. **Monitor with tcpdump**:
```bash
tcpdump -i any -s 0 -w audiosocket.pcap host YOUR_GO_SERVER_IP and port 9092
```

### Detailed Logging

Enable verbose logging in Asterisk:
```bash
# In Asterisk CLI
set verbose 10
set debug 10
logger add channel /var/log/asterisk/audiosocket.log notice,warning,error,debug,verbose
```

## What the Application Does

- Listens on TCP port 9092
- Accepts connections from Asterisk
- Reads audio messages using the AudioSocket protocol
- Prints connection info, audio data bytes, DTMF tones, and hangup events
- Displays first 16 bytes of each audio packet for debugging

## Expected Output

When working correctly, you should see:
```
AudioSocket server listening on :9092
New connection from 192.168.1.100:45678
Connection ID: 1640995200.123
Audio data received: 320 bytes - [0 1 255 254 128 127 ...]
Audio data received: 320 bytes - [2 3 253 252 130 125 ...]
DTMF received: 1
Received hangup message
```

## Advanced Configuration

For production use, consider:
1. **Security**: Use TLS or VPN tunnels
2. **Reliability**: Add connection retry logic
3. **Performance**: Buffer audio data appropriately
4. **Integration**: Connect to speech recognition services
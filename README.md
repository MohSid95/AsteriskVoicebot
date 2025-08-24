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

### 2. FreePBX16 Configuration

Since FreePBX16 doesn't have "Custom Applications" or "Miscellaneous Applications" modules, you need to manually edit the dialplan.

#### Option A: Extensions_custom.conf (Recommended)

1. SSH into your FreePBX server
2. Edit `/etc/asterisk/extensions_custom.conf`:

```bash
sudo nano /etc/asterisk/extensions_custom.conf
```

3. Add this dialplan context:

```
[audiosocket-test]
exten => s,1,NoOp(AudioSocket Test)
 same => n,Answer()
 same => n,Playback(hello-world)
 same => n,AudioSocket(YOUR_SERVER_IP:9092,in)
 same => n,Hangup()

; Direct extension access
exten => 8888,1,Goto(audiosocket-test,s,1)
```

4. Replace `YOUR_SERVER_IP` with your Go server's IP address
5. Reload dialplan: `sudo asterisk -rx "dialplan reload"`

#### Option B: Using FreePBX GUI with IVR

1. Go to **Applications > IVR**
2. Create a new IVR called "AudioSocket Test"
3. Set announcement to "None" or a greeting
4. In the destination, select **"Terminate Call - Hangup"** temporarily
5. Save and apply config
6. Edit `/etc/asterisk/extensions_additional.conf` and find your IVR context
7. Add the AudioSocket line before the hangup

### 3. Asterisk Configuration

Ensure AudioSocket is loaded in Asterisk:

1. Edit `/etc/asterisk/modules.conf` and ensure:
```
load => app_audiosocket.so
```

2. Restart Asterisk:
```bash
sudo systemctl restart asterisk
```

### 4. Testing

1. Start your Go application
2. Call extension 8888 from any phone
3. Check the Go application console for audio data output

## What the Application Does

- Listens on TCP port 9092
- Accepts connections from Asterisk
- Reads audio messages using the AudioSocket protocol
- Prints connection info, audio data bytes, DTMF tones, and hangup events
- Displays first 16 bytes of each audio packet for debugging

## Troubleshooting

- Ensure firewall allows port 9092
- Check Asterisk logs: `sudo tail -f /var/log/asterisk/full`
- Verify AudioSocket module is loaded: `sudo asterisk -rx "module show like audiosocket"`
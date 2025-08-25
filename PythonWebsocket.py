import threading
import queue
import audioop
import base64
import asyncio
import json
import numpy as np
import librosa
from datetime import datetime
from flask import Flask
from flask_sock import Sock
from google import genai
from google.cloud import storage
from google.genai import types
import os
from requests.auth import HTTPBasicAuth
import requests
import time
import struct

# Load configuration
def load_config(config_path="gs://calling-agent-transcription/ConfigJSON/config_dev.json"):
    """Load configuration from JSON file"""
    try:
        # Remove the gs://
        path = config_path[5:]
        bucket_name, blob_path = path.split('/', 1)
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_path)
        data = blob.download_as_text()
        return json.loads(data)
    except json.JSONDecodeError:
        print(f"Invalid JSON in configuration file {config_path}")
        raise
    except Exception as e:
        print(f"Error loading configuration: {e}")
        raise


# Load configuration
config_data = load_config()

# Extract configuration values
twilio_config = config_data["twilio"]
gemini_config = config_data["gemini"]
gcs_config = config_data["google_cloud"]
server_config = config_data["server"]
audio_config = config_data["audio"]
transcript_config = config_data["transcript"]
api_config = config_data["api"]
call_url = config_data["api"]["webhook_url"]
ai_config = config_data["gemini_config"]

# Set up credentials based on configuration
account_sid = twilio_config["account_sid"]
auth_token = twilio_config["auth_token"]
gemini_key = gemini_config["api_key"]

# You can switch to premium account by changing these:
# account_sid = twilio_config["premium"]["account_sid"]
# auth_token = twilio_config["premium"]["auth_token"]

app = Flask(__name__)
sock = Sock(app)

# Initialize Gemini client based on configuration
if gemini_config["use_vertex_ai"]:
    client = genai.Client(
        vertexai=True,
        project=gemini_config["project"],
        location=gemini_config["location"]
    )
    model = gemini_config["model"]
else:
    client = genai.Client(api_key=gemini_key)
    model = gemini_config["alternative_model"]


def write_to_gcs_without_local_save(bucket_name, blob_name, content):
    """Writes content to a GCS object without saving it locally."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)

    # Upload the content directly from a string
    blob.upload_from_string(content)
    print(f"Content successfully written to gs://{bucket_name}/{blob_name}")

# Function declaration for terminating calls
terminate_call_declaration = {
    "name": "terminateCall",
    "description": "After reaching the end of the questions listed in the prompt, this function will allow the LLM to terminate the call.",
    "parameters": {
        "type": "object",
        "properties": {
            "callStatus": {
                "type": "string",
                "enum": ["completed"],
                "description": "The call be either 'completed' or _____",
            },
            "referenceId": {
                "type": "string",
                "description": "The referenceId for the call that needs to be terminated.",
            },
            "streamSid": {
                "type": "string",
                "description": "The streamSid for the call that needs to be terminated,",
            },
        }
    },
}

terminationTool = types.Tool(function_declarations=[terminate_call_declaration])


# Build configuration for Gemini session
def build_gemini_session_config(callType=None, patientName=None, patientDateOfBirth=None, patientSSNNumber=None, callbackNumber=None, contactEmailID=None):
    """Build Gemini session configuration from loaded config"""
    
    # The first time the config is built for the connection, we go down the else route and provide all the config settings except system prompt.
    # This happens before we receive the callType and other parameters from Twilio in their event=start message.
    # Before the conversation starts, in the initial_greetings() function we send a system prompt update which goes down the if callType != None branch. 
    # This branch only returns the system prompt to send.
    if callType != None:
        system_instruction = ai_config["system_instructions"][callType]
        if callType == "canvassing":
            system_instruction = system_instruction + f" For internal records only: The patientName is {patientName}, the last 4 digits for the patientSSNNumber is {patientSSNNumber}, the patientDateOfBirth is {patientDateOfBirth}, the callbackNumber is {callbackNumber}, and the contactEmailID is {contactEmailID}. "
        return system_instruction + "Whenever you are ready to end the call, YOU MUST call the callTermination tool. DO NOT end the call without calling the callTermination tool. "
    else:
        return {
            "response_modalities": ai_config["response_modalities"],
            "tools": [terminationTool],
            "speech_config": ai_config["speech_config"],
            "realtime_input_config": ai_config["realtime_input_config"],
            "input_audio_transcription": ai_config["input_audio_transcription"],
            "output_audio_transcription": ai_config["output_audio_transcription"]
        }




# AudioSocket protocol constants
AUDIOSOCKET_TYPE_TERMINATE = 0x00
AUDIOSOCKET_TYPE_UUID = 0x01
AUDIOSOCKET_TYPE_DTMF = 0x03
AUDIOSOCKET_TYPE_SLIN = 0x10
AUDIOSOCKET_TYPE_ERROR = 0xff


def parse_audiosocket_message(data):
    """Parse AudioSocket TLV message format"""
    if len(data) < 3:
        return None, None
    
    # Header: 1 byte type + 2 bytes length (big-endian)
    msg_type = data[0]
    payload_length = struct.unpack('>H', data[1:3])[0]  # big-endian uint16
    
    if len(data) < 3 + payload_length:
        return None, None  # Incomplete message
    
    payload = data[3:3+payload_length] if payload_length > 0 else b''
    return msg_type, payload


def create_audiosocket_message(msg_type, payload=b''):
    """Create AudioSocket TLV message"""
    payload_length = len(payload)
    header = struct.pack('B>H', msg_type, payload_length)  # type(1) + length(2, big-endian)
    return header + payload


def pcm16_8khz_to_pcm_float32(pcm_bytes):
    """Convert 16-bit signed linear PCM bytes to float32 array"""
    # AudioSocket specifies little-endian format
    pcm16 = np.frombuffer(pcm_bytes, dtype='<i2')  # little-endian 16-bit signed
    return pcm16.astype(np.float32) / 32768.0


def resample_pcm(pcm, src_rate, tgt_rate):
    return np.clip(librosa.resample(pcm, orig_sr=src_rate, target_sr=tgt_rate), -1.0, 1.0)

        
@sock.route('/media')
def echo(ws):
    print("WebSocket connection accepted")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_event = asyncio.Event()


    # ——— shared queues & state flags ———
    TwilioToGeminiQueue = asyncio.Queue()
    GeminiToTwilioQueue = asyncio.Queue()
    ws_send_queue = queue.Queue()
    stream_sid = None
    ws_active = True
    callSid = None
    referenceId = None
    config = build_gemini_session_config()
    system_prompt = None
    transcriptWriteFlag = 0
    
    # ——— Open the Gemini Live connection ———
    session_cm = client.aio.live.connect(model=model, config=config)
    session    = loop.run_until_complete(session_cm.__aenter__())
    print("Agent session opened at", datetime.now())


    # ——— Function to update the Gemini Live system prompt with the custom parameters pulled in the twilio_reader's event==start message.
    async def initial_greeting():
        await start_event.wait()
        await session.send_client_content(
            turns={"role": "system", "parts":[{"text": system_prompt}]},
            turn_complete=False
        )
        await session.send_client_content(
        turns={"role": "user", "parts": [{"text": ""}]},
        turn_complete=True
        )

    # ——— Thread: blocking Twilio reader ———
    def twilio_reader():
        nonlocal stream_sid, ws_active, callSid, referenceId, system_prompt
        buffer = b''  # Buffer to accumulate partial messages
        
        try:
            while ws_active:
                msg = ws.receive()  # blocking - receives binary data
                if msg is None:
                    print("AudioSocket closed connection")
                    loop.call_soon_threadsafe(TwilioToGeminiQueue.put_nowait, None)
                    break

                # Add new data to buffer
                buffer += msg
                
                # Process complete messages from buffer
                while len(buffer) >= 3:  # Minimum message size (1 byte type + 2 bytes length)
                    # Parse without consuming the buffer yet
                    msg_type, payload = parse_audiosocket_message(buffer)
                    
                    if msg_type is None:
                        # Not enough data for complete message, wait for more
                        break
                    
                    # Calculate total message size and consume from buffer
                    msg_size = 3 + len(payload) if payload else 3
                    buffer = buffer[msg_size:]
                    
                    print(f"msg_type: {msg_type:#04x}")  # Show as hex for clarity
                    
                    if msg_type == AUDIOSOCKET_TYPE_SLIN:
                        # payload is 16-bit signed linear PCM at 8kHz
                        pcm_f32 = pcm16_8khz_to_pcm_float32(payload)
                        
                        # Resample from 8kHz to 16kHz for Gemini
                        pcm16k = resample_pcm(
                            pcm_f32,
                            audio_config["source_sample_rate"],  # 8000
                            audio_config["target_sample_rate"]   # 16000
                        )
                        pcm16b = (pcm16k * 32767).astype('<i2').tobytes()
                        loop.call_soon_threadsafe(
                            TwilioToGeminiQueue.put_nowait, pcm16b
                        )
                    elif msg_type == AUDIOSOCKET_TYPE_UUID:
                        # Handle UUID message
                        if payload:
                            stream_sid = payload.decode('utf-8')
                            print(f"Received UUID: {stream_sid}")
                    elif msg_type == AUDIOSOCKET_TYPE_TERMINATE:
                        print("Received terminate signal")
                        loop.call_soon_threadsafe(TwilioToGeminiQueue.put_nowait, None)
                        break
                    elif msg_type == AUDIOSOCKET_TYPE_ERROR:
                        print(f"Received error signal: {payload}")

        except Exception as e:
            print("twilio_reader error:", e)
            loop.call_soon_threadsafe(TwilioToGeminiQueue.put_nowait, None)

    threading.Thread(target=twilio_reader, daemon=True).start()

    # ——— Async: flush Gemini→Twilio frames ———
    async def send_audio_back():
        nonlocal ws_active
        try:
            while ws_active:
                return_msg = await GeminiToTwilioQueue.get()
                if return_msg:
                    ws.send(return_msg, binary=True)  # Send as binary, not text
        except Exception as e:
            print("send_audio_back error:", e)
        finally:
            ws_send_queue.put(None)
    

    # ——— Async: bridge Twilio ↔ Gemini ———
    Final_Transcript = []
    async def gemini_bridge():
        nonlocal ws_active, transcriptWriteFlag
        response_input_buffer = []
        response_output_buffer = []
        try:
            # — sender → Gemini —
            async def sender():
                while True:
                    chunk = await TwilioToGeminiQueue.get()
                    if chunk is None:
                        break

                    await session.send_realtime_input(
                        media=types.Blob(
                            data=chunk,
                            mime_type=f"audio/pcm;rate={audio_config['target_sample_rate']}"
                        )
                    )
                    
                    

            # — receiver ← Gemini —
            async def receiver():
                nonlocal Final_Transcript, transcriptWriteFlag
                input_token_count = 0
                output_token_count = 0
                while True:
                    async for response in session.receive():
                        sc = getattr(response, 'server_content', None)
                        output_transcription = getattr(sc, 'output_transcription', None)
                        input_transcription = getattr(sc, 'input_transcription', None)
                        turn_complete = getattr(sc, 'turn_complete', False)
                        usage_metadata = getattr(response, "usage_metadata", None)
                        if usage_metadata:
                            in_tokens  = getattr(usage_metadata, "prompt_token_count", None)
                            out_tokens = getattr(usage_metadata, "candidates_token_count", None)
                            if in_tokens:
                                input_token_count += in_tokens
                            if out_tokens:
                                output_token_count += out_tokens
                        if output_transcription and output_transcription.text:
                            response_output_buffer.append(output_transcription.text)

                        if input_transcription and input_transcription.text:
                            response_input_buffer.append(input_transcription.text)

                        if turn_complete:
                            if len(response_input_buffer) >= 1:
                                UserSpeech = " ".join(response_input_buffer)
                                Final_Transcript.append("User:  " + UserSpeech + "\n")
                                response_input_buffer.clear()
                            if len(response_output_buffer) >= 1:
                                GeminiSpeech = " ".join(response_output_buffer)
                                Final_Transcript.append("Virtual Agent: " + GeminiSpeech + "\n")
                                response_output_buffer.clear()

                        if response.tool_call:
                            try:
                                Transcript = "".join(Final_Transcript)
                                
                                # Upload to GCS using configured bucket
                                print(Transcript)

                            except Exception as api_exc:
                                api_json = {"error": str(api_exc)}
                                
                        # If the Agent has been interrupted, clear the GeminiToTwilioQueue and send a clear message to Twilio to clear audio data buffered on their end.
                        elif getattr(sc, "interrupted", False):
                            print("The Agent has just been interrupted")
                            try:
                                while True:
                                    GeminiToTwilioQueue.get_nowait()
                            except asyncio.QueueEmpty:
                                pass
                            continue
                            
                        elif response.data:
                            # Convert from Gemini's 24kHz to Asterisk's 8kHz
                            pcm24 = np.frombuffer(response.data, dtype='<i2').astype(np.float32) / 32768.0
                            pcm8 = resample_pcm(
                                pcm24,
                                audio_config["gemini_sample_rate"],  # 24000
                                audio_config["source_sample_rate"]   # 8000
                            )
                            pcm8b = (pcm8 * 32767).astype('<i2').tobytes()

                            # Send raw PCM in AudioSocket format (no μ-law conversion needed)
                            # Use configured chunk size (320 bytes = 160 samples @ 16-bit = 20ms @ 8kHz)
                            chunk_size = audio_config["chunk_size"]  # Should be 320 for 20ms chunks
                            for i in range(0, len(pcm8b), chunk_size):
                                pcm_chunk = pcm8b[i:i + chunk_size]
                                
                                # Wrap in AudioSocket TLV message
                                audiosocket_msg = create_audiosocket_message(
                                    AUDIOSOCKET_TYPE_SLIN, 
                                    pcm_chunk
                                )
                                
                                # Send raw binary message (not base64)
                                await GeminiToTwilioQueue.put(audiosocket_msg)

            await asyncio.gather(sender(), receiver())

        except Exception as e:
            print("Agent_bridge error:", e)

        finally:
            ws_active = False


    loop.run_until_complete(asyncio.gather(initial_greeting()))
    # Kick off the loops for updating the system prompt, sending GeminiInputQueue to Gemini to GeminiResponseQueue, and for GeminiResponseQueue to Twilio audio (i.e. phone call voice)
    loop.run_until_complete(asyncio.gather(
        send_audio_back(),
        gemini_bridge()
    ))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
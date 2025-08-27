import threading
import queue
import asyncio
import time
from datetime import datetime
from flask import Flask
from flask_sock import Sock
from voice_config import (
    load_all_config, initialize_gemini_client, build_gemini_session_config,
    write_to_gcs_without_local_save, pcm16_8khz_to_pcm_float32, resample_pcm
)
from audio_logger import AudioFlowLogger  # REMOVE FOR PRODUCTION
from websocket_debug import WebSocketDebugLogger  # REMOVE FOR PRODUCTION
from google.genai import types
import numpy as np

# Load all configuration
config = load_all_config()

# Extract individual config sections for easier access
twilio_config = config['twilio_config']
gemini_config = config['gemini_config']
gcs_config = config['gcs_config']
server_config = config['server_config']
audio_config = config['audio_config']
transcript_config = config['transcript_config']
api_config = config['api_config']
call_url = config['call_url']
ai_config = config['ai_config']
account_sid = config['account_sid']
auth_token = config['auth_token']
gemini_key = config['gemini_key']

app = Flask(__name__)
sock = Sock(app)

# Initialize Gemini client based on configuration
client, model = initialize_gemini_client(gemini_config)

        
@sock.route('/media')
def echo(ws):
    debug_logger = WebSocketDebugLogger()  # REMOVE FOR PRODUCTION
    debug_logger.log_connection_accepted()  # REMOVE FOR PRODUCTION
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    start_event = asyncio.Event()


    # ——— shared queues & state flags ———
    AudioInputQueue = asyncio.Queue()
    AudioOutputQueue = asyncio.Queue()
    ws_send_queue = queue.Queue()
    stream_sid = None
    ws_active = True
    callSid = None
    referenceId = None
    config = build_gemini_session_config(ai_config)
    system_prompt = None
    transcriptWriteFlag = 0
    
    # ——— Audio flow logger ———
    audio_logger = AudioFlowLogger()  # REMOVE FOR PRODUCTION
    
    # ——— Open the Gemini Live connection ———
    session_cm = client.aio.live.connect(model=model, config=config)
    session    = loop.run_until_complete(session_cm.__aenter__())
    debug_logger.log_gemini_session_opened()  # REMOVE FOR PRODUCTION


    # ——— Function to send initial system prompt to Gemini
    async def initial_greeting():
        debug_logger.log("Sending initial system prompt to Gemini")  # REMOVE FOR PRODUCTION
        await session.send_client_content(
            turns={"role": "system", "parts":[{"text": system_prompt}]},
            turn_complete=False
        )
        await session.send_client_content(
        turns={"role": "user", "parts": [{"text": ""}]},
        turn_complete=True
        )
        debug_logger.log("Initial greeting completed successfully")  # REMOVE FOR PRODUCTION

    # ——— Thread: blocking audio input reader ———
    def audio_input_reader():
        nonlocal stream_sid, ws_active, callSid, referenceId, system_prompt
        debug_logger.log_thread_started("Audio input reader")  # REMOVE FOR PRODUCTION
        
        try:
            while ws_active:
                debug_logger.log_waiting_for_message()  # REMOVE FOR PRODUCTION
                msg = ws.receive()  # blocking - receives binary data
                debug_logger.log_message_received(len(msg) if msg else 0)  # REMOVE FOR PRODUCTION
                
                if msg is None:
                    debug_logger.log_connection_closed()  # REMOVE FOR PRODUCTION
                    loop.call_soon_threadsafe(AudioInputQueue.put_nowait, None)
                    break


                # Go app sends raw PCM data directly (320 bytes = 20ms @ 8kHz, 16-bit)
                if len(msg) == 320:  # Expected chunk size from Go app
                    debug_logger.log_processing_chunk(320)  # REMOVE FOR PRODUCTION
                    # Convert raw PCM bytes to float32
                    pcm_f32 = pcm16_8khz_to_pcm_float32(msg)
                    
                    # Resample from 8kHz to 16kHz for Gemini
                    pcm16k = resample_pcm(
                        pcm_f32,
                        audio_config["source_sample_rate"],  # 8000
                        audio_config["target_sample_rate"]   # 16000
                    )
                    pcm16b = (pcm16k * 32767).astype('<i2').tobytes()
                    audio_logger.log_audio_sent_to_gemini(len(pcm16b))  # REMOVE FOR PRODUCTION
                    loop.call_soon_threadsafe(
                        AudioInputQueue.put_nowait, pcm16b
                    )
                    debug_logger.log_sent_to_gemini_queue(len(pcm16b))  # REMOVE FOR PRODUCTION
                else:
                    debug_logger.log_unexpected_chunk_size(len(msg), 320)  # REMOVE FOR PRODUCTION

        except Exception as e:
            debug_logger.log_error("audio_input_reader", e)  # REMOVE FOR PRODUCTION
            loop.call_soon_threadsafe(AudioInputQueue.put_nowait, None)

    threading.Thread(target=audio_input_reader, daemon=True).start()

    # ——— Async: flush Gemini→Audio Output frames ———
    async def send_audio_back():
        nonlocal ws_active
        try:
            while ws_active:
                return_msg = await AudioOutputQueue.get()
                if return_msg:
                    ws.send(return_msg, binary=True)  # Send as binary, not text

        except Exception as e:
            print("send_audio_back error:", e)
        finally:
            ws_send_queue.put(None)
    

    # ——— Async: bridge Audio Input ↔ Gemini ———
    Final_Transcript = []
    async def gemini_bridge():
        nonlocal ws_active, transcriptWriteFlag
        response_input_buffer = []
        response_output_buffer = []
        try:
            # — sender → Gemini —
            async def sender():
                while True:
                    chunk = await AudioInputQueue.get()
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
                response_count = 0  # REMOVE FOR PRODUCTION
                while True:
                    async for response in session.receive():
                        response_count += 1  # REMOVE FOR PRODUCTION
                        
                        # REMOVE FOR PRODUCTION: Log full response details
                        try:
                            with open("logs/gemini_responses.txt", "a", encoding="utf-8") as f:
                                f.write(f"\n=== GEMINI RESPONSE #{response_count} ({datetime.now().strftime('%H:%M:%S.%f')[:-3]}) ===\n")
                                f.write(f"Response type: {type(response)}\n")
                                f.write(f"Response attributes: {dir(response)}\n")
                                f.write(f"Has data: {hasattr(response, 'data')}\n")
                                if hasattr(response, 'data'):
                                    f.write(f"Data length: {len(response.data) if response.data else 'None'}\n")
                                f.write(f"Has server_content: {hasattr(response, 'server_content')}\n")
                                f.write(f"Has tool_call: {hasattr(response, 'tool_call')}\n")
                                f.write(f"Full response: {response}\n")
                                f.write("=" * 60 + "\n")
                        except Exception as e:
                            debug_logger.log_error("gemini_response_logging", e)  # REMOVE FOR PRODUCTION
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
                            audio_logger.log_gemini_response()  # REMOVE FOR PRODUCTION

                        if input_transcription and input_transcription.text:
                            response_input_buffer.append(input_transcription.text)

                        if turn_complete:
                            if len(response_input_buffer) >= 1:
                                UserSpeech = " ".join(response_input_buffer)
                                Final_Transcript.append("User:  " + UserSpeech + "\n")
                                response_input_buffer.clear()
                                # REMOVE FOR PRODUCTION: Log user speech in real-time
                                debug_logger.log(f"USER SPEECH: {UserSpeech}")  # REMOVE FOR PRODUCTION
                            if len(response_output_buffer) >= 1:
                                GeminiSpeech = " ".join(response_output_buffer)
                                Final_Transcript.append("Virtual Agent: " + GeminiSpeech + "\n")
                                response_output_buffer.clear()
                                # REMOVE FOR PRODUCTION: Log Gemini speech in real-time
                                debug_logger.log(f"GEMINI SPEECH: {GeminiSpeech}")  # REMOVE FOR PRODUCTION
                                
                                # REMOVE FOR PRODUCTION: Write ongoing transcript to file
                                try:
                                    ongoing_transcript = "".join(Final_Transcript)
                                    with open("logs/live_conversation_transcript.txt", "w", encoding="utf-8") as f:
                                        f.write(f"=== LIVE CONVERSATION TRANSCRIPT ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===\n")
                                        f.write(ongoing_transcript)
                                        f.write("\n=== CONVERSATION IN PROGRESS ===\n")
                                except Exception as live_transcript_error:
                                    debug_logger.log_error("live_transcript_writing", live_transcript_error)  # REMOVE FOR PRODUCTION
                     
                          
                        elif response.data:
                            # Convert from Gemini's 24kHz to target 8kHz
                            pcm24 = np.frombuffer(response.data, dtype='<i2').astype(np.float32) / 32768.0
                            audio_logger.log_audio_received_from_gemini(len(response.data))  # REMOVE FOR PRODUCTION
                            pcm8 = resample_pcm(
                                pcm24,
                                audio_config["gemini_sample_rate"],  # 24000
                                audio_config["source_sample_rate"]   # 8000
                            )
                            pcm8b = (pcm8 * 32767).astype('<i2').tobytes()

                            # Send raw PCM data directly to Go app (no AudioSocket TLV wrapping)
                            # Use configured chunk size (320 bytes = 160 samples @ 16-bit = 20ms @ 8kHz)
                            chunk_size = audio_config["chunk_size"]  # Should be 320 for 20ms chunks
                            for i in range(0, len(pcm8b), chunk_size):
                                pcm_chunk = pcm8b[i:i + chunk_size]
                                audio_logger.log_audio_chunk_sent_to_go()  # REMOVE FOR PRODUCTION
                                
                                # Send raw PCM chunk directly (Go app expects raw binary data)
                                await AudioOutputQueue.put(pcm_chunk)

            await asyncio.gather(sender(), receiver())

        except Exception as e:
            print("Agent_bridge error:", e)

        finally:
            ws_active = False


    loop.run_until_complete(asyncio.gather(initial_greeting()))
    # Kick off the loops for updating the system prompt, sending AudioInputQueue to Gemini to AudioOutputQueue, and for AudioOutputQueue to Go app audio
    loop.run_until_complete(asyncio.gather(
        send_audio_back(),
        gemini_bridge(),
        audio_logger.start_periodic_logging()  # REMOVE FOR PRODUCTION
    ))

if __name__ == "__main__":
    print("Starting Python WebSocket server...")
    print("Server will run on http://0.0.0.0:8080")
    print("WebSocket endpoint: ws://localhost:8080/media")
    print("Press Ctrl+C to stop")
    print("-" * 50)
    app.run(host="0.0.0.0", port=8080, debug=True)
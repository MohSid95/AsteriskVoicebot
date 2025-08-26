import json
import numpy as np
import librosa
import struct
from google.cloud import storage
from google import genai
from google.genai import types

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
def build_gemini_session_config(ai_config, callType=None, patientName=None, patientDateOfBirth=None, patientSSNNumber=None, callbackNumber=None, contactEmailID=None):
    """Build Gemini session configuration from loaded config"""
    
    # The first time the config is built for the connection, we go down the else route and provide all the config settings except system prompt.
    # This happens before we receive the callType and other parameters from audio source in their event=start message.
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


def initialize_gemini_client(gemini_config):
    """Initialize Gemini client based on configuration"""
    if gemini_config["use_vertex_ai"]:
        client = genai.Client(
            vertexai=True,
            project=gemini_config["project"],
            location=gemini_config["location"]
        )
        model = gemini_config["model"]
    else:
        client = genai.Client(api_key=gemini_config["api_key"])
        model = gemini_config["alternative_model"]
    
    return client, model


def load_all_config():
    """Load and parse all configuration data"""
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
    
    return {
        'config_data': config_data,
        'twilio_config': twilio_config,
        'gemini_config': gemini_config,
        'gcs_config': gcs_config,
        'server_config': server_config,
        'audio_config': audio_config,
        'transcript_config': transcript_config,
        'api_config': api_config,
        'call_url': call_url,
        'ai_config': ai_config,
        'account_sid': account_sid,
        'auth_token': auth_token,
        'gemini_key': gemini_key
    }
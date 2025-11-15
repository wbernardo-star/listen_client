from flask import Flask, render_template, request, jsonify
import os, base64, httpx
from tempfile import NamedTemporaryFile
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
OPENAI_API_KEY=os.getenv('OPENAI_API_KEY')
ORCHESTRATOR_URL=os.getenv('ORCHESTRATOR_URL')
ELEVENLABS_API_KEY=os.getenv('ELEVENLABS_API_KEY')
ELEVENLABS_VOICE_ID=os.getenv('ELEVENLABS_VOICE_ID','EXAVITQu4vr4xnSDxMaL')
ELEVENLABS_MODEL_ID=os.getenv('ELEVENLABS_MODEL_ID','eleven_multilingual_v2')

client = OpenAI(api_key=OPENAI_API_KEY)
app = Flask(__name__)

def transcribe(path):
    with open(path,'rb') as f:
        r = client.audio.transcriptions.create(model='whisper-1', file=f, language='en')
    return r.text or ''

def call_mcp(t):
    r = httpx.post(ORCHESTRATOR_URL, json={
        'channel':'web','user_id':'listen-user','session_id':'listen-user:web','text':t
    }, timeout=30)
    r.raise_for_status()
    return r.json()

def tts(text):
    if not ELEVENLABS_API_KEY:
        return None,None
    url=f"https://api.elevenlabs.io/v1/text-to-speech/{ELEVENLABS_VOICE_ID}"
    r=httpx.post(url,
        headers={'xi-api-key':ELEVENLABS_API_KEY,'Accept':'audio/mpeg','Content-Type':'application/json'},
        json={'text':text,'model_id':ELEVENLABS_MODEL_ID,'voice_settings':{'stability':0.4,'similarity_boost':0.7}},
        timeout=60
    )
    audio=r.content
    return base64.b64encode(audio).decode(),'audio/mpeg'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/voice', methods=['POST'])
def api_voice():
    if 'audio' not in request.files:
        return jsonify({'error':'no_audio'}),400
    f=request.files['audio']
    with NamedTemporaryFile(suffix='.webm',delete=False) as tmp:
        f.save(tmp.name); path=tmp.name
    try:
        text=transcribe(path)
        mcp=call_mcp(text)
        reply=mcp.get('reply_text','')
        session_done=bool(mcp.get('session_done'))
        audio_b64,mime=tts(reply)
        return jsonify({'user_text':text,'reply_text':reply,'audio_base64':audio_b64,'audio_mime':mime,'session_done':session_done})
    finally:
        try: os.remove(path)
        except: pass

@app.route('/api/welcome')
def api_welcome():
    welcome_text="Hi, I'm Blink, your AI Voice Assistant. How may I help you today?"
    audio_b64,mime=tts(welcome_text)
    return jsonify({'reply_text':welcome_text,'audio_base64':audio_b64,'audio_mime':mime})

if __name__=='__main__':
    app.run(host='0.0.0.0',port=5000,debug=True)

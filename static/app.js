(() => {
const chat=document.getElementById('chat');
const mic=document.getElementById('micButton');
const label=document.getElementById('micLabel');
const dot=document.getElementById('statusDot');
const status=document.getElementById('statusText');
let rec=null,chunks=[],recording=false;
let audioContext=null,analyser=null,silenceTimer=null;
const SILENCE_THRESHOLD=0.015,SILENCE_DURATION=5000;

function statusMode(m,t){dot.className='va-dot va-dot-'+m;status.textContent=t;}

function add(role,text){
  if(!text) return;
  const row=document.createElement('div');
  row.className='va-msg-row '+role;
  const bubble=document.createElement('div');
  bubble.className='va-bubble '+role;
  bubble.textContent=text;
  row.appendChild(bubble);
  chat.appendChild(row);
  chat.scrollTop=chat.scrollHeight;
}

async function start(){
  const stream=await navigator.mediaDevices.getUserMedia({audio:true});
  audioContext=new (window.AudioContext||window.webkitAudioContext)();
  const source=audioContext.createMediaStreamSource(stream);
  analyser=audioContext.createAnalyser();
  analyser.fftSize=2048;
  source.connect(analyser);
  function checkSilence(){
    if(!recording) return;
    const data=new Uint8Array(analyser.fftSize);
    analyser.getByteTimeDomainData(data);
    let rms=0;
    for(let i=0;i<data.length;i++){const v=(data[i]-128)/128;rms+=v*v;}
    rms=Math.sqrt(rms);
    if(rms<SILENCE_THRESHOLD){
      if(!silenceTimer){silenceTimer=setTimeout(()=>{stop();},SILENCE_DURATION);}
    }else{
      if(silenceTimer){clearTimeout(silenceTimer);silenceTimer=null;}
    }
    requestAnimationFrame(checkSilence);
  }
  checkSilence();
  rec=new MediaRecorder(stream);
  chunks=[];
  rec.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data);}
  rec.onstop=()=>{
    const blob=new Blob(chunks,{type:'audio/webm'});
    send(blob);
    stream.getTracks().forEach(t=>t.stop());
    if(audioContext){audioContext.close();audioContext=null;}
  };
  rec.start();
  recording=true;
  mic.classList.add('listening');
  label.textContent='Transmit';
  statusMode('listening','Listening...');
}

function stop(){
  if(rec && recording){
    rec.stop(); recording=false;
    mic.classList.remove('listening');
    label.textContent='Open Voice Link';
    statusMode('processing','Transmitting...');
    if(silenceTimer){clearTimeout(silenceTimer);silenceTimer=null;}
  }
}

async function send(blob){
  const fd=new FormData();
  fd.append('audio',blob,'voice.webm');
  try{
    const r=await fetch('/api/voice',{method:'POST',body:fd});
    const j=await r.json();
    if(j.user_text) add('user',j.user_text);
    add('assistant', j.reply_text||'[No reply]');
    if(j.audio_base64){
      const a=new Audio('data:'+j.audio_mime+';base64,'+j.audio_base64);
      statusMode('speaking','Responding...');
      a.play().then(()=>{a.onended=()=>statusMode('idle','Ready');});
    }else{
      statusMode('idle','Ready');
    }
  }catch(e){
    console.error('send error',e);
    add('assistant','[Error processing request]');
    statusMode('idle','Ready');
  }
}

async function playWelcome(){
  try{
    const r=await fetch('/api/welcome');
    const j=await r.json();
    add('assistant', j.reply_text || "Hi, I'm Blink, your AI Voice Assistant. How may I help you today?");
    if(j.audio_base64){
      const a=new Audio('data:'+j.audio_mime+';base64,'+j.audio_base64);
      statusMode('speaking','Responding...');
      a.play().then(()=>{a.onended=()=>statusMode('idle','Ready');});
    }
  }catch(e){console.error('welcome error',e);}
}

mic.onclick=()=> recording?stop():start();
statusMode('idle','Ready');
playWelcome();
})();
let mediaRecorder,chunks=[],btn=document.getElementById('recordBtn'),statusEl=document.getElementById('status'),u=document.getElementById('userText'),r=document.getElementById('replyText'),a=document.getElementById('replyAudio');
async function startRec(){chunks=[];const stream=await navigator.mediaDevices.getUserMedia({audio:true});mediaRecorder=new MediaRecorder(stream);
mediaRecorder.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data)};
mediaRecorder.onstop=async()=>{statusEl.textContent='Uploading...';const blob=new Blob(chunks,{type:'audio/webm'});const fd=new FormData();fd.append('audio',blob,'rec.webm');
const res=await fetch('/api/voice',{method:'POST',body:fd});const d=await res.json();
u.textContent=d.user_text||'';r.textContent=d.reply_text||'';if(d.audio_base64){a.src=`data:${d.audio_mime};base64,${d.audio_base64}`;a.play();}statusEl.textContent='Done'};
mediaRecorder.start();btn.textContent='⏹ Stop';}
btn.onclick=()=>{if(!mediaRecorder||mediaRecorder.state==='inactive')startRec();else mediaRecorder.stop()};
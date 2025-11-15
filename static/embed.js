(() => {
  const script=document.currentScript;
  const assistantURL=script.getAttribute('data-assistant-url');
  if(!assistantURL){console.error('[MatrixAssistant] Missing data-assistant-url');return;}
  const style=document.createElement('style');
  style.textContent=`#matrix-launcher{position:fixed;bottom:24px;right:24px;width:64px;height:64px;background:#001900;border:2px solid #00ff88;border-radius:50%;box-shadow:0 0 20px rgba(0,255,136,0.6);cursor:pointer;z-index:999999999;display:flex;align-items:center;justify-content:center;transition:transform .15s,box-shadow .25s;}#matrix-launcher:hover{box-shadow:0 0 30px rgba(0,255,136,0.9);transform:scale(1.05);}#matrix-launcher span{color:#00ff88;font-family:monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;text-align:center;}#matrix-frame{position:fixed;bottom:100px;right:24px;width:420px;height:600px;border:1px solid #00ff88;border-radius:12px;box-shadow:0 0 40px rgba(0,255,136,0.7);background:black;z-index:999999998;display:none;}@media(max-width:600px){#matrix-frame{width:92vw;height:80vh;right:4vw;bottom:80px;}}`;
  document.head.appendChild(style);
  const launcher=document.createElement('div');
  launcher.id='matrix-launcher'; launcher.innerHTML='<span>Blink</span>';
  document.body.appendChild(launcher);
  const iframe=document.createElement('iframe');
  iframe.id='matrix-frame'; iframe.src=assistantURL; iframe.allow='microphone *'; iframe.style.border='1px solid #00ff88';
  document.body.appendChild(iframe);
  let open=false;
  launcher.onclick=()=>{open=!open; iframe.style.display=open?'block':'none';};
})();

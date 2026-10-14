const $=id=>document.getElementById(id);
let sessionId=localStorage.getItem('paperinsight_session')||null;

async function loadPapers(){
  const res=await fetch('/api/papers');
  const papers=await res.json();
  $('papers').innerHTML=papers.map(p=>`<a class="paper" href="${p.url}" target="_blank" rel="noreferrer"><div class="paper-title">${esc(p.title)}</div><div class="paper-id">${esc(p.pmcid)}</div></a>`).join('');
}
function esc(s){const d=document.createElement('div');d.textContent=s||'';return d.innerHTML}
function addMessage(role,text,citations=[]){
  const wrap=document.createElement('div');wrap.className=`msg ${role}`;
  const bubble=document.createElement('div');bubble.className='bubble';
  if(role==='assistant'&&citations.length){
    const byKey=Object.fromEntries(citations.map(c=>[c.citation_key,c]));
    const parts=text.split(/\[(C\d+)\]/g);
    parts.forEach(part=>{
      const c=byKey[part];
      if(c){
        const b=document.createElement('button');b.className='cite inline-cite';
        b.textContent=`[${c.citation_key.slice(1)}] ${c.section_title} · ${c.pmcid}`;
        b.onclick=()=>showSource(c);bubble.appendChild(b);
      }else{
        bubble.appendChild(document.createTextNode(part));
      }
    });
  }else{bubble.textContent=text}
  wrap.appendChild(bubble);
  if(role==='assistant'&&citations.length){
    const row=document.createElement('div');row.className='citations';
    citations.forEach(c=>{const b=document.createElement('button');b.className='cite';b.textContent=`[${c.citation_key.replace('C','')}] ${c.title} · ${c.section_title}`;b.onclick=()=>showSource(c);row.appendChild(b)});
    wrap.appendChild(row);
  }
  $('messages').appendChild(wrap);$('messages').scrollTop=$('messages').scrollHeight;
}
function showSource(c){
  $('sourceEmpty').hidden=true;$('source').hidden=false;
  $('sourceSection').textContent=c.section_path?.join(' › ')||c.section_title;
  $('sourceTitle').textContent=c.title;
  $('sourceMeta').textContent=`${c.pmcid}${c.doi?` · DOI ${c.doi}`:''}`;
  $('sourceText').textContent=c.text;
  $('pmcLink').href=c.pmc_url;
  if(c.doi_url){$('doiLink').hidden=false;$('doiLink').href=c.doi_url}else $('doiLink').hidden=true;
}
async function sendQuestion(q){
  q=(q||$('question').value).trim();if(!q)return;
  const welcome=document.querySelector('.welcome');if(welcome)welcome.remove();
  $('question').value='';
  addMessage('user',q);
  $('send').disabled=true;
  try{
    const res=await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q,session_id:sessionId})});
    const data=await res.json();if(!res.ok)throw new Error(data.detail||'Backend error');
    sessionId=data.session_id;localStorage.setItem('paperinsight_session',sessionId);
    addMessage('assistant',data.answer,data.citations||[]);
  }catch(e){addMessage('assistant',`⚠ ${e.message}`)}
  $('send').disabled=false;$('question').focus();
}
$('send').onclick=()=>sendQuestion();
$('question').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendQuestion()}});
document.querySelectorAll('.examples button').forEach(b=>b.onclick=()=>sendQuestion(b.dataset.q));
$('newChat').onclick=()=>{localStorage.removeItem('paperinsight_session');sessionId=null;location.reload()};
$('clearChat').onclick=async()=>{if(sessionId)await fetch(`/api/session/${sessionId}`,{method:'DELETE'});sessionId=null;localStorage.removeItem('paperinsight_session');location.reload()};
loadPapers().catch(console.error);

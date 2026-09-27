from __future__ import annotations
import json

def render_dashboard() -> str:
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>HDS — Company OS</title>
<style>
:root{font-family:Inter,system-ui,sans-serif;background:#0b1020;color:#eef2ff;--muted:#9aa5bd;--card:#131a2b;--line:#26314a;--accent:#8b5cf6}
*{box-sizing:border-box}body{margin:0;background:linear-gradient(135deg,#0b1020,#111827);min-height:100vh}
header{padding:24px 28px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;gap:20px;align-items:center;position:sticky;top:0;background:#0b1020ee;backdrop-filter:blur(12px);z-index:2}
h1{margin:0;font-size:24px}p{color:var(--muted)}main{max-width:1400px;margin:auto;padding:24px}
.toolbar{display:flex;gap:12px;align-items:center;flex-wrap:wrap}select,button{background:var(--card);color:inherit;border:1px solid var(--line);border-radius:9px;padding:10px 13px}button{cursor:pointer}button.primary{background:var(--accent);border-color:var(--accent)}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:20px 0}.card{background:#131a2bdd;border:1px solid var(--line);border-radius:14px;padding:17px}.metric{font-size:28px;font-weight:750;margin-top:7px}.label{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.08em}
.cols{display:grid;grid-template-columns:1.25fr .75fr;gap:16px}@media(max-width:900px){.cols{grid-template-columns:1fr}}
h2{font-size:16px;margin-top:0}.list{display:grid;gap:8px}.row{border-top:1px solid var(--line);padding:12px 0}.row:first-child{border-top:0}.tag{display:inline-block;padding:3px 7px;border-radius:99px;background:#202a42;color:#cbd5e1;font-size:11px;margin-right:5px}.danger{color:#fca5a5}.good{color:#86efac}.muted{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word;color:#cbd5e1}
#status{font-size:13px;color:var(--muted)}
</style></head><body>
<header><div><h1>HDS Company OS</h1><div id="status">Loading company state…</div></div>
<div class="toolbar"><select id="project"></select><button class="primary" onclick="runCycle()">Run research cycle</button><button onclick="refresh()">Refresh</button></div></header>
<main>
<section class="grid" id="metrics"></section>
<div class="cols"><section class="card"><h2>Founder Intelligence</h2><div id="snapshot" class="list"></div></section>
<section class="card"><h2>Decisions & attention</h2><div id="decisions" class="list"></div></section></div>
<div class="cols" style="margin-top:16px"><section class="card"><h2>Scientific workflow</h2><div id="workflow" class="list"></div></section>
<section class="card"><h2>Latest findings</h2><div id="findings" class="list"></div></section></div>
</main>
<div id="chat" class="card" style="position:fixed;right:18px;bottom:18px;width:min(420px,calc(100vw - 36px));display:none;box-shadow:0 20px 60px #0008">
<h2>Founder AI</h2><div id="chatlog" style="max-height:280px;overflow:auto"></div>
<textarea id="chatmsg" maxlength="8000" placeholder="Ask about the current company state…" style="width:100%;min-height:70px;background:#0b1020;color:inherit;border:1px solid var(--line);border-radius:9px;padding:10px"></textarea>
<div class="toolbar" style="margin-top:8px"><button class="primary" onclick="askChat()">Ask</button><button onclick="document.getElementById('chat').style.display='none'">Close</button></div></div>
<button onclick="document.getElementById('chat').style.display='block'" style="position:fixed;right:18px;bottom:18px;border-radius:99px;background:var(--accent);border-color:var(--accent);font-weight:700">Founder AI</button>
<script>
let projects=[];
const esc=x=>String(x??"").replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
async function api(path,opts={}){const r=await fetch(path,opts);if(!r.ok)throw new Error((await r.text())||r.status);return r.json()}
function selected(){return document.getElementById("project").value}
function card(label,value,cls=""){return '<div class="card"><div class="label">'+esc(label)+'</div><div class="metric '+cls+'">'+esc(value)+'</div></div>'}
async function refresh(){
 const id=selected(); if(!id)return;
 document.getElementById("status").textContent="Refreshing "+id+"…";
 try{
  const [s,w,d]=await Promise.all([api("/api/founder/"+id),api("/api/founder/"+id+"/workflow"),api("/api/founder/"+id+"/decisions")]);
  const project=projects.find(p=>p.id===id)||{};
  const h=s.scientific_health||{};
  document.getElementById("metrics").innerHTML=[
   card("Project status",project.status||"—"),card("Integrity",h.integrity||"—",h.integrity==="HEALTHY"?"good":"danger"),
   card("Open contradictions",h.open_contradictions??0,h.open_contradictions?"danger":"good"),card("Decision queue",h.decision_queue??0,h.decision_queue?"danger":"good"),
   card("High-priority decisions",h.high_priority_decisions??0,h.high_priority_decisions?"danger":"good"),card("Research approved",s.research?.approved??0),
   card("Experiments running",s.experiments?.running??0),card("Founder attention",s.requires_founder_attention?"YES":"NO",s.requires_founder_attention?"danger":"good")
  ].join("");
  document.getElementById("snapshot").innerHTML=[
   "<div><b>Objective</b><br><span class='muted'>"+esc(project.objective)+"</span></div>",
   "<div><b>Founder action</b><br>"+esc(s.requires_founder_attention?"Required":"None")+"</div>",
   "<div><b>Latest brief</b><br><span class='muted'>"+esc((s.research?.completed??0)+" research items completed; "+(s.experiments?.completed??0)+" experiments completed.")+"</span></div>"
  ].join('<div class="row">')+"</div>";
  document.getElementById("decisions").innerHTML=(d.items||[]).slice(0,12).map(x=>'<div class="row"><span class="tag">'+esc(x.type)+'</span><b>'+esc(x.title||x.reason||x.id)+'</b><br><span class="muted">'+esc(x.status||"pending")+'</span></div>').join("")||'<p>No active decisions.</p>';
  document.getElementById("workflow").innerHTML=[
   ["Agent outputs",w.agent_outputs],["Findings",w.findings],["Claim revisions",w.claim_revisions],["Impact reviews",w.impact_reviews]
  ].map(([n,a])=>'<div class="row"><b>'+n+'</b><span class="muted"> '+(a||[]).length+'</span></div>').join("");
  document.getElementById("findings").innerHTML=(w.findings||[]).slice(0,8).map(x=>'<div class="row"><span class="tag">'+esc(x.status||"UNREVIEWED")+'</span>'+esc(x.title||x.statement||x.summary||x.id)+'</div>').join("")||'<p>No findings yet.</p>';
  document.getElementById("status").textContent="Live • "+new Date().toLocaleTimeString();
 }catch(e){document.getElementById("status").textContent="Could not load project state: "+e.message}
}
async function init(){try{projects=(await api("/api/founder/projects")).items||[];const s=document.getElementById("project");s.innerHTML=projects.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.objective||p.id)+'</option>').join("");await refresh()}catch(e){document.getElementById("status").textContent="Authentication or API error: "+e.message}}
async function askChat(){
 const msg=document.getElementById("chatmsg").value.trim(); if(!msg)return;
 const log=document.getElementById("chatlog"); log.innerHTML+='<div class="row"><b>You</b><br>'+esc(msg)+'</div>';
 document.getElementById("chatmsg").value="";
 try{const r=await api("/api/founder/"+selected()+"/chat",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({message:msg})});
 log.innerHTML+='<div class="row"><b>HDS AI</b><br>'+esc(r.answer)+'<br><span class="muted">Unverified advisory output.</span></div>';
 }catch(e){log.innerHTML+='<div class="row danger">Chat blocked: '+esc(e.message)+'</div>'}
}
async function runCycle(){const id=selected();if(!id)return;document.getElementById("status").textContent="Running governed research cycle…";try{await api("/api/science/research-cycle/"+id,{method:"POST"});await refresh()}catch(e){document.getElementById("status").textContent="Cycle blocked: "+e.message}}
document.getElementById("project").addEventListener("change",refresh);init();
</script></body></html>"""

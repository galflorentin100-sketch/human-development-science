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
h2{font-size:16px;margin-top:0}.research-lab{margin-bottom:16px}.research-lab textarea{display:block;width:100%;min-height:100px;margin-top:8px;background:#0b1020;color:inherit;border:1px solid var(--line);border-radius:9px;padding:12px;font:inherit}.research-lab label{color:var(--muted);font-size:13px}.research-output{background:#0b1020;border:1px solid var(--line);border-radius:10px;padding:12px;margin-top:10px}.research-output pre{max-height:520px;overflow:auto}.research-warning{color:#fbbf24}.research-error{color:#fca5a5}.list{display:grid;gap:8px}.row{border-top:1px solid var(--line);padding:12px 0}.row:first-child{border-top:0}.tag{display:inline-block;padding:3px 7px;border-radius:99px;background:#202a42;color:#cbd5e1;font-size:11px;margin-right:5px}.danger{color:#fca5a5}.good{color:#86efac}.muted{color:var(--muted)}pre{white-space:pre-wrap;word-break:break-word;color:#cbd5e1}
#status{font-size:13px;color:var(--muted)}
</style></head><body>
<header><div><h1>HDS Company OS</h1><div id="status">Loading company state…</div></div>
<div class="toolbar"><select id="project"></select><button class="primary" onclick="runCycle()">Run research cycle</button><button onclick="refreshAll()">Refresh</button></div></header>
<main>
<section class="grid" id="metrics"></section>
<section class="card research-lab">
<h2>HDS Mentality Research Lab</h2>
<p>Start a bounded scientific literature pass on a mental capability. HDS searches PubMed and Crossref, supplies readable abstracts to the configured AI model, and saves an unverified research output for review.</p>
<label for="mental-question">Research question</label>
<textarea id="mental-question" maxlength="4000">Which psychological and behavioral processes contribute to the development and maintenance of self-discipline in adults?</textarea>
<div class="toolbar" style="margin-top:10px"><label>Sources <select id="mental-limit"><option value="10">10 papers</option><option value="20" selected>20 papers</option><option value="30">30 papers</option><option value="50">50 papers</option></select></label><button class="primary" id="mental-run" onclick="runMentalResearch()">Start research</button></div>
<div id="mental-status" role="status" aria-live="polite" style="margin-top:12px">Ready. Research outputs remain unverified until independent review.</div>
<div id="mental-results" style="margin-top:14px"></div>
<div class="research-output"><h3>Autonomous research feed</h3><p>Background literature scans appear here automatically. The feed refreshes every five minutes while the dashboard is open.</p><div id="background-feed" class="list">Loading saved research runs…</div></div>
<div class="research-output"><h3>Project evidence map</h3><p>Descriptive summary of reviewer-verified excerpts linked to project claims. Study descriptors are displayed as recorded, not independently validated.</p><div id="evidence-map" class="list">Loading evidence map…</div></div>
</section>
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
async function loadBackgroundFeed(){
 const target=document.getElementById("background-feed"); if(!target)return;
 try{
  const rows=await Promise.all(projects.map(async p=>{try{const r=await api("/api/hds/research-loops/project/"+encodeURIComponent(p.id));return (r.items||[]).map(x=>({...x,project_objective:p.objective||""}))}catch(_){return []}}));
  const queueRows=await Promise.all(projects.map(async p=>{try{const r=await api("/api/science/research-queue/"+encodeURIComponent(p.id));return (Array.isArray(r)?r:(r.items||[])).map(x=>({...x,project_objective:p.objective||""}))}catch(_){return []}}));
  const queueItems=queueRows.flat().sort((a,b)=>String(b.created_at||"").localeCompare(String(a.created_at||""))).slice(0,12);
  const runs=rows.flat().sort((a,b)=>String(b.updated_at||b.created_at||"").localeCompare(String(a.updated_at||a.created_at||""))).slice(0,10);
  const enriched=await Promise.all(runs.map(async x=>{
   if(!x.workspace_id)return {...x,sources:[]};
   try{const r=await api("/api/hds/research-loops/"+encodeURIComponent(x.id)+"/sources");return {...x,sources:(r.items||[]).slice(0,5)}}catch(_){return {...x,sources:[]}}
  }));
  target.innerHTML=enriched.map(x=>{
   const sourceLinks=(x.sources||[]).map(s=>{
    const url=typeof s.url==="string"&&(s.url.startsWith("https://")||s.url.startsWith("http://"))?s.url:"";
    return '<div class="muted">• '+esc(s.title||"Untitled source")+(url?' — <a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Open</a>':"")+'</div>';
   }).join("");
   return '<div class="row"><span class="tag">'+esc(x.status||"UNKNOWN")+'</span><b>'+esc(x.gap||x.project_objective||"Research run")+'</b><br><span class="muted">'+esc(x.updated_at||x.created_at||"Date unavailable")+'</span>'+(x.sources?.length?'<div style="margin-top:8px"><b>Retrieved sources</b>'+sourceLinks+'</div>':'<div class="muted">No retrievable source records attached yet.</div>')+'</div>';
  }).join("")||"<p>No automatic research runs yet. The scheduler starts its first pass shortly after launch.</p>";
  target.innerHTML+='<div class="row"><h3>Proposed follow-up questions</h3><p class="muted">Questions generated from recorded research gaps. All remain proposals until reviewed; none changes a scientific claim.</p>'+(queueItems.map(q=>'<div class="row"><span class="tag">'+esc(q.status||"PROPOSED")+'</span><span class="tag">'+esc(q.priority||"NORMAL")+'</span><b>'+esc(q.question)+'</b><br><span class="muted">'+esc(q.rationale||"No rationale recorded.")+'</span></div>').join("")||'<p>No follow-up questions have been proposed yet.</p>')+'</div>';
 }catch(e){target.innerHTML='<p class="danger">Could not load research feed: '+esc(e.message)+'</p>'}
}
async function loadEvidenceMap(){
 const target=document.getElementById("evidence-map"); if(!target)return;
 const id=selected(); if(!id){target.textContent="Select a project to view its evidence map.";return}
 target.textContent="Loading evidence map…";
 try{
  const result=await api("/api/hds/projects/"+encodeURIComponent(id)+"/evidence-map");
  const claims=result.claims||[];
  target.innerHTML=claims.map(claim=>{
   const counts=claim.counts||{}, comparison=claim.study_comparison||{};
   const outcomeHtml=(claim.recorded_study_outcomes||[]).map(sourceGroup=>
    (sourceGroup.studies||[]).map(study=>
     '<div class="row"><b>'+esc(study.study_title||study.study_id)+'</b>'+
     ((study.outcomes||[]).map(outcome=>{
      const fmt=value=>value===null||value===undefined?"not recorded":String(value);
      return '<div class="muted">'+esc(outcome.outcome_name)+' ('+esc(outcome.unit)+', '+esc(outcome.observation_type)+', '+esc(outcome.phase)+'): n='+esc(outcome.n_observed)+' observed / '+esc(outcome.records_total)+' records; mean '+esc(fmt(outcome.mean))+'; median '+esc(fmt(outcome.median))+'; range '+esc(fmt(outcome.minimum))+'–'+esc(fmt(outcome.maximum))+'; missing '+esc(outcome.n_missing)+'.</div>';
     }).join("")||'<div class="muted">No structured outcome observations recorded.</div>')+'</div>'
    ).join("")
   ).join("");
   const adherenceHtml=(claim.recorded_study_adherence||[]).map(sourceGroup=>
    (sourceGroup.studies||[]).map(study=>
     '<div class="row"><b>'+esc(study.study_title||study.study_id)+'</b>'+
     ((study.phases||[]).map(phase=>{
      const rate=phase.completion_rate===null||phase.completion_rate===undefined?"not calculable":(phase.completion_rate*100).toFixed(1)+"%";
      return '<div class="muted">'+esc(phase.phase)+': '+esc(phase.completed_total)+' completed / '+esc(phase.planned_total)+' planned ('+esc(rate)+'); '+esc(phase.participants_total)+' participants, '+esc(phase.records_total)+' records.</div>';
     }).join("")||'<div class="muted">No adherence records recorded.</div>')+'</div>'
    ).join("")
   ).join("");
   const comparisonHtml=["design","population","findings"].map(field=>{
    const item=comparison[field]||{};
    const values=(item.recorded_values||[]).map(x=>'<div class="muted">• '+esc(x.study_title)+': '+esc(x.value)+'</div>').join("");
    const missing=(item.verified_sources_without_study_record||[]).length;
    return '<div><b>'+esc(field)+'</b> <span class="tag">'+esc(item.status||"NOT_RECORDED")+'</span>'+values+(missing?'<div class="muted">'+missing+' verified source(s) without a linked study record</div>':"")+'</div>';
   }).join("");
   return '<div class="row"><span class="tag">'+esc(claim.pattern)+'</span><b>'+esc(claim.claim)+'</b><div class="muted">Verified excerpts: '+esc(counts.verified_support_excerpts||0)+' supporting · '+esc(counts.verified_contradict_excerpts||0)+' contradicting · '+esc(counts.verified_neutral_excerpts||0)+' neutral. Excluded non-verified: '+esc(counts.excluded_nonverified_items||0)+'.</div><div class="muted">'+esc(claim.interpretation||"")+'</div><details style="margin-top:8px"><summary>Recorded study comparison</summary><div class="list" style="margin-top:8px">'+comparisonHtml+'</div></details><details style="margin-top:8px"><summary>Recorded study outcome data (within-study summaries only)</summary><div class="list" style="margin-top:8px">'+(outcomeHtml||'<div class="muted">No linked structured outcome observations recorded.</div>')+'</div></details><details style="margin-top:8px"><summary>Recorded intervention adherence (process measure)</summary><div class="list" style="margin-top:8px">'+(adherenceHtml||'<div class="muted">No linked adherence records recorded.</div>')+'</div></details></div>';
  }).join("")||"<p>No project claims have been registered yet.</p>";
  target.innerHTML+='<p class="muted">'+esc(result.method||"")+'</p><p class="muted">'+(result.limitations||[]).map(esc).join(" ")+'</p>';
 }catch(e){target.innerHTML='<p class="danger">Could not load evidence map: '+esc(e.message)+'</p>'}
}
async function init(){try{projects=(await api('/api/founder/projects')).items||[];const s=document.getElementById('project');s.innerHTML=projects.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.objective||p.id)+'</option>').join('');await refreshAll();document.getElementById("project").addEventListener("change",refreshAll)}catch(e){document.getElementById('status').textContent='Authentication or API error: '+e.message}}
async function refreshAll(){await Promise.all([refresh(),loadBackgroundFeed(),loadEvidenceMap()])}
async function refreshProjectFeed(){try{const previous=selected();projects=(await api('/api/founder/projects')).items||[];const s=document.getElementById('project');s.innerHTML=projects.map(p=>'<option value="'+esc(p.id)+'">'+esc(p.objective||p.id)+'</option>').join('');if(projects.some(p=>p.id===previous))s.value=previous;await loadBackgroundFeed()}catch(e){document.getElementById('background-feed').textContent='Feed refresh failed: '+e.message}}
setInterval(refreshProjectFeed,5*60*1000);
async function askChat(){
 const msg=document.getElementById("chatmsg").value.trim(); if(!msg)return;
 const log=document.getElementById("chatlog"); log.innerHTML+='<div class="row"><b>You</b><br>'+esc(msg)+'</div>';
 document.getElementById("chatmsg").value="";
 try{const r=await api("/api/founder/"+selected()+"/chat",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({message:msg})});
 log.innerHTML+='<div class="row"><b>HDS AI</b><br>'+esc(r.answer)+'<br><span class="muted">Unverified advisory output.</span></div>';
 }catch(e){log.innerHTML+='<div class="row danger">Chat blocked: '+esc(e.message)+'</div>'}
}
async function runMentalResearch(){
 const button=document.getElementById("mental-run");
 const status=document.getElementById("mental-status");
 const results=document.getElementById("mental-results");
 const question=document.getElementById("mental-question").value.trim();
 const limit=Number(document.getElementById("mental-limit").value||20);
 if(!question){status.textContent="Enter a research question first.";return}
 button.disabled=true;button.textContent="Researching…";results.innerHTML="";
 status.textContent="Creating research workspace…";
 try{
  const created=await api("/api/hds/research-loops/bootstrap",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({question})});
  const runId=created.run.id;
  status.textContent="Searching PubMed and Crossref, collecting available abstracts, and running one bounded AI analysis…";
  const output=await api("/api/hds/research-loops/"+encodeURIComponent(runId)+"/run-first-pass",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({query:question,providers:["pubmed","crossref"],limit})});
  const count=output.retrieval?.result_count??0;
  const claims=Array.isArray(output.agent_output?.candidate_claims)?output.agent_output.candidate_claims:[];
  const sourceData=await api("/api/hds/research-loops/"+encodeURIComponent(runId)+"/sources").catch(()=>({items:[]}));
  const sourceItems=sourceData.items||[];
  let html='<div class="research-output"><div class="toolbar"><span class="tag">'+esc(output.status||"UNKNOWN")+'</span><span class="tag">'+esc(output.scientific_status||"")+'</span><span class="tag">'+esc(count)+' retrieved records</span></div>';
  if(output.status==="RESEARCH_PASS_RECORDED"){
   html+='<h3>Candidate claims and observations ('+claims.length+')</h3>';
   if(claims.length){html+='<div class="list">'+claims.map((x,n)=>'<div class="row"><b>'+esc(x.statement||("Candidate "+(n+1)))+'</b><br><span class="tag">'+esc(x.classification||"UNCLASSIFIED")+'</span><span class="tag">'+esc(x.stance||"")+'</span><p>'+esc(x.exact_excerpt||"No excerpt supplied")+'</p><span class="muted">Source ID: '+esc(x.source_id||"not supplied")+'</span></div>').join("")+'</div>'}
   else html+='<p>No source-grounded candidate claims were returned. Read the analysis and limitations below; do not treat an empty claim list as a negative finding.</p>';
   html+='<h3>AI analysis</h3><pre>'+esc(output.agent_output?.result||"No narrative result supplied.")+'</pre>';
   html+='<h3>Limitations</h3><pre>'+esc(output.agent_output?.limitations||"Not supplied.")+'</pre>';
   html+='<h3>Uncertainty</h3><pre>'+esc(output.agent_output?.uncertainty||"Not supplied.")+'</pre>';
   html+='<h3>Retrieved scientific sources ('+sourceItems.length+')</h3>';
   html+='<div class="list">'+sourceItems.map((x,n)=>{
    const url=typeof x.url==="string"&&(x.url.startsWith("https://")||x.url.startsWith("http://"))?x.url:"";
    return '<div class="row"><b>'+(n+1)+'. '+esc(x.title||"Untitled source")+'</b><br><span class="muted">'+esc(x.authors||"Authors not listed")+' • '+esc(x.publication_year||"Year unknown")+'</span><br><span class="tag">'+esc(x.source_type||"SOURCE")+'</span> '+(url?'<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">Open source</a>':"No source URL")+'</div>';
   }).join("")+'</div>';
   html+='<p class="research-warning"><b>Unverified research output.</b> This is a discovery pass, not a scientific finding. Each claim needs independent source review and interpretation.</p>';
  }else{
   html+='<h3>Research could not complete</h3><pre>'+esc(JSON.stringify({reason:output.reason||output.error||output.validation_error||output.notice||"No further detail",next_action:output.next_action||null,errors:output.retrieval?.errors||output.errors||[]},null,2))+'</pre>';
   html+='<p>Check that Ollama is running with the selected model installed and that readable abstracts were retrieved. If the model provider is left on the safe placeholder, AI analysis will not run.</p>';
  }
  html+='<details><summary>Technical record</summary><pre>'+esc(JSON.stringify({run_id:runId,project_id:created.project?.id,run:output.run,retrieval:output.retrieval,task:output.task,agent_run_id:output.agent_run_id},null,2))+'</pre></details></div>';
  results.innerHTML=html;
  status.textContent=output.status==="RESEARCH_PASS_RECORDED"?"Research pass saved. Independent review is still required.":"Research pass stopped: "+(output.status||"unknown status");
 }catch(e){status.innerHTML='<span class="research-error">Research failed: '+esc(e.message)+'</span>'}
 finally{button.disabled=false;button.textContent="Start research"}
}
async function runCycle(){const id=selected();if(!id)return;document.getElementById("status").textContent="Running governed research cycle…";try{await api("/api/science/research-cycle/"+id,{method:"POST"});await refresh()}catch(e){document.getElementById("status").textContent="Cycle blocked: "+e.message}}
document.getElementById("project").addEventListener("change",refresh);init();
</script></body></html>"""

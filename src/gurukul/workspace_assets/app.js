'use strict';
const el=id=>document.getElementById(id);
let context=null,revision=0,saved='',dirty=false,busy=false,conflict=false,loading=false,timer=null,latestState=null;
const say=text=>{el('message').textContent=text;};
async function api(path,body){
 const response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw Error(data.error||'Request not confirmed');return data;
}
function controls(){
 const closed=latestState?.lifecycle.status==='CLOSED', interrupted=latestState?.lifecycle.status==='INTERRUPTED';
 for(const id of ['run','submit'])el(id).disabled=busy||conflict||closed||interrupted;
 el('start').disabled=busy||context!=='practice'||!latestState?.retrieval_available||!el('ready').checked;
 el('prepare').disabled=busy||!!latestState?.lifecycle.assessment&&latestState.lifecycle.status!=='CLOSED';
 el('editor').readOnly=!!closed;
 for(const id of ['help','review','interrupted'])el(id).disabled=busy||context==='practice'||closed;
 el('declare').disabled=busy||!latestState?.operations.some(o=>o.attempt);
}
function show(result){
 el('outcome').textContent=result.status||result.outcome||'Recorded';
 el('receipt').textContent=JSON.stringify(result,null,2);
 const execution=result.attempt?.execution;
 el('output').textContent=execution?('Execution: '+execution.status+'\n'+(execution.stdout||'')+(execution.stderr||'')):(result.reason||result.observation?.outcome||'');
}
async function refresh(force=false){
 const state=await api('/api/state'+(context?'?context='+encodeURIComponent(context):''));
 const changed=context!==state.context;context=state.context;latestState=state;
 if(force||changed||!loading){el('editor').value=state.draft.source;saved=state.draft.source;revision=state.draft.revision;dirty=false;conflict=false;loading=true;}
 else if(state.draft.revision!==revision&&state.draft.source!==saved){conflict=true;say('A newer draft exists. Your editor is preserved; load the saved draft explicitly.');}
 el('mode').textContent=context==='practice'?'Practice / preparation':'Assessment';
 el('task').textContent=state.task.prompt;
 el('values').textContent=state.task.initial_values?'Initial values:\n'+JSON.stringify(state.task.initial_values,null,2)+'\nReassignments:\n'+JSON.stringify(state.task.reassignments,null,2):'Assessment task data stays hidden until Start succeeds.';
 el('lifecycle').textContent='State: '+(state.lifecycle.status||state.lifecycle.phase)+(state.lifecycle.closed?' — '+state.lifecycle.closed.outcome:'');
 el('budget').textContent=state.reservation_limit?'Reservations: '+state.reservations_used+' / '+state.reservation_limit:'Practice mode';
 el('clock').textContent='Server time: '+state.server_time;
 el('saved').textContent=conflict?'Draft conflict — editor preserved':dirty?'Unsaved changes':'Saved revision '+revision;
 if(timer)clearInterval(timer);
 const base=Date.parse(state.server_time),loaded=performance.now(),deadline=state.deadline&&Date.parse(state.deadline);
 function tick(){if(!deadline){el('timer').textContent='Assessment timer not started';return;}const left=Math.max(0,Math.ceil((deadline-base-(performance.now()-loaded))/1000));el('timer').textContent=state.lifecycle.status==='CLOSED'?'Assessment closed':left?'Time remaining: '+Math.floor(left/60)+':'+String(left%60).padStart(2,'0'):'Deadline elapsed — reconcile / exit';}
 tick();timer=setInterval(tick,500);
 el('declarations').textContent=state.declarations?.length?JSON.stringify(state.declarations,null,2):'No bound declaration recorded yet.';
 el('reviews').textContent=state.reviews?.length?'Human review (separate from automatic checks):\n'+JSON.stringify(state.reviews,null,2):'';
 if(state.operations.length)show(state.operations[state.operations.length-1]);
 controls();return state;
}
async function save(){
 if(!dirty)return;if(conflict)throw Error('Reload or preserve your conflicting draft before continuing.');
 const source=el('editor').value;
 const draft=await api('/api/save',{context,revision,source});revision=draft.revision;saved=source;dirty=el('editor').value!==source;el('saved').textContent=dirty?'Unsaved changes':'Saved revision '+revision;
}
async function action(fn){if(busy)return;busy=true;controls();try{await fn();}catch(error){say(error.message);}finally{busy=false;controls();}}
let saveTimer;el('editor').addEventListener('input',()=>{dirty=true;el('saved').textContent='Saving…';clearTimeout(saveTimer);saveTimer=setTimeout(()=>action(async()=>{await save();}),500);});
el('editor').addEventListener('keydown',event=>{if(event.key==='Tab'){event.preventDefault();el('editor').setRangeText('    ',el('editor').selectionStart,el('editor').selectionEnd,'end');el('editor').dispatchEvent(new Event('input'));}});
el('ready').onchange=controls;
el('reload').onclick=()=>action(async()=>{if(dirty&&!confirm('Replace your editor with the server-saved draft?'))return;await refresh(true);say('Saved draft loaded.');});
el('prepare').onclick=()=>action(async()=>{await save();context='practice';await refresh(true);say('Preparation ready. No assessment task has been revealed.');});
el('start').onclick=()=>action(async()=>{await save();const opened=await api('/api/start',{ready:el('ready').checked});context=opened.context;await refresh(true);say('Assessment opened. The canonical deadline is running.');});
for(const kind of ['run','submit'])el(kind).onclick=()=>action(async()=>{await save();const result=await api('/api/'+kind,{context,revision,role:el('role').value});show(result);say(result.status);await refresh();});
el('declare').onclick=()=>action(async()=>{await api('/api/declare',{context,role:el('role').value,text:el('declaration').value,kind:el('kind').value,timing:el('timing').value});say('Declaration recorded as learner-declared.');await refresh();});
for(const reason of ['help','review','interrupted'])el(reason).onclick=()=>action(async()=>{const result=await api('/api/exit',{context,reason});show(result);await refresh();say('Exit confirmed: '+result.outcome+'. Teaching remains unavailable in this first slice.');});
(async()=>{try{const token=location.hash.slice(1);if(token){const response=await fetch('/api/bootstrap',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:'{}'});if(!response.ok)throw Error('Launch authorization failed.');history.replaceState(null,'','/');}await refresh(true);say('Workspace ready. Prior learning is legitimate; declarations describe assistance during this work.');setInterval(()=>{if(!busy&&!dirty)refresh().catch(error=>say(error.message));},2500);}catch(error){say(error.message);}})();

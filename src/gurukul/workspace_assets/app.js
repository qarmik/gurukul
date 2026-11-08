'use strict';
const el=id=>document.getElementById(id);
let context=null,revision=0,saved='',dirty=false,busy=false,conflict=false,loading=false,timer=null,latestState=null;
let generation=0,readSerial=0,transitioning=false,saveTimer;
function indicator(){el('saved').textContent=!loading?'Loading saved draft…':conflict?'Draft conflict — editor preserved':dirty?'Unsaved changes':'Saved revision '+revision;}
function scheduleSave(){clearTimeout(saveTimer);saveTimer=setTimeout(()=>action(save),500);}
function changeContext(next){
 ++generation;++readSerial;context=next;loading=false;revision=0;saved='';dirty=false;conflict=false;
 el('editor').value='';clearGuru();latestState=null;indicator();controls();
}

let messageText='',connectionError=null;
function renderMessage(){el('message').textContent=[connectionError,messageText].filter(Boolean).join(' ');}
const say=text=>{messageText=text;renderMessage();};
function reportError(error){if(error.connectionFailure){connectionError=error.message;renderMessage();}else say(error.message);}
function recovered(){
 // A state read or an older save acknowledgement cannot confirm unsaved edits.
 if(connectionError!==null&&!dirty&&!conflict){connectionError=null;renderMessage();}
}
async function api(path,body){
 let response;
 try{response=await fetch(path,{method:body===undefined?'GET':'POST',headers:body===undefined?{}:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});}
 catch(error){error.connectionFailure=true;throw error;}
 const data=await response.json();if(!response.ok)throw Error(data.error||'Request not confirmed');return data;
}
function clearGuru(){
 el('question').value='';el('guru-reply').textContent='';
 showGuruHistory([]);
}
function showGuruHistory(exchanges){
 const history=el('guru-history');
 const transcript=exchanges.map(({question,reply})=>'You: '+question+'\nGuru: '+reply).join('\n\n');
 if(history.textContent!==transcript)history.textContent=transcript;
}
function guruAvailable(){return context==='practice'&&['sample','pipeline'].includes(latestState?.teaching);}
function controls(){
 const closed=latestState?.lifecycle.status==='CLOSED', interrupted=latestState?.lifecycle.status==='INTERRUPTED';
 for(const id of ['run','submit'])el(id).disabled=!loading||busy||conflict||closed||interrupted;
 el('start').disabled=busy||context!=='practice'||!latestState?.retrieval_available||!el('ready').checked;
 el('prepare').disabled=busy||!!latestState?.lifecycle.assessment&&latestState.lifecycle.status!=='CLOSED';
 el('editor').readOnly=!loading||!!closed||transitioning;
 for(const id of ['help','review','interrupted'])el(id).disabled=busy||context==='practice'||closed;
 el('declare').disabled=busy||!latestState?.operations.some(o=>o.attempt);
 const available=guruAvailable();
 el('question').disabled=!available||busy;
 el('teach').disabled=!available||busy||!el('question').value.trim();
 el('guru-status').textContent=available?(latestState.teaching==='sample'?'Sample mode: no live tutor or assessment credit.':'Practice teaching does not award assessment credit.'):
  context&&context!=='practice'?'Ask Guru unavailable during assessment.':'Ask Guru unavailable for this launch.';
}
function show(result){
 el('outcome').textContent=result.status||result.outcome||'Recorded';
 el('receipt').textContent=JSON.stringify(result,null,2);
 const execution=result.attempt?.execution;
 el('output').textContent=execution?('Execution: '+execution.status+'\n'+(execution.stdout||'')+(execution.stderr||'')):(result.reason||result.observation?.outcome||'');
}
async function refresh(force=false){
 const request=++readSerial,requestedContext=context,requestedGeneration=generation;
 const state=await api('/api/state'+(context?'?context='+encodeURIComponent(context):''));
 // A read cannot overwrite edits, a newer save, or a context entered after dispatch.
 if(request!==readSerial||context!==requestedContext||generation!==requestedGeneration)return;
 if(loading&&context===state.context&&state.draft.revision<revision)return;
 const changed=context!==state.context;context=state.context;latestState=state;
 if(changed)clearGuru();
 showGuruHistory(context==='practice'?(state.teaching_exchanges||[]):[]);
 if(force||changed||!loading){el('editor').value=state.draft.source;saved=state.draft.source;revision=state.draft.revision;dirty=false;conflict=false;loading=true;}
 else if(state.draft.revision!==revision){conflict=true;say('A newer draft exists. Your editor is preserved; load the saved draft explicitly.');}
 el('mode').textContent=context==='practice'?'Practice / preparation':'Assessment';
 el('task').textContent=state.task.prompt;
 el('values').textContent=state.task.initial_values?'Initial values:\n'+JSON.stringify(state.task.initial_values,null,2)+'\nReassignments:\n'+JSON.stringify(state.task.reassignments,null,2):'Assessment task data stays hidden until Start succeeds.';
 el('lifecycle').textContent='State: '+(state.lifecycle.status||state.lifecycle.phase)+(state.lifecycle.closed?' — '+state.lifecycle.closed.outcome:'');
 el('budget').textContent=state.reservation_limit?'Reservations: '+state.reservations_used+' / '+state.reservation_limit:'Practice mode';
 el('clock').textContent='Server time: '+state.server_time;
 indicator();
 if(timer)clearInterval(timer);
 const base=Date.parse(state.server_time),loaded=performance.now(),deadline=state.deadline&&Date.parse(state.deadline);
 function tick(){if(!deadline){el('timer').textContent='Assessment timer not started';return;}const left=Math.max(0,Math.ceil((deadline-base-(performance.now()-loaded))/1000));el('timer').textContent=state.lifecycle.status==='CLOSED'?'Assessment closed':left?'Time remaining: '+Math.floor(left/60)+':'+String(left%60).padStart(2,'0'):'Deadline elapsed — reconcile / exit';}
 tick();timer=setInterval(tick,500);
 el('declarations').textContent=state.declarations?.length?JSON.stringify(state.declarations,null,2):'No bound declaration recorded yet.';
 el('reviews').textContent=state.reviews?.length?'Human review (separate from automatic checks):\n'+JSON.stringify(state.reviews,null,2):'';
 if(state.operations.length)show(state.operations[state.operations.length-1]);
 recovered();controls();return state;
}
async function save(){
 if(!dirty)return;if(conflict)throw Error('Reload or preserve your conflicting draft before continuing.');
 const source=el('editor').value,savingContext=context;++generation;
 const draft=await api('/api/save',{context:savingContext,revision,source});
 ++generation;
 if(context!==savingContext)return;
 revision=draft.revision;saved=source;dirty=el('editor').value!==source;indicator();recovered();
}
async function action(fn,transition=false){
 if(busy)return;busy=true;transitioning=transition;controls();let failed=false;
 try{await fn();}catch(error){failed=true;reportError(error);}finally{
  busy=false;transitioning=false;indicator();controls();
  // A timer that fired during an action must not swallow the final edit.
  if(dirty&&!conflict&&!failed)scheduleSave();
 }
}
el('editor').addEventListener('input',()=>{++generation;dirty=true;indicator();scheduleSave();});
window.addEventListener('online',()=>action(async()=>{await save();await refresh();}));
window.addEventListener('beforeunload',event=>{if(dirty){event.preventDefault();event.returnValue='';}});
el('editor').addEventListener('keydown',event=>{if(el('editor').readOnly)return;if(event.key==='Tab'){event.preventDefault();el('editor').setRangeText('    ',el('editor').selectionStart,el('editor').selectionEnd,'end');el('editor').dispatchEvent(new Event('input'));}});
el('ready').onchange=controls;
el('question').addEventListener('input',controls);
el('teach').onclick=()=>{
 if(!guruAvailable()||el('teach').disabled)return;
 return action(async()=>{
  el('guru-reply').textContent='';
  try{
   const result=await api('/api/teach',{question:el('question').value});
   if(guruAvailable()){
    if(result.kind==='sample')el('guru-reply').textContent='Sample reply: '+result.reply;
    else{
     ++readSerial; // An older state read must not erase the newly admitted exchange.
     showGuruHistory(result.teaching_exchanges);
    }
   }
  }catch(error){
   el('guru-reply').textContent=error.connectionFailure?'Could not reach Guru. Please try again.':error.message;
  }
 });
};
el('reload').onclick=()=>action(async()=>{if(dirty&&!confirm('Replace your editor with the server-saved draft?'))return;const loaded=await refresh(true);say(loaded?'Saved draft loaded.':'New edits preserved; the saved draft was not loaded.');});
el('prepare').onclick=()=>action(async()=>{await save();changeContext('practice');await refresh(true);say('Preparation ready. No assessment task has been revealed.');},true);
el('start').onclick=()=>action(async()=>{await save();const opened=await api('/api/start',{ready:el('ready').checked});changeContext(opened.context);await refresh(true);say('Assessment opened. The canonical deadline is running.');},true);
for(const kind of ['run','submit'])el(kind).onclick=()=>action(async()=>{await save();const result=await api('/api/'+kind,{context,revision,role:el('role').value});show(result);say(result.status);await refresh();});
el('declare').onclick=()=>action(async()=>{await api('/api/declare',{context,role:el('role').value,text:el('declaration').value,kind:el('kind').value,timing:el('timing').value});say('Declaration recorded as learner-declared.');await refresh();});
for(const reason of ['help','review','interrupted'])el(reason).onclick=()=>action(async()=>{const result=await api('/api/exit',{context,reason});show(result);await refresh();say('Exit confirmed: '+result.outcome+'.');});
(async()=>{try{const token=location.hash.slice(1);if(token){const response=await fetch('/api/bootstrap',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:'{}'});if(!response.ok)throw Error('Launch authorization failed.');history.replaceState(null,'','/');}await refresh(true);say('Workspace ready. Prior learning is legitimate; declarations describe assistance during this work.');setInterval(()=>{if(!busy&&!dirty)refresh().catch(reportError);},2500);}catch(error){reportError(error);}})();

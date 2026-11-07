// Deterministic DOM/fetch scheduling harness for the actual app.js.
// Unit evidence only: not a browser, Mac launch, or real learner ledger.
import test from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {readFileSync} from 'node:fs';
const source=readFileSync(new URL('../src/gurukul/workspace_assets/app.js',import.meta.url),'utf8');
const flush=async()=>{for(let i=0;i<20;i++)await Promise.resolve();};
function deferred(){let resolve;const promise=new Promise(r=>resolve=r);return {promise,resolve};}
function state(context='practice',revision=0,text=''){
 return {context,draft:{revision,source:text},lifecycle:{status:context==='practice'?'teaching':'OPEN'},task:{prompt:'Synthetic task'},operations:[],retrieval_available:true,declarations:[],reviews:[],server_time:'2026-10-18T00:00:00Z'};
}
async function harness(){
 const nodes=new Map(),timers=new Map();let next=0;
 const node=id=>{if(!nodes.has(id))nodes.set(id,{value:id==='role'?'repaired':'',textContent:'',checked:false,disabled:false,readOnly:false,addEventListener(k,v){this[k]=v;}});return nodes.get(id);};
 const h={server:state(),calls:[],slowRun:null,slowSave:null,slowRead:null};
 const sandbox={console,JSON,Error,Date,Promise,Event:class{},performance:{now:()=>0},location:{hash:''},history:{replaceState(){}},confirm:()=>true,
  document:{getElementById:node},window:{addEventListener(k,v){h[k]=v;}},
  setInterval(){return ++next;},clearInterval(){},setTimeout(fn){const id=++next;timers.set(id,fn);return id;},clearTimeout(id){timers.delete(id);},
  async fetch(path,options={}){
   const body=options.body&&JSON.parse(options.body);h.calls.push({path,body});
   if(path==='/api/save'&&h.failSave){h.failSave=false;throw Error('Synthetic disconnect');}
   if(path==='/api/save'&&h.rejectSave){h.rejectSave=false;return {ok:false,json:async()=>({error:'Synthetic permission rejection'})};}
   let result;
   if(path.startsWith('/api/state')){if(h.failRead){h.failRead=false;throw Error('Synthetic state disconnect');}result=structuredClone(h.server);if(h.slowRead){const d=h.slowRead;h.slowRead=null;await d.promise;}}
   else if(path==='/api/save'){
    if(h.slowSave){const d=h.slowSave;h.slowSave=null;await d.promise;}
    h.server.draft={revision:body.revision+1,source:body.source};result=structuredClone(h.server.draft);
   }else if(path==='/api/run'){
    if(h.slowRun){const d=h.slowRun;h.slowRun=null;await d.promise;}
    result={status:'EXECUTION_RECORDED'};
   }else throw Error('Unexpected route '+path);
   return {ok:true,json:async()=>result};
  }};
 vm.createContext(sandbox);vm.runInContext(source,sandbox);await flush();
 h.node=node;h.eval=code=>vm.runInContext(code,sandbox);
 h.type=text=>{node('editor').value=text;node('editor').input();};
 h.timers=async()=>{const pending=[...timers.values()];timers.clear();for(const f of pending)f();await flush();};
 return h;
}

test('final autosave fired while Run busy is eventually persisted',async()=>{
 const h=await harness();h.type('first revision');await h.timers();
 const slow=deferred();h.slowRun=slow;
 const running=h.node('run').onclick();await flush();
 h.type('latest while running');await h.timers();
 assert.notEqual(h.node('saved').textContent,'Saved revision 1');
 slow.resolve();await running;await h.timers();
 assert.equal(h.server.draft.source,'latest while running');
 assert.match(h.node('saved').textContent,/Saved revision 2/);
});

test('typing during a slow save queues the final edit without another keystroke',async()=>{
 const h=await harness(),slow=deferred();h.slowSave=slow;
 h.type('first');await h.timers();h.type('last');await h.timers();
 slow.resolve();await flush();await h.timers();
 assert.equal(h.server.draft.source,'last');assert.match(h.node('saved').textContent,/Saved revision 2/);
});

test('old periodic read arriving after save cannot create false conflict',async()=>{
 const h=await harness(),slow=deferred();h.slowRead=slow;
 const reading=h.eval('refresh()');await flush();
 h.type('newer saved text');await h.timers();slow.resolve();await reading;
 assert.equal(h.node('editor').value,'newer saved text');
 assert.doesNotMatch(h.node('saved').textContent,/conflict/i);
 assert.match(h.node('saved').textContent,/Saved revision 1/);
});

test('a response for the previous context cannot switch back or replace text',async()=>{
 const h=await harness(),slow=deferred();h.slowRead=slow;
 const reading=h.eval('refresh()');await flush();
 h.server=state('synthetic-assessment',0,'');h.eval("context='synthetic-assessment'");
 await h.eval('refresh(true)');h.type('own assessment text');slow.resolve();await reading;
 assert.equal(h.eval('context'),'synthetic-assessment');assert.equal(h.node('editor').value,'own assessment text');
 assert.match(h.node('saved').textContent,/Unsaved|Saving/);
});

test('typing while explicit reload awaits response is preserved and marked unsaved',async()=>{
 const h=await harness(),slow=deferred();h.slowRead=slow;
 const reading=h.node('reload').onclick();await flush();h.type('new text during reload');slow.resolve();await reading;
 assert.equal(h.node('editor').value,'new text during reload');
 assert.match(h.node('message').textContent,/New edits preserved/);
 assert.doesNotMatch(h.node('saved').textContent,/^Saved revision/);
});

test('external newer revision is a conflict; latest editor text is retained',async()=>{
 const h=await harness();h.type('local text');h.server.draft={revision:4,source:'other tab'};
 await h.eval('refresh()');assert.equal(h.node('editor').value,'local text');assert.match(h.node('saved').textContent,/conflict/i);
 await h.timers();assert.equal(h.server.draft.source,'other tab');
});


test('disconnect keeps an unsaved indicator; reconnect persists without more typing',async()=>{
 const h=await harness();h.failSave=true;h.type('offline edit');await h.timers();
 assert.match(h.node('saved').textContent,/Unsaved/);assert.equal(h.server.draft.source,'');
 let prevented=false;h.beforeunload({preventDefault(){prevented=true;}});assert.equal(prevented,true);
 await h.online();assert.equal(h.server.draft.source,'offline edit');assert.match(h.node('saved').textContent,/Saved revision 1/);
});

test('context transition freezes editing including the Tab insertion path',async()=>{
 const h=await harness(),slow=deferred();h.slowRead=slow;
 const switching=h.node('prepare').onclick();await flush();
 assert.equal(h.node('editor').readOnly,true);
 h.node('editor').keydown({key:'Tab',preventDefault(){throw Error('Tab must not insert into frozen editor');}});
 slow.resolve();await switching;assert.equal(h.node('editor').readOnly,false);
});

test('newest read wins when same-context responses arrive out of order',async()=>{
 const h=await harness(),slow=deferred();h.slowRead=slow;
 const old=h.eval('refresh()');await flush();h.server.draft={revision:3,source:'another tab'};
 await h.eval('refresh(true)');slow.resolve();await old;
 assert.equal(h.node('editor').value,'another tab');assert.match(h.node('saved').textContent,/Saved revision 3/);
});


test('failed context load keeps editor blank and disabled until confirmed reload',async()=>{
 const h=await harness();h.type('saved preparation');await h.timers();h.failRead=true;
 await h.node('prepare').onclick();assert.equal(h.node('editor').value,'');
 assert.equal(h.node('editor').readOnly,true);assert.equal(h.node('run').disabled,true);
 assert.match(h.node('saved').textContent,/Loading/);
 await h.eval('refresh(true)');assert.equal(h.node('editor').value,'saved preparation');assert.equal(h.node('run').disabled,false);
});

test('acknowledged reconnect save clears the connection error without refresh',async()=>{
 const h=await harness();h.failSave=true;h.type('offline edit');await h.timers();
 assert.match(h.node('message').textContent,/Synthetic disconnect/);
 await h.online();
 assert.equal(h.server.draft.source,'offline edit');
 assert.match(h.node('saved').textContent,/Saved revision 1/);
 assert.doesNotMatch(h.node('message').textContent,/Synthetic disconnect/);
});

test('failed reconnect save retains the error and unsaved editor',async()=>{
 const h=await harness();h.failSave=true;h.type('offline edit');await h.timers();
 h.failSave=true;await h.online();
 assert.equal(h.server.draft.source,'');assert.equal(h.node('editor').value,'offline edit');
 assert.match(h.node('saved').textContent,/Unsaved/);
 assert.match(h.node('message').textContent,/Synthetic disconnect/);
});

test('successful state read cannot clear a failed save for dirty text',async()=>{
 const h=await harness();h.failSave=true;h.type('offline edit');await h.timers();
 await h.eval('refresh()');
 assert.equal(h.server.draft.source,'');assert.match(h.node('saved').textContent,/Unsaved/);
 assert.match(h.node('message').textContent,/Synthetic disconnect/);
});

test('read recovery clears only the connection error for an already saved draft',async()=>{
 const h=await harness();h.failRead=true;await h.online();
 assert.match(h.node('message').textContent,/Synthetic state disconnect/);
 await h.eval('refresh()');
 assert.doesNotMatch(h.node('message').textContent,/Synthetic state disconnect/);
 assert.match(h.node('saved').textContent,/Saved revision 0/);
});

test('recovery preserves an unrelated unresolved completion warning',async()=>{
 const h=await harness();
 h.eval("say('Execution preserved; completion unresolved.')");
 h.failSave=true;h.type('offline edit');await h.timers();await h.online();
 assert.match(h.node('message').textContent,/Execution preserved; completion unresolved/);
 assert.doesNotMatch(h.node('message').textContent,/Synthetic disconnect/);
});

test('reconnect with a newer server draft retains conflict and local text',async()=>{
 const h=await harness();h.failSave=true;h.type('local offline edit');await h.timers();
 h.server.draft={revision:4,source:'other tab'};await h.eval('refresh()');await h.online();
 assert.equal(h.server.draft.source,'other tab');assert.equal(h.node('editor').value,'local offline edit');
 assert.match(h.node('saved').textContent,/conflict/i);
 assert.match(h.node('message').textContent,/conflict/i);
});

test('save acknowledgement does not clear failure while a newer edit is unsaved',async()=>{
 const h=await harness();h.failSave=true;h.type('first');await h.timers();
 const slow=deferred();h.slowSave=slow;const reconnect=h.online();await flush();
 h.type('newer unsaved edit');slow.resolve();await reconnect;
 assert.equal(h.server.draft.source,'first');assert.equal(h.node('editor').value,'newer unsaved edit');
 assert.match(h.node('saved').textContent,/Unsaved/);
 assert.match(h.node('message').textContent,/Synthetic disconnect/);
 await h.timers();assert.equal(h.server.draft.source,'newer unsaved edit');
 assert.doesNotMatch(h.node('message').textContent,/Synthetic disconnect/);
});

test('successful save does not dismiss a server-side permission error',async()=>{
 const h=await harness();h.rejectSave=true;h.type('rejected edit');await h.timers();
 assert.match(h.node('saved').textContent,/Unsaved/);
 await h.online();assert.equal(h.server.draft.source,'rejected edit');
 assert.match(h.node('message').textContent,/Synthetic permission rejection/);
});

test('connection failures and recovery preserve an unrelated error beneath them',async()=>{
 const h=await harness();h.eval("say('Evidence integrity error; review required.')");
 h.failSave=true;h.type('offline edit');await h.timers();
 assert.match(h.node('message').textContent,/Synthetic disconnect/);
 assert.match(h.node('message').textContent,/Evidence integrity error/);
 await h.online();assert.match(h.node('message').textContent,/Evidence integrity error/);
 assert.doesNotMatch(h.node('message').textContent,/Synthetic disconnect/);
});

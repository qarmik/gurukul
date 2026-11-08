// Run with Node, an existing Playwright installation and local Chrome/Chromium.
const assert=require('node:assert/strict');
const {spawn}=require('node:child_process');
const {once}=require('node:events');
const {createInterface}=require('node:readline');
const path=require('node:path');
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright-core');
const root=path.resolve(__dirname,'..');

async function main(){
 const browser=await chromium.launch({executablePath:process.env.CHROME_EXECUTABLE||undefined});
 const server=spawn(process.env.PYTHON||'python3',['-B','tests/ask_guru_browser_fixture.py'],{
  cwd:root,env:{...process.env,PYTHONPATH:path.join(root,'src')},stdio:['pipe','pipe','inherit']
 });
 const stopped=once(server,'close');
 const lines=createInterface({input:server.stdout})[Symbol.asyncIterator]();
 let launch,practice,denial,version;
 try{
  const first=await lines.next();
  assert.ok(!first.done,'Fixture failed to start');
  ({launch}=JSON.parse(first.value));
  const page=await browser.newPage();
  version=browser.version();
  page.setDefaultTimeout(8000);
  await page.goto(launch);
  const source='# Disposable practice draft';
  await page.locator('#editor').fill(source);
  await page.waitForFunction(()=>document.querySelector('#saved').textContent==='Saved revision 1');
  const question='What changes after reassignment?';
  const followup='Why didn’t the first print change?';
  for(const q of [question,followup]){
   await page.locator('#question').fill(q);
   const practiceResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/teach');
   await page.getByRole('button',{name:'Ask Guru',exact:true}).click();
   const response=await practiceResponse;
   assert.equal(response.status(),200);
   const result=await response.json();
   for(const flag of ['grants_assessment_credit','grants_mastery','advances_curriculum'])assert.equal(result[flag],false);
   await page.waitForFunction(q=>document.querySelector('#guru-history').textContent.includes(q),q);
  }
  const transcript='You: '+question+'\nGuru: The name now refers to the newly assigned value.\n\nYou: '+followup+'\nGuru: The first print already ran using the value available at that point.';
  assert.equal(await page.locator('#guru-history').isVisible(),true);
  assert.equal(await page.locator('#guru-history').textContent(),transcript);
  assert.equal(await page.locator('#editor').inputValue(),source);
  assert.equal(await page.locator('#saved').textContent(),'Saved revision 1');
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#saved').textContent==='Saved revision 1');
  assert.equal(await page.locator('#editor').inputValue(),source);
  assert.equal(await page.locator('#guru-history').textContent(),transcript);
  practice={transcript,draft_preserved_after_reload:true};
  await page.locator('#ready').check();
  await page.getByRole('button',{name:'Start assessment',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#lifecycle').textContent==='State: OPEN');
  assert.equal(await page.locator('#teach').isDisabled(),true);
  assert.equal(await page.locator('#question').isDisabled(),true);
  assert.equal(await page.locator('#guru-reply').textContent(),'');
  assert.equal(await page.locator('#guru-history').textContent(),'');
  denial=await page.evaluate(async question=>{
   const r=await fetch('/api/teach',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question})});
   return {status:r.status,...await r.json()};
  },question);
  assert.equal(denial.status,409);assert.match(denial.error,/Tutoring denied/);
 }catch(error){
  // The launch fragment is a credential; never include it in the receipt.
  throw Error(String(error).replaceAll(launch||'__no_launch__','[fixture URL]'));
 }finally{
  try{await browser.close();}finally{server.stdin.end();await stopped;}
 }
 const last=await lines.next();
 assert.ok(!last.done,'Fixture did not return ledger counts');
 const ledger=JSON.parse(last.value);
 assert.equal(ledger.responder_calls,2);
 assert.equal(ledger.followup_used_first_exchange,true);
 assert.equal(ledger.executions_after,ledger.executions_before);
 assert.equal(ledger.assessment_reservations,0);
 assert.equal(ledger.assessment_openings,1);
 assert.equal(ledger.provider_calls,0);
 console.log(JSON.stringify({result:'BROWSER_PASS',browser:version,practice,assessment:denial,ledger},null,2));
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});

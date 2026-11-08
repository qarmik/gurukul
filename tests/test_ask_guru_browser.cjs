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
  const source='# GURU-009 disposable draft';
  await page.locator('#editor').fill(source);
  await page.waitForFunction(()=>document.querySelector('#saved').textContent==='Saved revision 1');
  const question='What changes after reassignment?';
  await page.locator('#question').fill(question);
  const practiceResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/teach');
  await page.getByRole('button',{name:'Ask Guru',exact:true}).click();
  assert.equal((await practiceResponse).status(),200);
  await page.waitForFunction(()=>document.querySelector('#guru-reply').textContent.startsWith('Sample reply:'));
  assert.equal(await page.locator('#editor').inputValue(),source);
  assert.equal(await page.locator('#saved').textContent(),'Saved revision 1');
  const reply=await page.locator('#guru-reply').textContent();
  await page.reload();
  await page.waitForFunction(()=>document.querySelector('#saved').textContent==='Saved revision 1');
  assert.equal(await page.locator('#editor').inputValue(),source);
  practice={reply,draft_preserved_after_reload:true};
  await page.locator('#ready').check();
  await page.getByRole('button',{name:'Start assessment',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#lifecycle').textContent==='State: OPEN');
  assert.equal(await page.locator('#teach').isDisabled(),true);
  assert.equal(await page.locator('#question').isDisabled(),true);
  assert.equal(await page.locator('#guru-reply').textContent(),'');
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
 assert.equal(ledger.responder_calls,1);
 assert.equal(ledger.executions_after,ledger.executions_before);
 assert.equal(ledger.assessment_reservations,0);
 assert.equal(ledger.assessment_openings,1);
 assert.equal(ledger.provider_calls,0);
 console.log(JSON.stringify({result:'BROWSER_PASS',browser:version,practice,assessment:denial,ledger},null,2));
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});

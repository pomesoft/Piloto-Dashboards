// Prueba del componente de almacenamiento, sin red ni llamadas al modelo.
import {readFileSync} from 'node:fs';
import assert from 'node:assert/strict';

const source=readFileSync(new URL('../core/chat_quota.py',import.meta.url),'utf8');
const js=source.match(/js='''([\s\S]*?)'''/)[1];
const {default: render}=await import('data:text/javascript;base64,'+Buffer.from(js).toString('base64'));
const saved=new Map();
globalThis.localStorage={getItem:key=>saved.get(key)??null,setItem:(key,value)=>saved.set(key,value)};
globalThis.window={addEventListener(){},removeEventListener(){}};
let queue=Promise.resolve();
Object.defineProperty(globalThis,'navigator',{configurable:true,value:{locks:{request(_key,fn){
  const next=queue.then(fn);queue=next.catch(()=>{});return next;
}}}});
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const key='test-quota';
function browser(){
  const events=[];
  const parentElement={};
  return {events,update(request_id=null){
    render({parentElement,data:{storage_key:key,request_id},setStateValue:(_key,value)=>events.push(value)});
  },get last(){return events.at(-1);}};
}

const tab=browser();tab.update();await tick();
assert.equal(tab.last.used,0);
for(let i=1;i<=5;i++){
  tab.update('question-'+i);await tick();
  assert.equal(tab.last.used,i);assert.equal(tab.last.accepted,true);
  tab.update('question-'+i);await tick();
  assert.equal(JSON.parse(saved.get(key)).used,i,'rerun must not charge twice');
}
tab.update('sixth');await tick();
assert.equal(tab.last.used,5);assert.equal(tab.last.accepted,false);
const reopened=browser();reopened.update();await tick();
assert.equal(reopened.last.used,5,'reopening must retain the quota');

saved.clear();
const tabs=Array.from({length:6},()=>browser());
tabs.forEach((t,i)=>t.update('concurrent-'+i));await tick();await queue;
assert.equal(tabs.filter(t=>t.last.accepted).length,5,'tabs must share five slots');
assert.equal(JSON.parse(saved.get(key)).used,5);

saved.set(key,'invalid json');
const corrupt=browser();corrupt.update();await tick();
assert.equal(corrupt.last.error,true);
localStorage.setItem=()=>{throw new Error('blocked');};
saved.clear();
const blocked=browser();blocked.update('blocked');await tick();
assert.equal(blocked.last.error,true);assert.equal(blocked.last.accepted,false);
console.log('Quota browser checks passed: five slots, idempotency, reopening, concurrent tabs and storage failure.');

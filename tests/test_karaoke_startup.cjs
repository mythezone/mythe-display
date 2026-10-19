const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const timers = new Map();
let nextTimer = 0;
const scope = {module:{exports:{}},URL,AbortController,console,location:{protocol:'http:',host:'localhost'},
  setTimeout(fn,delay){const id=++nextTimer;timers.set(id,{fn,delay});return id;},
  clearTimeout(id){timers.delete(id);},setInterval(){return ++nextTimer;},clearInterval(){}};
vm.createContext(scope);
vm.runInContext(fs.readFileSync('public/kiosk-test/karaoke-output.js','utf8'),scope);
const {KaraokeOutput} = scope.module.exports;
const flush = () => new Promise(setImmediate);
function fixture(fetchSnapshot, blocked=false) {
  const messages=[],sockets=[];
  const engine = {clockValid:false,uncertainty:0,context:{state:'running'},async unlock(){if(blocked)throw Error('gesture required');},
    observeClock(){this.clockValid=true;return true;},resetConnection(){},muteLease(){}};
  const audio = {paused:true,src:'',addEventListener(){},pause(){},load(){},removeAttribute(){}};
  const output = new KaraokeOutput({engine,audio,getRoom:()=>({}),continuous:true,now:()=>100,fetchSnapshot,
    onStatus:message=>messages.push(message),socketFactory:url=>{sockets.push(url);return {close(){}};}});
  return {output,messages,sockets};
}
async function fire(delay) {
  const [id,timer] = [...timers].find(([,timer])=>timer.delay===delay) || [];
  assert.ok(timer,`missing ${delay}ms timer`);timers.delete(id);timer.fn();await flush();
}
(async()=>{
  let calls=0;
  const recovered=fixture(async()=>{calls++;if(calls===1)throw Error('upstream unavailable');return {server_time:100};});
  await assert.rejects(()=>recovered.output.start());
  assert.equal(recovered.output.listening,false);assert.equal(recovered.output.startRequested,true);
  assert.match(recovered.messages.at(-1),/正在重试/);
  await fire(5000);
  assert.equal(recovered.output.listening,true);assert.equal(recovered.sockets.length,1);
  assert.equal(timers.size,0,'successful retry leaves no startup timer');recovered.output.stop();

  const stopped=fixture(async()=>{throw Error('unavailable');});
  await assert.rejects(()=>stopped.output.start());stopped.output.stop();
  assert.equal(stopped.output.startRequested,false);assert.equal(timers.size,0,'manual stop cancels automatic retries');

  const blocked=fixture(async()=>assert.fail('network before unlock'),true);
  await assert.rejects(()=>blocked.output.start());
  assert.equal(blocked.output.startRequested,false);assert.equal(timers.size,0,'blocked audio still needs a real unlock');
  assert.match(blocked.messages.at(-1),/浏览器音频/);blocked.output.stop();

  const timedOut=fixture((_,signal)=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>reject(Error('timeout')),{once:true})));
  const pending=assert.rejects(()=>timedOut.output.start());await flush();
  await fire(8000);await pending;
  assert.ok([...timers.values()].some(timer=>timer.delay===5000),'a startup timeout also retries');timedOut.output.stop();
  assert.equal(timers.size,0);

  let finish;
  const cancelled=fixture(()=>new Promise(resolve=>{finish=resolve;}));
  const starting=cancelled.output.start();await flush();cancelled.output.stop();finish({server_time:100});await starting;
  assert.equal(cancelled.sockets.length,0,'late initialization cannot restart a stopped player');assert.equal(timers.size,0);
  console.log('PASS: upstream recovery, bounded retries, timeout, unlock failure, explicit stop and late initialization');
})().catch(error=>{console.error(error);process.exitCode=1;});

const assert = require('node:assert/strict');
const {KaraokeAudio, positionAt} = require('../public/kiosk-test/karaoke-audio.js');
global.positionAt = positionAt;
global.location = {protocol:'http:',host:'localhost',origin:'http://localhost',href:'http://localhost/kiosk-test/'};
const {KaraokeOutput} = require('../public/kiosk-test/karaoke-output.js');
class Param {
  constructor() { this.value=0; this.calls=[]; }
  cancelScheduledValues(at) { this.calls.push(['cancel',at]); }
  setValueAtTime(value,at) { this.value=value; this.calls.push(['set',value,at]); }
  linearRampToValueAtTime(value,at) { this.calls.push(['ramp',value,at]); }
}
class Node {
  constructor() { this.gain=new Param(); this.stops=[]; }
  connect() {} disconnect() {} start() {} stop(at) { this.stops.push(at); }
}
class Context {
  constructor() { this.currentTime=0; this.state='running'; this.destination={}; }
  createGain() { return new Node(); } createBufferSource() { return new Node(); }
  async resume() {}
}
const flush=()=>new Promise(setImmediate);
(async()=>{
  const context=new Context(),engine=new KaraokeAudio({createContext:()=>context,now:()=>100+context.currentTime});
  engine.buffer=async()=>({});
  let pendingProgress,progressCalls=0,activeProgress=0,maxProgress=0;
  const uploads=[],sent=[],sockets=[];
  const room={status:'connected',room:{status:'open'},playback:{fileId:'song',mediaUrl:'/faio-listen/media/song'},publicOutput:{playing:true,volume:70}};
  const audio={paused:true,src:'',readyState:1,currentTime:0,addEventListener(){},load(){},pause(){this.paused=true;},removeAttribute(){this.src='';},async play(){this.paused=false;}};
  const chunks=Array.from({length:30},(_,index)=>({index,start_frame:index*40,frames:40,url:`/music/rooms/demo/karaoke/assets/a/chunk_${index}.wav`}));
  const version={version_id:'a',file_id:'song',sample_rate:10,channels:2,chunk_frames:40,duration_seconds:120,bus_gain:.6,tracks:{original:chunks,accompaniment:chunks}};
  const state={type:'state',continuous:true,instance:'fixture',revision:1,transport_revision:1,transport_token:'token-1',file_id:'song',
    status:'playing',position:1,anchor:100,duration:120,ratio:.25,server_time:100,apply_at:100,lease_until:130,can_report_progress:true,
    preview_version:'a',active_version:'a',versions:[version]};
  const output=new KaraokeOutput({engine,audio,getRoom:()=>room,continuous:true,now:()=>100+context.currentTime,
    fetchSnapshot:async ping=>({...state,ping,server_received_at:ping,server_sent_at:ping}),
    socketFactory:url=>{const ws={url,readyState:1,send(value){sent.push(JSON.parse(value));},close(){this.readyState=3;}};sockets.push(ws);return ws;},
    sendProgress:async(payload,signal)=>{progressCalls++;uploads.push(payload);activeProgress++;maxProgress=Math.max(maxProgress,activeProgress);
      try { return await new Promise((resolve,reject)=>{pendingProgress=resolve;signal.addEventListener('abort',()=>reject(Error('aborted')),{once:true});}); }
      finally { activeProgress--; }
    }});
  await output.start();const socket=sockets[0];socket.onopen();assert.match(socket.url,/mode=events/);
  socket.onmessage({data:JSON.stringify(state)});await flush();await output.process();
  const graph=engine.graph,origin=graph.origin,nodes=[...graph.nodes];assert.ok(graph);
  const lease=output.leaseUntil;
  socket.onmessage({data:JSON.stringify({type:'notice',message:'fixture'})});
  assert.equal(output.continuous,true,'unrelated events cannot select the legacy report protocol');
  assert.equal(output.leaseUntil,lease,'an unrelated event cannot extend a lease');
  const denied={...state,versions:[],preview_version:'',lease_until:100};delete denied.continuous;
  socket.onmessage({data:JSON.stringify(denied)});await flush();
  assert.equal(output.continuous,true,'an access-limited state without a continuous flag is still an event');
  assert.equal(output.stateIsFresh(),false);assert.equal(engine.gate.gain.value,0,'access-limited state must mute');
  socket.onmessage({data:JSON.stringify(state)});await flush();
  assert.equal(output.stateIsFresh(),true);assert.equal(engine.graph,graph,'valid state resumes without rebuilding the source clock');
  // Reproduce a slow database/progress path. Its latency cannot revoke a 30s event lease.
  for(let second=1;second<=8;second++){
    context.currentTime=second;output.localTick();await flush();
    assert.equal(output.stateIsFresh(),true);assert.equal(engine.graph,graph);assert.equal(graph.origin,origin);
    assert.ok(nodes.every(node=>node.stops.length===0));assert.equal(engine.gate.gain.calls.at(-2)[1],.7);
  }
  assert.equal(progressCalls,1);assert.equal(maxProgress,1);assert.equal(output.reportInFlight,false);
  assert.ok(engine.gate.gain.calls.some(call=>call[0]==='set'&&call[1]===0&&call[2]===30),'audio clock retains the server expiry');
  pendingProgress();await flush();
  context.currentTime=10;output.report();output.localTick();await flush();
  assert.deepEqual(sent.at(-1),{ping:110});assert.equal(progressCalls,2);
  socket.onmessage({data:JSON.stringify({type:'heartbeat',lease_until:140})});await flush();
  assert.equal(engine.graph,graph);assert.equal(graph.origin,origin);
  socket.onmessage({data:JSON.stringify({...state,revision:2,position:100,ratio:.5,lease_until:140})});await flush();
  assert.equal(engine.graph,graph);assert.equal(graph.origin,origin,'metadata and mix events preserve the source clock');
  assert.equal(graph.x.gain.calls.at(-1)[1],.3);
  // End while an upload is pending: serialize it, then send actual ended immediately.
  context.currentTime=origin+120;
  output.finished(graph.playbackKey);assert.equal(engine.graph,null);assert.equal(progressCalls,2);
  pendingProgress();await flush();assert.equal(progressCalls,3);assert.equal(uploads.at(-1).playback_status,'ended');
  assert.equal(uploads.at(-1).position_seconds,120);assert.equal(maxProgress,1);
  const heartbeats=sent.length;pendingProgress({advanced:true});await flush();
  assert.equal(sent.length,heartbeats+1,'an accepted natural end requests the next track immediately');
  output.stop();await flush();

  const expiryEngine=new KaraokeAudio({createContext:()=>new Context(),now:()=>100});await expiryEngine.unlock();
  expiryEngine.observeClock(100,100,100);expiryEngine.buffer=async()=>({});
  let clock=100;
  const expiry=new KaraokeOutput({engine:expiryEngine,audio,getRoom:()=>room,continuous:true,now:()=>clock});
  expiry.listening=true;expiry.socket={readyState:1,close(){}};expiry.receiveContinuous({...state,can_report_progress:false});await flush();
  assert.equal(expiry.stateIsFresh(),true);
  expiryEngine.now=()=>131;clock=131;expiry.localTick();
  assert.equal(expiry.stateIsFresh(),false);assert.equal(expiryEngine.gate.gain.value,0,'an actually expired server lease still mutes');
  expiryEngine.now=()=>100;clock=100;expiry.receiveContinuous({...state,can_report_progress:false});await flush();
  expiry.fail('Access denied');assert.equal(expiryEngine.gate.gain.value,0,'connection/permission failure immediately mutes');expiry.stop();
  const rawEngine=new KaraokeAudio({createContext:()=>new Context(),now:()=>100});await rawEngine.unlock();rawEngine.observeClock(100,100,100);
  const raw=new KaraokeOutput({engine:rawEngine,audio,getRoom:()=>room,continuous:true,now:()=>100});
  raw.listening=true;raw.socket={readyState:1,close(){}};
  raw.receiveContinuous({...state,preview_version:'',active_version:null,can_report_progress:false});await flush();
  assert.equal(audio.paused,false);assert.equal(rawEngine.graph,null,'normal listening uses the original media');
  rawEngine.now=()=>104;raw.localTick();await flush();assert.equal(audio.paused,false,'slow confirmation does not interrupt original media');
  rawEngine.now=()=>131;raw.localTick();assert.equal(audio.paused,true,'expired event leases stop original media as well');raw.stop();
  let calibrationClock=100,calibrations=0;
  const retryEngine=new KaraokeAudio({createContext:()=>new Context(),now:()=>calibrationClock});
  const retry=new KaraokeOutput({engine:retryEngine,audio,getRoom:()=>room,continuous:true,now:()=>calibrationClock,
    fetchSnapshot:async ping=>{calibrations++;if(calibrations===1){calibrationClock++;return {...state,server_time:ping+.5};}
      return {...state,server_time:ping,server_received_at:ping,server_sent_at:ping};},
    socketFactory:()=>({readyState:1,close(){}})});
  await retry.start();assert.equal(calibrations,2,'a delayed startup sample is retried before playback');assert.equal(retryEngine.uncertainty,0);retry.stop();
  const fallbackEngine=new KaraokeAudio({createContext:()=>new Context(),now:()=>100});await fallbackEngine.unlock();fallbackEngine.observeClock(100,100,100);
  const fallbackSockets=[];
  const fallback=new KaraokeOutput({engine:fallbackEngine,audio,getRoom:()=>room,continuous:true,now:()=>100,
    socketFactory:url=>{const ws={url,readyState:1,send(){},close(){}};fallbackSockets.push(ws);return ws;}});
  fallback.listening=true;fallback.connect();fallbackSockets[0].onopen();
  const legacy={...state,ping:100};delete legacy.type;delete legacy.continuous;
  fallbackSockets[0].onmessage({data:JSON.stringify(legacy)});
  assert.equal(fallback.continuous,false,'a real untyped legacy snapshot retains old-server compatibility');
  fallbackSockets[0].onclose({code:1006});fallback.connect();
  assert.equal(fallback.continuous,true,'reconnect retries the configured continuous channel');
  assert.match(fallbackSockets.at(-1).url,/mode=events/);fallback.stop();
  console.log('PASS: continuous lease, slow isolated progress, single upload, heartbeats, stable clock/mix, natural end, expiry and disconnect');
})().catch(error=>{console.error(error);process.exitCode=1;});

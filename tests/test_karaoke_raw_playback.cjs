const assert = require('node:assert/strict');
global.location = {protocol:'http:',host:'localhost',origin:'http://localhost',href:'http://localhost/kiosk-test/'};
global.positionAt = require('../public/kiosk-test/karaoke-audio.js').positionAt;
const {KaraokeOutput} = require('../public/kiosk-test/karaoke-output.js');
const flush = () => new Promise(setImmediate);

(async () => {
  let now = 100;
  const listeners = {};
  const audio = {src:'',readyState:0,currentTime:0,paused:true,loads:0,plays:0,
    addEventListener(name,fn){listeners[name]=fn;},
    load(){this.loads++;this.readyState=0;this.currentTime=0;this.paused=true;},
    pause(){this.paused=true;},removeAttribute(){this.src='';},
    async play(){this.plays++;this.paused=false;}};
  const engine = {graph:null,clockValid:true,context:{state:'running'},serverNow:()=>now,localPosition:()=>null,
    silence(){},muteLease(){},setVolume(){},resetConnection(){},validate(){return true;}};
  const room = {status:'connected',room:{status:'open'},playback:{fileId:'song',mediaUrl:'/faio-listen/media/song?v=1'},publicOutput:{playing:true,volume:70}};
  const output = new KaraokeOutput({engine,audio,getRoom:()=>room,continuous:true,now:()=>now});
  output.listening=true;output.protocol=2;output.socket={readyState:1,close(){}};output.ackAuthorized=true;output.leaseUntil=1000;
  const state = {type:'state',instance:'fixture',transport_token:'first',transport_revision:1,revision:1,
    file_id:'song',position:45,anchor:100,duration:240,status:'playing',lease_until:1000,
    active_version:null,preview_version:'',pending:null,versions:[]};
  output.latest=state;
  await output.process();
  assert.equal(audio.loads,1);
  assert.equal(audio.paused,true,'wait for metadata and the initial seek before audible playback');
  now=102;
  output.receiveContinuous({...state});await flush();
  audio.readyState=1;listeners.loadedmetadata();await flush();
  assert.equal(audio.currentTime,47,'joining an existing song must start at the current position');
  assert.equal(audio.paused,false);
  audio.currentTime=63;
  const loads=audio.loads;
  for(let revision=2;revision<20;revision++){
    room.playback.mediaUrl='/faio-listen/media/song?v='+revision;
    output.roomChanged();await flush();
    assert.equal(audio.loads,loads,'passive cache-busting revisions must not reload buffered media');
    assert.equal(audio.currentTime,63,'room refresh cannot rewind the current song');
  }
  // Explicit transport changes still seek once, after the new metadata is ready.
  now=103;output.latest={...state,transport_token:'seek',transport_revision:2,position:90,anchor:103};
  await output.process();assert.equal(audio.loads,loads+1);assert.equal(audio.paused,true);
  audio.readyState=1;listeners.loadedmetadata();await flush();
  assert.equal(audio.currentTime,90);assert.equal(audio.paused,false);
  output.latest={...state,transport_token:'stopped',transport_revision:3,position:120};
  await output.process();output.stop();audio.readyState=1;listeners.loadedmetadata();await flush();
  assert.equal(audio.paused,true,'late metadata cannot resume a stopped player');
  assert.equal(audio.src,'');assert.equal(output.rawSeek,null);
  console.log('PASS: delayed metadata, join position, repeated room revisions, explicit seek, stop and late callbacks');
})().catch(error=>{console.error(error);process.exitCode=1;});

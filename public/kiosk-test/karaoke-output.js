/* Opt-in output owner. Playback observations never issue room commands. */
(function(root){
'use strict';
class KaraokeOutput {
  constructor({engine,audio,getRoom,onState=()=>{},onStatus=()=>{},onRoom=()=>{},socketFactory=url=>new WebSocket(url),now=()=>performance.now()/1000,continuous=false,fetchSnapshot=async(ping,signal)=>{
    const response=await fetch('/faio-listen/karaoke/snapshot?ping='+ping+'&continuous=true',{cache:'no-store',signal});
    if(!response.ok)throw Error('播放时钟暂不可用');return response.json();
  },sendProgress=async(payload,signal)=>{
    const response=await fetch('/faio-listen/playback-progress',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload),signal});
    if(!response.ok)throw Error('播放进度暂不可用');return response.json();
  },fetchState=async signal=>{
    const response=await fetch('/faio-listen/state',{cache:'no-store',signal});
    if(!response.ok)throw Error('歌曲状态暂不可用');return response.json();
  }}) {
    Object.assign(this,{engine,audio,getRoom,onState,onStatus,onRoom,socketFactory,now});
    this.socket=null;this.latest=null;this.listening=false;this.processing=false;this.timer=null;this.retry=null;this.sequence=0;this.received=0;this.reportInFlight=false;this.reportSentAt=0;this.rawKey='';this.endedKey='';
    this.fetchState=fetchState;this.idleTimer=null;this.authorityAbort=null;this.authorityRoom=null;this.authorityReceived=0;
    this.protocol=1;this.reportSeq=0;this.expectedReportSeq=0;this.controlAck=-1;this.initializedV2=false;
    this.ackReceived=0;this.ackAuthorized=false;this.leaseUntil=0;this.tickTimer=null;this.endedPosition=0;
    this.publicOutput=null;this.uiLastAt=-Infinity;this.trace={v1Reports:0,v2Reports:0,acks:0,controls:0,initials:0,authorityGets:0};
    this.preferContinuous=continuous;this.continuous=continuous;this.fetchSnapshot=fetchSnapshot;this.sendProgress=sendProgress;
    this.progressAbort=null;this.progressAgain=false;this.progressSeq=0;this.progressLastAt=-Infinity;this.startAbort=null;
    this.engine.onBuffered=()=>{if(this.listening)void this.process();};
    this.engine.onEnded=key=>this.finished(key);
    this.audio.addEventListener?.('ended',()=>{if(this.audio.ended)this.finished(this.rawKey);});
  }
  playbackKey(state){return `${state.instance}:${state.transport_token||state.transport_revision}:${state.file_id}`;}
  get isPlayingLocally(){return this.protocol===2 && !!this.latest && this.latest.status==='playing' && this.playbackKey(this.latest)!==this.endedKey && (!!this.engine.graph || this.audio.paused===false);}
  localProgress(){
    if(this.latest && this.playbackKey(this.latest)===this.endedKey)return {position_seconds:this.endedPosition,playback_status:'ended'};
    const position=this.engine.localPosition?.();
    if(position!==null && typeof position!=='undefined')return {position_seconds:position,playback_status:this.latest?.status==='paused'?'paused':'playing'};
    if(this.audio.getAttribute?.('src') || this.audio.src)return {position_seconds:Number.isFinite(this.audio.currentTime)?this.audio.currentTime:0,playback_status:this.audio.ended?'ended':this.audio.paused?'paused':'playing'};
    return {position_seconds:Math.max(0,Number(this.latest?.position)||0),playback_status:this.latest?.status==='paused'?'paused':'idle'};
  }
  finished(key){
    if(!this.listening || !key || key===this.endedKey)return;
    this.endedPosition=this.localProgress().position_seconds;
    this.endedKey=key;this.engine.silence();this.stopRaw();this.report();
    void this.refreshAuthority();this.idlePoll(true);
  }
  idlePoll(idle){
    if(!idle){clearTimeout(this.idleTimer);this.idleTimer=null;return;}
    if(!this.listening || this.idleTimer)return;
    this.idleTimer=setTimeout(()=>{this.idleTimer=null;void this.refreshAuthority();},10000);
  }
  async refreshAuthority(){
    if(!this.listening || this.authorityAbort)return;
    const abort=this.authorityAbort=new AbortController(),sequence=this.sequence;
    const timeout=setTimeout(()=>abort.abort(),8000);
    try{
      this.trace.authorityGets++;
      const room=await this.fetchState(abort.signal);
      if(abort.signal.aborted || sequence!==this.sequence || !this.listening)return;
      if(this.engine.graph || this.audio.paused===false)return;
      const old=Date.parse(this.authorityRoom?.generatedAt||''),next=Date.parse(room?.generatedAt||'');
      if(!Number.isFinite(old) || !Number.isFinite(next) || next>=old){this.authorityRoom=room;this.authorityReceived=this.now();this.onRoom(room);}
      await this.process();
    }catch{/* Keep ended fence and retry only while idle; never replay. */}
    finally{clearTimeout(timeout);if(this.authorityAbort===abort)this.authorityAbort=null;this.idlePoll(!this.engine.graph && this.audio.paused!==false);}
  }
  currentRoom(){
    const room=this.getRoom(),fresh=this.authorityRoom && this.now()-this.authorityReceived<=10;
    const cacheTime=Date.parse(room?.generatedAt||''),authorityTime=Date.parse(this.authorityRoom?.generatedAt||'');
    return fresh && (!Number.isFinite(cacheTime) || authorityTime>=cacheTime)?this.authorityRoom:room;
  }
  stopRaw(){if(this.audio.paused && !this.audio.src)return;this.audio.pause();this.audio.removeAttribute('src');this.audio.load();}
  async start(){
    if(this.listening || this.startAbort)return;
    const abort=this.startAbort=new AbortController(),timeout=setTimeout(()=>abort.abort(),8000);
    try{
      await this.engine.unlock();
      if(this.continuous){
        for(let attempt=0;attempt<3;attempt++){
          const ping=this.now(),snapshot=await this.fetchSnapshot(ping,abort.signal);
          if(abort.signal.aborted)return;
          if(this.engine.observeClock(snapshot.server_time,ping,this.now(),snapshot,ping) && this.engine.uncertainty<=.1)break;
          this.engine.resetConnection();
        }
        if(!this.engine.clockValid)throw Error('播放时钟暂不可用');
      }
      if(abort.signal.aborted)return;
      this.listening=true;this.connect();
    }finally{clearTimeout(timeout);if(this.startAbort===abort)this.startAbort=null;}
  }
  connect(){
    if(!this.listening)return;
    this.continuous=this.preferContinuous;
    this.authorityAbort?.abort();this.authorityAbort=null;
    if(this.protocol===2 || this.continuous){this.engine.muteLease();this.audio.pause();}
    else{this.engine.resetConnection();this.stopRaw();this.latest=null;}
    this.ackAuthorized=false;this.initializedV2=false;this.reportSeq=0;this.reportInFlight=false;this.sequence++;
    const sequence=this.sequence, id=this.clientId='display_'+Math.random().toString(36).slice(2);
    const protocol=location.protocol==='https:'?'wss:':'ws:';
    const socket=this.socket=this.socketFactory(`${protocol}//${location.host}/faio-listen/karaoke/ws?client_id=${id}${this.continuous?'&mode=events':''}`);
    socket.onopen=()=>{if(sequence!==this.sequence)return;this.onStatus('本机音频已开启 · 同步中');this.timer=setInterval(()=>this.report(),this.continuous?10000:500);this.report();};
    socket.onmessage=event=>{
      if(sequence!==this.sequence)return;
      const expectedPing=this.reportInFlight?this.reportSentAt:NaN;
      try {
        const state=JSON.parse(event.data);
        if(state.type==='connection_error') {
          this.fail(state.error_code==='upstream_unavailable'?'上游暂不可用 · 已静音':'连接故障 · 已静音');
          socket.close();return;
        }
        if(this.continuous){
          if(state.type==='state' || state.type==='heartbeat'){this.receiveContinuous(state);return;}
          if(state.type!==undefined || !this.engine.validate(state))return;
          // Only an untyped legacy snapshot proves mode=events was ignored.
          this.continuous=false;clearInterval(this.timer);this.timer=setInterval(()=>this.report(),500);
        }
        if(this.protocol===2){this.receiveV2(state,expectedPing);return;}
        this.reportInFlight=false;
        if(!this.engine.validate(state))throw Error('无效音频状态');
        if(this.latest&&state.instance===this.latest.instance&&(state.transport_revision<this.latest.transport_revision||state.revision<this.latest.revision))return;
        state.versions=state.versions.map(v=>({...v,tracks:Object.fromEntries(['original','accompaniment'].map(role=>[role,(v.tracks?.[role]||[]).map(c=>{
          const path=new URL(c.url,location.href).pathname;
          const match=path.match(/^\/music\/rooms\/[^/]+\/karaoke\/assets\/([A-Za-z0-9_-]{1,100})\/([A-Za-z0-9_-]{1,100}\.wav)$/);
          if(!match||match[1]!==v.version_id)throw Error('无效音频地址');
          return {...c,url:`/faio-listen/karaoke/assets/${match[1]}/${match[2]}`};
        })])) }));
        const clockAccepted=this.engine.observeClock(state.server_time,state.ping,this.now(),state,expectedPing);
        if(!clockAccepted){
          this.engine.silence();this.stopRaw();this.latest=state;this.received=this.now();this.onState(state);
          this.onStatus('时钟数据校验失败 · 已静音');return;
        }
        if(this.latest&&(state.instance!==this.latest.instance||state.transport_revision!==this.latest.transport_revision||state.file_id!==this.latest.file_id)) {this.engine.silence();this.stopRaw();}
        if(state.lease_until<=this.engine.serverNow())this.engine.muteLease();
        this.latest=state;this.received=this.now();this.onState(state);void this.process();
        if(state.report_protocols?.includes(2) && typeof state.transport_token==='string' && state.transport_token){
          this.protocol=2;this.ackAuthorized=false;this.publicOutput={...(this.getRoom()?.publicOutput||{})};
          if(!this.tickTimer)this.tickTimer=setInterval(()=>this.localTick(),200);
        }
      }catch{this.fail('音频状态校验失败 · 已静音');socket.close();}
    };
    socket.onclose=event=>{if(sequence!==this.sequence)return;if(event.code===4400 && this.protocol===2){this.protocol=1;this.initializedV2=false;clearInterval(this.tickTimer);this.tickTimer=null;}this.fail(event.code===4401?'身份已失效 · 已静音':event.code===4403?'访问被拒绝 · 已静音':'连接中断 · 已静音');this.retry=setTimeout(()=>this.connect(),2000);};
    socket.onerror=()=>{if(sequence===this.sequence)this.fail('连接中断 · 已静音');};
  }
  fail(message){
    this.ackAuthorized=false;
    if(this.protocol===2 || this.continuous){this.engine.muteLease();this.audio.pause();}else{this.engine.resetConnection();this.stopRaw();this.latest=null;}
    this.reportInFlight=false;clearInterval(this.timer);this.timer=null;this.onStatus(message);
  }
  mapState(state){
    if(!this.engine.validate(state))throw Error('无效音频状态');
    return {...state,versions:state.versions.map(v=>({...v,tracks:Object.fromEntries(['original','accompaniment'].map(role=>[role,(v.tracks?.[role]||[]).map(c=>{
      const path=new URL(c.url,location.href).pathname,match=path.match(/^\/music\/rooms\/[^/]+\/karaoke\/assets\/([A-Za-z0-9_-]{1,100})\/([A-Za-z0-9_-]{1,100}\.wav)$/);
      if(!match||match[1]!==v.version_id)throw Error('无效音频地址');return {...c,url:`/faio-listen/karaoke/assets/${match[1]}/${match[2]}`};
    })]))}))};
  }
  receiveContinuous(message){
    if(!Number.isFinite(message.lease_until))throw Error('无效播放期限');
    if(message.type==='state'){
      const state=this.mapState(message),previous=this.latest;
      if(previous && state.instance===previous.instance && (state.transport_revision<previous.transport_revision || state.revision<previous.revision))return;
      const same=previous && this.playbackKey(state)===this.playbackKey(previous);
      if(same && (this.engine.graph || this.audio.src)){
        state.position=this.localProgress().position_seconds;state.anchor=this.engine.serverNow();
      }
      if(!same){this.engine.silence();this.stopRaw();}
      this.protocol=2;this.latest={...state,_localClock:true};
      this.publicOutput={...(this.getRoom()?.publicOutput||{})};
      this.onState(this.latest);
      if(String(this.getRoom()?.playback?.fileId)!==String(state.file_id))void this.refreshAuthority();
      if(!this.tickTimer)this.tickTimer=setInterval(()=>this.localTick(),200);
    }
    this.ackReceived=this.now();this.ackAuthorized=!!this.latest;this.leaseUntil=message.lease_until;
    void this.process();
  }
  async reportProgress(immediate=false){
    if(!this.listening || !this.latest?.can_report_progress)return;
    if(this.progressAbort){this.progressAgain=this.progressAgain||immediate;return;}
    const abort=this.progressAbort=new AbortController(),sequence=this.sequence;
    const timeout=setTimeout(()=>abort.abort(),8000);
    try{
      const state=this.latest;
      const result=await this.sendProgress({protocol:2,client_id:this.clientId,report_seq:++this.progressSeq,instance:state.instance,
        transport_token:state.transport_token,...this.localProgress()},abort.signal);
      if(result?.advanced && sequence===this.sequence && this.listening && this.socket?.readyState===1)this.socket.send(JSON.stringify({ping:this.now()}));
    }catch{/* Progress telemetry cannot interrupt an authenticated audio lease. */}
    finally{
      clearTimeout(timeout);if(this.progressAbort===abort)this.progressAbort=null;
      if(this.progressAgain && this.listening && sequence===this.sequence){this.progressAgain=false;void this.reportProgress();}
    }
  }
  receiveV2(message,expectedPing){
    if(message.type==='report_result'){
      for(const event of message.events||[])this.receiveV2(event,expectedPing);
      this.receiveV2(message.ack,expectedPing);return;
    }
    if(message.protocol!==2)return; // Passive/legacy metadata cannot control v2 audio.
    if(message.type==='initial' || message.type==='control'){
      if(!Number.isInteger(message.control_seq) || message.control_seq<0)throw Error('无效控制序号');
      if(message.type==='control' && message.control_seq<=this.controlAck)return;
      const state=this.mapState(message.snapshot);
      if(typeof state.transport_token!=='string' || !state.transport_token)throw Error('无效播放代次');
      const same=this.latest && this.playbackKey(state)===this.playbackKey(this.latest);
      if(message.type==='initial' && this.initializedV2)return;
      if(message.type==='initial'){
        this.trace.initials++;this.initializedV2=true;
        if(this.latest && message.control_seq<this.controlAck)return;
        // Preserve a reconnecting graph's source clock and mix for the same token.
        if(same && this.engine.graph && this.latest.preview_version===state.preview_version){state.position=this.latest.position;state.anchor=this.latest.anchor;state.ratio=this.latest.ratio;state.active_version=this.latest.active_version;}
      }else{
        if(!['transport','version','mix'].includes(message.action))throw Error('无效控制动作');
        if(message.action==='mix' && (!same || state.preview_version!==this.latest?.preview_version))throw Error('混音代次不匹配');
        if(message.action==='version' && same && this.engine.graph){state.position=this.engine.localPosition();state.anchor=this.engine.serverNow();}
        this.trace.controls++;
      }
      if(!same){this.engine.silence();this.stopRaw();this.ackAuthorized=false;}
      this.latest={...state,_localClock:true,pending:null};this.controlAck=message.control_seq;this.onState(this.latest);
      if(message.type==='control' && message.action==='transport' && String(this.getRoom()?.playback?.fileId)!==String(state.file_id))void this.refreshAuthority();
      void this.process();return;
    }
    if(message.type!=='report_ack')return;
    if(!this.reportInFlight || message.report_seq!==this.expectedReportSeq || message.ping!==expectedPing)return;
    const {server_received_at:t2,server_sent_at:t3}=message;
    const elapsed=this.now()-expectedPing;
    if(![t2,t3,message.lease_until].every(Number.isFinite) || t3<t2 || elapsed<0)throw Error('无效确认时间');
    this.reportInFlight=false;this.trace.acks++;
    // Calibrate at bootstrap only; ACK clock samples never move an owned origin.
    if(!this.engine.clockValid && !this.engine.observeClock(t3,expectedPing,this.now(),message,expectedPing))throw Error('初始时钟无效');
    this.ackReceived=this.now();this.ackAuthorized=this.initializedV2 && message.transport_token===this.latest?.transport_token;
    this.leaseUntil=message.lease_until;
    if(!this.ackAuthorized || this.leaseUntil<=this.engine.serverNow())this.engine.muteLease();
    void this.process();
  }
  localTick(){
    if(this.protocol!==2 || !this.listening || !this.latest)return;
    if(!this.stateIsFresh()){this.engine.muteLease();this.audio.pause();return;}
    void this.process();
    if(this.continuous && this.now()-this.progressLastAt>=2){this.progressLastAt=this.now();void this.reportProgress();}
    const progress=this.localProgress(),time=this.engine.serverNow();
    if(this.now()-this.uiLastAt>=1){this.uiLastAt=this.now();this.onState({...this.latest,position:progress.position_seconds,anchor:time,server_time:time});}
  }
  stateIsFresh(){
    if(this.continuous)return !!(this.latest && this.socket?.readyState===1 && this.ackAuthorized && this.engine.clockValid && this.leaseUntil>this.engine.serverNow());
    if(this.protocol===2)return !!(this.latest && this.socket?.readyState===1 && this.ackAuthorized && this.engine.clockValid && this.now()-this.ackReceived<=2);
    return !!(this.latest&&this.engine.clockValid&&this.now()-this.received<=2&&this.engine.serverNow()-this.latest.server_time<=2);
  }
  report(){
    if(!this.socket||this.socket.readyState!==1)return;
    if(this.continuous){this.socket.send(JSON.stringify({ping:this.now()}));void this.reportProgress(true);return;}
    if(this.latest&&!this.stateIsFresh()){if(this.protocol===2){this.engine.muteLease();this.audio.pause();}else{this.engine.silence();this.stopRaw();}this.onStatus('状态超时 · 已静音');}
    if(this.reportInFlight){
      if(this.now()-this.reportSentAt>4){this.engine.muteLease();this.audio.pause();this.socket.close();}
      return;
    }
    const fresh=this.stateIsFresh();
    this.reportInFlight=true;this.reportSentAt=this.now();
    const report={...this.engine.readiness,listening:!!(fresh&&this.listening),unlocked:this.engine.enabled&&this.engine.context?.state==='running',uncertainty:this.engine.uncertainty,state_revision:this.latest?.revision??-1,ping:this.reportSentAt};
    if(this.protocol===2){this.trace.v2Reports++;this.expectedReportSeq=++this.reportSeq;Object.assign(report,{protocol:2,report_seq:this.reportSeq,instance:this.latest?.instance||'',transport_token:this.latest?.transport_token||'',...this.localProgress(),control_ack:this.controlAck});}
    else this.trace.v1Reports++;
    this.socket.send(JSON.stringify(report));
  }
  async process(){
    if(this.processing)return;this.processing=true;
    try{
      let state;
      do{
        state=this.latest;if(!state)break;
        if(this.protocol===2){
          if(!this.stateIsFresh()){this.engine.muteLease();this.audio.pause();break;}
          state={...state,lease_until:this.leaseUntil};
        }
        const room=this.currentRoom(), playback=room?.playback||{}, output=room?.publicOutput||{};
        const currentOutput=this.protocol===2?this.publicOutput||output:output;
        const allowed=this.listening&&this.stateIsFresh()&&(this.protocol===2 || (room?.status==='connected'&&room?.room?.status!=='closed'))&&String(playback.fileId)===String(state.file_id)&&currentOutput.playing!==false;
        this.engine.setVolume(currentOutput.volume??70);
        if(!allowed){this.engine.silence();this.stopRaw();
          this.onStatus(room?.status!=='connected'?'房间连接中断 · 已静音':output.playing===false?'公共音响已暂停':!state.file_id?'已连接 · 等待歌曲':'已连接 · 等待歌曲状态');break;}
        if(this.playbackKey(state)===this.endedKey){this.engine.silence();this.stopRaw();this.onStatus('本曲已结束 · 等待下一首');break;}
        if(!state.active_version&&!state.preview_version&&!state.pending){
          this.engine.silence();
          // Ordinary source is allowed only after an authenticated normal WS state.
          const url=new URL(playback.mediaUrl||'',location.href);
          if(!playback.mediaUrl||url.origin!==location.origin||!url.pathname.startsWith('/faio-listen/')){this.stopRaw();this.onStatus('已连接 · 等待可播放曲目');break;}
          const key=this.playbackKey(state);
          if(key===this.endedKey){this.audio.pause();break;}
          const changed=key!==this.rawKey||this.audio.src!==url.href;
          if(changed){this.rawKey=key;this.endedKey='';this.audio.src=url.href;this.audio.load();}
          const position=root.positionAt(state,this.engine.serverNow());
          if(changed&&this.audio.readyState>0)this.audio.currentTime=position;
          this.audio.volume=Math.max(0,Math.min(1,(currentOutput.volume??70)/100));
          if(state.status==='playing'){if(this.audio.paused!==false)await this.audio.play();}else this.audio.pause();
          this.onStatus(state.status==='playing'?'本机音频 · 原唱':'已连接 · 播放暂停');
        }else{
          this.stopRaw();await this.engine.sync(state,true);
          this.onStatus(this.engine.uncertainty>.1?'时钟同步精度不足 · 已静音':state.status==='paused'?'已连接 · 播放暂停':state.lease_until>this.engine.serverNow()&&this.engine.readiness.output_version?'本机音频 · 双轨已同步':this.engine.prefetchError||'等待音频缓冲与输出租约');
        }
      }while(this.protocol!==2 && state!==this.latest);
    }catch{this.engine.silence();this.stopRaw();this.onStatus('双轨读取失败 · 已静音');}
    finally{this.processing=false;this.idlePoll(!this.engine.graph && this.audio.paused!==false);}
  }
  roomChanged(){
    if(this.protocol===2){const output=this.getRoom()?.publicOutput;if(output && Number(output.revision)>Number(this.publicOutput?.revision??-1))this.publicOutput={...output};}
    if(this.latest)void this.process();
  }
  stop(){this.listening=false;this.sequence++;this.startAbort?.abort();this.progressAbort?.abort();this.progressAgain=false;clearInterval(this.timer);clearInterval(this.tickTimer);this.tickTimer=null;clearTimeout(this.retry);clearTimeout(this.idleTimer);this.idleTimer=null;this.authorityAbort?.abort();this.socket?.close();this.socket=null;this.fail('本机音频已关闭');this.engine.resetConnection();this.stopRaw();}
}
if(typeof module!=='undefined'&&module.exports)module.exports={KaraokeOutput};else root.KaraokeOutput=KaraokeOutput;
})(typeof globalThis!=='undefined'?globalThis:window);

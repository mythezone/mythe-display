/* Shared-clock PCM output adapted to FAIO's v6 chunk/lease contract.
 * This engine never requests room transport or mix changes. */
(function (root) {
  'use strict';
  const clamp = (n, lo, hi) => Math.max(lo, Math.min(hi, n));
  const positionAt = (s, now) => clamp(s.position + (s.status === 'playing' ? Math.max(0, now - s.anchor) : 0), 0, s.duration);
  function readPcm(bytes, rate, frames) {
    const view = new DataView(bytes);
    const tag = at => String.fromCharCode(...new Uint8Array(bytes, at, 4));
    if (bytes.byteLength < 44 || tag(0) !== 'RIFF' || tag(8) !== 'WAVE') throw Error('无效音频片段');
    let format = false, offset = -1, count = 0;
    for (let at = 12; at + 8 <= bytes.byteLength;) {
      const kind = tag(at), size = view.getUint32(at + 4, true), start = at + 8;
      if (start + size > bytes.byteLength) throw Error('音频片段不完整');
      if (kind === 'fmt ') {
        if (size < 16 || view.getUint16(start, true) !== 3 || view.getUint16(start + 2, true) !== 2 || view.getUint32(start + 4, true) !== rate || view.getUint16(start + 14, true) !== 32) throw Error('双轨格式不一致');
        format = true;
      }
      if (kind === 'data') { offset = start; count = size / 8; }
      at = start + size + size % 2;
    }
    if (!format || offset < 0 || count !== frames) throw Error('双轨帧数不一致');
    const channels = [new Float32Array(frames), new Float32Array(frames)];
    for (let i = 0; i < frames; i++) for (let c = 0; c < 2; c++) {
      const sample = view.getFloat32(offset + i * 8 + c * 4, true);
      if (!Number.isFinite(sample)) throw Error('无效音频样本');
      channels[c][i] = sample;
    }
    return channels;
  }
  const emptyReadiness = () => ({ready_version:'', buffer_start:0, buffer_end:0, ack_generation:-1, output_version:'', output_start:0, output_end:0});
  class KaraokeAudio {
    constructor(options = {}) {
      this.createContext = options.createContext || (() => new AudioContext());
      this.fetch = options.fetch || ((url, init) => fetch(url, init));
      this.digest = options.digest || (bytes => crypto.subtle.digest('SHA-256', bytes));
      this.now = options.now || (() => performance.now() / 1000);
      this.context = null; this.gate = null; this.graph = null;
      this.cache = new Map(); this.loading = new Map();
      this.offset = 0; this.bestRtt = Infinity; this.clockValid = false; this.lastClockSample = null; this.lastClockRejection = ""; this.enabled = false;
      this.epoch = 0; this.state = null; this.fence = ''; this.revision = -1;
      this.readiness = emptyReadiness(); this.volume = 1;
      this.prefetches = new Map(); this.retryAfter = new Map(); this.prefetchError = '';
      this.endedKey = ''; this.onBuffered = options.onBuffered || (() => {}); this.onEnded = options.onEnded || (() => {});
    }
    async unlock() {
      if (!this.context) {
        this.context = this.createContext(); this.gate = this.context.createGain();
        this.gate.gain.value = 0; this.gate.connect(this.context.destination);
      }
      await this.context.resume(); this.enabled = this.context.state === 'running';
      if (!this.enabled) throw Error('请再次点击开启本机音频');
    }
    observeClock(serverTime, ping, received = this.now(), timestamps = {}, expectedPing = ping) {
      const reject = reason => {this.clockValid=false;this.lastClockSample=null;this.lastClockRejection=reason;return false;};
      if (![serverTime,ping,received,expectedPing].every(Number.isFinite) || ping!==expectedPing || received<ping) return reject('uncorrelated_or_invalid_ping');
      const rawRtt=received-ping;
      const hasReceived=typeof timestamps.server_received_at!=='undefined';
      const hasSent=typeof timestamps.server_sent_at!=='undefined';
      let processing=0, networkRtt=rawRtt, offset=serverTime-(ping+received)/2;
      if(hasReceived||hasSent){
        if(!hasReceived||!hasSent)return reject('incomplete_server_timestamps');
        const t2=timestamps.server_received_at,t3=timestamps.server_sent_at;
        if(!Number.isFinite(t2)||!Number.isFinite(t3)||t3<t2)return reject('invalid_server_timestamp_order');
        processing=t3-t2;networkRtt=rawRtt-processing;
        if(networkRtt<0)return reject('negative_network_rtt');
        offset=((t2-ping)+(t3-received))/2;
      }
      if(!Number.isFinite(offset)||!Number.isFinite(networkRtt))return reject('invalid_clock_sample');
      if(Number.isFinite(this.bestRtt)&&Math.abs(offset-this.offset)>.25)return reject('clock_offset_jump');
      this.lastClockSample={rawRtt,processing,networkRtt,uncertainty:networkRtt/2,mode:hasReceived?'four_timestamp':'legacy'};
      this.lastClockRejection='';this.clockValid=true;
      this.bestRtt=Math.min(this.bestRtt,networkRtt);this.offset=offset;
      return true;
    }
    get uncertainty() { return this.clockValid&&this.lastClockSample ? this.lastClockSample.uncertainty : 99; }
    serverNow() { return this.now() + this.offset; }
    audioTime(serverTime) { return this.context.currentTime + serverTime - this.serverNow(); }
    playbackKey(s) {return `${s.instance}:${s.transport_token||s.transport_revision}:${s.file_id}`;}
    localPosition() {return this.graph?clamp(this.context.currentTime-this.graph.origin,0,this.graph.version.duration_seconds):null;}
    setVolume(percent) { this.volume = clamp(Number(percent) || 0, 0, 100) / 100; }
    async buffer(version, chunk) {
      const response = await this.fetch(chunk.url, {credentials:'same-origin', cache:'no-store'});
      if (!response.ok) throw Error('音频片段读取失败');
      if (response.headers.get('X-Audio-SHA256') !== chunk.sha256) throw Error('音频版本校验失败');
      const bytes = await response.arrayBuffer();
      if (bytes.byteLength > 4 * 1024 * 1024) throw Error('音频片段过大');
      const sum = Array.from(new Uint8Array(await this.digest(bytes)), b => b.toString(16).padStart(2, '0')).join('');
      if (sum !== chunk.sha256) throw Error('音频内容校验失败');
      const channels = readPcm(bytes, version.sample_rate, chunk.frames);
      const result = this.context.createBuffer(2, chunk.frames, version.sample_rate);
      channels.forEach((data, channel) => result.copyToChannel(data, channel));
      return result;
    }
    async pair(version, index) {
      const key = `${version.version_id}:${index}`;
      if (this.cache.has(key)) return this.cache.get(key);
      if (!this.loading.has(key)) {
        const original = version.tracks.original[index], accompaniment = version.tracks.accompaniment[index];
        if (!original || !accompaniment || original.index !== index || accompaniment.index !== index || original.frames !== accompaniment.frames || original.start_frame !== accompaniment.start_frame) throw Error('双轨时间轴不一致');
        const epoch = this.epoch;
        const pending = Promise.all([this.buffer(version, original), this.buffer(version, accompaniment)]).then(([x,a]) => {
          const pair = {original:x, accompaniment:a};
          if (epoch === this.epoch) {this.cache.set(key,pair);this.onBuffered();}
          return pair;
        }).finally(() => {if(this.loading.get(key)===pending)this.loading.delete(key);});
        this.loading.set(key,pending);
      }
      return this.loading.get(key);
    }
    async preload(version, position) {
      const size = version.chunk_frames / version.sample_rate;
      if (!(size >= .5) || !Number.isFinite(version.bus_gain) || version.bus_gain < 0 || version.bus_gain > 2 || version.channels !== 2 || !version.tracks?.original?.length || version.tracks.original.length !== version.tracks.accompaniment.length) throw Error('无效双轨描述');
      const first = Math.min(version.tracks.original.length-1, Math.floor(position / size));
      const last = Math.min(version.tracks.original.length-1, Math.floor((position+10) / size));
      await Promise.all(Array.from({length:last-first+1}, (_,i) => this.pair(version,first+i)));
      return {start:first*size, end:Math.min(version.duration_seconds,(last+1)*size)};
    }
    bufferedRange(version, position) {
      const size=version.chunk_frames/version.sample_rate;
      const first=Math.min(version.tracks.original.length-1,Math.floor(position/size));
      let last=first;
      while(last<version.tracks.original.length && this.cache.has(`${version.version_id}:${last}`))last++;
      return last>first ? {start:first*size,end:Math.min(version.duration_seconds,last*size)} : null;
    }
    validVersion(version) {
      return version?.channels===2 && Number.isFinite(version.sample_rate) && version.sample_rate>0 && Number.isFinite(version.chunk_frames) && version.chunk_frames/version.sample_rate>=.5 && Number.isFinite(version.bus_gain) && version.bus_gain>=0 && version.bus_gain<=2 && Number.isFinite(version.duration_seconds) && version.duration_seconds>0 && !!version.tracks?.original?.length && version.tracks.original.length===version.tracks.accompaniment?.length;
    }
    prefetch(version, position) {
      const range=this.bufferedRange(version,position);
      if(range && range.end>=Math.min(version.duration_seconds,position+10))return;
      const first=Math.floor(position/(version.chunk_frames/version.sample_rate));
      const key=`${this.epoch}:${version.version_id}:${first}`, epoch=this.epoch;
      if(this.prefetches.has(key) || (this.retryAfter.get(key)||0)>this.now())return;
      const pending=this.preload(version,position).then(()=>{
        if(epoch===this.epoch){this.retryAfter.delete(key);this.prefetchError='';this.onBuffered();}
      }).catch(()=>{
        if(epoch===this.epoch){this.prefetchError='音频片段暂未加载';this.retryAfter.set(key,this.now()+2);}
      }).finally(()=>{if(this.prefetches.get(key)===pending)this.prefetches.delete(key);});
      this.prefetches.set(key,pending);
    }
    renewLease(s) {
      if(!this.context || !this.gate)return;
      const now=this.context.currentTime, until=this.audioTime(s.lease_until);
      this.gate.gain.cancelScheduledValues(now);
      this.gate.gain.setValueAtTime(until>now?this.volume:0,now);
      if(until>now)this.gate.gain.setValueAtTime(0,until);
    }
    retire(graph, at, immediate = false) {
      const end = immediate ? at : at + .03;
      graph.output.gain.cancelScheduledValues(at);
      graph.output.gain.setValueAtTime(immediate ? 0 : 1, at);
      if (!immediate) graph.output.gain.linearRampToValueAtTime(0,end);
      for (const node of graph.nodes) { try {node.stop(end);} catch {} }
      // Nodes disconnect themselves on ended; disconnect gains without timers
      // only for immediate revocation, whose shared gate is already zero.
      if (immediate) { graph.x.disconnect(); graph.a.disconnect(); graph.output.disconnect(); }
    }
    schedule(graph, s) {
      const ctx = this.context;
      for (const chunk of graph.version.tracks.original) {
        const start = chunk.start_frame / graph.version.sample_rate;
        const end = start + chunk.frames / graph.version.sample_rate, when = graph.origin + start;
        if (graph.scheduled.has(chunk.index) || graph.origin+end <= ctx.currentTime || when > ctx.currentTime+12) continue;
        const pair = this.cache.get(`${graph.version.version_id}:${chunk.index}`);
        if (!pair) continue;
        const at = Math.max(graph.startsAt,when,ctx.currentTime+.02), offset = Math.max(0,at-when);
        if (offset >= end-start) continue;
        for (const role of ['original','accompaniment']) {
          const node = ctx.createBufferSource(); node.buffer = pair[role];
          node.connect(role === 'original' ? graph.x : graph.a); node.start(at,offset); graph.nodes.push(node);
          node.onended = () => {
            node.disconnect(); graph.nodes = graph.nodes.filter(n => n !== node);
            if(this.graph!==graph || graph.ended || graph.nodes.length || ctx.currentTime<graph.origin+graph.version.duration_seconds-.005)return;
            graph.ended=true;this.endedKey=graph.playbackKey;this.muteLease();this.readiness=emptyReadiness();this.onEnded(graph.playbackKey);
          };
        }
        graph.scheduled.add(chunk.index);
      }
      const mix=`${s.active_version?s.ratio:1}:${graph.version.bus_gain}`;
      if (graph.mix !== mix) {
        const at = s._localClock ? ctx.currentTime : Math.max(ctx.currentTime,this.audioTime(s.apply_at));
        for (const [node,ratio] of [[graph.x,s.active_version ? s.ratio : 1],[graph.a,s.active_version ? 1-s.ratio : 0]]) {
          node.gain.cancelScheduledValues(at); node.gain.setValueAtTime(node.gain.value,at);
          node.gain.linearRampToValueAtTime(ratio*graph.version.bus_gain,at+.03);
        }
        graph.mix = mix;
      }
    }
    validate(s) {
      return s && typeof s.instance === 'string' && ['revision','transport_revision','position','anchor','duration','ratio','lease_until','apply_at','server_time'].every(k=>Number.isFinite(s[k])) && ['playing','paused'].includes(s.status) && s.duration>=0 && s.position>=0 && s.revision>=0 && s.transport_revision>=0 && s.ratio>=0 && s.ratio<=1 && Array.isArray(s.versions);
    }
    async sync(s, listening = true) {
      if (!this.context || !this.enabled) return this.readiness;
      if (!listening || this.context.state !== 'running' || !this.validate(s) || this.uncertainty > .1) {this.silence();return this.readiness;}
      const fence = `${s.instance}:${s.transport_token||s.transport_revision}`;
      if (this.fence === fence && s.revision < this.revision) return this.readiness;
      if (this.state && s.instance === this.state.instance && s.transport_revision < this.state.transport_revision) return this.readiness;
      if (fence !== this.fence) {this.silence();this.fence=fence;}
      this.revision=s.revision; this.state=s;
      const version=s.versions.find(v=>v.version_id === s.preview_version);
      if (!version || version.file_id !== s.file_id || (s.active_version && version.version_id !== s.active_version)) {this.silence();return this.readiness;}
      if(!this.validVersion(version)){this.silence();throw Error('无效双轨描述');}
      const ctx=this.context;
      const key=`${fence}:${version.version_id}`;
      const playbackKey=this.playbackKey(s);
      if(this.endedKey===playbackKey){this.muteLease();this.readiness=emptyReadiness();return this.readiness;}
      if(this.graph && this.graph.key!==key)this.silence();
      if(s.status==='paused' && this.graph)this.silence();
      // The audio clock owns progress after start. Snapshots never move origin.
      const position=this.graph ? clamp(ctx.currentTime-this.graph.origin,0,version.duration_seconds) : positionAt(s,this.serverNow());
      if(!this.graph && position>=version.duration_seconds){this.endedKey=playbackKey;this.muteLease();this.readiness=emptyReadiness();this.onEnded(playbackKey);return this.readiness;}
      this.renewLease(s); // Never wait for current/pending network reads to renew.
      let range=this.bufferedRange(version,position);
      this.prefetch(version,position);
      let ready=range?{...emptyReadiness(),ready_version:version.version_id,buffer_start:range.start,buffer_end:range.end}:emptyReadiness();
      if(s.pending){
        const pending=s.versions.find(v=>v.version_id===s.pending.version_id);
        if(this.validVersion(pending) && Number.isFinite(s.pending.position) && s.pending.position>=0){
          this.prefetch(pending,s.pending.position);
          const next=this.bufferedRange(pending,s.pending.position);
          if(next && next.end>=Math.min(pending.duration_seconds,s.pending.position+10))ready={...ready,ready_version:pending.version_id,buffer_start:next.start,buffer_end:next.end,ack_generation:s.pending.generation};
        }
      }
      if(s.status==='paused'){this.muteLease();this.readiness=ready;return ready;}
      if (!this.graph && range) {
        const serverAt=Math.max(this.serverNow()+.12,s.apply_at), at=this.audioTime(serverAt), source=positionAt(s,serverAt);
        if (this.graph) this.retire(this.graph,at);
        const x=ctx.createGain(),a=ctx.createGain(),output=ctx.createGain();
        x.gain.value=(s.active_version?s.ratio:1)*version.bus_gain;
        a.gain.value=(s.active_version?1-s.ratio:0)*version.bus_gain;
        output.gain.value=0;output.gain.setValueAtTime(0,at);output.gain.linearRampToValueAtTime(1,at+.03);
        x.connect(output);a.connect(output);output.connect(this.gate);
        this.graph={key,playbackKey,version,origin:at-source,startsAt:at,scheduled:new Set(),nodes:[],x,a,output,mix:null,ended:false};
      }
      if(this.graph){
        this.schedule(this.graph,s);
        if(range && this.graph.nodes.length)ready={...ready,output_version:version.version_id,output_start:range.start,output_end:range.end};
      }
      this.readiness=ready;
      const keep=new Set([version.version_id,s.pending?.version_id]);
      for (const key of this.cache.keys()) {
        const split=key.lastIndexOf(':'),id=key.slice(0,split),index=Number(key.slice(split+1));
        const v=s.versions.find(item=>item.version_id===id), at=id===s.pending?.version_id?s.pending.position:position;
        const time=v?index*v.chunk_frames/v.sample_rate:-1;
        if (!keep.has(id) || time<at-4 || time>at+12) this.cache.delete(key);
      }
      return ready;
    }
    muteLease() {
      // Preserve real preload/readiness while awaiting a lease; gate both tracks.
      if(this.context && this.gate) {this.gate.gain.cancelScheduledValues(this.context.currentTime);this.gate.gain.setValueAtTime(0,this.context.currentTime);}
    }
    silence() {
      this.epoch++; this.readiness=emptyReadiness();
      this.prefetches.clear();this.retryAfter.clear();this.loading.clear();this.prefetchError='';
      if (this.context && this.gate) {this.gate.gain.cancelScheduledValues(this.context.currentTime);this.gate.gain.setValueAtTime(0,this.context.currentTime);}
      if (this.graph && this.context) this.retire(this.graph,this.context.currentTime,true);
      this.graph=null;
    }
    resetConnection() {this.silence();this.bestRtt=Infinity;this.clockValid=false;this.lastClockSample=null;this.lastClockRejection="";this.state=null;this.fence='';this.revision=-1;this.cache.clear();}
    dispose() {this.resetConnection();this.enabled=false;this.loading.clear();void this.context?.close();}
  }
  const exports={KaraokeAudio,readPcm,positionAt,emptyReadiness};
  if (typeof module!=='undefined' && module.exports) module.exports=exports;
  else Object.assign(root,exports);
})(typeof globalThis!=='undefined'?globalThis:window);

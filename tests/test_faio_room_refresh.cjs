const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('public/kiosk-test/index.html', 'utf8');
function source(name, asynchronous = false) {
  const start = html.indexOf(`function ${name}(`);
  assert.ok(start >= 0, name);
  return (asynchronous ? 'async ' : '') + html.slice(start, html.indexOf('\n      }', start) + 8);
}
class Element {
  constructor() {
    this.children = [];
    this.style = {};
    this.dataset = {};
    this.offsetTop = 0;
    this.offsetHeight = 40;
    this.clientHeight = 400;
  }
  replaceChildren() { this.children = []; }
  appendChild(child) { this.children.push(child); }
  removeAttribute(name) { delete this[name]; }
}

let clock = Date.parse('2026-10-10T00:00:00Z');
let lyrics = [];
let nextTimer = 0;
const timers = new Map();
const requests = [];
const nodes = Object.fromEntries(['RoomPill', 'Online', 'Title', 'Artist', 'Contributor', 'Cover', 'CoverEmpty', 'Progress', 'Elapsed', 'Duration', 'Lyrics'].map(name => [`faio${name}`, new Element()]));
function snapshot() {
  return { generatedAt: new Date(clock).toISOString(), refreshMs: 10000, status: 'connected', roomId: 'room-a',
    room: { status: 'open', name: 'Fixture room' }, source: 'faio.musicRoom',
    playback: { fileId: 'song-a', status: 'playing', positionSeconds: 150, durationSeconds: 200 },
    karaoke: { fileId: 'song-a', mode: 'karaoke', status: 'playing', positionSeconds: 150, durationSeconds: 200 },
    lyrics, publicOutput: { playing: true, volume: 70 }, queue: [] };
}
const context = { ...nodes, console, Math, Number, String, AbortController,
  Date: class extends Date { static now() { return clock; } },
  document: { createElement: () => new Element() },
  faioListen: null, faioPublicOutput: {}, browserAudioEnabled: false, karaokeOutputRequested: true,
  faioSourceUrl: '/runtime/faio-listen.json', faioFallbackUrl: './faio-listen.mock.json', faioRefreshMs: 10000,
  faioLoadTimer: null, faioLoadSequence: 0, faioLoadAbort: null, faioLoadFailures: 0,
  karaokeOutputClient: { isPlayingLocally: true, latest: { file_id: 'song-a' },
    localProgress: () => ({ position_seconds: 25, playback_status: 'playing' }), roomChanged() {} },
  renderKaraokeState() {}, renderFaioQueue() {}, syncFaioAudio() {}, formatTrackTime: String,
  setTimeout(fn, delay) { const id = ++nextTimer; timers.set(id, { fn, delay }); return id; },
  clearTimeout(id) { timers.delete(id); },
  async fetch(url) {
    requests.push(url);
    return { ok: true, json: async () => ({ ...snapshot(), lyrics: url === '/faio-listen/state' ? [] : lyrics }) };
  },
  async fetchJsonWithFallback(url) { requests.push(url); return snapshot(); }
};
context.window = context;
vm.createContext(context);
for (const name of ['desiredFaioPosition', 'renderFaioLyrics', 'renderFaioPlaybackFrame', 'renderFaioListen']) {
  vm.runInContext(source(name), context);
}
vm.runInContext(source('loadFaioListen', true), context);

(async () => {
  await context.loadFaioListen();
  assert.deepEqual(requests, ['/runtime/faio-listen.json'], 'local playback must still read display metadata');
  assert.equal(context.faioLyrics.children[0].textContent, '暂无歌词');
  lyrics = [{ time: 0, text: 'Before' }, { time: 20, text: 'Singing now' }, { time: 40, text: 'After' }];
  for (let i = 0; i < 6; i++) {
    clock += 10000;
    await context.loadFaioListen();
    context.renderFaioPlaybackFrame();
    assert.equal(context.faioListen.status, 'connected');
    assert.equal(context.faioRoomPill.dataset.connected, 'true');
    assert.doesNotMatch(context.faioRoomPill.textContent, /过期/);
    assert.equal(context.faioLyrics.children.length, 3, 'lyrics arriving during playback must appear');
    assert.equal(context.faioLyrics.children.find(row => row.className.includes('is-active')).textContent, 'Singing now', 'passive metadata must not move the local lyric clock');
  }
  assert.equal(requests.length, 7, 'display stays fresh beyond the 45-second expiry threshold');
  context.renderFaioListen({ ...snapshot(), lyrics: [] }, true);
  assert.equal(context.faioListen.lyrics.length, 3, 'deferred lyrics do not erase the current song');
  context.browserAudioEnabled = true;
  await context.loadFaioListen(true);
  assert.equal(requests.at(-1), '/faio-listen/state');
  assert.equal(context.faioListen.lyrics.length, 3, 'immediate end checks retain same-song lyrics');
  context.renderFaioListen({ ...snapshot(), roomId: 'room-b', lyrics: [] }, true);
  assert.equal(context.faioListen.lyrics.length, 0, 'another room cannot inherit cached lyrics');
  context.renderFaioListen(snapshot());
  context.renderFaioListen({ ...snapshot(), playback: { ...snapshot().playback, fileId: 'song-b' }, lyrics: [] }, true);
  assert.equal(context.faioListen.lyrics.length, 0, 'another song cannot inherit cached lyrics');
  context.renderFaioListen(snapshot());
  context.renderFaioListen({ ...snapshot(), lyrics: [] });
  assert.equal(context.faioListen.lyrics.length, 0, 'a full snapshot can clear removed lyrics');
  context.renderFaioListen({ ...snapshot(), generatedAt: new Date(clock - 46000).toISOString() });
  assert.equal(context.faioListen.status, 'error', 'actually stale room data still expires');
  assert.equal(context.faioRoomPill.dataset.connected, 'false');
  assert.match(context.faioRoomPill.textContent, /过期/);
  await context.loadFaioListen();
  assert.equal(context.faioListen.status, 'connected', 'fresh metadata recovers the room');
  assert.equal(context.faioRoomPill.dataset.connected, 'true');
  assert.equal(timers.size, 1, 'only one metadata refresh remains scheduled');
  console.log('FAIO room refresh: active playback, late lyrics, deferred lyrics, local clock, room/song changes, genuine expiry and recovery: PASS');
})().catch(error => { console.error(error); process.exitCode = 1; });

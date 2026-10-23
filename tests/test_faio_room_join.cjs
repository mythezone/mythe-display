const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const html = fs.readFileSync('public/kiosk-test/index.html', 'utf8');
const start = html.indexOf('function renderFaioRoomJoin(');
assert.ok(start >= 0);
const join = { href: '', hidden: true }, canvas = {};
const drawings = [];
const scope = { URL, faioListen: null,
  document: { getElementById: id => id === 'faio-room-join' ? join : canvas },
  QRCode: { toCanvas(target, text, options, done) {
    assert.equal(target, canvas);
    drawings.push({text, options});
    done(null);
  } }
};
vm.createContext(scope);
vm.runInContext(html.slice(start, html.indexOf('\n      }', start) + 8), scope);
function render(url, roomId = 'room-a', status = 'open') {
  scope.faioListen = {roomId, room: {shareUrl: url, status}};
  scope.renderFaioRoomJoin();
}

render('https://music.example/listen/room-a?passcode=private#session');
assert.equal(join.hidden, false);
assert.equal(join.href, 'https://music.example/listen/room-a', 'only the public invitation enters the QR code');
assert.equal(drawings.length, 1);
render('https://music.example/listen/room-a');
assert.equal(drawings.length, 1, 'metadata refreshes reuse the existing QR code');
render('https://music.example/listen/room-b', 'room-b');
assert.equal(join.href, 'https://music.example/listen/room-b', 'changing rooms replaces the invitation');

for (const host of ['127.0.0.1:4173', '127.1:4173', 'localhost:4173', 'kiosk.localhost', '[::1]:4173', '0.0.0.0:4173']) {
  render(`http://${host}/listen/room-a`);
  assert.equal(join.hidden, false);
  assert.equal(join.href, 'https://faio.muiao.cloud/listen/room-a', 'a phone cannot use the collector loopback URL');
}
render('http://192.0.2.10:4173/listen/room-a');
assert.equal(join.href, 'http://192.0.2.10:4173/listen/room-a', 'configured network origins are preserved');
scope.faioListen = {roomUrl:'https://music.example/listen/room-a', room:{}};
scope.renderFaioRoomJoin();
assert.equal(join.hidden, false, 'older snapshots can supply roomUrl');

for (const url of ['', '/listen/room-a', 'javascript:alert(1)', 'ftp://music.example/listen/room-a',
  'https://name:secret@music.example/listen/room-a', 'https://music.example/other/room-a', 'https://music.example/listen/room-b']) {
  render(url);
  assert.equal(join.hidden, true, `invalid or mismatched invitation: ${url}`);
}
render('https://music.example/listen/room-a', 'room-a', 'closed');
assert.equal(join.hidden, true, 'closed rooms have no invitation');
scope.QRCode.toCanvas = (_canvas, _text, _options, done) => done(Error('render unavailable'));
render('https://music.example/listen/room-c', 'room-c');
assert.equal(join.hidden, true, 'a failed renderer cannot expose the previous room code');
console.log('PASS: current-room QR, refresh reuse, room changes, reachable origins, private query removal and invalid/closed rooms');

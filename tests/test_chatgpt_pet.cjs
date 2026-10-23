const assert = require('node:assert/strict'), fs = require('node:fs'), vm = require('node:vm');
const html = fs.readFileSync('public/kiosk-test/index.html','utf8');
function source(name) {
  const start=html.indexOf(`function ${name}(`);
  assert.ok(start>=0,name);
  return html.slice(start,html.indexOf('\n      }',start)+8);
}
class Element {
  constructor(){this.dataset={};this.attributes={};this.style={setProperty(name,value){this[name]=value;}};this.offsetWidth=250;}
  setAttribute(name,value){this.attributes[name]=value;}
  removeAttribute(name){delete this.attributes[name];}
}
let now=Date.parse('2026-10-23T00:00:00Z'),nextTimer=0;
const nodes=new Map(),timers=new Map();
const get=id=>nodes.get(id)||(nodes.set(id,new Element()),nodes.get(id));
const scope={Date:class extends Date{static now(){return now;}},Number,Math,document:{getElementById:get},
  codexUsage:null,agentRefreshMs:300000,usageColor:()=> 'green',
  mascotPanel:get('mascot-panel'),mascotSprite:get('mascot-sprite'),mascotAction:get('mascot-action'),
  mascotActionRows:{idle:0,right:1,left:2,wave:3,jump:4,failed:5,wait:6,running:7,review:8},
  mascotSpriteConfig:{rows:9,frames:8,fps:9,frameCounts:[6,8,8,4,5,8,6,6,6]},mascotReturnTimer:null,
  setTimeout(fn,delay){const id=++nextTimer;timers.set(id,{fn,delay});return id;},clearTimeout(id){timers.delete(id);}};
vm.createContext(scope);
for(const name of ['renderCodexUsage','setMascotSpriteAction'])vm.runInContext(source(name),scope);
const usage=()=>({available:true,status:'ready',updatedAt:new Date(now).toISOString(),usedPercent:42.5,
  resetsAt:now/1000+2*86400+3*3600+5*60,windowMinutes:10080,planType:'pro'});
scope.codexUsage=usage();scope.renderCodexUsage();
assert.equal(get('codex-usage-percent').textContent,'已用 42.5%');
assert.equal(get('codex-usage-bar').style.width,'42.5%');
assert.equal(get('codex-plan').textContent,'ChatGPT Pro');
assert.equal(get('codex-reset').textContent,'距重置 2天 3小时 5分');
assert.equal(get('codex-usage-track').attributes['aria-valuenow'],'42.5');
now+=61000;scope.renderCodexUsage();assert.equal(get('codex-reset').textContent,'距重置 2天 3小时 3分');
scope.codexUsage={...usage(),usedPercent:0};scope.renderCodexUsage();assert.equal(get('codex-usage-percent').textContent,'已用 0%','real zero usage is valid');
for(const invalid of [null,{available:false},{...usage(),usedPercent:'42'},{...usage(),usedPercent:NaN},{...usage(),windowMinutes:300}]) {
  scope.codexUsage=invalid;scope.renderCodexUsage();
  assert.equal(get('codex-usage').dataset.state,'unavailable');assert.equal(get('codex-usage-percent').textContent,'--');
  assert.equal(get('codex-usage-track').attributes['aria-valuenow'],undefined,'unavailable quota must not look like zero');
}
scope.codexUsage={...usage(),updatedAt:new Date(now-900001).toISOString()};scope.renderCodexUsage();assert.match(get('codex-reset').textContent,/已过期/);
scope.codexUsage={...usage(),resetsAt:now/1000};scope.renderCodexUsage();assert.equal(get('codex-usage-percent').textContent,'--');assert.match(get('codex-reset').textContent,/重置后/);
scope.codexUsage={available:false,status:'not-signed-in'};scope.renderCodexUsage();assert.match(get('codex-reset').textContent,/请登录/);
scope.mascotPanel.dataset={runtime:'codex-pet',petSource:'chatgpt'};
for(const [action,row,frames] of [['idle',0,6],['right',1,8],['left',2,8],['wave',3,4],['jump',4,5],['failed',5,8],['wait',6,6],['running',7,6],['review',8,6]]) {
  scope.setMascotSpriteAction(action);
  assert.equal(scope.mascotSprite.style['--pet-row'],String(row));
  assert.equal(scope.mascotSprite.style['--pet-frames'],String(frames),'unused transparent cells must never play');
  assert.equal(timers.size,[3,4,5].includes(row)?1:0,'one-shot actions have one return timer');
}
scope.setMascotSpriteAction('wave');timers.get(scope.mascotReturnTimer).fn();
assert.equal(scope.mascotSprite.style['--pet-row'],'0');assert.equal(scope.mascotSprite.style['--pet-frames'],'6');
assert.equal(scope.mascotAction.textContent,'待机');assert.equal(timers.size,0);
console.log('PASS: weekly quota, live countdown, real zero, invalid/stale/reset/login states, nine native actions and idle return');

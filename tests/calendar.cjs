// Run with: node --test tests/calendar.cjs
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('planner/static/planner/app.js', 'utf8');
function calendar() {
  const elements = new Map();
  function element() {
    return {children:[], dataset:{}, attrs:{}, textContent:'',
      append(...children) { this.children.push(...children); },
      replaceChildren() { this.children = []; },
      contains() { return false; },
      setAttribute(key,value) { this.attrs[key] = value; }};
  }
  const context = vm.createContext({Date, Intl, Map, document:{activeElement:null},
    tasks:[], node:(tag,text) => Object.assign(element(), {textContent:text}),
    $:key => { if (!elements.has(key)) elements.set(key,element()); return elements.get(key); },
    renderTasks:(list,tasks) => { list.tasks=tasks; }});
  vm.runInContext(source.slice(source.indexOf('function dayKey('),source.indexOf('async function load()')),context);
  return {run:code => vm.runInContext(code,context), elements, context};
}
test('month navigation handles year rollover, leap February, and day selection', () => {
  const c = calendar();
  c.run('calendarMonth = new Date(2023,11,1); changeMonth(1)');
  assert.equal(c.run('dayKey(calendarMonth)'), '2024-01-01');
  c.run('changeMonth(1)');
  const buttons = c.elements.get('#calendar-days').children.filter(el => el.dataset.day);
  assert.equal(buttons.length,29);
  buttons[28].onclick();
  assert.equal(c.run('dayKey(selectedDay)'), '2024-02-29');
  assert.equal(c.elements.get('#calendar-days').children.filter(el => el.attrs['aria-pressed']==='true').length,1);
  c.run('changeMonth(-2)');
  assert.equal(c.run('dayKey(calendarMonth)'), '2023-12-01');
});
test('local day grouping includes both task types, completed tasks, and sorts deadlines', () => {
  const original = process.env.TZ;
  try {
    for (const zone of ['America/Chicago','Asia/Tokyo','Pacific/Honolulu']) {
      process.env.TZ = zone;
      const c = calendar();
      c.context.tasks = [
        {id:2,kind:'exam',completed:true,due_at:'2026-03-09T02:00:00Z'},
        {id:1,kind:'assignment',completed:false,due_at:'2026-03-09T01:00:00Z'},
        {id:3,kind:'exam',due_at:'2026-03-11T01:00:00Z'}
      ];
      c.run("selectedDay = new Date('2026-03-09T01:00:00Z'); calendarMonth = new Date(2026,2,1); renderCalendar()");
      assert.equal(c.run('dayKey(selectedDay)'), zone==='Asia/Tokyo'?'2026-03-09':'2026-03-08');
      assert.deepEqual(Array.from(c.elements.get('#calendar-task-list').tasks,t=>t.id),[1,2]);
      c.run('selectedDay = new Date(2026,2,20); renderCalendar()');
      assert.equal(c.elements.get('#calendar-task-list').tasks.length,0);
      c.run("$('#calendar-today').onclick()");
      assert.equal(c.run('dayKey(selectedDay)'),c.run('dayKey(new Date())'));
    }
  } finally { if(original===undefined) delete process.env.TZ; else process.env.TZ=original; }
});
test('DST transitions keep every local date selectable', () => {
  const original = process.env.TZ;
  try {
    process.env.TZ='America/Chicago';
    const c=calendar();
    for (const month of [2,10]) {
      c.run(`calendarMonth = new Date(2026,${month},1); renderCalendar()`);
      const buttons=c.elements.get('#calendar-days').children.filter(el=>el.dataset.day);
      assert.equal(buttons.length,month===2?31:30);
      assert.equal(new Set(buttons.map(el=>el.dataset.day)).size,buttons.length);
    }
  } finally { if(original===undefined) delete process.env.TZ; else process.env.TZ=original; }
});

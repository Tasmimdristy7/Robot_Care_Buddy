let jokeTimers = [];
function clearJokeTimers() { jokeTimers.forEach(clearTimeout); jokeTimers = []; }
const $ = selector => document.querySelector(selector);
let tasks = [], filter = 'upcoming', activeReminder = null, polling = false;
const dismissed = new Map();
const dialog = $('#task-dialog'), form = $('#task-form'), reminder = $('#reminder');
const csrf = form.querySelector('[name=csrfmiddlewaretoken]').value;
const reduced = matchMedia('(prefers-reduced-motion: reduce)');
let paused = reduced.matches;
function motion() {
  document.body.classList.toggle('paused', paused);
  $('#motion').textContent = paused ? 'Motion paused' : 'Pause motion';
  $('#motion').setAttribute('aria-pressed', String(paused));
  $('#motion').disabled = reduced.matches;
}
$('#motion').onclick = () => { paused = !paused; motion(); };
reduced.addEventListener('change', () => { paused = reduced.matches; motion(); }); motion();
async function api(url, data) {
  const response = await fetch(url, data ? {method:'POST', headers:{'X-CSRFToken':csrf}, body:data} : {cache:'no-store'});
  let result;
  try { result = await response.json(); } catch { throw Error('The server is unavailable. Your changes were not saved.'); }
  if (!response.ok) {
    const detail = result.errors ? Object.values(result.errors).flat().map(e => e.message).join(' ') : result.error;
    throw Error(detail || 'Could not save that change. Please try again.');
  }
  return result;
}
function node(tag, text, className) {
  const el = document.createElement(tag); if (text !== undefined) el.textContent = text;
  if (className) el.className = className; return el;
}
function deadline(task) {
  const minutes = Math.ceil((new Date(task.due_at) - Date.now()) / 60000);
  if (minutes <= 0) return 'Overdue';
  if (minutes < 60) return `Due in ${minutes} min`;
  if (minutes < 1440) return `Due in ${Math.ceil(minutes / 60)} hours`;
  return `Due in ${Math.ceil(minutes / 1440)} days`;
}
function render() {
  const now = Date.now();
  $('#open-count').textContent = tasks.filter(t => !t.completed).length;
  $('#soon-count').textContent = tasks.filter(t => !t.completed && new Date(t.due_at)>=now && new Date(t.due_at)<=now+172800000).length;
  $('#done-count').textContent = tasks.filter(t => t.completed).length;
  const query = $('#search').value.toLowerCase();
  const visible = tasks.filter(t => {
    const overdue = new Date(t.due_at)<now;
    return (filter==='all' || (filter==='completed' ? t.completed : !t.completed && (filter==='overdue' ? overdue : !overdue))) && `${t.title} ${t.course}`.toLowerCase().includes(query);
  });
  const list = $('#task-list'); list.replaceChildren();
  if (!visible.length) {
    const empty = node('div', undefined, 'empty');
    empty.append(node('h3', tasks.length ? 'A little breathing room.' : 'Your buddy is ready when you are.'), node('p', tasks.length ? 'No tasks match this view. Try another filter or add something new.' : 'Add your first assignment or exam. I’ll keep an eye on the deadline.'));
    list.append(empty); return;
  }
  visible.forEach(task => {
    const late = !task.completed && new Date(task.due_at)<now;
    const card = node('article', undefined, `task${task.completed?' completed':''}${late?' late':''}`);
    const done = node('button',task.completed?'✓':'','check');
    done.setAttribute('aria-label',`${task.completed?'Reopen':'Complete'} ${task.title}`);
    done.onclick = () => mutate(task.id, task.completed?'reopen':'complete');
    const body = node('div'); body.append(node('h3',task.title),node('p',`${task.kind==='exam'?'EXAM':'ASSIGNMENT'}${task.course?' / '+task.course:''}`));
    const date = new Date(task.due_at).toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
    body.append(node('p',`${task.completed?'Completed':deadline(task)} · ${date}`,late?'due':''));
    const actions = node('div',undefined,'task-actions');
    const edit = node('button','Edit');edit.onclick=()=>openForm(task);
    const remove=node('button','Delete');remove.onclick=()=>{if(confirm(`Delete “${task.title}”?`)) mutate(task.id,'delete');};
    actions.append(edit,remove);card.append(done,body,actions);list.append(card);
  });
}
async function load() { tasks = (await api('/tasks/')).tasks; render(); }
function openForm(task) {
  form.reset(); $('#form-error').textContent='';
  form.elements.task_id.value=task?.id || '';
  $('#form-title').textContent=task?'Edit your task':'What’s coming up?';
  if(task) {
    ['title','course','kind'].forEach(key=>form.elements[key].value=task[key]);
    const d = new Date(task.due_at);const local = new Date(d.getTime()-d.getTimezoneOffset()*60000);
    form.elements.due_at.value=local.toISOString().slice(0,16);
  }
  dialog.showModal();form.elements.title.focus();
}
$('#new-task').onclick=()=>openForm();$('#cancel').onclick=()=>dialog.close();
form.onsubmit=async event=>{
  event.preventDefault();const submit=form.querySelector('[type=submit]');submit.disabled=true;
  try {
    const data=new FormData(form);data.set('due_at',new Date(form.elements.due_at.value).toISOString());
    const id=data.get('task_id');if(id)data.set('action','edit');
    await api(id?`/tasks/${id}/`:'/tasks/',data);
    if(id) dismissed.delete(Number(id));
    dialog.close();$('#notice').textContent='Saved. Your buddy is on deadline duty.';
    await load();await poll();
  } catch(error){$('#form-error').textContent=error.message;}finally{submit.disabled=false;}
};
async function mutate(id,action) {
  try {
    await api(`/tasks/${id}/`,new URLSearchParams({action}));
    if(activeReminder?.id===id) hideReminder();
    await load();
    if(action==='complete') showBubble('One more thing done! Take a breath. I’m proud of you.',null,true);
    $('#notice').textContent=action==='delete'?'Task deleted.':action==='snooze'?'Reminder snoozed for 15 minutes.':'Task updated.';
  }catch(error){$('#notice').textContent=error.message;$('#bubble-error').textContent=error.message;}
}
function hideReminder(){clearJokeTimers();reminder.hidden=true;activeReminder=null;}
function showBubble(message,task=null,celebrate=false){
  clearJokeTimers();
  $('.bubble > .eyebrow').hidden = false;
  $('#bubble-text').hidden = false;
  $('#fact-label').parentElement.hidden = false;
  $('#fact-content').hidden=true;
  activeReminder=task;$('#bubble-text').textContent=message;$('#bubble-error').textContent='';
  $('#reminder-actions').hidden=!task;
  reminder.classList.remove('nudging');
  reminder.classList.toggle('celebrate',celebrate);reminder.hidden=false;
  if (task && !paused && !reduced.matches) {
    void reminder.offsetWidth;
    reminder.classList.add('nudging');
  }
}
$('#dismiss').onclick=()=>{if(activeReminder) dismissed.set(activeReminder.id,Date.now()+30*60000);hideReminder();};
$('#snooze').onclick=()=>{if(activeReminder)mutate(activeReminder.id,'snooze');};
$('#complete-reminder').onclick=()=>{if(activeReminder)mutate(activeReminder.id,'complete');};
$('#preview').onclick=()=>showBubble('Hi, I’m Buddy! Add a deadline and I’ll float over when it’s less than 48 hours away. One small step at a time.');
async function poll(){
  if(polling||document.hidden)return;polling=true;
  try {
    const result=await api('/reminders/');
    if(activeReminder && !result.tasks.some(t=>t.id===activeReminder.id)) hideReminder();
    if(activeReminder||dialog.open)return;
    const task=result.tasks.find(t=>(dismissed.get(t.id)||0)<=Date.now());
    if(task){
      const timing=deadline(task);
      showBubble(timing==='Overdue'?`Hey, “${task.title}” is overdue. Let’s check on it together.`:`A little heads-up: “${task.title}” is ${timing.toLowerCase()}. You’ve got this!`,task);
    }
  }catch{ $('#notice').textContent='Buddy can’t reach the server. Reminders will retry when the connection returns.'; }
  finally{polling=false;}
}
document.querySelectorAll('[data-filter]').forEach(button=>button.onclick=()=>{
  filter=button.dataset.filter;document.querySelectorAll('[data-filter]').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));render();
});
$('#search').oninput=render;
async function refresh(){try{await load();await poll();}catch(error){$('#notice').textContent=error.message;}}
refresh();setInterval(refresh,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh();});

$('#roaming-buddy').onclick = () => shareJoke();

// Drag with mouse or touch; arrow keys provide the same positioning control.
function makeDraggable(element, handle, storageKey) {
  let drag = null, suppressClick = false, positioned = false;
  function place(x, y, save = false) {
    positioned = true;
    element.classList.add('manually-placed');
    const maxX = Math.max(8, innerWidth - element.offsetWidth - 8);
    const maxY = Math.max(8, innerHeight - element.offsetHeight - 8);
    element.style.left = `${Math.max(8, Math.min(x, maxX))}px`;
    element.style.top = `${Math.max(8, Math.min(y, maxY))}px`;
    element.style.right = 'auto'; element.style.bottom = 'auto';
    if (save) { try { localStorage.setItem(storageKey, JSON.stringify([parseFloat(element.style.left), parseFloat(element.style.top)])); } catch {} }
  }
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    if (Array.isArray(saved) && saved.length === 2 && saved.every(Number.isFinite)) place(...saved);
  } catch {}
  handle.addEventListener('pointerdown', event => {
    if (event.button !== 0) return;
    const rect = element.getBoundingClientRect();
    drag = {id:event.pointerId, x:event.clientX, y:event.clientY, left:rect.left, top:rect.top, moved:false};
    suppressClick = false;
    handle.setPointerCapture(event.pointerId);
  });
  handle.addEventListener('pointermove', event => {
    if (!drag || drag.id !== event.pointerId) return;
    const dx = event.clientX - drag.x, dy = event.clientY - drag.y;
    if (!drag.moved && Math.hypot(dx,dy) < 5) return;
    drag.moved = true; element.classList.add('dragging');
    place(drag.left + dx, drag.top + dy);
  });
  function end(event) {
    if (!drag || drag.id !== event.pointerId) return;
    suppressClick = drag.moved;
    if (drag.moved) place(parseFloat(element.style.left), parseFloat(element.style.top), true);
    drag = null; element.classList.remove('dragging');
    if (handle.hasPointerCapture(event.pointerId)) handle.releasePointerCapture(event.pointerId);
  }
  handle.addEventListener('pointerup', end); handle.addEventListener('pointercancel', end);
  handle.addEventListener('click', event => {
    if (suppressClick) { event.preventDefault(); event.stopImmediatePropagation(); suppressClick = false; }
  }, true);
  handle.addEventListener('keydown', event => {
    const directions = {ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
    if (!directions[event.key]) return;
    event.preventDefault(); const rect = element.getBoundingClientRect(); const step = event.shiftKey ? 30 : 10;
    place(rect.left + directions[event.key][0]*step, rect.top + directions[event.key][1]*step, true);
  });
  function clamp() { if (positioned && !element.hidden) place(parseFloat(element.style.left),parseFloat(element.style.top)); }
  window.addEventListener('resize', clamp);
  new MutationObserver(clamp).observe(element,{attributes:true,attributeFilter:['hidden']});
}
makeDraggable($('#roaming-buddy'), $('#roaming-buddy'), 'buddy-position');
makeDraggable(reminder, reminder.querySelector('.reminder-robot'), 'buddy-reminder-position');

// End the greeting after one short sequence; normal floating resumes.
reminder.querySelector('.reminder-robot').addEventListener('animationend', event => {
  if (event.animationName === 'buddy-nudge') reminder.classList.remove('nudging');
});

let previousFact = '', fetchingFact = false;
async function shareFact() {
  if (fetchingFact) return;
  fetchingFact = true;
  $('#fun-fact').disabled = true; $('#another-fact').disabled = true;
  try {
    const result = await api('/fun-fact/?previous=' + encodeURIComponent(previousFact));
    previousFact = String(result.id);
    // Keep a real deadline and its actions visible if one is already showing.
    if (!activeReminder) showBubble('A little brain break? Here’s something fun about code.');
    $('#fact-content').hidden = false;
    clearJokeTimers();
    $('#fact-label').parentElement.hidden = false;
    $('#fact-label').textContent = 'BUDDY’S SOFTWARE FUN FACT';
    $('#another-fact').textContent = 'Another fact ↻';
    $('#another-fact').onclick = shareFact;
    $('#fact-text').textContent = result.fact;
  } catch (error) { $('#notice').textContent = error.message; }
  finally { fetchingFact = false; $('#fun-fact').disabled = false; $('#another-fact').disabled = false; }
}
$('#fun-fact').onclick = shareFact;
$('#another-fact').onclick = shareFact;

let previousJoke = '';
async function shareJoke() {
  if (fetchingFact) return;
  fetchingFact = true;
  $('#tell-joke').disabled = true; $('#another-fact').disabled = true;
  try {
    const result = await api('/joke/?previous=' + encodeURIComponent(previousJoke));
    previousJoke = String(result.id);
    clearJokeTimers();
    if (!activeReminder) {
      showBubble('');
      $('.bubble > .eyebrow').hidden = true;
      $('#bubble-text').hidden = true;
    }
    $('#fact-content').hidden = false;
    $('#fact-label').parentElement.hidden = true;
    const split = result.joke.match(/^(.+?[?.!])\s+([\s\S]+)$/);
    $('#fact-text').textContent = split ? split[1] : result.joke;
    if (split) jokeTimers.push(setTimeout(() => { $('#fact-text').textContent = split[1] + '\n\n' + split[2]; }, 1600));
    jokeTimers.push(setTimeout(() => { $('#fact-text').textContent += '\n\nhahaha 😄'; }, split ? 3200 : 1600));
    $('#another-fact').textContent = 'Another joke ↻';
    $('#another-fact').onclick = shareJoke;
  } catch (error) { $('#notice').textContent = error.message; }
  finally { fetchingFact = false; $('#tell-joke').disabled = false; $('#another-fact').disabled = false; }
}
$('#tell-joke').onclick = shareJoke;
// The docked robot also tells jokes; the drag handler suppresses clicks after dragging.
reminder.querySelector('.reminder-robot').addEventListener('click', shareJoke);
reminder.querySelector('.reminder-robot').addEventListener('keydown', event => {
  if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); shareJoke(); }
});

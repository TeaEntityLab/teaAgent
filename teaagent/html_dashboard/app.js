function renderWorkflow(data) {
  const el = document.getElementById('workflow-state');
  el.textContent = JSON.stringify(data.workflow ?? null, null, 2);
  const notes = document.getElementById('polish-notes');
  if (data.polish_notes && !notes.value) {
    notes.value = data.polish_notes;
  }
}

function renderFocus(data) {
  const list = document.getElementById('focus-list');
  list.innerHTML = '';
  const frames = (data.focus && data.focus.frames) || [];
  if (!frames.length) {
    const li = document.createElement('li');
    li.textContent = '(empty stack)';
    list.appendChild(li);
    return;
  }
  for (const frame of frames) {
    const li = document.createElement('li');
    li.textContent = `${frame.topic} — ${frame.state}`;
    list.appendChild(li);
  }
}

function renderJit(data) {
  const pendingEl = document.getElementById('pending-list');
  pendingEl.innerHTML = '';
  for (const item of data.pending || []) {
    const card = document.createElement('div');
    card.className = 'pending-card';
    card.innerHTML = `<strong>${item.tool_name}</strong> by ${item.agent_name}<br/><span>${item.reason}</span>`;
    const actions = document.createElement('div');
    actions.className = 'actions';
    const approve = document.createElement('button');
    approve.textContent = 'Approve';
    approve.addEventListener('click', () => postJit('/api/jit/approve', item.request_id));
    const reject = document.createElement('button');
    reject.textContent = 'Reject';
    reject.className = 'reject';
    reject.addEventListener('click', () => postJit('/api/jit/reject', item.request_id));
    actions.appendChild(approve);
    actions.appendChild(reject);
    card.appendChild(actions);
    pendingEl.appendChild(card);
  }
  const diffEl = document.getElementById('diff-view');
  const diffs = data.diffs || [];
  if (!diffs.length) {
    diffEl.textContent = '(no diffs yet)';
    return;
  }
  const latest = diffs[diffs.length - 1];
  diffEl.textContent = latest.unified_diff || latest.new_text || '';
}

async function postJit(path, requestId) {
  await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId }),
  });
}

document.getElementById('polish-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const notes = document.getElementById('polish-notes').value;
  await fetch('/api/workflow/polish', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ notes }),
  });
});

function connectStream(path, handler) {
  const source = new EventSource(path);
  source.addEventListener('workflow_update', (event) => {
    handler(JSON.parse(event.data));
  });
  source.addEventListener('focus_update', (event) => {
    handler(JSON.parse(event.data));
  });
  source.addEventListener('jit_diff', (event) => {
    handler(JSON.parse(event.data));
  });
  source.onerror = () => {
    /* browser reconnects automatically */
  };
}

connectStream('/api/workflow/stream', renderWorkflow);
connectStream('/api/focus/stream', renderFocus);
connectStream('/api/jit/diff', renderJit);

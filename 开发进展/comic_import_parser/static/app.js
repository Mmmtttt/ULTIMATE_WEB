const state = {
  sessionId: null,
  cleanRoot: null,
  tree: null,
  nodeMap: {},
  assignments: {},
  selectedNodeId: null,
  collapsedIds: new Set(),
  exportItems: [],
  downloadUrl: null,
  warnings: [],
};

const els = {
  pathInput: document.getElementById('pathInput'),
  archiveInput: document.getElementById('archiveInput'),
  folderInput: document.getElementById('folderInput'),
  importPathBtn: document.getElementById('importPathBtn'),
  uploadBtn: document.getElementById('uploadBtn'),
  clearSessionBtn: document.getElementById('clearSessionBtn'),
  statusBar: document.getElementById('statusBar'),
  treeContainer: document.getElementById('treeContainer'),
  selectionInfo: document.getElementById('selectionInfo'),
  assignmentList: document.getElementById('assignmentList'),
  warningsBox: document.getElementById('warningsBox'),
  jsonPreview: document.getElementById('jsonPreview'),
  sessionIdLabel: document.getElementById('sessionIdLabel'),
  cleanRootLabel: document.getElementById('cleanRootLabel'),
  selectedLabel: document.getElementById('selectedLabel'),
  markAuthorBtn: document.getElementById('markAuthorBtn'),
  markWorkBtn: document.getElementById('markWorkBtn'),
  clearLayerBtn: document.getElementById('clearLayerBtn'),
  clearMarksBtn: document.getElementById('clearMarksBtn'),
  exportBtn: document.getElementById('exportBtn'),
  downloadBtn: document.getElementById('downloadBtn'),
};

function setStatus(message, type = 'info') {
  els.statusBar.textContent = message;
  els.statusBar.classList.remove('success', 'error');
  if (type === 'success') {
    els.statusBar.classList.add('success');
  }
  if (type === 'error') {
    els.statusBar.classList.add('error');
  }
}

function roleLabel(role) {
  if (role === 'author') return '作者层';
  if (role === 'work') return '作品层';
  return '未标记';
}

function resetState() {
  state.sessionId = null;
  state.cleanRoot = null;
  state.tree = null;
  state.nodeMap = {};
  state.assignments = {};
  state.selectedNodeId = null;
  state.collapsedIds = new Set();
  state.exportItems = [];
  state.downloadUrl = null;
  state.warnings = [];
}

function hydrateTree(tree) {
  state.nodeMap = {};

  function walk(node, parentId = null) {
    state.nodeMap[node.id] = {
      ...node,
      parentId,
      childIds: (node.children || []).map((child) => child.id),
    };
    (node.children || []).forEach((child) => walk(child, node.id));
  }

  walk(tree, null);
}

function currentNode() {
  return state.selectedNodeId ? state.nodeMap[state.selectedNodeId] : null;
}

function currentLayerInfo() {
  const node = currentNode();
  if (!node) return null;
  if (node.parentId === null) return null;
  const parent = state.nodeMap[node.parentId];
  return {
    parent,
    role: state.assignments[node.parentId] || '',
    siblingCount: parent ? parent.childIds.length : 0,
  };
}

function setImportedData(payload) {
  state.sessionId = payload.session_id;
  state.cleanRoot = payload.clean_root;
  state.tree = payload.tree;
  state.assignments = {};
  state.exportItems = [];
  state.downloadUrl = null;
  state.warnings = payload.warnings || [];
  state.collapsedIds = new Set();
  hydrateTree(payload.tree);

  if (payload.tree.children && payload.tree.children.length > 0) {
    state.selectedNodeId = payload.tree.children[0].id;
  } else {
    state.selectedNodeId = payload.tree.id;
  }

  renderAll();
}

function renderMeta() {
  els.sessionIdLabel.textContent = state.sessionId || '-';
  els.cleanRootLabel.textContent = state.cleanRoot || '-';

  const node = currentNode();
  els.selectedLabel.textContent = node ? node.rel_path : '-';
}

function renderSelectionInfo() {
  const node = currentNode();
  if (!node) {
    els.selectionInfo.textContent = '请先从左侧目录树中选择一个目录。';
    return;
  }

  if (node.parentId === null) {
    els.selectionInfo.innerHTML = [
      '<div><strong>当前目录：</strong>根目录</div>',
      '<div><strong>说明：</strong>根目录本身不能直接标记为作者层或作品层，请选择它下面的某个目录后再操作。</div>',
    ].join('');
    return;
  }

  const parent = state.nodeMap[node.parentId];
  const layerRole = state.assignments[node.parentId] || '';
  els.selectionInfo.innerHTML = [
    `<div><strong>当前目录：</strong>${escapeHtml(node.rel_path)}</div>`,
    `<div><strong>所在层父目录：</strong>${escapeHtml(parent ? parent.rel_path : '-')}</div>`,
    `<div><strong>同层目录数量：</strong>${parent ? parent.childIds.length : 0}</div>`,
    `<div><strong>这一层当前状态：</strong>${escapeHtml(roleLabel(layerRole))}</div>`,
  ].join('');
}

function renderAssignments() {
  const entries = Object.entries(state.assignments);
  if (entries.length === 0) {
    els.assignmentList.className = 'assignment-list empty-panel';
    els.assignmentList.textContent = '尚未设置任何层级标记。';
    return;
  }

  els.assignmentList.className = 'assignment-list';
  els.assignmentList.innerHTML = '';
  entries
    .sort((a, b) => a[0].localeCompare(b[0], 'zh-CN'))
    .forEach(([parentId, role]) => {
      const parent = state.nodeMap[parentId];
      if (!parent) return;
      const item = document.createElement('div');
      item.className = 'assignment-item';
      item.innerHTML = `
        <div class="assignment-title">${escapeHtml(parent.rel_path)} → ${escapeHtml(roleLabel(role))}</div>
        <div class="muted">该层一共包含 ${parent.childIds.length} 个同级目录，它们会被一起视为同一种语义。</div>
      `;
      els.assignmentList.appendChild(item);
    });
}

function renderWarnings() {
  if (!state.warnings || state.warnings.length === 0) {
    els.warningsBox.className = 'warnings-box empty-panel';
    els.warningsBox.textContent = '暂无警告。';
    return;
  }
  els.warningsBox.className = 'warnings-box';
  els.warningsBox.innerHTML = '';
  state.warnings.forEach((warning) => {
    const item = document.createElement('div');
    item.className = 'warning-item';
    item.textContent = warning;
    els.warningsBox.appendChild(item);
  });
}

function renderJsonPreview() {
  els.jsonPreview.textContent = JSON.stringify(state.exportItems || [], null, 2);
}

function getNodeRoleBadge(node) {
  if (!node || node.parentId === null) return '';
  return state.assignments[node.parentId] || '';
}

function renderTree() {
  if (!state.tree) {
    els.treeContainer.className = 'tree-container empty-panel';
    els.treeContainer.textContent = '还没有导入任何目录。';
    return;
  }

  els.treeContainer.className = 'tree-container';
  els.treeContainer.innerHTML = '';

  const rootList = document.createElement('ul');
  rootList.className = 'tree-root';
  rootList.appendChild(renderTreeNode(state.tree));
  els.treeContainer.appendChild(rootList);
}

function renderTreeNode(node) {
  const nodeInfo = state.nodeMap[node.id];
  const li = document.createElement('li');
  const row = document.createElement('div');
  row.className = 'tree-row';
  if (state.selectedNodeId === node.id) {
    row.classList.add('selected');
  }

  const hasChildren = (node.children || []).length > 0;
  const toggleBtn = document.createElement('button');
  toggleBtn.className = hasChildren ? 'tree-toggle' : 'tree-toggle placeholder';
  toggleBtn.type = 'button';
  toggleBtn.textContent = hasChildren ? (state.collapsedIds.has(node.id) ? '▸' : '▾') : '·';
  if (hasChildren) {
    toggleBtn.addEventListener('click', (event) => {
      event.stopPropagation();
      if (state.collapsedIds.has(node.id)) {
        state.collapsedIds.delete(node.id);
      } else {
        state.collapsedIds.add(node.id);
      }
      renderTree();
    });
  }

  const label = document.createElement('div');
  label.className = 'tree-label';

  const name = document.createElement('span');
  name.className = 'tree-name';
  name.textContent = node.id === '.' ? '📦 根目录' : `📁 ${node.real_name}`;
  label.appendChild(name);

  const meta = document.createElement('span');
  meta.className = 'badge count';
  meta.textContent = `总图 ${node.total_images}`;
  label.appendChild(meta);

  if (node.direct_images > 0) {
    const direct = document.createElement('span');
    direct.className = 'badge count';
    direct.textContent = `直图 ${node.direct_images}`;
    label.appendChild(direct);
  }

  const role = getNodeRoleBadge(nodeInfo);
  if (role) {
    const badge = document.createElement('span');
    badge.className = `badge ${role}`;
    badge.textContent = role === 'author' ? '作者目录' : '作品目录';
    label.appendChild(badge);
  }

  row.appendChild(toggleBtn);
  row.appendChild(label);
  row.addEventListener('click', () => {
    state.selectedNodeId = node.id;
    renderAll();
  });

  li.appendChild(row);

  if (hasChildren && !state.collapsedIds.has(node.id)) {
    const childrenList = document.createElement('ul');
    node.children.forEach((child) => childrenList.appendChild(renderTreeNode(child)));
    li.appendChild(childrenList);
  }

  return li;
}

function renderAll() {
  renderMeta();
  renderTree();
  renderSelectionInfo();
  renderAssignments();
  renderWarnings();
  renderJsonPreview();
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function handleJsonResponse(response) {
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || '请求失败');
  }
  return data;
}

async function importFromPath() {
  const sourcePath = els.pathInput.value.trim();
  if (!sourcePath) {
    setStatus('请先输入一个本地路径。', 'error');
    return;
  }

  setStatus('正在按路径导入并递归清洗目录，请稍候……');
  try {
    const response = await fetch('/api/import/from-path', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ source_path: sourcePath }),
    });
    const data = await handleJsonResponse(response);
    setImportedData(data);
    setStatus(`导入完成，已生成干净目录树。当前会话：${data.session_id}`, 'success');
  } catch (error) {
    setStatus(`导入失败：${error.message}`, 'error');
  }
}

function collectUploadFiles() {
  const archiveFiles = Array.from(els.archiveInput.files || []);
  const folderFiles = Array.from(els.folderInput.files || []);
  return [...archiveFiles, ...folderFiles];
}

async function importFromUpload() {
  const allFiles = collectUploadFiles();
  if (allFiles.length === 0) {
    setStatus('请至少选择一个压缩包或一个文件夹。', 'error');
    return;
  }

  const formData = new FormData();
  allFiles.forEach((file) => {
    formData.append('files', file, file.name);
    const relativePath = file.webkitRelativePath && file.webkitRelativePath.trim().length > 0
      ? file.webkitRelativePath
      : file.name;
    formData.append('relative_paths', relativePath);
  });

  setStatus(`正在上传 ${allFiles.length} 个文件并递归清洗目录，请稍候……`);
  try {
    const response = await fetch('/api/import/upload', {
      method: 'POST',
      body: formData,
    });
    const data = await handleJsonResponse(response);
    setImportedData(data);
    setStatus(`上传并导入完成，已生成干净目录树。当前会话：${data.session_id}`, 'success');
  } catch (error) {
    setStatus(`上传导入失败：${error.message}`, 'error');
  }
}

function applyLayerRole(role) {
  const node = currentNode();
  if (!node) {
    setStatus('请先选择一个目录。', 'error');
    return;
  }
  if (node.parentId === null) {
    setStatus('根目录不能直接标记，请选择根目录下面的某个目录。', 'error');
    return;
  }
  state.assignments[node.parentId] = role;
  state.downloadUrl = null;
  setStatus(`已将 ${node.parentId} 这一层标记为${roleLabel(role)}。`, 'success');
  renderAll();
}

function clearCurrentLayer() {
  const node = currentNode();
  if (!node || node.parentId === null) {
    setStatus('请先选择一个可操作的目录。', 'error');
    return;
  }
  if (state.assignments[node.parentId]) {
    delete state.assignments[node.parentId];
    state.downloadUrl = null;
    setStatus(`已清除 ${node.parentId} 这一层的标记。`, 'success');
    renderAll();
    return;
  }
  setStatus('这一层当前没有标记。');
}

function clearAllMarks() {
  state.assignments = {};
  state.downloadUrl = null;
  state.exportItems = [];
  setStatus('已清空全部层级标记。', 'success');
  renderAll();
}

async function exportJson() {
  if (!state.sessionId) {
    setStatus('请先导入目录。', 'error');
    return false;
  }

  setStatus('正在根据你的层级标记生成 JSON……');
  try {
    const response = await fetch('/api/export-json', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        session_id: state.sessionId,
        assignments: state.assignments,
      }),
    });
    const data = await handleJsonResponse(response);
    state.exportItems = data.items || [];
    state.downloadUrl = data.download_url || null;
    renderJsonPreview();
    setStatus(`JSON 已生成，共解析出 ${data.count} 个作品目录。`, 'success');
    return true;
  } catch (error) {
    setStatus(`生成 JSON 失败：${error.message}`, 'error');
    return false;
  }
}

async function downloadJson() {
  const ok = await exportJson();
  if (!ok || !state.downloadUrl) {
    return;
  }
  window.location.href = state.downloadUrl;
}

async function clearSession() {
  if (!state.sessionId) {
    resetState();
    renderAll();
    setStatus('当前没有可清理的会话。');
    return;
  }

  try {
    await fetch(`/api/sessions/${state.sessionId}`, { method: 'DELETE' });
  } catch (_error) {
    // 会话清理失败时仍然清掉前端状态，避免界面残留。
  }

  resetState();
  renderAll();
  setStatus('当前会话已清理。', 'success');
}

els.importPathBtn.addEventListener('click', importFromPath);
els.uploadBtn.addEventListener('click', importFromUpload);
els.markAuthorBtn.addEventListener('click', () => applyLayerRole('author'));
els.markWorkBtn.addEventListener('click', () => applyLayerRole('work'));
els.clearLayerBtn.addEventListener('click', clearCurrentLayer);
els.clearMarksBtn.addEventListener('click', clearAllMarks);
els.exportBtn.addEventListener('click', exportJson);
els.downloadBtn.addEventListener('click', downloadJson);
els.clearSessionBtn.addEventListener('click', clearSession);

renderAll();

    let ws = null;
    let currentFile = null;


    const statusDiv = document.getElementById('status');
    const terminalDiv = document.getElementById('terminal');
    const inputField = document.getElementById('input');
    const connectBtn = document.getElementById('connectBtn');
    const disconnectBtn = document.getElementById('disconnectBtn');
    const sendBtn = document.getElementById('sendBtn');
    const clearBtn = document.getElementById('clearBtn');
    const urlInput = document.getElementById('urlInput');
    const fileList = document.getElementById('fileList');
    const listFilesBtn = document.getElementById('listFilesBtn');
    const newFileBtn = document.getElementById('newFileBtn');
    const deleteFileBtn = document.getElementById('deleteFileBtn');
    const filenameInput = document.getElementById('filenameInput');
    const fileEditor = document.getElementById('fileEditor');
    const saveFileBtn = document.getElementById('saveFileBtn');
    const readFileBtn = document.getElementById('readFileBtn');
    const runFileBtn = document.getElementById('runFileBtn');
    const fileInfo = document.getElementById('fileInfo');

    function log(message, type = 'output') {
    const line = document.createElement('div');
    line.className = type;
    line.textContent = message;
    terminalDiv.appendChild(line);
    terminalDiv.scrollTop = terminalDiv.scrollHeight;
}

    function updateStatus(connected) {
    if (connected) {
    statusDiv.textContent = '已连接到ESP32';
    statusDiv.className = 'status connected';
    connectBtn.disabled = true;
    disconnectBtn.disabled = false;
    inputField.disabled = false;
    sendBtn.disabled = false;
    listFilesBtn.disabled = false;
    newFileBtn.disabled = false;
    filenameInput.disabled = false;
    fileEditor.disabled = false;
    saveFileBtn.disabled = false;
    readFileBtn.disabled = false;
    runFileBtn.disabled = false;
    inputField.focus();
} else {
    statusDiv.textContent = '未连接';
    statusDiv.className = 'status disconnected';
    connectBtn.disabled = false;
    disconnectBtn.disabled = true;
    inputField.disabled = true;
    sendBtn.disabled = true;
    listFilesBtn.disabled = true;
    newFileBtn.disabled = true;
    deleteFileBtn.disabled = true;
    filenameInput.disabled = true;
    fileEditor.disabled = true;
    saveFileBtn.disabled = true;
    readFileBtn.disabled = true;
    runFileBtn.disabled = true;
}
}

    function connect() {
    const url = urlInput.value.trim();
    if (!url) {
    alert('请输入WebSocket URL');
    return;
}

    log('正在连接 ' + url + '...', 'command');

    try {
    ws = new WebSocket(url);

    ws.onopen = function(event) {
    log('连接成功!', 'output');
    updateStatus(true);
    sendCommand('LIST');
};

    ws.onmessage = function(event) {
    const message = event.data;

    if (message.startsWith('FILE_CONTENT:')) {
    const content = message.substring('FILE_CONTENT:'.length);
    fileEditor.value = content;
    log(`已加载文件: ${filenameInput.value}`, 'output');
}
    else if (message.includes('文件列表: [')) {
    updateFileList(message);
    log(message, 'output');
} else {
    log(message, 'output');
}
};

    ws.onclose = function(event) {
    log('连接关闭', 'error');
    updateStatus(false);
    ws = null;
};

    ws.onerror = function(event) {
    log('连接错误', 'error');
    updateStatus(false);
    ws = null;
};

} catch (error) {
    log('连接失败: ' + error, 'error');
    updateStatus(false);
}
}

    function disconnect() {
    if (ws) {
    ws.close();
    ws = null;
}
    updateStatus(false);
}

    function sendCommand(command) {
    if (!command || !ws || ws.readyState !== WebSocket.OPEN) {
    if (document.activeElement === inputField) {
    inputField.value = '';
}
    return;
}

    if (document.activeElement === inputField || command === inputField.value) {
    inputField.value = '';
}


    try {
    ws.send(command);
} catch (error) {
    log('发送错误: ' + error, 'error');
}
}

    function updateFileList(response) {
    try {
    const match = response.match(/文件列表: (\[.*\])/);
    if (match && match[1]) {
    const files = JSON.parse(match[1]); // 现在可以正确解析 ["file.py"]
    fileList.innerHTML = '';

    if (files.length === 0) {
    fileList.innerHTML = '<div style="color: #6c757d; text-align: center;">没有文件</div>';
} else {
    files.forEach(file => {
    const div = document.createElement('div');
    div.className = 'file-item';
    div.textContent = file;
    div.onclick = () => {
    document.querySelectorAll('.file-item').forEach(item => {
    item.classList.remove('selected');
});
    div.classList.add('selected');
    currentFile = file;
    deleteFileBtn.disabled = false;
    filenameInput.value = file;
    fileInfo.textContent = `已选择: ${file}`;
    // 自动读取文件内容
    sendCommand('READ:' + file);
};
    fileList.appendChild(div);
});
}
} else {
    console.error('无法从响应中解析文件列表:', response);
}
} catch (e) {
    console.error('解析文件列表错误:', e, '响应:', response);
}
}

    function saveFile() {
    const filename = filenameInput.value.trim();
    const content = fileEditor.value;

    if (!filename) {
    alert('请输入文件名');
    return;
}
    sendCommand('SAVE:' + filename + ':' + content);
}

    function readFile() {
    const filename = filenameInput.value.trim();
    if (!filename) {
    alert('请输入文件名');
    return;
}
    sendCommand('READ:' + filename);
}

    function runFile() {
    const code = fileEditor.value;
    if (!code.trim()) {
    alert('编辑器中没有要运行的代码');
    return;
}
    log('>>> [正在运行编辑器中的代码...]', 'command');
    sendCommand(code);
}


    function deleteFile() {
    if (!currentFile) {
    alert('请先选择要删除的文件');
    return;
}

    if (confirm('确定要删除文件 ' + currentFile + ' 吗？')) {
    sendCommand('DELETE:' + currentFile);
    currentFile = null;
    filenameInput.value = '';
    fileEditor.value = '';
    fileInfo.textContent = '未选择文件';
    deleteFileBtn.disabled = true;
    setTimeout(() => sendCommand('LIST'), 500);
}
}

    function newFile() {
    document.querySelectorAll('.file-item').forEach(item => {
        item.classList.remove('selected');
    });
    currentFile = null;
    filenameInput.value = '';
    fileEditor.value = '';
    fileInfo.textContent = '新文件';
    deleteFileBtn.disabled = true;
    log('已创建新文件编辑器，输入文件名和内容后点击保存', 'output');
}

    connectBtn.addEventListener('click', connect);
    disconnectBtn.addEventListener('click', disconnect);
    sendBtn.addEventListener('click', () => {
    if (inputField.value.trim()) {
    sendCommand(inputField.value.trim());
}
});
    clearBtn.addEventListener('click', () => terminalDiv.innerHTML = '');

    listFilesBtn.addEventListener('click', () => sendCommand('LIST'));
    newFileBtn.addEventListener('click', newFile);
    deleteFileBtn.addEventListener('click', deleteFile);
    saveFileBtn.addEventListener('click', saveFile);
    readFileBtn.addEventListener('click', readFile);
    runFileBtn.addEventListener('click', runFile);

    inputField.addEventListener('keypress', function(e) {
    if (e.key === 'Enter') {
    if (inputField.value.trim()) {
    sendCommand(inputField.value.trim());
}
}
});

    updateStatus(false);

    log('欢迎使用 MicroPython Web IDE', 'output');
    log('使用方法:', 'output');
    log('1. 连接ESP32 (确保URL正确)', 'output');
    log('2. 点击"刷新文件列表"查看文件', 'output');
    log('3. 在文件列表中选择文件进行编辑', 'output');
    log('4. 点击"运行文件"执行当前编辑器中的代码', 'output');
    log('5. 在终端输入Python代码或命令', 'output');

/**
 * Android项目构建工具 - 前端交互逻辑
 */

// 全局状态
const state = {
    currentProject: null,
    currentBranch: null,
    uploadedFiles: [],
    buildStatus: 'idle' // idle, running, success, error
};

// API基础URL
const API_BASE = '';

// DOM元素
const elements = {
    // 项目相关
    projectSelect: document.getElementById('project-select'),
    branchSelect: document.getElementById('branch-select'),
    btnNewProject: document.getElementById('btn-new-project'),
    btnRefreshBranches: document.getElementById('btn-refresh-branches'),
    projectInfo: document.getElementById('project-info'),

    // 模态框
    modalNewProject: document.getElementById('modal-new-project'),
    formNewProject: document.getElementById('form-new-project'),
    btnCloseModal: document.getElementById('btn-close-modal'),
    btnCancelModal: document.getElementById('btn-cancel-modal'),

    // 文件上传
    dropZone: document.getElementById('drop-zone'),
    fileInput: document.getElementById('file-input'),
    uploadProgress: document.getElementById('upload-progress'),
    uploadPercent: document.getElementById('upload-percent'),
    uploadProgressBar: document.getElementById('upload-progress-bar'),
    uploadedFiles: document.getElementById('uploaded-files'),
    fileList: document.getElementById('file-list'),

    // 构建控制
    btnStartBuild: document.getElementById('btn-start-build'),
    btnStopBuild: document.getElementById('btn-stop-build'),
    btnClearLog: document.getElementById('btn-clear-log'),
    buildLogContainer: document.getElementById('build-log-container'),
    buildLog: document.getElementById('build-log'),
    buildResultContainer: document.getElementById('build-result-container'),
    buildResult: document.getElementById('build-result'),

    // Toast容器
    toastContainer: document.getElementById('toast-container')
};

/**
 * 显示Toast通知
 */
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `px-6 py-4 rounded-lg shadow-lg text-white transform transition-all duration-300 ${
        type === 'success' ? 'bg-green-500' :
        type === 'error' ? 'bg-red-500' :
        type === 'warning' ? 'bg-yellow-500' :
        'bg-blue-500'
    }`;
    toast.textContent = message;

    elements.toastContainer.appendChild(toast);

    // 3秒后自动移除
    setTimeout(() => {
        toast.style.opacity = '0';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

/**
 * 加载项目列表
 */
async function loadProjects() {
    try {
        const response = await fetch(`${API_BASE}/api/projects/`);
        if (!response.ok) throw new Error('加载项目列表失败');

        const projects = await response.json();

        // 清空并重新填充select
        elements.projectSelect.innerHTML = '<option value="">-- 请选择项目 --</option>';
        projects.forEach(project => {
            const option = document.createElement('option');
            option.value = project.id;
            option.textContent = project.display_name || project.name;
            elements.projectSelect.appendChild(option);
        });

        console.log(`加载了 ${projects.length} 个项目`);

    } catch (error) {
        console.error('加载项目失败:', error);
        showToast('加载项目列表失败', 'error');
    }
}

/**
 * 获取项目详情并加载分支
 */
async function loadProjectDetails(projectId) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/${projectId}`);
        if (!response.ok) throw new Error('加载项目详情失败');

        const project = await response.json();
        state.currentProject = project;

        // 显示项目信息
        elements.projectInfo.classList.remove('hidden');
        document.getElementById('info-path').textContent = project.path;
        document.getElementById('info-branch').textContent = project.current_branch || '未知';
        document.getElementById('info-commit').textContent = project.latest_commit?.short_sha || '未知';
        document.getElementById('info-status').textContent = project.is_dirty ? '有未提交更改' : '干净';

        // 启用分支选择
        elements.branchSelect.disabled = false;
        elements.btnRefreshBranches.disabled = false;

        // 加载分支列表（这里需要后端API支持）
        await loadBranches(projectId);

    } catch (error) {
        console.error('加载项目详情失败:', error);
        showToast('加载项目详情失败', 'error');
    }
}

/**
 * 加载分支列表
 */
async function loadBranches(projectId) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/${projectId}/branches`);

        if (!response.ok) {
            if (response.status === 400) {
                // 不是Git仓库
                elements.branchSelect.innerHTML = '<option value="">-- 不是Git仓库 --</option>';
                showToast('该项目不是Git仓库', 'warning');
                return;
            }
            throw new Error('加载分支列表失败');
        }

        const data = await response.json();
        const branches = data.branches || [];

        // 清空并重新填充分支选择
        elements.branchSelect.innerHTML = '';

        if (branches.length === 0) {
            elements.branchSelect.innerHTML = '<option value="">-- 无可用分支 --</option>';
        } else {
            branches.forEach(branch => {
                const option = document.createElement('option');
                option.value = branch;
                option.textContent = branch;

                // 标记当前分支
                if (branch === data.current_branch) {
                    option.textContent += ' (当前)';
                    option.selected = true;
                }

                elements.branchSelect.appendChild(option);
            });
        }

        // 更新当前分支显示
        state.currentBranch = data.current_branch;
        console.log(`加载了 ${branches.length} 个分支，当前分支: ${data.current_branch}`);

    } catch (error) {
        console.error('加载分支失败:', error);
        elements.branchSelect.innerHTML = '<option value="">-- 加载失败 --</option>';
        showToast('加载分支列表失败', 'error');
    }
}

/**
 * 创建新项目
 */
async function createProject(formData) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name: formData.name,
                alias: formData.alias || null,
                path: formData.path,
                description: formData.description || null
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '创建项目失败');
        }

        const project = await response.json();
        showToast('项目创建成功！', 'success');

        // 关闭模态框并刷新项目列表
        elements.modalNewProject.classList.add('hidden');
        elements.formNewProject.reset();
        await loadProjects();

        // 自动选中新创建的项目
        elements.projectSelect.value = project.id;
        await loadProjectDetails(project.id);

    } catch (error) {
        console.error('创建项目失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 上传文件
 */
async function uploadFile(file) {
    try {
        if (!state.currentProject) {
            showToast('请先选择项目', 'warning');
            return;
        }

        // 显示上传进度
        elements.uploadProgress.classList.remove('hidden');

        const formData = new FormData();
        formData.append('file', file);
        formData.append('project_id', state.currentProject.id);

        // 创建XMLHttpRequest以支持进度显示
        const xhr = new XMLHttpRequest();

        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percent = Math.round((e.loaded / e.total) * 100);
                elements.uploadPercent.textContent = `${percent}%`;
                elements.uploadProgressBar.style.width = `${percent}%`;
            }
        });

        xhr.addEventListener('load', () => {
            if (xhr.status === 201) {
                const result = JSON.parse(xhr.responseText);
                showToast('文件上传成功！', 'success');

                // 添加到已上传列表
                state.uploadedFiles.push(result);
                displayUploadedFiles();

                // 启用构建按钮
                elements.btnStartBuild.disabled = false;

                // 重置进度
                setTimeout(() => {
                    elements.uploadProgress.classList.add('hidden');
                    elements.uploadPercent.textContent = '0%';
                    elements.uploadProgressBar.style.width = '0%';
                }, 1000);
            } else {
                const error = JSON.parse(xhr.responseText);
                showToast(error.detail || '文件上传失败', 'error');
            }
        });

        xhr.addEventListener('error', () => {
            showToast('文件上传失败', 'error');
        });

        xhr.open('POST', `${API_BASE}/api/files/upload`);
        xhr.send(formData);

    } catch (error) {
        console.error('上传文件失败:', error);
        showToast('上传文件失败', 'error');
    }
}

/**
 * 显示已上传文件列表
 */
function displayUploadedFiles() {
    if (state.uploadedFiles.length === 0) {
        elements.uploadedFiles.classList.add('hidden');
        return;
    }

    elements.uploadedFiles.classList.remove('hidden');
    elements.fileList.innerHTML = '';

    state.uploadedFiles.forEach((file, index) => {
        const fileItem = document.createElement('div');
        fileItem.className = 'flex items-center justify-between p-3 bg-gray-50 rounded-md';
        fileItem.innerHTML = `
            <div class="flex items-center space-x-3">
                <span class="text-2xl">📦</span>
                <div>
                    <p class="text-sm font-medium text-gray-900">${file.original_filename}</p>
                    <p class="text-xs text-gray-500">${(file.file_size / 1024 / 1024).toFixed(2)} MB</p>
                </div>
            </div>
            <button onclick="removeFile(${index})" class="text-red-500 hover:text-red-700">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
            </button>
        `;
        elements.fileList.appendChild(fileItem);
    });
}

/**
 * 移除已上传文件
 */
function removeFile(index) {
    state.uploadedFiles.splice(index, 1);
    displayUploadedFiles();

    if (state.uploadedFiles.length === 0) {
        elements.btnStartBuild.disabled = true;
    }
}

/**
 * 添加构建日志
 */
function addBuildLog(message, type = 'info') {
    const logEntry = document.createElement('div');
    logEntry.className = type === 'error' ? 'text-red-400' : type === 'success' ? 'text-green-400' : 'text-gray-300';
    logEntry.textContent = `[${new Date().toLocaleTimeString()}] ${message}`;
    elements.buildLog.appendChild(logEntry);
    elements.buildLog.scrollTop = elements.buildLog.scrollHeight;
}

/**
 * 初始化事件监听器
 */
function initEventListeners() {
    // 项目选择
    elements.projectSelect.addEventListener('change', (e) => {
        if (e.target.value) {
            loadProjectDetails(e.target.value);
        } else {
            elements.projectInfo.classList.add('hidden');
            elements.branchSelect.disabled = true;
            elements.btnRefreshBranches.disabled = true;
        }
    });

    // 新建项目按钮
    elements.btnNewProject.addEventListener('click', () => {
        elements.modalNewProject.classList.remove('hidden');
    });

    // 关闭模态框
    elements.btnCloseModal.addEventListener('click', () => {
        elements.modalNewProject.classList.add('hidden');
    });

    elements.btnCancelModal.addEventListener('click', () => {
        elements.modalNewProject.classList.add('hidden');
    });

    // 新建项目表单提交
    elements.formNewProject.addEventListener('submit', async (e) => {
        e.preventDefault();
        const formData = {
            name: document.getElementById('input-project-name').value,
            alias: document.getElementById('input-project-alias').value,
            path: document.getElementById('input-project-path').value,
            description: document.getElementById('input-project-description').value
        };
        await createProject(formData);
    });

    // 拖拽上传
    elements.dropZone.addEventListener('click', () => {
        elements.fileInput.click();
    });

    elements.dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.dropZone.classList.add('border-blue-500', 'bg-blue-50');
    });

    elements.dropZone.addEventListener('dragleave', () => {
        elements.dropZone.classList.remove('border-blue-500', 'bg-blue-50');
    });

    elements.dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        elements.dropZone.classList.remove('border-blue-500', 'bg-blue-50');

        const files = e.dataTransfer.files;
        if (files.length > 0) {
            uploadFile(files[0]);
        }
    });

    elements.fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            uploadFile(e.target.files[0]);
        }
    });

    // 刷新分支
    elements.btnRefreshBranches.addEventListener('click', () => {
        if (state.currentProject) {
            loadBranches(state.currentProject.id);
        }
    });

    // 开始构建
    elements.btnStartBuild.addEventListener('click', () => {
        elements.buildLogContainer.classList.remove('hidden');
        elements.btnStartBuild.classList.add('hidden');
        elements.btnStopBuild.classList.remove('hidden');
        state.buildStatus = 'running';

        // 清空日志
        elements.buildLog.innerHTML = '';
        addBuildLog('准备开始构建...');
        addBuildLog('验证项目配置...', 'info');
        addBuildLog('检查资源包...', 'info');

        // TODO: 实现实际的构建逻辑
        setTimeout(() => {
            addBuildLog('构建功能待实现 (User Story 2)', 'warning');
        }, 1000);
    });

    // 停止构建
    elements.btnStopBuild.addEventListener('click', () => {
        elements.btnStartBuild.classList.remove('hidden');
        elements.btnStopBuild.classList.add('hidden');
        state.buildStatus = 'idle';
        addBuildLog('构建已停止', 'warning');
    });

    // 清空日志
    elements.btnClearLog.addEventListener('click', () => {
        elements.buildLog.innerHTML = '<div class="text-gray-500">日志已清空</div>';
    });
}

/**
 * 初始化应用
 */
async function init() {
    console.log('初始化Android项目构建工具...');

    // 加载项目列表
    await loadProjects();

    // 初始化事件监听器
    initEventListeners();

    console.log('初始化完成！');
}

// 页面加载完成后初始化
document.addEventListener('DOMContentLoaded', init);

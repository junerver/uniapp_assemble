/**
 * Android项目构建工具 - 前端交互逻辑
 */

// 全局状态
const state = {
    currentProject: null,
    currentBranch: null,
    uploadedFiles: [],
    buildStatus: 'idle', // idle, running, success, error
    buildTaskId: null // 当前构建任务ID
};

// 实时日志流相关
let logEventSource = null;

// API基础URL
const API_BASE = '';

// DOM元素
const elements = {
    // 项目相关
    projectSelect: document.getElementById('project-select'),
    branchSelect: document.getElementById('branch-select'),
    btnNewProject: document.getElementById('btn-new-project'),
    btnDeleteProject: document.getElementById('btn-delete-project'),
    btnRefreshBranches: document.getElementById('btn-refresh-branches'),
    btnResetWorkspace: document.getElementById('btn-reset-workspace'),
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
        document.getElementById('info-branch').textContent = '-- 加载中 --';

        // commit信息将在选择分支后由loadResourcePackages函数更新
        document.getElementById('info-commit').textContent = '-- 加载中 --';
        document.getElementById('info-commit-msg').textContent = '-- 加载中 --';
        document.getElementById('info-commit-author').textContent = '-- 加载中 --';
        document.getElementById('info-status').textContent = '-- 加载中 --';

        // 启用删除按钮和分支选择
        elements.btnDeleteProject.disabled = false;
        elements.branchSelect.disabled = false;
        elements.btnRefreshBranches.disabled = false;

        // 启用APK扫描按钮
        if (apkElements.btnScanApks) {
            apkElements.btnScanApks.disabled = false;
        }

        // 加载工作区状态
        await loadWorkspaceStatus(projectId);

        // 加载分支列表
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
        document.getElementById('info-branch').textContent = data.current_branch || '未知';
        console.log(`加载了 ${branches.length} 个分支，当前分支: ${data.current_branch}`);

        // 加载当前分支的资源包ID
        if (data.current_branch && state.currentProject) {
            await loadResourcePackages(state.currentProject.id, data.current_branch);
        }

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
 * 删除项目
 */
async function deleteProject(projectId) {
    if (!confirm('确定要删除该项目吗？此操作不可恢复！')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/projects/${projectId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '删除项目失败');
        }

        showToast('项目删除成功！', 'success');

        // 清空当前状态
        state.currentProject = null;
        state.currentBranch = null;
        elements.projectInfo.classList.add('hidden');
        elements.branchSelect.disabled = true;
        elements.btnRefreshBranches.disabled = true;
        elements.btnDeleteProject.disabled = true;

        // 禁用APK扫描按钮
        if (apkElements.btnScanApks) {
            apkElements.btnScanApks.disabled = true;
        }

        // 刷新项目列表
        await loadProjects();

    } catch (error) {
        console.error('删除项目失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 加载工作区状态
 */
async function loadWorkspaceStatus(projectId) {
    try {
        const response = await fetch(`${API_BASE}/api/projects/${projectId}/workspace-status`);

        if (!response.ok) {
            if (response.status === 400) {
                // 不是Git仓库
                document.getElementById('info-status').textContent = '-- 不是Git仓库 --';
                elements.btnResetWorkspace.classList.add('hidden');
                return;
            }
            throw new Error('加载工作区状态失败');
        }

        const data = await response.json();

        // 更新工作区状态显示
        document.getElementById('info-status').textContent = data.status_description;

        // 根据状态决定是否显示回滚按钮
        if (data.can_clean_reset === false && data.is_dirty) {
            elements.btnResetWorkspace.classList.remove('hidden');
            elements.btnResetWorkspace.disabled = false;

            // 根据状态类型设置按钮样式
            elements.btnResetWorkspace.className = data.status_type === 'dirty'
                ? 'ml-2 px-3 py-1 bg-orange-600 text-white text-xs rounded hover:bg-orange-700 transition-colors'
                : 'ml-2 px-3 py-1 bg-red-600 text-white text-xs rounded hover:bg-red-700 transition-colors';

            // 设置按钮提示信息
            elements.btnResetWorkspace.title = data.status_description;
        } else {
            elements.btnResetWorkspace.classList.add('hidden');
            elements.btnResetWorkspace.disabled = true;
        }

        console.log(`工作区状态: ${data.status_description}`);

    } catch (error) {
        console.error('加载工作区状态失败:', error);
        document.getElementById('info-status').textContent = '-- 加载失败 --';
        elements.btnResetWorkspace.classList.add('hidden');
    }
}

/**
 * 重置工作区到最新提交
 */
async function resetWorkspace(projectId) {
    if (!confirm('确定要回滚工作区吗？此操作将丢弃所有未提交的更改并删除未跟踪的文件，不可恢复！')) {
        return;
    }

    try {
        // 禁用回滚按钮，显示加载状态
        elements.btnResetWorkspace.disabled = true;
        elements.btnResetWorkspace.textContent = '🔄 回滚中...';

        const response = await fetch(`${API_BASE}/api/projects/${projectId}/reset-workspace`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '回滚失败');
        }

        const result = await response.json();

        if (result.success) {
            showToast('工作区已成功回滚到最新提交', 'success');

            // 重新加载工作区状态
            await loadWorkspaceStatus(projectId);

            // 重新加载当前分支的资源包（如果已选择分支）
            if (state.currentBranch) {
                await loadResourcePackages(projectId, state.currentBranch);
            }
        } else {
            showToast('回滚过程中出现错误', 'error');
        }

    } catch (error) {
        console.error('重置工作区失败:', error);
        showToast(error.message || '重置工作区失败', 'error');
    } finally {
        // 恢复按钮状态
        elements.btnResetWorkspace.disabled = false;
        elements.btnResetWorkspace.textContent = '🔄 回滚';
    }
}

/**
 * 加载资源包ID列表
 */
async function loadResourcePackages(projectId, branch) {
    const resourcePackagesList = document.getElementById('resource-packages-list');

    try {
        resourcePackagesList.innerHTML = '<span class="text-xs text-gray-500">加载中...</span>';

        const response = await fetch(`${API_BASE}/api/projects/${projectId}/resource-packages?branch=${encodeURIComponent(branch)}`);

        if (!response.ok) {
            throw new Error('加载资源包列表失败');
        }

        const data = await response.json();
        const packages = data.resource_packages || [];

        // 更新资源包列表显示
        if (packages.length === 0) {
            resourcePackagesList.innerHTML = '<span class="text-xs text-gray-500">该分支下无资源包</span>';
        } else {
            resourcePackagesList.innerHTML = '';
            packages.forEach(pkg => {
                const badge = document.createElement('span');
                badge.className = 'px-3 py-1 bg-blue-100 text-blue-800 text-xs rounded-full';
                badge.textContent = pkg;
                resourcePackagesList.appendChild(badge);
            });
        }

        // 更新分支的commit信息
        if (data.latest_commit) {
            document.getElementById('info-commit').textContent = data.latest_commit.short_sha || '未知';
            document.getElementById('info-commit-msg').textContent = data.latest_commit.message || '无';
            document.getElementById('info-commit-author').textContent = data.latest_commit.author || '未知';
        }

        console.log(`加载了 ${packages.length} 个资源包ID`);

    } catch (error) {
        console.error('加载资源包失败:', error);
        resourcePackagesList.innerHTML = '<span class="text-xs text-red-500">加载失败</span>';
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

        // 验证文件类型 - 支持ZIP, RAR, 7Z格式
        const fileName = file.name.toLowerCase();
        const supportedFormats = ['.zip', '.rar', '.7z'];
        const isSupported = supportedFormats.some(format => fileName.endsWith(format));

        if (!isSupported) {
            showToast('只支持ZIP、RAR、7Z格式的资源包文件！', 'error');
            return;
        }

        // 验证文件大小 (最大500MB)
        const maxSize = 500 * 1024 * 1024; // 500MB in bytes
        if (file.size > maxSize) {
            showToast(`文件大小超过限制！最大支持500MB，当前文件：${(file.size / 1024 / 1024).toFixed(2)}MB`, 'error');
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
 * 启动实时日志流
 */
function startLogStreaming(taskId) {
    if (!taskId) {
        console.error('任务ID不能为空');
        return;
    }

    // 保存任务ID
    state.buildTaskId = taskId;

    // 如果已有现有的EventSource，先关闭它
    if (logEventSource) {
        logEventSource.close();
        logEventSource = null;
    }

    try {
        // 创建EventSource连接到日志流API
        logEventSource = new EventSource(`${API_BASE}/api/builds/tasks/${taskId}/logs/stream`);

        // 监听连接建立事件
        logEventSource.addEventListener('open', () => {
            console.log('日志流连接已建立');
            addBuildLog('已连接到实时日志流', 'success');
        });

        // 监听默认的 message 事件
        logEventSource.addEventListener('message', (event) => {
            try {
                const logData = JSON.parse(event.data);
                console.log('[SSE message]:', logData);
                // 处理普通消息（如果有的话）
                if (logData.message) {
                    addBuildLog(logData.message, 'info');
                }
            } catch (error) {
                console.error('解析message事件失败:', error);
                addBuildLog(event.data, 'info');
            }
        });

        // 监听自定义的 log 事件（这是后端实际发送的日志事件）
        logEventSource.addEventListener('log', (event) => {
            try {
                const logData = JSON.parse(event.data);
                console.log('[SSE log]:', logData);

                // 处理不同类型的事件
                if (logData.type === 'heartbeat') {
                    // 心跳事件，不显示在日志中
                    console.log(`心跳: ${logData.message}`);
                    return;
                }

                if (logData.type === 'task_completed') {
                    // 任务完成事件
                    addBuildLog('任务已完成！', 'success');
                    state.buildStatus = 'success';  // 立即设置状态,避免error事件误判

                    // 延迟关闭连接,确保所有日志都已接收
                    setTimeout(() => {
                        stopLogStreaming();
                        handleBuildComplete(logData);
                    }, 500);  // 减少延迟到500ms
                    return;
                }

                if (logData.type === 'timeout') {
                    // 超时事件
                    addBuildLog(`日志流超时: ${logData.message}`, 'warning');
                    addBuildLog('任务可能仍在执行中，请手动检查任务状态', 'info');
                    stopLogStreaming(); // 停止连接，避免重新连接
                    return;
                }

                if (logData.type === 'error') {
                    // 错误事件
                    addBuildLog(`SSE错误: ${logData.error}`, 'error');

                    // 如果是致命错误，停止连接
                    if (logData.error && logData.error.includes('任务不存在')) {
                        state.buildStatus = 'error';
                        stopLogStreaming();
                    }
                    return;
                }

                if (logData.type === 'limit_reached') {
                    // 达到日志数量限制
                    addBuildLog(`达到日志数量限制: ${logData.message}`, 'warning');
                    addBuildLog('日志流已结束，请手动检查任务状态', 'info');
                    stopLogStreaming(); // 停止连接
                    return;
                }

                // 处理普通日志数据
                if (logData.message) {
                    let logType = 'info';

                    // 根据日志级别设置显示样式
                    if (logData.log_level === 'ERROR') {
                        logType = 'error';
                    } else if (logData.log_level === 'WARNING') {
                        logType = 'warning';
                    } else if (logData.log_level === 'SUCCESS' || logData.message.includes('成功') || logData.message.includes('完成')) {
                        logType = 'success';
                    }

                    // 添加日志到界面
                    addBuildLog(logData.message, logType);

                    // 如果有进度信息，更新进度显示
                    if (logData.progress !== undefined) {
                        updateBuildProgress(logData.progress, logData.message);
                    }
                }
            } catch (error) {
                console.error('解析日志数据失败:', error);
                // 如果解析失败，直接显示原始消息
                addBuildLog(event.data, 'info');
            }
        });

        // 监听连接关闭事件
        logEventSource.addEventListener('error', (event) => {
            console.error('日志流连接错误:', event);

            // 只有在任务仍在运行时才尝试重新连接
            if (state.buildStatus === 'running') {
                addBuildLog('日志流连接中断，尝试重新连接...', 'warning');

                setTimeout(() => {
                    if (state.buildTaskId === taskId && state.buildStatus === 'running') {
                        console.log('尝试重新连接日志流...');
                        startLogStreaming(taskId);
                    }
                }, 3000); // 3秒后重试
            } else {
                console.log('任务已结束，不重新连接日志流');
            }
        });

        // 监听自定义的连接事件
        logEventSource.addEventListener('connected', (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('SSE连接已建立:', data.message);
                addBuildLog(data.message || '已连接到实时日志流', 'success');
            } catch (error) {
                console.log('SSE连接已建立');
                addBuildLog('已连接到实时日志流', 'success');
            }
        });

        // 监听自定义的状态事件
        logEventSource.addEventListener('status', (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log(`任务状态更新: ${data.status} (${data.progress}%)`);

                // 更新构建状态
                if (data.status === 'completed') {
                    state.buildStatus = 'success';
                } else if (data.status === 'failed') {
                    state.buildStatus = 'error';
                }

                if (data.progress !== undefined) {
                    updateBuildProgress(data.progress, `任务状态: ${data.status}`);
                }
            } catch (error) {
                console.error('解析状态事件失败:', error);
            }
        });

        // 监听自定义的完成事件
        logEventSource.addEventListener('completed', (event) => {
            try {
                const data = JSON.parse(event.data);
                console.log('收到任务完成事件:', data);
                addBuildLog('任务已完成！', 'success');

                // 根据最终状态判断是成功还是失败
                const isSuccess = data.status === 'completed' || data.status === 'success';

                if (data.final) {
                    // 立即设置状态,避免error事件误判为连接中断
                    state.buildStatus = isSuccess ? 'success' : 'error';

                    // 延迟关闭连接,确保所有日志都已接收
                    setTimeout(() => {
                        stopLogStreaming();

                        if (isSuccess) {
                            handleBuildComplete(data);
                        } else {
                            handleBuildFailed(data);
                        }
                    }, 500); // 减少延迟到500ms
                }
            } catch (error) {
                console.error('解析完成事件失败:', error);
            }
        });

        // 监听自定义的错误事件
        logEventSource.addEventListener('error', (event) => {
            try {
                // 检查event.data是否存在，如果不存在则是原生error事件
                if (event.data) {
                    const data = JSON.parse(event.data);
                    addBuildLog(`SSE错误: ${data.error}`, 'error');

                    // 如果是严重错误，停止连接
                    if (data.error && data.error.includes('任务不存在')) {
                        state.buildStatus = 'error';
                        stopLogStreaming();
                    }
                } else {
                    // 原生error事件，没有具体数据
                    addBuildLog('SSE连接发生错误', 'warning');
                }
            } catch (error) {
                console.error('解析错误事件失败:', error);
                addBuildLog('SSE错误事件解析失败', 'warning');
            }
        });

        // 监听自定义的超时事件
        logEventSource.addEventListener('timeout', (event) => {
            try {
                const data = JSON.parse(event.data);
                addBuildLog(`日志流超时: ${data.message}`, 'warning');
                addBuildLog('任务可能仍在执行中，请手动检查任务状态', 'info');
                stopLogStreaming(); // 停止连接，避免重新连接
            } catch (error) {
                console.error('解析超时事件失败:', error);
            }
        });

        // 监听自定义的限制事件
        logEventSource.addEventListener('limit_reached', (event) => {
            try {
                const data = JSON.parse(event.data);
                addBuildLog(`达到日志数量限制: ${data.message}`, 'warning');
                addBuildLog('日志流已结束，请手动检查任务状态', 'info');
                stopLogStreaming(); // 停止连接
            } catch (error) {
                console.error('解析限制事件失败:', error);
            }
        });

    } catch (error) {
        console.error('创建日志流连接失败:', error);
        addBuildLog(`创建日志流连接失败: ${error.message}`, 'error');
    }
}

/**
 * 停止日志流
 */
function stopLogStreaming() {
    if (logEventSource) {
        console.log('正在关闭SSE连接...');
        logEventSource.close();
        logEventSource = null;
        console.log('日志流已停止');
    }

    // 清空任务ID
    state.buildTaskId = null;

    // 强制设置状态为非运行状态
    state.buildStatus = 'idle';
    console.log('构建状态已重置为: idle');
}

/**
 * 更新构建进度
 */
function updateBuildProgress(progress, message) {
    // 更新进度条（如果有）
    const progressBar = document.getElementById('build-progress-bar');
    if (progressBar) {
        progressBar.style.width = `${progress}%`;
    }

    // 更新进度文本（如果有）
    const progressText = document.getElementById('build-progress-text');
    if (progressText) {
        progressText.textContent = `${progress}% - ${message}`;
    }
}

/**
 * 处理构建完成
 */
function handleBuildComplete(result) {
    console.log('构建完成:', result);

    // 确保状态被正确设置
    state.buildStatus = 'success';

    addBuildLog('构建任务完成！', 'success');

    // 自动扫描APK文件
    setTimeout(() => {
        if (state.currentProject) {
            scanApkFiles();
        }
    }, 1000);

    // 显示基本构建结果
    if (elements.buildResult) {
        elements.buildResult.classList.remove('hidden');
        elements.buildResult.innerHTML = `
            <div class="p-4 bg-green-50 border border-green-200 rounded-md">
                <h4 class="text-green-800 font-semibold mb-2">🎉 构建完成</h4>
                <div class="text-sm text-green-700">
                    <p>任务ID: ${result.task_id || 'unknown'}</p>
                    <p>最终状态: ${result.status || 'completed'}</p>
                    ${result.build_time ? `<p>⏱️ 构建时间: ${result.build_time}秒</p>` : ''}
                    ${result.artifacts ? `<p>📦 构建产物: ${result.artifacts.length} 个</p>` : ''}
                    ${result.artifacts && result.artifacts.length > 0 ?
                        `<div class="mt-2">
                            <p class="font-medium">生成的文件:</p>
                            <ul class="list-disc list-inside text-xs">
                                ${result.artifacts.map(artifact => `<li>${artifact.name || artifact}</li>`).join('')}
                            </ul>
                        </div>` : ''}
                </div>
            </div>

            <!-- APK下载区域 -->
            <div id="apk-download-section" class="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-md">
                <h4 class="text-blue-800 font-semibold mb-3">📱 APK文件管理</h4>
                <div id="apk-download-list">
                    <div class="text-center text-gray-500">
                        <div class="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                        <p class="mt-2">正在加载APK信息...</p>
                    </div>
                </div>
            </div>
        `;
    }

    // 恢复UI状态
    if (elements.btnStartBuild) {
        elements.btnStartBuild.classList.remove('hidden');
    }
    if (elements.btnStopBuild) {
        elements.btnStopBuild.classList.add('hidden');
    }

    // 加载并显示构建结果
    if (result.task_id) {
        loadBuildResults(result.task_id);
    }

    // 显示成功通知
    showToast('构建任务完成！正在自动扫描APK文件...', 'success');
}

/**
 * 加载构建结果
 */
async function loadBuildResults(taskId) {
    try {
        const response = await fetch(`${API_BASE}/api/results/tasks/${taskId}/results`);

        if (!response.ok) {
            console.error('加载构建结果失败:', response.status);
            return;
        }

        const resultsData = await response.json();
        displayBuildResults(resultsData);

    } catch (error) {
        console.error('加载构建结果失败:', error);
        // 即使加载失败，也要移除加载状态
        const downloadSection = document.getElementById('apk-download-section');
        if (downloadSection) {
            downloadSection.innerHTML = `
                <div class="text-center text-gray-500">
                    <p>加载构建结果失败</p>
                </div>
            `;
        }
    }
}

/**
 * 显示构建结果
 */
function displayBuildResults(resultsData) {
    const downloadSection = document.getElementById('apk-download-section');
    if (!downloadSection) return;

    if (resultsData.results.length === 0) {
        downloadSection.innerHTML = `
            <div class="text-center text-gray-500">
                <p>暂无构建产物</p>
            </div>
        `;
        return;
    }

    // 按文件类型分组
    const apks = resultsData.results.filter(r => r.file_type === 'apk');
    const logs = resultsData.results.filter(r => r.file_type === 'log');
    const metadata = resultsData.results.filter(r => r.file_type === 'metadata');

    let html = '';

    // APK文件部分
    if (apks.length > 0) {
        html += `
            <div class="mb-4">
                <h5 class="text-lg font-medium text-gray-900 mb-2">📱 APK文件 (${apks.length})</h5>
                <div class="grid grid-cols-1 gap-2">
                    ${apks.map(apk => createBuildResultItem(apk, 'apk')).join('')}
                </div>
            </div>
        `;
    }

    // 日志文件部分
    if (logs.length > 0) {
        html += `
            <div class="mb-4">
                <h5 class="text-lg font-medium text-gray-900 mb-2">📄 构建日志 (${logs.length})</h5>
                <div class="grid grid-cols-1 gap-2">
                    ${logs.map(log => createBuildResultItem(log, 'log')).join('')}
                </div>
            </div>
        `;
    }

    // 元数据文件部分
    if (metadata.length > 0) {
        html += `
            <div class="mb-4">
                <h5 class="text-lg font-medium text-gray-900 mb-2">📋 元数据 (${metadata.length})</h5>
                <div class="grid grid-cols-1 gap-2">
                    ${metadata.map(meta => createBuildResultItem(meta, 'metadata')).join('')}
                </div>
            </div>
        `;
    }

    // 统计信息
    html += `
        <div class="mt-4 pt-4 border-t border-gray-200 text-sm text-gray-600">
            <div class="flex justify-between">
                <span>总文件数: ${resultsData.total_count}</span>
                <span>总大小: ${formatFileSize(resultsData.total_size)}</span>
            </div>
        </div>
    `;

    downloadSection.innerHTML = html;
}

/**
 * 创建构建结果项
 */
function createBuildResultItem(result, type) {
    const fileIcon = getFileIcon(type);
    const actionButton = getActionButton(result, type);

    return `
        <div class="flex items-center justify-between p-3 bg-white rounded border border-gray-200 hover:border-gray-300 transition-colors">
            <div class="flex items-center space-x-3">
                <span class="text-2xl">${fileIcon}</span>
                <div>
                    <p class="text-sm font-medium text-gray-900">${result.filename}</p>
                    <div class="flex items-center space-x-4 mt-1">
                        <span class="text-xs text-gray-500">${formatFileSize(result.file_size)}</span>
                        ${result.file_hash ? `<span class="text-xs text-gray-400">SHA256: ${result.file_hash.substring(0, 12)}...</span>` : ''}
                        ${result.created_at ? `<span class="text-xs text-gray-400">${formatTimestamp(new Date(result.created_at).getTime() / 1000)}</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="flex items-center space-x-2">
                ${actionButton}
            </div>
        </div>
    `;
}

/**
 * 获取文件图标
 */
function getFileIcon(type) {
    switch (type) {
        case 'apk': return '📱';
        case 'log': return '📄';
        case 'metadata': return '📋';
        default: return '📁';
    }
}

/**
 * 获取操作按钮
 */
function getActionButton(result, type) {
    if (type === 'apk') {
        return `
            <button onclick="downloadBuildResult('${result.id}')"
                    class="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors"
                    title="下载APK">
                ⬇️ 下载
            </button>
            ${result.metadata && result.metadata.package_info ? `
                <button onclick="showApkInfo('${result.id}')"
                        class="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
                        title="查看APK信息">
                    📋 详情
                </button>
            ` : ''}
        `;
    } else {
        return `
            <button onclick="downloadBuildResult('${result.id}')"
                    class="px-3 py-1 bg-gray-600 text-white text-sm rounded hover:bg-gray-700 transition-colors"
                    title="下载文件">
                ⬇️ 下载
            </button>
        `;
    }
}

/**
 * 下载构建结果
 */
function downloadBuildResult(fileId) {
    // 创建下载链接
    const link = document.createElement('a');
    link.href = `${API_BASE}/api/results/files/${fileId}/download`;
    link.target = '_blank';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('开始下载文件', 'success');
}

/**
 * 显示APK详细信息
 */
async function showApkInfo(fileId) {
    try {
        showToast('正在加载APK信息...', 'info');

        const response = await fetch(`${API_BASE}/api/results/tasks/${state.buildTaskId}/apks/${fileId}/info`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '获取APK信息失败');
        }

        const apkInfo = await response.json();

        // 显示详情模态框
        displayApkDetails(apkInfo);
        apkElements.modalApkDetails.classList.remove('hidden');

    } catch (error) {
        console.error('获取APK信息失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 处理构建失败
 */
function handleBuildFailed(error) {
    console.error('构建失败:', error);

    // 确保状态被正确设置
    state.buildStatus = 'error';

    addBuildLog('构建任务失败！', 'error');

    // 从SSE完成事件中获取完整的任务详情
    if (state.buildTaskId) {
        // 获取完整的任务详情以显示错误信息
        fetch(`${API_BASE}/api/builds/tasks/${state.buildTaskId}`)
            .then(response => response.json())
            .then(taskDetails => {
                // 显示详细的错误结果
                if (elements.buildResult) {
                    elements.buildResult.classList.remove('hidden');
                    elements.buildResult.innerHTML = `
                        <div class="p-4 bg-red-50 border border-red-200 rounded-md">
                            <h4 class="text-red-800 font-semibold mb-2">构建失败</h4>
                            <div class="text-sm text-red-700">
                                <p>任务ID: ${taskDetails.id || '未知'}</p>
                                <p>错误信息: ${taskDetails.error_message || taskDetails.error || '未知错误'}</p>
                                <p>失败原因: ${taskDetails.error_message ? '请查看具体错误信息' : '请查看日志了解详细信息'}</p>
                                <p>资源包: ${taskDetails.resource_package_path || '未知'}</p>
                                <p>Git分支: ${taskDetails.git_branch || '未知'}</p>
                            </div>
                        </div>
                    `;
                }
            })
            .catch(err => {
                console.error('获取任务详情失败:', err);
                // 如果无法获取详情，使用传入的错误信息
                if (elements.buildResult) {
                    elements.buildResult.classList.remove('hidden');
                    elements.buildResult.innerHTML = `
                        <div class="p-4 bg-red-50 border border-red-200 rounded-md">
                            <h4 class="textred-800 font-semibold mb-2">构建失败</h4>
                            <div class="text-sm text-red-700">
                                <p>任务ID: ${error.task_id || '未知'}</p>
                                <p>错误信息: ${error.error || error.message || '未知错误'}</p>
                                <p>失败原因: ${error.reason || '请查看日志了解详细信息'}</p>
                            </div>
                        </div>
                    `;
                }
            });
    } else {
        // 如果没有任务ID，直接使用传入的错误信息
        if (elements.buildResult) {
            elements.buildResult.classList.remove('hidden');
            elements.buildResult.innerHTML = `
                <div class="p-4 bg-red-50 border border-red-200 rounded-md">
                    <h4 class="text-red-800 font-semibold mb-2">构建失败</h4>
                    <div class="text-sm text-red-700">
                        <p>任务ID: ${error.task_id || '未知'}</p>
                        <p>错误信息: ${error.error || error.message || '未知错误'}</p>
                        <p>失败原因: ${error.reason || '请查看日志了解详细信息'}</p>
                    </div>
                </div>
            `;
        }
    }

    // 恢复UI状态
    if (elements.btnStartBuild) {
        elements.btnStartBuild.classList.remove('hidden');
    }
    if (elements.btnStopBuild) {
        elements.btnStopBuild.classList.add('hidden');
    }

    // 显示失败通知
    showToast('构建任务失败！', 'error');
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
            elements.btnDeleteProject.disabled = true;
        }
    });

    // 删除项目按钮
    elements.btnDeleteProject.addEventListener('click', () => {
        if (state.currentProject) {
            deleteProject(state.currentProject.id);
        }
    });

    // 回滚工作区按钮
    elements.btnResetWorkspace.addEventListener('click', () => {
        if (state.currentProject) {
            resetWorkspace(state.currentProject.id);
        }
    });

    // 分支切换
    elements.branchSelect.addEventListener('change', (e) => {
        const selectedBranch = e.target.value;
        if (selectedBranch && state.currentProject) {
            state.currentBranch = selectedBranch;
            // 更新当前分支显示
            document.getElementById('info-branch').textContent = selectedBranch;
            // 重新加载工作区状态
            loadWorkspaceStatus(state.currentProject.id);
            // 加载新分支的资源包ID
            loadResourcePackages(state.currentProject.id, selectedBranch);
            // 同步Git分支选择并刷新提交历史（用于回滚）
            loadGitBranches();
            loadCommitHistory();
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
    elements.btnStartBuild.addEventListener('click', async () => {
        if (!state.currentProject || !state.currentBranch || state.uploadedFiles.length === 0) {
            showToast('请先选择项目、分支并上传资源包', 'warning');
            return;
        }

        try {
            elements.buildLogContainer.classList.remove('hidden');
            elements.btnStartBuild.classList.add('hidden');
            elements.btnStopBuild.classList.remove('hidden');
            state.buildStatus = 'running';

            // 清空日志
            elements.buildLog.innerHTML = '';
            addBuildLog('准备开始构建...');

            // 1. 验证构建环境
            addBuildLog('验证构建环境...', 'info');
            const validationResponse = await fetch(`${API_BASE}/api/projects/${state.currentProject.id}/build-validation`);
            const validation = await validationResponse.json();

            if (!validation.valid) {
                throw new Error(`构建环境验证失败: ${validation.issues.join(', ')}`);
            }

            addBuildLog('构建环境验证通过', 'success');

            // 2. 创建构建任务 (包含资源替换和Gradle构建)
            addBuildLog('创建构建任务...', 'info');
            const taskResponse = await fetch(`${API_BASE}/api/builds/tasks`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    project_id: state.currentProject.id,
                    task_type: 'build', // 完整构建流程: 资源替换 + Gradle构建
                    git_branch: state.currentBranch,
                    resource_package_path: state.uploadedFiles[0].file_path,
                    config_options: {
                        // 资源替换配置
                        replace_mode: 'overwrite',

                        // Gradle构建配置
                        build_type: 'clean :app:assembleRelease',
                        parallel: true,
                        daemon: true,
                        stacktrace: true,
                        info: false,

                        // 超时设置 (30分钟)
                        timeout_minutes: 30
                    }
                })
            });

            if (!taskResponse.ok) {
                const error = await taskResponse.json();
                throw new Error(error.detail || '创建构建任务失败');
            }

            const task = await taskResponse.json();
            addBuildLog(`构建任务创建成功: ${task.id}`, 'success');

            // 3. 开始执行构建
            addBuildLog('开始执行构建...', 'info');
            const startResponse = await fetch(`${API_BASE}/api/builds/tasks/${task.id}/start`, {
                method: 'POST'
            });

            if (!startResponse.ok) {
                const error = await startResponse.json();
                throw new Error(error.detail || '启动构建任务失败');
            }

            addBuildLog('构建任务已启动', 'success');

            // 4. 启动实时日志流
            startLogStreaming(task.id);

        } catch (error) {
            console.error('构建失败:', error);
            addBuildLog(`构建失败: ${error.message}`, 'error');

            // 恢复UI状态
            elements.btnStartBuild.classList.remove('hidden');
            elements.btnStopBuild.classList.add('hidden');
            state.buildStatus = 'idle';

            showToast('构建失败: ' + error.message, 'error');
        }
    });

    // 停止构建
    elements.btnStopBuild.addEventListener('click', async () => {
        if (!state.buildTaskId) {
            showToast('没有正在运行的构建任务', 'warning');
            return;
        }

        try {
            addBuildLog('正在停止构建任务...', 'info');

            const response = await fetch(`${API_BASE}/api/builds/tasks/${state.buildTaskId}/cancel`, {
                method: 'POST'
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || '停止构建任务失败');
            }

            addBuildLog('构建任务已停止', 'warning');

            // 停止日志流
            stopLogStreaming();

            // 恢复UI状态
            elements.btnStartBuild.classList.remove('hidden');
            elements.btnStopBuild.classList.add('hidden');
            state.buildStatus = 'idle';

            showToast('构建任务已停止', 'info');

        } catch (error) {
            console.error('停止构建失败:', error);
            addBuildLog(`停止构建失败: ${error.message}`, 'error');
            showToast('停止构建失败: ' + error.message, 'error');
        }
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

// 页面卸载时清理资源
window.addEventListener('beforeunload', () => {
    stopLogStreaming();
});

// ===== APK管理功能 =====

// APK相关状态
const apkState = {
    apkList: [],
    currentFilter: '',
    currentSort: 'modified_time',
    buildVariants: []
};

// APK相关DOM元素
const apkElements = {
    // APK管理
    btnScanApks: document.getElementById('btn-scan-apks'),
    btnApkSettings: document.getElementById('btn-apk-settings'),
    apkManagementContainer: document.getElementById('apk-management-container'),

    // APK统计
    apkCount: document.getElementById('apk-count'),
    apkTotalSize: document.getElementById('apk-total-size'),
    apkVariants: document.getElementById('apk-variants'),
    apkLatestTime: document.getElementById('apk-latest-time'),

    // APK筛选和排序
    apkVariantFilter: document.getElementById('apk-variant-filter'),
    apkSortBy: document.getElementById('apk-sort-by'),
    btnRefreshApks: document.getElementById('btn-refresh-apks'),

    // APK列表
    apkLoading: document.getElementById('apk-loading'),
    apkList: document.getElementById('apk-list'),
    apkEmpty: document.getElementById('apk-empty'),

    // APK详情模态框
    modalApkDetails: document.getElementById('modal-apk-details'),
    btnCloseApkModal: document.getElementById('btn-close-apk-modal'),
    apkDetailsContent: document.getElementById('apk-details-content'),

    // APK比较模态框
    modalApkCompare: document.getElementById('modal-apk-compare'),
    btnCloseCompareModal: document.getElementById('btn-close-compare-modal'),
    compareApk1: document.getElementById('compare-apk1'),
    compareApk2: document.getElementById('compare-apk2'),
    btnStartCompare: document.getElementById('btn-start-compare'),
    apkCompareResult: document.getElementById('apk-compare-result')
};

/**
 * 格式化文件大小
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * 格式化时间戳
 */
function formatTimestamp(timestamp) {
    if (!timestamp) return '-';
    const date = new Date(timestamp * 1000);
    return date.toLocaleString('zh-CN');
}

/**
 * 扫描APK文件
 */
async function scanApkFiles() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    try {
        // 显示加载状态
        apkElements.apkLoading.classList.remove('hidden');
        apkElements.apkList.classList.add('hidden');
        apkElements.apkEmpty.classList.add('hidden');

        // 执行扫描
        const response = await fetch(`${API_BASE}/api/apks/projects/${state.currentProject.id}/apks`, {
            method: 'GET'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '扫描APK文件失败');
        }

        const result = await response.json();
        apkState.apkList = result.apk_files || [];

        // 更新统计信息
        updateApkStats(result);

        // 更新构建变体筛选器
        updateApkVariantFilter();

        // 显示APK列表
        displayApkList();

        // 更新步骤指示器
        updateStepIndicator(4, 'completed');

        showToast(`扫描完成，找到 ${result.total_count} 个APK文件`, 'success');

    } catch (error) {
        console.error('扫描APK文件失败:', error);
        showToast(error.message, 'error');

        // 显示空状态
        apkElements.apkLoading.classList.add('hidden');
        apkElements.apkEmpty.classList.remove('hidden');
    }
}

/**
 * 更新APK统计信息
 */
function updateApkStats(result) {
    apkElements.apkCount.textContent = result.total_count || 0;
    apkElements.apkTotalSize.textContent = formatFileSize(result.total_size || 0);

    // 计算构建变体数量
    const variants = new Set();
    apkState.apkList.forEach(apk => {
        if (apk.build_variant) {
            variants.add(apk.build_variant);
        }
    });
    apkElements.apkVariants.textContent = variants.size;

    // 显示最新构建时间
    if (apkState.apkList.length > 0) {
        const latestApk = apkState.apkList.reduce((latest, apk) => {
            return (apk.modified_time > latest.modified_time) ? apk : latest;
        });
        apkElements.apkLatestTime.textContent = formatTimestamp(latestApk.modified_time);
    } else {
        apkElements.apkLatestTime.textContent = '-';
    }
}

/**
 * 更新APK构建变体筛选器
 */
function updateApkVariantFilter() {
    const variants = new Set();
    apkState.apkList.forEach(apk => {
        if (apk.build_variant) {
            variants.add(apk.build_variant);
        }
    });

    apkElements.apkVariantFilter.innerHTML = '<option value="">所有构建变体</option>';
    Array.from(variants).sort().forEach(variant => {
        const option = document.createElement('option');
        option.value = variant;
        option.textContent = variant;
        apkElements.apkVariantFilter.appendChild(option);
    });
}

/**
 * 显示APK列表
 */
function displayApkList() {
    // 隐藏加载状态
    apkElements.apkLoading.classList.add('hidden');

    // 如果没有APK文件，显示空状态
    if (apkState.apkList.length === 0) {
        apkElements.apkEmpty.classList.remove('hidden');
        apkElements.apkList.classList.add('hidden');
        return;
    }

    // 显示APK列表
    apkElements.apkEmpty.classList.add('hidden');
    apkElements.apkList.classList.remove('hidden');
    apkElements.apkList.innerHTML = '';

    // 应用筛选和排序
    let filteredApks = filterAndSortApks();

    // 生成APK列表HTML
    filteredApks.forEach(apk => {
        const apkItem = createApkItem(apk);
        apkElements.apkList.appendChild(apkItem);
    });
}

/**
 * 创建APK列表项
 */
function createApkItem(apk) {
    const item = document.createElement('div');
    item.className = 'bg-gray-50 rounded-lg p-4 hover:bg-gray-100 transition-colors';

    // 获取构建变体标签样式
    const variantColor = getVariantColor(apk.build_variant);

    // 对文件路径进行Base64编码，避免HTML属性转义问题
    const encodedPath = encodeBase64(apk.file_path);

    item.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex items-center space-x-4">
                <div class="text-3xl">📱</div>
                <div>
                    <h3 class="text-lg font-medium text-gray-900">${apk.file_name}</h3>
                    <div class="flex items-center space-x-4 mt-1">
                        <span class="text-sm text-gray-500">${formatFileSize(apk.file_size)}</span>
                        <span class="px-2 py-1 text-xs rounded-full ${variantColor}">${apk.build_variant || 'unknown'}</span>
                        <span class="text-sm text-gray-400">${formatTimestamp(apk.modified_time)}</span>
                    </div>
                    ${apk.package_info ? `
                        <div class="text-xs text-gray-600 mt-1">
                            包名: ${apk.package_info.package_name || '未知'} |
                            版本: ${apk.package_info.version_name || apk.package_info.version_code || '未知'}
                        </div>
                    ` : ''}
                </div>
            </div>
            <div class="flex items-center space-x-2">
                <button data-encodedpath="${encodedPath}" onclick="showApkDetails(this.dataset.encodedpath)" class="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors" title="查看详情">
                    📋 详情
                </button>
                <button data-encodedpath="${encodedPath}" onclick="addToCompare(this.dataset.encodedpath)" class="px-3 py-1 bg-purple-600 text-white text-sm rounded hover:bg-purple-700 transition-colors" title="添加到比较">
                    ⚖️ 比较
                </button>
                <button data-encodedpath="${encodedPath}" onclick="downloadApkEncoded(this.dataset.encodedpath)" class="px-3 py-1 bg-green-600 text-white text-sm rounded hover:bg-green-700 transition-colors" title="下载APK">
                    ⬇️ 下载
                </button>
            </div>
        </div>
    `;

    return item;
}

/**
 * 获取构建变体标签颜色
 */
function getVariantColor(variant) {
    if (!variant) return 'bg-gray-100 text-gray-800';

    const variantLower = variant.toLowerCase();
    if (variantLower.includes('debug')) return 'bg-orange-100 text-orange-800';
    if (variantLower.includes('release')) return 'bg-green-100 text-green-800';
    if (variantLower.includes('staging')) return 'bg-blue-100 text-blue-800';
    if (variantLower.includes('prod')) return 'bg-purple-100 text-purple-800';

    return 'bg-gray-100 text-gray-800';
}

/**
 * 筛选和排序APK列表
 */
function filterAndSortApks() {
    let filtered = [...apkState.apkList];

    // 应用构建变体筛选
    const variantFilter = apkElements.apkVariantFilter.value;
    if (variantFilter) {
        filtered = filtered.filter(apk => apk.build_variant === variantFilter);
    }

    // 应用排序
    const sortBy = apkElements.apkSortBy.value;
    filtered.sort((a, b) => {
        switch (sortBy) {
            case 'file_size':
                return b.file_size - a.file_size;
            case 'file_name':
                return a.file_name.localeCompare(b.file_name);
            case 'build_variant':
                return (a.build_variant || '').localeCompare(b.build_variant || '');
            case 'modified_time':
            default:
                return b.modified_time - a.modified_time;
        }
    });

    return filtered;
}

/**
 * 显示APK详情（接收Base64编码的路径）
 */
async function showApkDetails(encodedPath) {
    try {
        showToast('正在加载APK详情...', 'info');

        // 解码Base64路径
        const apkFilePath = decodeBase64(encodedPath);
        if (!apkFilePath) {
            showToast('文件路径解码失败', 'error');
            return;
        }

        const response = await fetch(`${API_BASE}/api/apks/files/${encodeURIComponent(apkFilePath)}/info`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '获取APK详情失败');
        }

        const apkInfo = await response.json();

        // 显示详情模态框
        displayApkDetails(apkInfo);
        apkElements.modalApkDetails.classList.remove('hidden');

    } catch (error) {
        console.error('获取APK详情失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 显示APK详情内容
 */
function displayApkDetails(apkInfo) {
    const content = apkElements.apkDetailsContent;

    content.innerHTML = `
        <!-- 基本信息 -->
        <div class="bg-gray-50 rounded-lg p-4">
            <h4 class="text-lg font-semibold text-gray-900 mb-3">基本信息</h4>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span class="text-gray-600">文件名:</span>
                    <span class="text-gray-900 ml-2">${apkInfo.file_name}</span>
                </div>
                <div>
                    <span class="text-gray-600">文件大小:</span>
                    <span class="text-gray-900 ml-2">${formatFileSize(apkInfo.file_size)}</span>
                </div>
                <div>
                    <span class="text-gray-600">构建变体:</span>
                    <span class="text-gray-900 ml-2">${apkInfo.build_variant || '未知'}</span>
                </div>
                <div>
                    <span class="text-gray-600">文件哈希:</span>
                    <span class="text-gray-900 ml-2 font-mono text-xs">${apkInfo.file_hash.substring(0, 16)}...</span>
                </div>
                <div>
                    <span class="text-gray-600">修改时间:</span>
                    <span class="text-gray-900 ml-2">${formatTimestamp(apkInfo.modified_time)}</span>
                </div>
                <div>
                    <span class="text-gray-600">创建时间:</span>
                    <span class="text-gray-900 ml-2">${formatTimestamp(apkInfo.created_time)}</span>
                </div>
            </div>
        </div>

        ${apkInfo.package_info ? `
            <!-- 包信息 -->
            <div class="bg-blue-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">包信息</h4>
                <div class="grid grid-cols-2 gap-4 text-sm">
                    <div>
                        <span class="text-gray-600">包名:</span>
                        <span class="text-gray-900 ml-2 font-mono">${apkInfo.package_info.package_name || '未知'}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">版本号:</span>
                        <span class="text-gray-900 ml-2">${apkInfo.package_info.version_code || '未知'}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">版本名:</span>
                        <span class="text-gray-900 ml-2">${apkInfo.package_info.version_name || '未知'}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">目标SDK:</span>
                        <span class="text-gray-900 ml-2">${apkInfo.package_info.target_sdk || '未知'}</span>
                    </div>
                </div>
            </div>
        ` : ''}

        ${apkInfo.permissions && apkInfo.permissions.length > 0 ? `
            <!-- 权限信息 -->
            <div class="bg-yellow-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">权限 (${apkInfo.permissions.length})</h4>
                <div class="max-h-40 overflow-y-auto">
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        ${apkInfo.permissions.map(permission => `
                            <div class="text-gray-700 font-mono text-xs truncate" title="${permission}">
                                ${permission}
                            </div>
                        `).join('')}
                    </div>
                </div>
            </div>
        ` : ''}

        ${apkInfo.activities && apkInfo.activities.length > 0 ? `
            <!-- 组件信息 -->
            <div class="bg-purple-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">组件信息</h4>
                <div class="grid grid-cols-3 gap-4 text-sm">
                    <div>
                        <span class="text-gray-600">Activity:</span>
                        <span class="text-gray-900 ml-2">${apkInfo.activities.length}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">Service:</span>
                        <span class="text-gray-900 ml-2">${apkInfo.services.length}</span>
                    </div>
                    <div>
                        <span class="text-gray-600">Receiver:</span>
                        <span class="text-gray-900 ml-2">${(apkInfo.package_info?.receivers || []).length}</span>
                    </div>
                </div>
            </div>
        ` : ''}

        ${apkInfo.native_libs && apkInfo.native_libs.length > 0 ? `
            <!-- 原生库信息 -->
            <div class="bg-green-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">原生库 (${apkInfo.native_libs.length})</h4>
                <div class="space-y-2 text-sm max-h-40 overflow-y-auto">
                    ${apkInfo.native_libs.map(lib => `
                        <div class="flex justify-between">
                            <span class="text-gray-700">${lib.name}</span>
                            <span class="text-gray-500">${lib.architecture} (${formatFileSize(lib.size)})</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}

        ${apkInfo.analysis_error ? `
            <!-- 分析错误 -->
            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-red-900 mb-2">分析警告</h4>
                <p class="text-sm text-red-700">${apkInfo.analysis_error}</p>
            </div>
        ` : ''}
    `;
}

/**
 * 添加APK到比较列表（接收Base64编码的路径）
 */
function addToCompare(encodedPath) {
    // 解码Base64路径
    const apkFilePath = decodeBase64(encodedPath);
    if (!apkFilePath) {
        showToast('文件路径解码失败', 'error');
        return;
    }

    // 打开比较模态框
    openCompareModal();

    // 填充比较选项
    updateCompareOptions();

    // 自动选择该APK
    if (!apkElements.compareApk1.value) {
        apkElements.compareApk1.value = apkFilePath;
    } else if (!apkElements.compareApk2.value && apkElements.compareApk1.value !== apkFilePath) {
        apkElements.compareApk2.value = apkFilePath;
    }

    updateCompareButton();
}

/**
 * 打开比较模态框
 */
function openCompareModal() {
    apkElements.modalApkCompare.classList.remove('hidden');
    updateCompareOptions();
}

/**
 * 更新比较选项
 */
function updateCompareOptions() {
    const apk1 = apkElements.compareApk1;
    const apk2 = apkElements.compareApk2;

    // 保存当前选择
    const currentValue1 = apk1.value;
    const currentValue2 = apk2.value;

    // 清空并重新填充
    apk1.innerHTML = '<option value="">选择APK文件</option>';
    apk2.innerHTML = '<option value="">选择APK文件</option>';

    apkState.apkList.forEach(apk => {
        const option1 = document.createElement('option');
        option1.value = apk.file_path;
        option1.textContent = `${apk.file_name} (${apk.build_variant})`;
        if (apk.file_path === currentValue1) option1.selected = true;
        apk1.appendChild(option1);

        const option2 = document.createElement('option');
        option2.value = apk.file_path;
        option2.textContent = `${apk.file_name} (${apk.build_variant})`;
        if (apk.file_path === currentValue2) option2.selected = true;
        apk2.appendChild(option2);
    });
}

/**
 * 更新比较按钮状态
 */
function updateCompareButton() {
    const apk1 = apkElements.compareApk1.value;
    const apk2 = apkElements.compareApk2.value;

    apkElements.btnStartCompare.disabled = !apk1 || !apk2 || apk1 === apk2;
}

/**
 * 开始APK比较
 */
async function startApkCompare() {
    const apk1 = apkElements.compareApk1.value;
    const apk2 = apkElements.compareApk2.value;

    if (!apk1 || !apk2 || apk1 === apk2) {
        showToast('请选择两个不同的APK文件进行比较', 'warning');
        return;
    }

    try {
        apkElements.btnStartCompare.disabled = true;
        apkElements.btnStartCompare.textContent = '🔄 比较中...';

        const response = await fetch(`${API_BASE}/api/apks/compare`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                apk_file1: apk1,
                apk_file2: apk2
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'APK比较失败');
        }

        const comparison = await response.json();
        displayComparisonResult(comparison);

    } catch (error) {
        console.error('APK比较失败:', error);
        showToast(error.message, 'error');
    } finally {
        apkElements.btnStartCompare.disabled = false;
        apkElements.btnStartCompare.textContent = '🔍 开始比较';
    }
}

/**
 * 显示比较结果
 */
function displayComparisonResult(comparison) {
    const resultDiv = apkElements.apkCompareResult;

    const isSame = comparison.differences.hash_same;

    resultDiv.innerHTML = `
        <!-- 文件信息比较 -->
        <div class="bg-gray-50 rounded-lg p-4">
            <h4 class="text-lg font-semibold text-gray-900 mb-3">文件信息比较</h4>
            <div class="grid grid-cols-2 gap-6 text-sm">
                <div>
                    <h5 class="font-medium text-gray-700 mb-2">文件1</h5>
                    <div class="space-y-1">
                        <div><span class="text-gray-600">名称:</span> ${comparison.file1.name}</div>
                        <div><span class="text-gray-600">大小:</span> ${formatFileSize(comparison.file1.size)}</div>
                        <div><span class="text-gray-600">哈希:</span> <span class="font-mono text-xs">${comparison.file1.hash.substring(0, 16)}...</span></div>
                    </div>
                </div>
                <div>
                    <h5 class="font-medium text-gray-700 mb-2">文件2</h5>
                    <div class="space-y-1">
                        <div><span class="text-gray-600">名称:</span> ${comparison.file2.name}</div>
                        <div><span class="text-gray-600">大小:</span> ${formatFileSize(comparison.file2.size)}</div>
                        <div><span class="text-gray-600">哈希:</span> <span class="font-mono text-xs">${comparison.file2.hash.substring(0, 16)}...</span></div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 差异总结 -->
        <div class="${isSame ? 'bg-green-50' : 'bg-yellow-50'} rounded-lg p-4">
            <h4 class="text-lg font-semibold text-gray-900 mb-3">差异总结</h4>
            <div class="text-sm space-y-2">
                <div>
                    <span class="text-gray-600">文件是否相同:</span>
                    <span class="${isSame ? 'text-green-700' : 'text-yellow-700'} font-medium ml-2">
                        ${isSame ? '✅ 完全相同' : '❌ 存在差异'}
                    </span>
                </div>
                <div>
                    <span class="text-gray-600">大小差异:</span>
                    <span class="text-gray-900 ml-2">${formatFileSize(Math.abs(comparison.differences.size_diff))}</span>
                    ${comparison.differences.size_diff !== 0 ?
                        (comparison.differences.size_diff > 0 ? ' (文件2更大)' : ' (文件1更大)') : ''}
                </div>
                <div>
                    <span class="text-gray-600">构建变体:</span>
                    <span class="text-gray-900 ml-2">
                        ${comparison.differences.build_variant_diff ? '不同' : '相同'}
                    </span>
                </div>
            </div>
        </div>

        ${comparison.package_differences ? `
            <!-- 包信息差异 -->
            <div class="bg-blue-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">包信息差异</h4>
                <div class="text-sm space-y-2">
                    <div>
                        <span class="text-gray-600">版本号:</span>
                        <span class="text-gray-900 ml-2">
                            ${comparison.package_differences.version_code_diff ? '不同' : '相同'}
                        </span>
                    </div>
                    <div>
                        <span class="text-gray-600">版本名:</span>
                        <span class="text-gray-900 ml-2">
                            ${comparison.package_differences.version_name_diff ? '不同' : '相同'}
                        </span>
                    </div>
                    <div>
                        <span class="text-gray-600">包名:</span>
                        <span class="text-gray-900 ml-2">
                            ${comparison.package_differences.package_name_diff ? '不同' : '相同'}
                        </span>
                    </div>
                </div>
            </div>
        ` : ''}

        ${!isSame && comparison.permission_differences ? `
            <!-- 权限差异 -->
            <div class="bg-purple-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">权限差异</h4>
                <div class="text-sm space-y-2">
                    ${comparison.permission_differences.added.length > 0 ? `
                        <div>
                            <span class="text-green-700 font-medium">新增权限 (${comparison.permission_differences.added.length}):</span>
                            <div class="mt-1 space-y-1">
                                ${comparison.permission_differences.added.map(permission => `
                                    <div class="text-gray-700 font-mono text-xs">+ ${permission}</div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${comparison.permission_differences.removed.length > 0 ? `
                        <div>
                            <span class="text-red-700 font-medium">移除权限 (${comparison.permission_differences.removed.length}):</span>
                            <div class="mt-1 space-y-1">
                                ${comparison.permission_differences.removed.map(permission => `
                                    <div class="text-gray-700 font-mono text-xs">- ${permission}</div>
                                `).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${comparison.permission_differences.common.length > 0 ? `
                        <div>
                            <span class="text-gray-700 font-medium">共同权限 (${comparison.permission_differences.common.length}):</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        ` : ''}
    `;

    resultDiv.classList.remove('hidden');
}

/**
 * 将字符串编码为Base64
 */
function encodeBase64(str) {
    try {
        // 使用浏览器内置的Base64编码
        return btoa(unescape(encodeURIComponent(str)));
    } catch (error) {
        console.error('Base64编码失败:', error);
        return null;
    }
}

/**
 * 将Base64字符串解码为原始字符串
 */
function decodeBase64(encodedStr) {
    try {
        return decodeURIComponent(escape(atob(encodedStr)));
    } catch (error) {
        console.error('Base64解码失败:', error);
        return null;
    }
}

/**
 * 下载APK文件（接收Base64编码的路径）
 */
function downloadApkEncoded(encodedPath) {
    if (!encodedPath) {
        showToast('无效的文件路径', 'error');
        return;
    }

    // 解码路径以获取文件名
    const decodedPath = decodeBase64(encodedPath);
    if (!decodedPath) {
        showToast('文件路径解码失败', 'error');
        return;
    }

    // 创建下载链接
    const link = document.createElement('a');
    link.href = `/api/files/download-base64?encoded_path=${encodedPath}`;
    link.download = decodedPath.split(/[/\\]/).pop(); // 获取文件名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    showToast('开始下载APK文件', 'success');
}

/**
 * 下载APK文件（使用Base64编码方案 - 兼容旧接口）
 */
function downloadApk(apkFilePath) {
    // 清理路径中的控制字符
    const cleanPath = apkFilePath.replace(/[\x00-\x1F\x7F]/g, '');

    // 使用Base64编码文件路径
    const encodedPath = encodeBase64(cleanPath);
    if (!encodedPath) {
        showToast('文件路径编码失败', 'error');
        return;
    }

    // 调用新的编码版本函数
    downloadApkEncoded(encodedPath);
}

/**
 * 更新步骤指示器
 */
function updateStepIndicator(stepNumber, status) {
    const steps = document.querySelectorAll('nav[aria-label="Progress"] ol li');

    if (stepNumber > 0 && stepNumber <= steps.length) {
        const step = steps[stepNumber - 1];
        const circle = step.querySelector('span.flex-shrink-0');
        const text = step.querySelector('span.ml-4');

        if (status === 'completed') {
            circle.className = 'flex-shrink-0 w-10 h-10 flex items-center justify-center bg-green-600 rounded-full';
            circle.innerHTML = '<span class="text-white">✓</span>';
            text.className = 'ml-4 text-sm font-medium text-green-600';
        } else if (status === 'active') {
            circle.className = 'flex-shrink-0 w-10 h-10 flex items-center justify-center bg-blue-600 rounded-full';
            circle.innerHTML = `<span class="text-white">${stepNumber}</span>`;
            text.className = 'ml-4 text-sm font-medium text-blue-600';
        }
    }
}

/**
 * 初始化APK相关事件监听器
 */
function initApkEventListeners() {
    // 扫描APK按钮
    apkElements.btnScanApks.addEventListener('click', scanApkFiles);

    // APK设置按钮
    apkElements.btnApkSettings.addEventListener('click', () => {
        showToast('APK设置功能开发中...', 'info');
    });

    // 刷新APK按钮
    apkElements.btnRefreshApks.addEventListener('click', scanApkFiles);

    // 构建变体筛选
    apkElements.apkVariantFilter.addEventListener('change', displayApkList);

    // 排序选择
    apkElements.apkSortBy.addEventListener('change', displayApkList);

    // APK详情模态框关闭
    apkElements.btnCloseApkModal.addEventListener('click', () => {
        apkElements.modalApkDetails.classList.add('hidden');
    });

    // APK比较模态框关闭
    apkElements.btnCloseCompareModal.addEventListener('click', () => {
        apkElements.modalApkCompare.classList.add('hidden');
    });

    // APK比较选择变化
    apkElements.compareApk1.addEventListener('change', updateCompareButton);
    apkElements.compareApk2.addEventListener('change', updateCompareButton);

    // 开始比较按钮
    apkElements.btnStartCompare.addEventListener('click', startApkCompare);
}

// ===== Git操作功能 =====

// Git相关状态
const gitState = {
    operationHistory: [],
    backupList: [],
    currentBranches: [],
    gitStatus: null
};

// Git相关DOM元素
const gitElements = {
    // Git操作面板
    btnGitStatus: document.getElementById('btn-git-status'),
    btnGitSettings: document.getElementById('btn-git-settings'),

    // Git状态概览
    gitWorkspaceStatus: document.getElementById('git-workspace-status'),
    gitCurrentBranch: document.getElementById('git-current-branch'),
    gitStagedFiles: document.getElementById('git-staged-files'),
    gitBackupCount: document.getElementById('git-backup-count'),

    // 提交操作
    gitCommitMessage: document.getElementById('git-commit-message'),
    gitCommitBackup: document.getElementById('git-commit-backup'),
    gitBackupDays: document.getElementById('git-backup-days'),
    btnGitCommit: document.getElementById('btn-git-commit'),
    btnGitStageAll: document.getElementById('btn-git-stage-all'),
    btnGitUnstageAll: document.getElementById('btn-git-unstage-all'),

    // 回滚操作
    gitRollbackCommit: document.getElementById('git-rollback-commit'),
    gitRollbackBackup: document.getElementById('git-rollback-backup'),
    btnGitRollback: document.getElementById('btn-git-rollback'),

    // 分支操作
    gitNewBranchName: document.getElementById('git-new-branch-name'),
    gitBranchSource: document.getElementById('git-branch-source'),
    btnGitCreateBranch: document.getElementById('btn-git-create-branch'),
    btnGitSwitchBranch: document.getElementById('btn-git-switch-branch'),

    // 备份管理
    gitBackupList: document.getElementById('git-backup-list'),
    btnRefreshBackups: document.getElementById('btn-refresh-backups'),
    btnGitCreateBackup: document.getElementById('btn-git-create-backup'),
    btnGitCleanupBackups: document.getElementById('btn-git-cleanup-backups'),

    // 操作历史
    gitHistoryFilter: document.getElementById('git-history-filter'),
    btnRefreshHistory: document.getElementById('btn-refresh-history'),
    gitOperationHistory: document.getElementById('git-operation-history'),

    // Git操作详情模态框
    modalGitOperationDetails: document.getElementById('modal-git-operation-details'),
    btnCloseGitModal: document.getElementById('btn-close-git-modal'),
    gitOperationDetailsContent: document.getElementById('git-operation-details-content'),

    // Git备份恢复模态框
    modalGitBackupRestore: document.getElementById('modal-git-backup-restore'),
    btnCloseBackupModal: document.getElementById('btn-close-backup-modal'),
    backupRestoreInfo: document.getElementById('backup-restore-info'),
    confirmBackupRestore: document.getElementById('confirm-backup-restore'),
    btnCancelBackupRestore: document.getElementById('btn-cancel-backup-restore'),
    btnConfirmBackupRestore: document.getElementById('btn-confirm-backup-restore')
};

/**
 * 检查Git仓库状态
 */
async function checkGitStatus() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    try {
        gitElements.btnGitStatus.disabled = true;
        gitElements.btnGitStatus.textContent = '🔄 检查中...';

        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/status`);

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '获取Git状态失败');
        }

        const statusData = await response.json();
        gitState.gitStatus = statusData.data;

        // 更新状态概览
        updateGitStatusOverview(statusData.data);

        // 加载操作历史
        await loadGitOperationHistory();

        // 加载备份列表
        await loadGitBackupList();

        // 先加载分支列表（用于分支操作），以便提交历史按正确分支过滤
        await loadGitBranches();

        // 加载提交历史（用于回滚选择，按已选分支）
        await loadCommitHistory();

        // 启用Git操作按钮
        enableGitOperations();

        showToast('Git状态检查完成', 'success');

    } catch (error) {
        console.error('检查Git状态失败:', error);
        showToast(error.message, 'error');
        disableGitOperations();
    } finally {
        gitElements.btnGitStatus.disabled = false;
        gitElements.btnGitStatus.textContent = '📊 状态检查';
    }
}

/**
 * 更新Git状态概览
 */
function updateGitStatusOverview(statusData) {
    // 工作区状态
    const workspaceStatus = statusData.is_clean ? '干净' : '有变更';
    const statusColor = statusData.is_clean ? 'text-green-600' : 'text-orange-600';
    gitElements.gitWorkspaceStatus.textContent = workspaceStatus;
    gitElements.gitWorkspaceStatus.className = `text-sm font-semibold ${statusColor}`;

    // 当前分支
    gitElements.gitCurrentBranch.textContent = statusData.current_branch || '未知';

    // 待提交文件数
    const stagedCount = statusData.staged_files ? statusData.staged_files.length : 0;
    gitElements.gitStagedFiles.textContent = stagedCount;

    // 更新提交按钮状态
    gitElements.btnGitCommit.disabled = stagedCount === 0;
}

/**
 * 加载Git操作历史
 */
async function loadGitOperationHistory(operationType = null) {
    if (!state.currentProject) return;

    try {
        const filter = operationType ? `&operation_type=${operationType}` : '';
        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/operations?limit=20${filter}`);

        if (!response.ok) {
            throw new Error('加载操作历史失败');
        }

        const data = await response.json();
        gitState.operationHistory = data.data.operations || [];

        // 更新操作历史显示
        displayGitOperationHistory();

    } catch (error) {
        console.error('加载Git操作历史失败:', error);
    }
}

/**
 * 显示Git操作历史
 */
function displayGitOperationHistory() {
    const historyContainer = gitElements.gitOperationHistory;

    if (gitState.operationHistory.length === 0) {
        historyContainer.innerHTML = '<p class="text-sm text-gray-500 text-center">暂无操作历史</p>';
        return;
    }

    historyContainer.innerHTML = '';

    gitState.operationHistory.forEach(operation => {
        const operationItem = createGitOperationItem(operation);
        historyContainer.appendChild(operationItem);
    });
}

/**
 * 创建Git操作历史项
 */
function createGitOperationItem(operation) {
    const item = document.createElement('div');
    item.className = 'p-3 bg-gray-50 rounded-md hover:bg-gray-100 transition-colors cursor-pointer';
    item.onclick = () => showGitOperationDetails(operation.id);

    const operationIcon = getGitOperationIcon(operation.operation_type);
    const operationStatus = getGitOperationStatus(operation.status);
    const operationTime = formatTimestamp(new Date(operation.created_at).getTime() / 1000);

    item.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex items-center space-x-3">
                <span class="text-lg">${operationIcon}</span>
                <div>
                    <div class="flex items-center space-x-2">
                        <span class="text-sm font-medium text-gray-900">${getGitOperationTypeName(operation.operation_type)}</span>
                        <span class="px-2 py-1 text-xs rounded-full ${operationStatus.className}">${operationStatus.text}</span>
                    </div>
                    <div class="text-xs text-gray-500 mt-1">
                        ${operation.description || '无描述'} | ${operationTime}
                    </div>
                </div>
            </div>
            <button class="text-blue-600 hover:text-blue-800" onclick="event.stopPropagation(); showGitOperationDetails('${operation.id}')">
                📋 详情
            </button>
        </div>
    `;

    return item;
}

/**
 * 获取Git操作图标
 */
function getGitOperationIcon(operationType) {
    const icons = {
        'commit': '📤',
        'rollback': '⏮️',
        'branch_switch': '🌿',
        'branch_create': '🌳',
        'branch_delete': '🗑️',
        'merge': '🔀',
        'stash': '📦',
        'stash_pop': '📤'
    };
    return icons[operationType] || '⚙️';
}

/**
 * 获取Git操作类型名称
 */
function getGitOperationTypeName(operationType) {
    const names = {
        'commit': '提交',
        'rollback': '回滚',
        'branch_switch': '切换分支',
        'branch_create': '创建分支',
        'branch_delete': '删除分支',
        'merge': '合并',
        'stash': '暂存',
        'stash_pop': '恢复暂存'
    };
    return names[operationType] || operationType;
}

/**
 * 获取Git操作状态
 */
function getGitOperationStatus(status) {
    const statusMap = {
        'pending': { text: '等待中', className: 'bg-gray-100 text-gray-800' },
        'in_progress': { text: '进行中', className: 'bg-blue-100 text-blue-800' },
        'completed': { text: '已完成', className: 'bg-green-100 text-green-800' },
        'failed': { text: '失败', className: 'bg-red-100 text-red-800' },
        'cancelled': { text: '已取消', className: 'bg-yellow-100 text-yellow-800' }
    };
    return statusMap[status] || { text: status, className: 'bg-gray-100 text-gray-800' };
}

/**
 * 显示Git操作详情
 */
async function showGitOperationDetails(operationId) {
    try {
        const response = await fetch(`${API_BASE}/api/git/operations/${operationId}`);

        if (!response.ok) {
            throw new Error('获取操作详情失败');
        }

        const data = await response.json();
        displayGitOperationDetails(data.data);

        // 显示模态框
        gitElements.modalGitOperationDetails.classList.remove('hidden');

    } catch (error) {
        console.error('获取Git操作详情失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 显示Git操作详情内容
 */
function displayGitOperationDetails(operation) {
    const content = gitElements.gitOperationDetailsContent;

    const operationIcon = getGitOperationIcon(operation.operation_type);
    const operationStatus = getGitOperationStatus(operation.status);

    content.innerHTML = `
        <!-- 基本信息 -->
        <div class="bg-gray-50 rounded-lg p-4">
            <h4 class="text-lg font-semibold text-gray-900 mb-3">
                ${operationIcon} ${getGitOperationTypeName(operation.operation_type)}
            </h4>
            <div class="grid grid-cols-2 gap-4 text-sm">
                <div>
                    <span class="text-gray-600">操作ID:</span>
                    <span class="text-gray-900 ml-2 font-mono text-xs">${operation.id.substring(0, 16)}...</span>
                </div>
                <div>
                    <span class="text-gray-600">状态:</span>
                    <span class="ml-2 px-2 py-1 text-xs rounded-full ${operationStatus.className}">${operationStatus.text}</span>
                </div>
                <div>
                    <span class="text-gray-600">创建时间:</span>
                    <span class="text-gray-900 ml-2">${formatTimestamp(new Date(operation.created_at).getTime() / 1000)}</span>
                </div>
                <div>
                    <span class="text-gray-600">完成时间:</span>
                    <span class="text-gray-900 ml-2">${operation.completed_at ? formatTimestamp(new Date(operation.completed_at).getTime() / 1000) : '-'}</span>
                </div>
                ${operation.duration_seconds ? `
                    <div>
                        <span class="text-gray-600">执行时长:</span>
                        <span class="text-gray-900 ml-2">${operation.duration_seconds}秒</span>
                    </div>
                ` : ''}
            </div>
        </div>

        ${operation.description ? `
            <!-- 描述 -->
            <div class="bg-blue-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-2">描述</h4>
                <p class="text-sm text-gray-700">${operation.description}</p>
            </div>
        ` : ''}

        ${operation.commit_message ? `
            <!-- 提交消息 -->
            <div class="bg-green-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-2">提交消息</h4>
                <p class="text-sm text-gray-700">${operation.commit_message}</p>
            </div>
        ` : ''}

        ${operation.commit_hash_before || operation.commit_hash_after ? `
            <!-- Git哈希信息 -->
            <div class="bg-purple-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">Git哈希信息</h4>
                <div class="space-y-2 text-sm">
                    ${operation.commit_hash_before ? `
                        <div>
                            <span class="text-gray-600">操作前:</span>
                            <span class="text-gray-900 ml-2 font-mono">${operation.commit_hash_before}</span>
                        </div>
                    ` : ''}
                    ${operation.commit_hash_after ? `
                        <div>
                            <span class="text-gray-600">操作后:</span>
                            <span class="text-gray-900 ml-2 font-mono">${operation.commit_hash_after}</span>
                        </div>
                    ` : ''}
                </div>
            </div>
        ` : ''}

        ${operation.files_affected && operation.files_affected.length > 0 ? `
            <!-- 受影响的文件 -->
            <div class="bg-yellow-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">受影响的文件 (${operation.files_affected.length})</h4>
                <div class="max-h-40 overflow-y-auto space-y-1">
                    ${operation.files_affected.map(file => `
                        <div class="text-sm text-gray-700 font-mono">${file}</div>
                    `).join('')}
                </div>
            </div>
        ` : ''}

        ${operation.error_message ? `
            <!-- 错误信息 -->
            <div class="bg-red-50 border border-red-200 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-red-900 mb-2">错误信息</h4>
                <p class="text-sm text-red-700">${operation.error_message}</p>
            </div>
        ` : ''}

        ${operation.repository_backups && operation.repository_backups.length > 0 ? `
            <!-- 相关备份 -->
            <div class="bg-orange-50 rounded-lg p-4">
                <h4 class="text-lg font-semibold text-gray-900 mb-3">相关备份 (${operation.repository_backups.length})</h4>
                <div class="space-y-2">
                    ${operation.repository_backups.map(backup => `
                        <div class="flex items-center justify-between text-sm">
                            <div>
                                <span class="text-gray-700">${backup.backup_type} - ${backup.description || '无描述'}</span>
                                <span class="text-gray-500 ml-2">${formatFileSize(backup.backup_size || 0)}</span>
                            </div>
                            <button onclick="showGitBackupDetails('${backup.id}')" class="text-blue-600 hover:text-blue-800">
                                查看详情
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>
        ` : ''}
    `;
}

/**
 * 加载Git备份列表
 */
async function loadGitBackupList() {
    if (!state.currentProject) return;

    try {
        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/backups?limit=10`);

        if (!response.ok) {
            throw new Error('加载备份列表失败');
        }

        const data = await response.json();
        gitState.backupList = data.data.backups || [];

        // 更新备份计数
        gitElements.gitBackupCount.textContent = gitState.backupList.length;

        // 更新备份列表显示
        displayGitBackupList();

    } catch (error) {
        console.error('加载Git备份列表失败:', error);
    }
}

/**
 * 显示Git备份列表
 */
function displayGitBackupList() {
    const backupListContainer = gitElements.gitBackupList;

    if (gitState.backupList.length === 0) {
        backupListContainer.innerHTML = '<p class="text-sm text-gray-500 text-center">暂无备份</p>';
        return;
    }

    backupListContainer.innerHTML = '';

    gitState.backupList.forEach(backup => {
        const backupItem = createGitBackupItem(backup);
        backupListContainer.appendChild(backupItem);
    });
}

/**
 * 创建Git备份项
 */
function createGitBackupItem(backup) {
    const item = document.createElement('div');
    item.className = 'p-2 bg-gray-50 rounded hover:bg-gray-100 transition-colors';

    const backupTime = formatTimestamp(new Date(backup.created_at).getTime() / 1000);
    const backupType = backup.backup_type === 'full' ? '完整' : '快照';

    item.innerHTML = `
        <div class="flex items-center justify-between">
            <div class="flex-1">
                <div class="text-xs font-medium text-gray-900">${backupType}备份</div>
                <div class="text-xs text-gray-500">${backupTime}</div>
                ${backup.description ? `<div class="text-xs text-gray-600">${backup.description}</div>` : ''}
            </div>
            <div class="flex space-x-1">
                <button onclick="showGitBackupDetails('${backup.id}')" class="text-blue-600 hover:text-blue-800 text-xs">
                    📋
                </button>
                <button onclick="showGitBackupRestore('${backup.id}')" class="text-green-600 hover:text-green-800 text-xs">
                    🔙
                </button>
                <button onclick="deleteGitBackup('${backup.id}')" class="text-red-600 hover:text-red-800 text-xs">
                    🗑️
                </button>
            </div>
        </div>
    `;

    return item;
}

/**
 * 显示Git备份详情
 */
async function showGitBackupDetails(backupId) {
    // 这里可以扩展显示备份的详细信息
    showGitOperationDetails(backupId);
}

/**
 * 显示Git备份恢复确认
 */
async function showGitBackupRestore(backupId) {
    const backup = gitState.backupList.find(b => b.id === backupId);
    if (!backup) {
        showToast('备份不存在', 'error');
        return;
    }

    // 显示备份信息
    const backupInfo = gitElements.backupRestoreInfo;
    const backupTime = formatTimestamp(new Date(backup.created_at).getTime() / 1000);
    const backupType = backup.backup_type === 'full' ? '完整' : '快照';

    backupInfo.innerHTML = `
        <div class="space-y-2 text-sm">
            <div><strong>备份类型:</strong> ${backupType}备份</div>
            <div><strong>创建时间:</strong> ${backupTime}</div>
            <div><strong>分支:</strong> ${backup.branch_name || '未知'}</div>
            <div><strong>提交哈希:</strong> <span class="font-mono">${backup.commit_hash || '未知'}</span></div>
            <div><strong>文件数量:</strong> ${backup.tracked_files_count || 0}</div>
            <div><strong>备份大小:</strong> ${formatFileSize(backup.backup_size || 0)}</div>
            ${backup.description ? `<div><strong>描述:</strong> ${backup.description}</div>` : ''}
        </div>
    `;

    // 显示模态框
    gitElements.modalGitBackupRestore.classList.remove('hidden');

    // 绑定确认按钮事件
    gitElements.btnConfirmBackupRestore.onclick = () => confirmGitBackupRestore(backupId);
}

/**
 * 确认Git备份恢复
 */
async function confirmGitBackupRestore(backupId) {
    if (!gitElements.confirmBackupRestore.checked) {
        showToast('请确认您理解此操作的风险', 'warning');
        return;
    }

    try {
        gitElements.btnConfirmBackupRestore.disabled = true;
        gitElements.btnConfirmBackupRestore.textContent = '🔄 恢复中...';

        const response = await fetch(`${API_BASE}/api/git/backups/${backupId}/restore`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                confirm_restore: true
            })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '恢复备份失败');
        }

        const result = await response.json();

        showToast('备份恢复成功', 'success');

        // 关闭模态框
        gitElements.modalGitBackupRestore.classList.add('hidden');
        gitElements.confirmBackupRestore.checked = false;

        // 重新检查Git状态
        await checkGitStatus();

    } catch (error) {
        console.error('恢复Git备份失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnConfirmBackupRestore.disabled = false;
        gitElements.btnConfirmBackupRestore.textContent = '🔙 确认恢复';
    }
}

/**
 * 删除Git备份
 */
async function deleteGitBackup(backupId) {
    if (!confirm('确定要删除此备份吗？此操作不可恢复！')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE}/api/git/backups/${backupId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '删除备份失败');
        }

        showToast('备份删除成功', 'success');

        // 重新加载备份列表
        await loadGitBackupList();

    } catch (error) {
        console.error('删除Git备份失败:', error);
        showToast(error.message, 'error');
    }
}

/**
 * 加载提交历史
 */
async function loadCommitHistory() {
    if (!state.currentProject) return;

    try {
        const branchFromGitSelect = gitElements.gitBranchSource && gitElements.gitBranchSource.value ? gitElements.gitBranchSource.value : null;
        const preferredBranch = branchFromGitSelect || state.currentBranch || '';
        const branchParam = preferredBranch ? `&branch=${encodeURIComponent(preferredBranch)}` : '';
        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/commits?limit=20${branchParam}`);

        if (!response.ok) {
            // 可能不是Git仓库，忽略错误
            return;
        }

        const data = await response.json();
        const commits = data.data.commits || [];

        // 更新回滚选择框
        updateRollbackCommitSelect(commits);

    } catch (error) {
        console.error('加载提交历史失败:', error);
    }
}

/**
 * 更新回滚提交选择框
 */
function updateRollbackCommitSelect(commits) {
    const select = gitElements.gitRollbackCommit;

    // 清空并重新填充
    select.innerHTML = '<option value="">选择要回滚到的提交</option>';

    commits.forEach(commit => {
        // 兼容后端返回的字段：sha/short_sha/message
        const sha = commit.sha || commit.hash || '';
        const shortSha = commit.short_sha || (sha ? sha.substring(0, 8) : '');
        const message = (commit.message || '').toString();

        // 跳过无有效sha的记录，避免生成不可用选项
        if (!sha) return;

        const option = document.createElement('option');
        option.value = sha;
        option.textContent = `${shortSha} - ${message.substring(0, 50)}${message.length > 50 ? '...' : ''}`;
        select.appendChild(option);
    });

    // 启用选择框
    select.disabled = commits.length === 0;
}

/**
 * 加载Git分支列表
 */
async function loadGitBranches() {
    if (!state.currentProject) return;

    try {
        const response = await fetch(`${API_BASE}/api/projects/${state.currentProject.id}/branches`);

        if (!response.ok) {
            // 可能不是Git仓库，忽略错误
            return;
        }

        const data = await response.json();
        const branches = data.branches || [];
        // 优先使用项目选择的分支，其次使用仓库当前分支
        const currentBranch = state.currentBranch || data.current_branch;

        // 更新分支选择框
        updateBranchSelect(branches, currentBranch);

    } catch (error) {
        console.error('加载Git分支失败:', error);
    }
}

/**
 * 更新分支选择框
 */
function updateBranchSelect(branches, currentBranch) {
    const select = gitElements.gitBranchSource;

    // 清空并重新填充
    select.innerHTML = '<option value="">当前分支</option>';

    branches.forEach(branch => {
        const option = document.createElement('option');
        option.value = branch;
        option.textContent = branch;

        // 标记当前分支
        if (branch === currentBranch) {
            option.textContent += ' (当前)';
            option.selected = true;
        }

        select.appendChild(option);
    });

    // 启用选择框
    select.disabled = branches.length === 0;
}

/**
 * 执行Git提交
 */
async function executeGitCommit() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    const commitMessage = gitElements.gitCommitMessage.value.trim();
    if (!commitMessage) {
        showToast('请输入提交消息', 'warning');
        return;
    }

    try {
        gitElements.btnGitCommit.disabled = true;
        gitElements.btnGitCommit.textContent = '🔄 提交中...';

        const requestData = {
            commit_message: commitMessage,
            create_backup: gitElements.gitCommitBackup.checked,
            backup_expiry_days: parseInt(gitElements.gitBackupDays.value)
        };

        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/commit`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Git提交失败');
        }

        const result = await response.json();

        showToast('Git提交成功', 'success');

        // 清空提交消息
        gitElements.gitCommitMessage.value = '';

        // 重新检查Git状态
        await checkGitStatus();

    } catch (error) {
        console.error('Git提交失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnGitCommit.disabled = false;
        gitElements.btnGitCommit.textContent = '📤 提交';
    }
}

/**
 * 执行Git回滚
 */
async function executeGitRollback() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    const targetCommit = gitElements.gitRollbackCommit.value;
    if (!targetCommit) {
        showToast('请选择要回滚到的提交', 'warning');
        return;
    }

    if (!confirm(`确定要回滚到提交 ${targetCommit.substring(0, 8)} 吗？此操作将丢弃当前分支的所有后续提交！`)) {
        return;
    }

    try {
        gitElements.btnGitRollback.disabled = true;
        gitElements.btnGitRollback.textContent = '🔄 回滚中...';

        const requestData = {
            target_commit_hash: targetCommit,
            create_backup: gitElements.gitRollbackBackup.checked
        };

        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/rollback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Git回滚失败');
        }

        const result = await response.json();

        showToast('Git回滚成功', 'success');

        // 重新检查Git状态
        await checkGitStatus();

    } catch (error) {
        console.error('Git回滚失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnGitRollback.disabled = false;
        gitElements.btnGitRollback.textContent = '⏮️ 回滚到选中提交';
    }
}

/**
 * 创建Git分支
 */
async function createGitBranch() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    const branchName = gitElements.gitNewBranchName.value.trim();
    if (!branchName) {
        showToast('请输入新分支名称', 'warning');
        return;
    }

    const sourceBranch = gitElements.gitBranchSource.value;

    try {
        gitElements.btnGitCreateBranch.disabled = true;
        gitElements.btnGitCreateBranch.textContent = '🔄 创建中...';

        const requestData = {
            branch_name: branchName,
            source_branch: sourceBranch || null,
            create_backup: true, // 默认创建备份
            backup_expiry_days: 30
        };

        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/branches/${encodeURIComponent(branchName)}/create`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '创建分支失败');
        }

        const result = await response.json();

        showToast(`分支 '${branchName}' 创建成功`, 'success');

        // 清空分支名称
        gitElements.gitNewBranchName.value = '';

        // 重新检查Git状态
        await checkGitStatus();

    } catch (error) {
        console.error('创建Git分支失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnGitCreateBranch.disabled = false;
        gitElements.btnGitCreateBranch.textContent = '🌿 创建分支';
    }
}

/**
 * 清理过期备份
 */
async function cleanupExpiredBackups() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    if (!confirm('确定要清理所有过期备份吗？此操作不可恢复！')) {
        return;
    }

    try {
        gitElements.btnGitCleanupBackups.disabled = true;
        gitElements.btnGitCleanupBackups.textContent = '🔄 清理中...';

        const response = await fetch(`${API_BASE}/api/git/projects/${state.currentProject.id}/backups/cleanup`, {
            method: 'POST'
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || '清理过期备份失败');
        }

        const result = await response.json();

        showToast(`已清理 ${result.data.deleted_count} 个过期备份`, 'success');

        // 重新加载备份列表
        await loadGitBackupList();

    } catch (error) {
        console.error('清理过期备份失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnGitCleanupBackups.disabled = false;
        gitElements.btnGitCleanupBackups.textContent = '🗑️ 清理过期';
    }
}

/**
 * 创建手动备份
 */
async function createManualBackup() {
    if (!state.currentProject) {
        showToast('请先选择项目', 'warning');
        return;
    }

    try {
        gitElements.btnGitCreateBackup.disabled = true;
        gitElements.btnGitCreateBackup.textContent = '🔄 备份中...';

        // 这里可以调用创建备份的API（如果有的话）
        // 或者调用提交API但不实际提交，只创建备份

        showToast('手动备份功能开发中...', 'info');

    } catch (error) {
        console.error('创建手动备份失败:', error);
        showToast(error.message, 'error');
    } finally {
        gitElements.btnGitCreateBackup.disabled = false;
        gitElements.btnGitCreateBackup.textContent = '💾 创建备份';
    }
}

/**
 * 启用Git操作按钮
 */
function enableGitOperations() {
    // 提交相关按钮
    gitElements.btnGitStageAll.disabled = false;
    gitElements.btnGitUnstageAll.disabled = false;

    // 回滚相关按钮
    gitElements.btnGitRollback.disabled = false;

    // 分支相关按钮
    gitElements.btnGitCreateBranch.disabled = false;
    gitElements.btnGitSwitchBranch.disabled = false;

    // 备份相关按钮
    gitElements.btnRefreshBackups.disabled = false;
    gitElements.btnGitCreateBackup.disabled = false;
    gitElements.btnGitCleanupBackups.disabled = false;

    // 历史相关按钮
    gitElements.btnRefreshHistory.disabled = false;
}

/**
 * 禁用Git操作按钮
 */
function disableGitOperations() {
    // 禁用所有Git操作按钮
    gitElements.btnGitStageAll.disabled = true;
    gitElements.btnGitUnstageAll.disabled = true;
    gitElements.btnGitCommit.disabled = true;
    gitElements.btnGitRollback.disabled = true;
    gitElements.btnGitCreateBranch.disabled = true;
    gitElements.btnGitSwitchBranch.disabled = true;
    gitElements.btnRefreshBackups.disabled = true;
    gitElements.btnGitCreateBackup.disabled = true;
    gitElements.btnGitCleanupBackups.disabled = true;
    gitElements.btnRefreshHistory.disabled = true;

    // 禁用选择框
    gitElements.gitRollbackCommit.disabled = true;
    gitElements.gitBranchSource.disabled = true;
}

/**
 * 初始化Git操作事件监听器
 */
function initGitEventListeners() {
    // Git状态检查
    gitElements.btnGitStatus.addEventListener('click', checkGitStatus);

    // Git设置按钮
    gitElements.btnGitSettings.addEventListener('click', () => {
        showToast('Git设置功能开发中...', 'info');
    });

    // 提交操作
    gitElements.btnGitCommit.addEventListener('click', executeGitCommit);

    // 暂存操作（暂时只是提示）
    gitElements.btnGitStageAll.addEventListener('click', () => {
        showToast('暂存所有文件功能将在Git集成完成后实现', 'info');
    });

    gitElements.btnGitUnstageAll.addEventListener('click', () => {
        showToast('取消暂存功能将在Git集成完成后实现', 'info');
    });

    // 回滚操作
    gitElements.btnGitRollback.addEventListener('click', executeGitRollback);

    // 分支操作
    gitElements.btnGitCreateBranch.addEventListener('click', createGitBranch);

    gitElements.btnGitSwitchBranch.addEventListener('click', () => {
        showToast('切换分支功能将在Git集成完成后实现', 'info');
    });

    // 分支源变更时刷新回滚提交选择（按选中分支加载提交历史）
    gitElements.gitBranchSource.addEventListener('change', () => {
        loadCommitHistory();
    });

    // 回滚下拉框获得焦点时刷新提交历史，确保显示最新分支的提交
    gitElements.gitRollbackCommit.addEventListener('focus', () => {
        loadCommitHistory();
    });

    // 备份操作
    gitElements.btnRefreshBackups.addEventListener('click', loadGitBackupList);
    gitElements.btnGitCreateBackup.addEventListener('click', createManualBackup);
    gitElements.btnGitCleanupBackups.addEventListener('click', cleanupExpiredBackups);

    // 历史操作
    gitElements.btnRefreshHistory.addEventListener('click', () => {
        const filterType = gitElements.gitHistoryFilter.value;
        loadGitOperationHistory(filterType);
    });

    gitElements.gitHistoryFilter.addEventListener('change', (e) => {
        const filterType = e.target.value;
        loadGitOperationHistory(filterType);
    });

    // 模态框关闭事件
    gitElements.btnCloseGitModal.addEventListener('click', () => {
        gitElements.modalGitOperationDetails.classList.add('hidden');
    });

    gitElements.btnCloseBackupModal.addEventListener('click', () => {
        gitElements.modalGitBackupRestore.classList.add('hidden');
        gitElements.confirmBackupRestore.checked = false;
    });

    gitElements.btnCancelBackupRestore.addEventListener('click', () => {
        gitElements.modalGitBackupRestore.classList.add('hidden');
        gitElements.confirmBackupRestore.checked = false;
    });

    // 备份恢复确认复选框
    gitElements.confirmBackupRestore.addEventListener('change', (e) => {
        gitElements.btnConfirmBackupRestore.disabled = !e.target.checked;
    });
}

// 在现有的initEventListeners函数中添加APK和Git事件监听器
const originalInitEventListeners = initEventListeners;
initEventListeners = function() {
    originalInitEventListeners();
    initApkEventListeners();
    initGitEventListeners();
};

// 当项目选择变化时，重置Git操作状态
const originalLoadProjectDetails = loadProjectDetails;
loadProjectDetails = async function(projectId) {
    await originalLoadProjectDetails(projectId);

    // 重置Git操作状态
    gitState.gitStatus = null;
    gitState.operationHistory = [];
    gitState.backupList = [];

    // 禁用Git操作按钮，直到用户点击状态检查
    disableGitOperations();

    // 如果有当前项目且是Git仓库，自动启用状态检查按钮
    if (state.currentProject) {
        gitElements.btnGitStatus.disabled = false;
    }
};

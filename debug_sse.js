// SSE连接调试脚本
// 将此代码复制到浏览器控制台中运行，用于调试SSE连接问题

console.log('🔧 开始SSE连接调试...');

// 强制清除可能的定时器
const highestTimeoutId = setTimeout(() => {}, 0);
for (let i = 0; i < highestTimeoutId; i++) {
    clearTimeout(i);
}

// 检查当前状态
console.log('📊 当前状态:', {
    buildStatus: window.state?.buildStatus,
    buildTaskId: window.state?.buildTaskId,
    logEventSource: window.logEventSource
});

// 强制设置状态为空闲
if (window.state) {
    window.state.buildStatus = 'idle';
    window.state.buildTaskId = null;
    console.log('✅ 状态已重置');
}

// 强制停止所有SSE连接
if (window.logEventSource) {
    console.log('🔚 强制关闭现有SSE连接');
    window.logEventSource.close();
    window.logEventSource = null;
}

// 测试新的SSE连接
console.log('🧪 开始测试SSE连接...');
const testEventSource = new EventSource('/api/builds/tasks/a58a2d40-250c-463b-9082-85e0c38ff3e0/logs/stream');

let eventCount = 0;
let completedReceived = false;

testEventSource.addEventListener('open', () => {
    console.log('✅ SSE连接已建立');
    eventCount++;
});

testEventSource.addEventListener('connected', (event) => {
    try {
        const data = JSON.parse(event.data);
        console.log('📡 连接事件:', data);
        eventCount++;
    } catch (e) {
        console.log('📡 连接事件:', event.data);
        eventCount++;
    }
});

testEventSource.addEventListener('status', (event) => {
    try {
        const data = JSON.parse(event.data);
        console.log('📊 状态事件:', data);
        eventCount++;

        // 检查任务状态
        if (data.status === 'failed' || data.status === 'completed') {
            console.log('🎯 任务已完成，应该停止连接');
        }
    } catch (e) {
        console.log('📊 状态事件:', event.data);
        eventCount++;
    }
});

testEventSource.addEventListener('completed', (event) => {
    try {
        const data = JSON.parse(event.data);
        console.log('🏁 完成事件:', data);
        eventCount++;
        completedReceived = true;

        if (data.final) {
            console.log('🎉 收到最终完成事件！');
            console.log('✅ SSE连接工作正常');

            // 3秒后关闭连接
            setTimeout(() => {
                console.log('🔚 测试完成，关闭SSE连接');
                testEventSource.close();
            }, 3000);
        }
    } catch (e) {
        console.log('🏁 完成事件:', event.data);
        eventCount++;
        completedReceived = true;
    }
});

testEventSource.addEventListener('error', (event) => {
    console.log('❌ SSE错误:', event);
    eventCount++;
});

// 10秒后总结
setTimeout(() => {
    console.log('📋 测试总结:');
    console.log('- 收到事件数量:', eventCount);
    console.log('- 是否收到完成事件:', completedReceived);

    testEventSource.close();

    if (completedReceived) {
        console.log('✅ SSE后端工作正常！');
        console.log('💡 如果前端仍显示连接问题，请强制刷新浏览器缓存 (Ctrl+F5)');
    } else {
        console.log('❌ SSE连接可能存在问题');
    }
}, 10000);
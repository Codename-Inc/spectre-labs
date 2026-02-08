/**
 * Execution Panel - Pipeline execution control and log streaming
 */

let ws = null;
let executionStatus = 'idle';

/**
 * Start pipeline execution
 */
async function startExecution() {
    if (!selectedPipeline) {
        alert('Select a pipeline first');
        return;
    }

    const tasksFile = document.getElementById('tasks-file').value.trim();
    if (!tasksFile) {
        alert('Enter a tasks file path');
        return;
    }

    const contextFilesInput = document.getElementById('context-files').value.trim();
    const contextFiles = contextFilesInput
        ? contextFilesInput.split(',').map(s => s.trim()).filter(s => s)
        : [];

    const agent = document.getElementById('agent-select').value;

    try {
        await fetchJSON('/api/execution/start', {
            method: 'POST',
            body: JSON.stringify({
                pipeline_name: selectedPipeline,
                tasks_file: tasksFile,
                context_files: contextFiles,
                agent: agent
            })
        });

        setExecutionStatus('running');
        connectWebSocket();
        addLogEntry('Pipeline started: ' + selectedPipeline, 'pipeline');
    } catch (e) {
        alert('Failed to start: ' + e.message);
    }
}

/**
 * Stop pipeline execution
 */
async function stopExecution() {
    try {
        await fetchJSON('/api/execution/stop', { method: 'POST' });
        setExecutionStatus('stopped');
        addLogEntry('Pipeline stopped by user', 'error');
    } catch (e) {
        alert('Failed to stop: ' + e.message);
    }
}

/**
 * Set execution status and update UI
 */
function setExecutionStatus(status) {
    executionStatus = status;
    const badge = document.getElementById('status-badge');
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');

    badge.textContent = status.charAt(0).toUpperCase() + status.slice(1);
    badge.className = 'status-badge ' + status;

    switch (status) {
        case 'running':
            startBtn.disabled = true;
            stopBtn.disabled = false;
            break;
        case 'completed':
        case 'failed':
        case 'stopped':
        case 'idle':
            startBtn.disabled = false;
            stopBtn.disabled = true;
            break;
    }
}

/**
 * Connect to WebSocket for live updates
 */
function connectWebSocket() {
    if (ws) {
        ws.close();
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws/execution`);

    ws.onopen = () => {
        console.log('WebSocket connected');
    };

    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        handleEvent(data);
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected');
        if (executionStatus === 'running') {
            // Try to reconnect
            setTimeout(connectWebSocket, 1000);
        }
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
    };
}

/**
 * Handle incoming WebSocket event
 */
function handleEvent(event) {
    if (event.type === 'status') {
        setExecutionStatus(event.status);

        // Update stage highlighting on canvas if available
        if (typeof highlightStage === 'function' && event.current_stage) {
            highlightStage(event.current_stage);
        }
        return;
    }

    switch (event.type) {
        case 'StageStartedEvent':
            addLogEntry(`▶ Stage started: ${event.stage}`, 'stage-started');
            break;

        case 'StageCompletedEvent':
            const signal = event.signal ? ` (${event.signal})` : '';
            addLogEntry(`✓ Stage completed: ${event.stage}${signal}`, 'stage-completed');
            break;

        case 'StageIterationEvent':
            addLogEntry(`  Iteration ${event.iteration}/${event.max_iterations}`, 'iteration');
            break;

        case 'PipelineCompletedEvent':
            addLogEntry(`✓ Pipeline ${event.status}: ${event.total_iterations} iterations`, 'pipeline');
            if (event.final_signal) {
                addLogEntry(`  Final signal: ${event.final_signal}`, 'iteration');
            }
            break;

        case 'OutputEvent':
            if (event.text) {
                addLogEntry(event.text, 'output');
            }
            break;

        case 'ErrorEvent':
        case 'error':
            addLogEntry(`✗ Error: ${event.message || event.error}`, 'error');
            break;

        default:
            // Log unknown events for debugging
            console.log('Unknown event:', event);
    }
}

/**
 * Add entry to log container
 */
function addLogEntry(text, type = 'default') {
    const container = document.getElementById('log-container');
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    entry.textContent = text;
    container.appendChild(entry);

    // Auto-scroll to bottom
    container.scrollTop = container.scrollHeight;

    // Limit log entries
    while (container.children.length > 500) {
        container.removeChild(container.firstChild);
    }
}

/**
 * Clear log entries
 */
function clearLog() {
    document.getElementById('log-container').innerHTML = '';
}

/**
 * Highlight a stage on the canvas
 */
function highlightStage(stageName) {
    if (typeof stages === 'undefined' || !stages.length) return;

    const index = stages.findIndex(s => s.name === stageName);
    if (index >= 0 && typeof selectedStageIndex !== 'undefined') {
        selectedStageIndex = index;
        if (typeof drawPipeline === 'function') {
            drawPipeline();
        }
    }
}

/**
 * Poll execution status (fallback if WebSocket fails)
 */
async function pollStatus() {
    if (executionStatus !== 'running') return;

    try {
        const status = await fetchJSON('/api/execution/status');
        setExecutionStatus(status.status);

        if (status.current_stage) {
            highlightStage(status.current_stage);
        }

        // Get new events
        const eventsData = await fetchJSON(`/api/execution/events?since=${window.lastEventIndex || 0}`);
        eventsData.events.forEach(handleEvent);
        window.lastEventIndex = eventsData.next_index;
    } catch (e) {
        console.error('Status poll failed:', e);
    }

    // Continue polling if still running
    if (executionStatus === 'running') {
        setTimeout(pollStatus, 2000);
    }
}

/**
 * Get execution statistics
 */
async function getStats() {
    try {
        return await fetchJSON('/api/execution/stats');
    } catch (e) {
        console.error('Failed to get stats:', e);
        return null;
    }
}

// Initialize
window.lastEventIndex = 0;

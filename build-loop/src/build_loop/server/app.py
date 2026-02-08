"""
FastAPI application for Spectre Build GUI.

Provides web interface for visual pipeline editing and execution monitoring.
"""

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from .routes import execution_router, pipelines_router, ws_router

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Spectre Build",
    description="Visual pipeline editor and execution monitor for Spectre Build",
    version="1.0.0",
)

# Add CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routers
app.include_router(pipelines_router)
app.include_router(execution_router)
app.include_router(ws_router)

# Get static files directory
STATIC_DIR = Path(__file__).parent / "static"


# Mount static files if directory exists
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> FileResponse:
    """Serve the main application page."""
    index_path = STATIC_DIR / "index.html"
    if index_path.is_file():
        return FileResponse(index_path)

    # Return embedded HTML if no static file exists
    return HTMLResponse(content=get_embedded_html())


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "service": "spectre-build"}


def get_embedded_html() -> str:
    """Return embedded HTML for when static files are not available."""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Spectre Build</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117;
            color: #c9d1d9;
            min-height: 100vh;
            display: flex;
            flex-direction: column;
        }
        header {
            background: #161b22;
            border-bottom: 1px solid #30363d;
            padding: 16px 24px;
            display: flex;
            align-items: center;
            gap: 16px;
        }
        header h1 {
            font-size: 20px;
            font-weight: 600;
            color: #f0f6fc;
        }
        .status-badge {
            padding: 4px 12px;
            border-radius: 16px;
            font-size: 12px;
            font-weight: 500;
            background: #238636;
            color: white;
        }
        .status-badge.idle { background: #6e7681; }
        .status-badge.running { background: #1f6feb; }
        .status-badge.failed { background: #da3633; }
        main {
            flex: 1;
            display: flex;
            gap: 1px;
            background: #30363d;
        }
        .panel {
            background: #0d1117;
            flex: 1;
            display: flex;
            flex-direction: column;
        }
        .panel-header {
            padding: 12px 16px;
            border-bottom: 1px solid #30363d;
            font-weight: 600;
            color: #f0f6fc;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .panel-content {
            flex: 1;
            padding: 16px;
            overflow: auto;
        }
        #canvas-container {
            width: 100%;
            height: 100%;
            position: relative;
        }
        canvas {
            width: 100%;
            height: 100%;
        }
        .log-entry {
            font-family: 'Monaco', 'Menlo', monospace;
            font-size: 12px;
            padding: 4px 0;
            border-bottom: 1px solid #21262d;
        }
        .log-entry.stage-started { color: #58a6ff; }
        .log-entry.stage-completed { color: #3fb950; }
        .log-entry.error { color: #f85149; }
        button {
            padding: 8px 16px;
            border-radius: 6px;
            border: 1px solid #30363d;
            background: #21262d;
            color: #c9d1d9;
            cursor: pointer;
            font-size: 14px;
            transition: background 0.2s;
        }
        button:hover {
            background: #30363d;
        }
        button.primary {
            background: #238636;
            border-color: #238636;
            color: white;
        }
        button.primary:hover {
            background: #2ea043;
        }
        button.danger {
            background: #da3633;
            border-color: #da3633;
            color: white;
        }
        .button-group {
            display: flex;
            gap: 8px;
        }
        .form-group {
            margin-bottom: 16px;
        }
        .form-group label {
            display: block;
            margin-bottom: 4px;
            font-size: 14px;
            color: #8b949e;
        }
        .form-group input, .form-group select {
            width: 100%;
            padding: 8px 12px;
            border-radius: 6px;
            border: 1px solid #30363d;
            background: #161b22;
            color: #c9d1d9;
            font-size: 14px;
        }
        .pipeline-list {
            list-style: none;
        }
        .pipeline-item {
            padding: 12px;
            border: 1px solid #30363d;
            border-radius: 6px;
            margin-bottom: 8px;
            cursor: pointer;
            transition: border-color 0.2s;
        }
        .pipeline-item:hover {
            border-color: #58a6ff;
        }
        .pipeline-item.selected {
            border-color: #58a6ff;
            background: #161b22;
        }
        .pipeline-item h3 {
            font-size: 14px;
            margin-bottom: 4px;
        }
        .pipeline-item p {
            font-size: 12px;
            color: #8b949e;
        }
        .empty-state {
            text-align: center;
            padding: 48px;
            color: #6e7681;
        }
        .stage-node {
            position: absolute;
            width: 120px;
            height: 60px;
            background: #161b22;
            border: 2px solid #30363d;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: move;
            font-weight: 500;
        }
        .stage-node.active {
            border-color: #58a6ff;
            box-shadow: 0 0 10px rgba(88, 166, 255, 0.3);
        }
        .stage-node.complete {
            border-color: #3fb950;
        }
    </style>
</head>
<body>
    <header>
        <h1>🔧 Spectre Build</h1>
        <span id="status-badge" class="status-badge idle">Idle</span>
    </header>
    <main>
        <div class="panel" style="max-width: 300px;">
            <div class="panel-header">Pipelines</div>
            <div class="panel-content">
                <div id="pipeline-list" class="pipeline-list">
                    <div class="empty-state">Loading pipelines...</div>
                </div>
                <button class="primary" style="width: 100%; margin-top: 16px;" onclick="createPipeline()">
                    + New Pipeline
                </button>
            </div>
        </div>
        <div class="panel" style="flex: 2;">
            <div class="panel-header">
                Pipeline Canvas
                <div class="button-group">
                    <button onclick="savePipeline()">Save</button>
                </div>
            </div>
            <div class="panel-content" id="canvas-container">
                <canvas id="pipeline-canvas"></canvas>
            </div>
        </div>
        <div class="panel" style="max-width: 400px;">
            <div class="panel-header">
                Execution
                <div class="button-group">
                    <button id="start-btn" class="primary" onclick="startExecution()">Start</button>
                    <button id="stop-btn" class="danger" onclick="stopExecution()" disabled>Stop</button>
                </div>
            </div>
            <div class="panel-content">
                <div class="form-group">
                    <label>Tasks File</label>
                    <input type="text" id="tasks-file" placeholder="docs/tasks.md">
                </div>
                <div class="form-group">
                    <label>Context Files (comma-separated)</label>
                    <input type="text" id="context-files" placeholder="docs/scope.md">
                </div>
                <div id="log-container" style="margin-top: 16px; max-height: 400px; overflow-y: auto;">
                </div>
            </div>
        </div>
    </main>

    <script>
        // State
        let pipelines = [];
        let selectedPipeline = null;
        let stages = [];
        let ws = null;

        // Canvas setup
        const canvas = document.getElementById('pipeline-canvas');
        const ctx = canvas.getContext('2d');

        function resizeCanvas() {
            const container = document.getElementById('canvas-container');
            canvas.width = container.clientWidth;
            canvas.height = container.clientHeight;
            drawPipeline();
        }
        window.addEventListener('resize', resizeCanvas);

        // API helpers
        async function fetchJSON(url, options = {}) {
            const response = await fetch(url, {
                ...options,
                headers: { 'Content-Type': 'application/json', ...options.headers }
            });
            if (!response.ok) throw new Error(await response.text());
            return response.json();
        }

        // Load pipelines
        async function loadPipelines() {
            try {
                pipelines = await fetchJSON('/api/pipelines');
                renderPipelineList();
            } catch (e) {
                document.getElementById('pipeline-list').innerHTML =
                    '<div class="empty-state">Failed to load pipelines</div>';
            }
        }

        function renderPipelineList() {
            const container = document.getElementById('pipeline-list');
            if (pipelines.length === 0) {
                container.innerHTML = '<div class="empty-state">No pipelines found.<br>Create one to get started.</div>';
                return;
            }
            container.innerHTML = pipelines.map(p => `
                <div class="pipeline-item ${selectedPipeline === p.name ? 'selected' : ''}"
                     onclick="selectPipeline('${p.name}')">
                    <h3>${p.name}</h3>
                    <p>${p.description || 'No description'}</p>
                    <p style="margin-top: 4px; color: #58a6ff;">${p.stages.join(' → ')}</p>
                </div>
            `).join('');
        }

        async function selectPipeline(name) {
            try {
                const data = await fetchJSON(`/api/pipelines/${name}`);
                selectedPipeline = name;
                stages = data.config.stages || [];
                renderPipelineList();
                drawPipeline();
            } catch (e) {
                console.error('Failed to load pipeline:', e);
            }
        }

        function createPipeline() {
            const name = prompt('Pipeline name:');
            if (!name) return;

            // Create default pipeline structure
            const config = {
                name: name,
                description: '',
                start_stage: 'build',
                end_signals: ['BUILD_COMPLETE', 'COMPLETE'],
                stages: [
                    {
                        name: 'build',
                        prompt: 'prompts/build.md',
                        completion: { type: 'promise', signals: ['TASK_COMPLETE', 'BUILD_COMPLETE'] },
                        max_iterations: 10,
                        transitions: { BUILD_COMPLETE: 'validate' }
                    },
                    {
                        name: 'validate',
                        prompt: 'prompts/validate.md',
                        completion: { type: 'json', statuses: ['COMPLETE', 'GAPS_FOUND'] },
                        max_iterations: 1,
                        transitions: { GAPS_FOUND: 'build' }
                    }
                ]
            };

            savePipelineConfig(name, config);
        }

        async function savePipelineConfig(name, config) {
            try {
                await fetchJSON(`/api/pipelines/${name}`, {
                    method: 'PUT',
                    body: JSON.stringify({ config })
                });
                await loadPipelines();
                selectPipeline(name);
            } catch (e) {
                alert('Failed to save pipeline: ' + e.message);
            }
        }

        function savePipeline() {
            if (!selectedPipeline || stages.length === 0) {
                alert('No pipeline selected');
                return;
            }
            // In a full implementation, this would collect the edited stage data
            alert('Save functionality - edit stages on canvas first');
        }

        // Draw pipeline on canvas
        function drawPipeline() {
            ctx.clearRect(0, 0, canvas.width, canvas.height);

            if (stages.length === 0) {
                ctx.fillStyle = '#6e7681';
                ctx.font = '14px sans-serif';
                ctx.textAlign = 'center';
                ctx.fillText('Select a pipeline to view', canvas.width / 2, canvas.height / 2);
                return;
            }

            const nodeWidth = 120;
            const nodeHeight = 60;
            const startX = 50;
            const startY = canvas.height / 2 - nodeHeight / 2;
            const gap = 80;

            // Draw connections
            ctx.strokeStyle = '#30363d';
            ctx.lineWidth = 2;
            stages.forEach((stage, i) => {
                if (i < stages.length - 1) {
                    const x1 = startX + i * (nodeWidth + gap) + nodeWidth;
                    const x2 = startX + (i + 1) * (nodeWidth + gap);
                    ctx.beginPath();
                    ctx.moveTo(x1, startY + nodeHeight / 2);
                    ctx.lineTo(x2, startY + nodeHeight / 2);
                    ctx.stroke();

                    // Arrow
                    ctx.beginPath();
                    ctx.moveTo(x2 - 10, startY + nodeHeight / 2 - 5);
                    ctx.lineTo(x2, startY + nodeHeight / 2);
                    ctx.lineTo(x2 - 10, startY + nodeHeight / 2 + 5);
                    ctx.stroke();
                }
            });

            // Draw nodes
            stages.forEach((stage, i) => {
                const x = startX + i * (nodeWidth + gap);
                const y = startY;

                // Node background
                ctx.fillStyle = '#161b22';
                ctx.strokeStyle = '#30363d';
                ctx.lineWidth = 2;
                ctx.beginPath();
                ctx.roundRect(x, y, nodeWidth, nodeHeight, 8);
                ctx.fill();
                ctx.stroke();

                // Node text
                ctx.fillStyle = '#c9d1d9';
                ctx.font = '14px sans-serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(stage.name, x + nodeWidth / 2, y + nodeHeight / 2);

                // Max iterations badge
                ctx.fillStyle = '#6e7681';
                ctx.font = '10px sans-serif';
                ctx.fillText(`max: ${stage.max_iterations}`, x + nodeWidth / 2, y + nodeHeight - 8);
            });
        }

        // Execution
        async function startExecution() {
            if (!selectedPipeline) {
                alert('Select a pipeline first');
                return;
            }

            const tasksFile = document.getElementById('tasks-file').value;
            if (!tasksFile) {
                alert('Enter a tasks file path');
                return;
            }

            const contextFiles = document.getElementById('context-files').value
                .split(',')
                .map(s => s.trim())
                .filter(s => s);

            try {
                await fetchJSON('/api/execution/start', {
                    method: 'POST',
                    body: JSON.stringify({
                        pipeline_name: selectedPipeline,
                        tasks_file: tasksFile,
                        context_files: contextFiles,
                        agent: 'claude'
                    })
                });

                document.getElementById('start-btn').disabled = true;
                document.getElementById('stop-btn').disabled = false;
                document.getElementById('status-badge').textContent = 'Running';
                document.getElementById('status-badge').className = 'status-badge running';

                connectWebSocket();
            } catch (e) {
                alert('Failed to start: ' + e.message);
            }
        }

        async function stopExecution() {
            try {
                await fetchJSON('/api/execution/stop', { method: 'POST' });
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
                document.getElementById('status-badge').textContent = 'Stopped';
                document.getElementById('status-badge').className = 'status-badge idle';
            } catch (e) {
                alert('Failed to stop: ' + e.message);
            }
        }

        function connectWebSocket() {
            const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${location.host}/ws/execution`);

            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleEvent(data);
            };

            ws.onclose = () => {
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
            };
        }

        function handleEvent(event) {
            const container = document.getElementById('log-container');

            if (event.type === 'status') {
                const badge = document.getElementById('status-badge');
                badge.textContent = event.status.charAt(0).toUpperCase() + event.status.slice(1);
                badge.className = `status-badge ${event.status}`;

                if (event.status === 'completed' || event.status === 'failed' || event.status === 'stopped') {
                    document.getElementById('start-btn').disabled = false;
                    document.getElementById('stop-btn').disabled = true;
                }
                return;
            }

            const div = document.createElement('div');
            div.className = `log-entry ${event.type.toLowerCase().replace('event', '')}`;

            switch (event.type) {
                case 'StageStartedEvent':
                    div.className += ' stage-started';
                    div.textContent = `▶ Stage started: ${event.stage}`;
                    break;
                case 'StageCompletedEvent':
                    div.className += ' stage-completed';
                    div.textContent = `✓ Stage completed: ${event.stage} (${event.signal})`;
                    break;
                case 'StageIterationEvent':
                    div.textContent = `  Iteration ${event.iteration}/${event.max_iterations}`;
                    break;
                case 'PipelineCompletedEvent':
                    div.textContent = `✓ Pipeline ${event.status}: ${event.total_iterations} iterations`;
                    break;
                default:
                    div.textContent = JSON.stringify(event);
            }

            container.appendChild(div);
            container.scrollTop = container.scrollHeight;
        }

        // Initialize
        resizeCanvas();
        loadPipelines();
    </script>
</body>
</html>"""

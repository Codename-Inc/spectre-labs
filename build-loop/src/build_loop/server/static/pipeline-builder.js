/**
 * Pipeline Builder - Canvas-based visual pipeline editor
 */

// State
let pipelines = [];
let selectedPipeline = null;
let pipelineConfig = null;
let stages = [];
let selectedStageIndex = -1;
let editingStageIndex = -1;

// Drag state
let isDragging = false;
let dragStageIndex = -1;
let dragOffsetX = 0;
let dragOffsetY = 0;

// Stage positions (calculated or stored)
let stagePositions = [];

// Canvas setup
const canvas = document.getElementById('pipeline-canvas');
const ctx = canvas.getContext('2d');

// Node dimensions
const NODE_WIDTH = 140;
const NODE_HEIGHT = 70;
const NODE_GAP = 100;
const NODE_PADDING = 50;

/**
 * Resize canvas to container
 */
function resizeCanvas() {
    const container = document.getElementById('canvas-container');
    canvas.width = container.clientWidth;
    canvas.height = container.clientHeight;
    calculateStagePositions();
    drawPipeline();
}

window.addEventListener('resize', resizeCanvas);

/**
 * Calculate automatic stage positions
 */
function calculateStagePositions() {
    stagePositions = stages.map((stage, i) => ({
        x: NODE_PADDING + i * (NODE_WIDTH + NODE_GAP),
        y: canvas.height / 2 - NODE_HEIGHT / 2
    }));
}

/**
 * API helper for JSON requests
 */
async function fetchJSON(url, options = {}) {
    const response = await fetch(url, {
        ...options,
        headers: { 'Content-Type': 'application/json', ...options.headers }
    });
    if (!response.ok) {
        const text = await response.text();
        throw new Error(text);
    }
    return response.json();
}

/**
 * Load all pipelines from server
 */
async function loadPipelines() {
    const container = document.getElementById('pipeline-list');
    container.innerHTML = '<div class="empty-state">Loading...</div>';

    try {
        console.log('Fetching pipelines...');
        pipelines = await fetchJSON('/api/pipelines');
        console.log('Loaded pipelines:', pipelines);
        renderPipelineList();

        // Auto-select first pipeline if none selected
        if (pipelines.length > 0 && !selectedPipeline) {
            console.log('Auto-selecting first pipeline:', pipelines[0].name);
            await selectPipeline(pipelines[0].name);
        }
    } catch (e) {
        container.innerHTML =
            `<div class="empty-state">Failed to load pipelines<br><small>${e.message}</small></div>`;
        console.error('Failed to load pipelines:', e);
    }
}

/**
 * Render the pipeline list sidebar
 */
function renderPipelineList() {
    const container = document.getElementById('pipeline-list');
    if (pipelines.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                No pipelines found.<br>
                Create one to get started.
            </div>
        `;
        return;
    }
    container.innerHTML = pipelines.map(p => `
        <div class="pipeline-item ${selectedPipeline === p.name ? 'selected' : ''}"
             onclick="selectPipeline('${p.name}')">
            <h3>${p.name}</h3>
            <p>${p.description || 'No description'}</p>
            <div class="stages">${p.stages.join(' → ')}</div>
        </div>
    `).join('');
}

/**
 * Select and load a pipeline
 */
async function selectPipeline(name) {
    try {
        const data = await fetchJSON(`/api/pipelines/${name}`);
        selectedPipeline = name;
        pipelineConfig = data.config;
        stages = data.config.stages || [];
        document.getElementById('canvas-title').textContent = `Pipeline: ${name}`;
        renderPipelineList();
        calculateStagePositions();
        drawPipeline();
    } catch (e) {
        console.error('Failed to load pipeline:', e);
        alert('Failed to load pipeline: ' + e.message);
    }
}

/**
 * Create a new pipeline
 */
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

/**
 * Save pipeline configuration to server
 */
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

/**
 * Save current pipeline
 */
async function savePipeline() {
    if (!selectedPipeline || !pipelineConfig) {
        alert('No pipeline selected');
        return;
    }

    // Update config with current stages
    pipelineConfig.stages = stages;

    try {
        await fetchJSON(`/api/pipelines/${selectedPipeline}`, {
            method: 'PUT',
            body: JSON.stringify({ config: pipelineConfig })
        });
        await loadPipelines();
        alert('Pipeline saved!');
    } catch (e) {
        alert('Failed to save pipeline: ' + e.message);
    }
}

/**
 * Add a new stage
 */
function addStage() {
    if (!selectedPipeline) {
        alert('Select a pipeline first');
        return;
    }

    editingStageIndex = -1; // New stage
    document.getElementById('stage-modal-title').textContent = 'Add Stage';
    document.getElementById('delete-stage-btn').style.display = 'none';

    // Clear form
    document.getElementById('stage-name').value = '';
    document.getElementById('stage-prompt').value = 'prompts/';
    document.getElementById('stage-max-iterations').value = '10';
    document.getElementById('stage-completion-type').value = 'promise';
    document.getElementById('stage-signals').value = 'TASK_COMPLETE, BUILD_COMPLETE';
    document.getElementById('stage-statuses').value = 'COMPLETE';
    document.getElementById('stage-transitions').value = '';

    updateCompletionFields();
    document.getElementById('stage-modal').style.display = 'flex';
}

/**
 * Edit an existing stage
 */
function editStage(index) {
    if (index < 0 || index >= stages.length) return;

    editingStageIndex = index;
    const stage = stages[index];

    document.getElementById('stage-modal-title').textContent = 'Edit Stage';
    document.getElementById('delete-stage-btn').style.display = 'block';

    // Populate form
    document.getElementById('stage-name').value = stage.name || '';
    document.getElementById('stage-prompt').value = stage.prompt || '';
    document.getElementById('stage-max-iterations').value = stage.max_iterations || 10;

    const completionType = stage.completion?.type || 'promise';
    document.getElementById('stage-completion-type').value = completionType;

    if (completionType === 'promise') {
        const signals = stage.completion?.signals || [];
        document.getElementById('stage-signals').value = signals.join(', ');
    } else {
        const statuses = stage.completion?.statuses || [];
        document.getElementById('stage-statuses').value = statuses.join(', ');
    }

    // Format transitions
    const transitions = stage.transitions || {};
    const transitionLines = Object.entries(transitions)
        .map(([signal, target]) => `${signal} → ${target}`)
        .join('\n');
    document.getElementById('stage-transitions').value = transitionLines;

    updateCompletionFields();
    document.getElementById('stage-modal').style.display = 'flex';
}

/**
 * Update completion type form fields
 */
function updateCompletionFields() {
    const type = document.getElementById('stage-completion-type').value;
    document.getElementById('promise-signals-group').style.display = type === 'promise' ? 'block' : 'none';
    document.getElementById('json-statuses-group').style.display = type === 'json' ? 'block' : 'none';
}

document.getElementById('stage-completion-type').addEventListener('change', updateCompletionFields);

/**
 * Save stage from modal
 */
function saveStage() {
    const name = document.getElementById('stage-name').value.trim();
    if (!name) {
        alert('Stage name is required');
        return;
    }

    const completionType = document.getElementById('stage-completion-type').value;
    const completion = { type: completionType };

    if (completionType === 'promise') {
        completion.signals = document.getElementById('stage-signals').value
            .split(',')
            .map(s => s.trim())
            .filter(s => s);
    } else {
        completion.statuses = document.getElementById('stage-statuses').value
            .split(',')
            .map(s => s.trim())
            .filter(s => s);
    }

    // Parse transitions
    const transitionLines = document.getElementById('stage-transitions').value.split('\n');
    const transitions = {};
    for (const line of transitionLines) {
        const match = line.match(/^\s*(\w+)\s*(?:→|->|=>)+\s*(\w+)\s*$/);
        if (match) {
            transitions[match[1]] = match[2];
        }
    }

    const stage = {
        name: name,
        prompt: document.getElementById('stage-prompt').value.trim(),
        completion: completion,
        max_iterations: parseInt(document.getElementById('stage-max-iterations').value) || 10,
        transitions: transitions
    };

    if (editingStageIndex >= 0) {
        // Update existing stage
        stages[editingStageIndex] = stage;
    } else {
        // Add new stage
        stages.push(stage);
    }

    closeStageModal();
    calculateStagePositions();
    drawPipeline();
}

/**
 * Delete current stage
 */
function deleteStage() {
    if (editingStageIndex < 0 || !confirm('Delete this stage?')) return;

    stages.splice(editingStageIndex, 1);
    closeStageModal();
    calculateStagePositions();
    drawPipeline();
}

/**
 * Close stage modal
 */
function closeStageModal() {
    document.getElementById('stage-modal').style.display = 'none';
    editingStageIndex = -1;
}

/**
 * Draw the pipeline on canvas
 */
function drawPipeline() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    if (stages.length === 0) {
        ctx.fillStyle = '#6e7681';
        ctx.font = '14px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('Select a pipeline to view', canvas.width / 2, canvas.height / 2);
        return;
    }

    // Draw connections first (so they're behind nodes)
    drawConnections();

    // Draw nodes
    stages.forEach((stage, i) => {
        drawStageNode(stage, i);
    });
}

/**
 * Draw connections between stages
 */
function drawConnections() {
    ctx.lineWidth = 2;

    // Create a map of stage names to indices
    const stageIndices = {};
    stages.forEach((stage, i) => {
        stageIndices[stage.name] = i;
    });

    // Draw transitions
    stages.forEach((stage, i) => {
        const fromPos = stagePositions[i];
        const transitions = stage.transitions || {};

        for (const [signal, targetName] of Object.entries(transitions)) {
            const targetIndex = stageIndices[targetName];
            if (targetIndex === undefined) continue;

            const toPos = stagePositions[targetIndex];

            // Determine if this is a forward or backward connection
            if (targetIndex > i) {
                // Forward: straight line from right edge to left edge
                drawArrow(
                    fromPos.x + NODE_WIDTH,
                    fromPos.y + NODE_HEIGHT / 2,
                    toPos.x,
                    toPos.y + NODE_HEIGHT / 2,
                    '#58a6ff'
                );
            } else if (targetIndex === i) {
                // Self-loop: small loop on the right side
                drawSelfLoop(fromPos.x, fromPos.y, '#f0883e');
            } else {
                // Backward: curved line going above the nodes
                drawBackwardArrow(fromPos, toPos, '#f0883e');
            }
        }
    });
}

/**
 * Draw an arrow between two points
 */
function drawArrow(x1, y1, x2, y2, color) {
    ctx.strokeStyle = color;
    ctx.fillStyle = color;

    // Line
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2 - 10, y2);
    ctx.stroke();

    // Arrowhead
    ctx.beginPath();
    ctx.moveTo(x2 - 10, y2 - 5);
    ctx.lineTo(x2, y2);
    ctx.lineTo(x2 - 10, y2 + 5);
    ctx.closePath();
    ctx.fill();
}

/**
 * Draw a backward arrow (loop back to earlier stage)
 */
function drawBackwardArrow(fromPos, toPos, color) {
    ctx.strokeStyle = color;
    ctx.fillStyle = color;

    // Start from bottom of source node
    const x1 = fromPos.x + NODE_WIDTH / 2;
    const y1 = fromPos.y + NODE_HEIGHT;

    // End at left side of target node
    const x2 = toPos.x;
    const y2 = toPos.y + NODE_HEIGHT / 2;

    // Calculate curve control points - go below and to the left
    const maxY = Math.max(y1, toPos.y + NODE_HEIGHT) + 50;

    ctx.beginPath();
    ctx.moveTo(x1, y1);
    // First curve down and left
    ctx.bezierCurveTo(
        x1, maxY,           // control point 1: straight down
        x2 - 50, maxY,      // control point 2: at the bottom, left of target
        x2 - 50, y2         // intermediate point: left of target
    );
    // Then curve into the target
    ctx.quadraticCurveTo(
        x2 - 20, y2,        // control point
        x2, y2              // end point
    );
    ctx.stroke();

    // Arrowhead pointing right into the node
    ctx.beginPath();
    ctx.moveTo(x2 - 8, y2 - 4);
    ctx.lineTo(x2, y2);
    ctx.lineTo(x2 - 8, y2 + 4);
    ctx.closePath();
    ctx.fill();
}

/**
 * Draw a self-loop arrow
 */
function drawSelfLoop(x, y, color) {
    ctx.strokeStyle = color;
    ctx.fillStyle = color;

    const cx = x + NODE_WIDTH + 20;
    const cy = y + NODE_HEIGHT / 2;
    const radius = 15;

    // Draw circle arc
    ctx.beginPath();
    ctx.arc(cx, cy, radius, Math.PI * 0.5, Math.PI * 2.5, false);
    ctx.stroke();

    // Arrowhead
    ctx.beginPath();
    ctx.moveTo(cx - radius - 4, cy + 5);
    ctx.lineTo(cx - radius, cy - 2);
    ctx.lineTo(cx - radius + 6, cy + 3);
    ctx.closePath();
    ctx.fill();
}

/**
 * Draw a single stage node
 */
function drawStageNode(stage, index) {
    const pos = stagePositions[index];
    const x = pos.x;
    const y = pos.y;
    const isSelected = index === selectedStageIndex;

    // Node background
    ctx.fillStyle = isSelected ? '#1f2937' : '#161b22';
    ctx.strokeStyle = isSelected ? '#58a6ff' : '#30363d';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.roundRect(x, y, NODE_WIDTH, NODE_HEIGHT, 8);
    ctx.fill();
    ctx.stroke();

    // Start stage indicator
    if (pipelineConfig && stage.name === pipelineConfig.start_stage) {
        ctx.fillStyle = '#238636';
        ctx.beginPath();
        ctx.arc(x + 10, y + 10, 5, 0, Math.PI * 2);
        ctx.fill();
    }

    // Stage name
    ctx.fillStyle = '#f0f6fc';
    ctx.font = '14px sans-serif';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText(stage.name, x + NODE_WIDTH / 2, y + NODE_HEIGHT / 2 - 8);

    // Max iterations badge
    ctx.fillStyle = '#6e7681';
    ctx.font = '11px sans-serif';
    ctx.fillText(`max: ${stage.max_iterations}`, x + NODE_WIDTH / 2, y + NODE_HEIGHT / 2 + 12);

    // Completion type indicator
    const typeLabel = stage.completion?.type === 'json' ? 'JSON' : 'Promise';
    ctx.fillStyle = '#8b949e';
    ctx.font = '10px sans-serif';
    ctx.fillText(typeLabel, x + NODE_WIDTH / 2, y + NODE_HEIGHT - 10);
}

/**
 * Canvas click handler
 */
canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if clicked on a stage
    for (let i = 0; i < stagePositions.length; i++) {
        const pos = stagePositions[i];
        if (x >= pos.x && x <= pos.x + NODE_WIDTH &&
            y >= pos.y && y <= pos.y + NODE_HEIGHT) {
            selectedStageIndex = i;
            drawPipeline();
            return;
        }
    }

    // Clicked on empty space
    selectedStageIndex = -1;
    drawPipeline();
});

/**
 * Canvas double-click handler (edit stage)
 */
canvas.addEventListener('dblclick', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if double-clicked on a stage
    for (let i = 0; i < stagePositions.length; i++) {
        const pos = stagePositions[i];
        if (x >= pos.x && x <= pos.x + NODE_WIDTH &&
            y >= pos.y && y <= pos.y + NODE_HEIGHT) {
            editStage(i);
            return;
        }
    }
});

/**
 * Canvas drag handlers
 */
canvas.addEventListener('mousedown', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    // Check if started drag on a stage
    for (let i = 0; i < stagePositions.length; i++) {
        const pos = stagePositions[i];
        if (x >= pos.x && x <= pos.x + NODE_WIDTH &&
            y >= pos.y && y <= pos.y + NODE_HEIGHT) {
            isDragging = true;
            dragStageIndex = i;
            dragOffsetX = x - pos.x;
            dragOffsetY = y - pos.y;
            canvas.style.cursor = 'grabbing';
            return;
        }
    }
});

canvas.addEventListener('mousemove', (e) => {
    const rect = canvas.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;

    if (isDragging && dragStageIndex >= 0) {
        stagePositions[dragStageIndex] = {
            x: x - dragOffsetX,
            y: y - dragOffsetY
        };
        drawPipeline();
    } else {
        // Update cursor based on hover
        let onNode = false;
        for (let i = 0; i < stagePositions.length; i++) {
            const pos = stagePositions[i];
            if (x >= pos.x && x <= pos.x + NODE_WIDTH &&
                y >= pos.y && y <= pos.y + NODE_HEIGHT) {
                onNode = true;
                break;
            }
        }
        canvas.style.cursor = onNode ? 'grab' : 'default';
    }
});

canvas.addEventListener('mouseup', () => {
    isDragging = false;
    dragStageIndex = -1;
    canvas.style.cursor = 'default';
});

canvas.addEventListener('mouseleave', () => {
    isDragging = false;
    dragStageIndex = -1;
    canvas.style.cursor = 'default';
});

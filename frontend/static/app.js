const API_BASE = '/api/v1';
const WS_URL = '/ws/clinical';

let ws = null;
let patients = [];
let selectedPatient = null;
let currentUser = null;
let ecgData = [];
let spo2Data = [];
const SESSION_KEY = 'codeblue_session';
const PATIENT_KEY = 'codeblue_selected_patient';
const USER_KEY = 'codeblue_user';

function initClock() {
    function updateClock() {
        const now = new Date();
        document.getElementById('mainClock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
        document.getElementById('mainDate').textContent = now.toISOString().split('T')[0];
    }
    updateClock();
    setInterval(updateClock, 1000);
}

function saveSession() {
    const session = {
        selectedPatient: selectedPatient ? selectedPatient.id : null,
        timestamp: Date.now(),
    };
    localStorage.setItem(PATIENT_KEY, JSON.stringify(session));
}

function restoreSession() {
    try {
        const saved = localStorage.getItem(PATIENT_KEY);
        if (saved) {
            const session = JSON.parse(saved);
            const age = (Date.now() - session.timestamp) / 1000 / 60;
            if (age < 480 && session.selectedPatient) {
                return session.selectedPatient;
            }
            localStorage.removeItem(PATIENT_KEY);
        }
    } catch (e) {
        localStorage.removeItem(PATIENT_KEY);
    }
    return null;
}

async function checkAuth() {
    const savedUser = localStorage.getItem(USER_KEY);
    if (savedUser) {
        try {
            const user = JSON.parse(savedUser);
            if (user.access_token) {
                currentUser = user;
                updateUserDisplay();
                return true;
            }
        } catch (e) {
            localStorage.removeItem(USER_KEY);
        }
    }

    const result = await loginDemo();
    if (result) {
        updateUserDisplay();
    }
    return !!result;
}

async function loginDemo() {
    try {
        const response = await fetch(`${API_BASE}/auth/login`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({username: 'physician', password: 'Physician123!'}),
        });
        if (response.ok) {
            const data = await response.json();
            currentUser = data.user;
            currentUser.access_token = data.access_token;
            localStorage.setItem(USER_KEY, JSON.stringify(currentUser));
            return true;
        }
    } catch (e) {
        console.error('Auth failed:', e);
    }
    return false;
}

async function apiFetch(endpoint, options = {}) {
    const headers = {'Content-Type': 'application/json'};
    if (currentUser && currentUser.access_token) {
        headers['Authorization'] = `Bearer ${currentUser.access_token}`;
    }

    const response = await fetch(`${API_BASE}${endpoint}`, {
        ...options,
        headers: {...headers, ...options.headers},
    });

    if (response.status === 401) {
        localStorage.removeItem(USER_KEY);
        await checkAuth();
        return apiFetch(endpoint, options);
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({detail: 'Request failed'}));
        throw new Error(error.detail || `HTTP ${response.status}`);
    }

    return response.json();
}

function updateUserDisplay() {
    const userInfo = document.querySelector('.user-info');
    if (userInfo && currentUser) {
        userInfo.innerHTML = `
            <span class="user-name">${currentUser.full_name || currentUser.username}</span>
            <span class="user-role">${currentUser.role?.toUpperCase() || 'USER'}</span>
        `;
    }
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${WS_URL}`;

    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
        console.log('WebSocket connected');
        if (currentUser && currentUser.access_token) {
            ws.send(JSON.stringify({type: 'AUTH', token: currentUser.access_token}));
        }
        addSystemMessage('Clinical monitoring websocket connected');
    };

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleWebSocketMessage(data);
        } catch (e) {
            console.error('WebSocket parse error:', e);
        }
    };

    ws.onclose = () => {
        console.log('WebSocket disconnected, reconnecting...');
        setTimeout(initWebSocket, 3000);
    };

    ws.onerror = (err) => {
        console.error('WebSocket error:', err);
    };
}

function handleWebSocketMessage(data) {
    if (data.type === 'ALERT') {
        displayAlert(data);
        if (data.patient_id === selectedPatient?.id) {
            updateScores(data.scores);
        }
    } else if (data.type === 'AGENT_MESSAGE') {
        addAgentMessage(data.agent, data.message, data.data);
    } else if (data.type === 'DEMO_START') {
        handleDemoStart(data);
    } else if (data.type === 'SESSION_RESTORED') {
        if (data.selected_patient_id) {
            selectPatient(data.selected_patient_id);
        }
    }
}

async function loadPatients() {
    try {
        const data = await apiFetch('/patients?limit=100');
        patients = data;
        renderPatientList(patients);
        updateFooterStats();

        const restoredPatientId = restoreSession();
        if (restoredPatientId) {
            const exists = patients.find(p => p.id === restoredPatientId);
            if (exists) {
                await selectPatient(restoredPatientId);
            }
        }
    } catch (error) {
        console.error('Failed to load patients:', error);
        document.getElementById('patientList').innerHTML = '<div class="loading-indicator">Failed to load patients</div>';
    }
}

function renderPatientList(patientList) {
    const container = document.getElementById('patientList');

    if (!patientList || patientList.length === 0) {
        container.innerHTML = '<div class="loading-indicator">No patients found</div>';
        return;
    }

    container.innerHTML = patientList.map(p => `
        <div class="patient-item ${selectedPatient?.id === p.id ? 'selected' : ''}" data-id="${p.id}" onclick="selectPatient('${p.id}')">
            <div class="patient-header">
                <span class="patient-name">${p.first_name} ${p.last_name}</span>
                <span class="risk-indicator ${p.risk_level}">${p.risk_level}</span>
            </div>
            <div class="patient-meta">
                <span class="patient-mrn">${p.mrn}</span>
                <span class="patient-bed">Bed ${p.bed_number}</span>
            </div>
            <div class="patient-diagnosis">${p.primary_diagnosis || 'No diagnosis'}</div>
        </div>
    `).join('');

    document.getElementById('patientCount').textContent = `${patientList.length} patients`;
}

async function selectPatient(patientId) {
    document.querySelectorAll('.patient-item').forEach(el => el.classList.remove('selected'));
    document.querySelector(`[data-id="${patientId}"]`)?.classList.add('selected');

    try {
        const patient = await apiFetch(`/patients/${patientId}`);
        selectedPatient = patient;

        saveSession();

        document.getElementById('patientInfoDisplay').innerHTML = `
            <div>
                <div class="patient-name">${patient.first_name} ${patient.last_name}</div>
                <div class="patient-details">
                    <span>${patient.mrn}</span>
                    <span>${patient.sex === 'M' ? 'Male' : 'Female'}</span>
                    <span>${calculateAge(patient.date_of_birth)} y/o</span>
                    <span>Bed ${patient.bed_number}</span>
                    <span>${patient.unit_type}</span>
                </div>
            </div>
        `;

        updateVitals(patient);
        updateMedications(patient.medications || []);
        updateAllergies(patient.allergies || []);

        try {
            const analysis = await apiFetch(`/analyze/${patientId}`);
            updateScores(analysis.monitor.scores);
            updateExplainability(analysis);
        } catch (e) {
            console.error('Analysis failed:', e);
        }

        startWaveformSimulation();

    } catch (error) {
        console.error('Failed to load patient details:', error);
    }
}

function calculateAge(dob) {
    const birthDate = new Date(dob);
    const today = new Date();
    let age = today.getFullYear() - birthDate.getFullYear();
    const monthDiff = today.getMonth() - birthDate.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birthDate.getDate())) {
        age--;
    }
    return age;
}

function updateVitals(patient) {
    const latestVitals = patient.vitals?.[patient.vitals.length - 1] || {};

    document.getElementById('hrValue').textContent = latestVitals.heart_rate || '--';
    document.getElementById('bpValue').textContent = latestVitals.systolic_bp && latestVitals.diastolic_bp
        ? `${Math.round(latestVitals.systolic_bp)}/${Math.round(latestVitals.diastolic_bp)}`
        : '--/--';
    document.getElementById('spo2Value').textContent = latestVitals.spo2 || '--';
    document.getElementById('rrValue').textContent = latestVitals.respiratory_rate || '--';
    document.getElementById('tempValue').textContent = latestVitals.temperature
        ? latestVitals.temperature.toFixed(1)
        : '--';
    document.getElementById('mapValue').textContent = latestVitals.mean_arterial_pressure
        ? Math.round(latestVitals.mean_arterial_pressure)
        : '--';
    document.getElementById('lactateValue').textContent = latestVitals.lactate
        ? latestVitals.lactate.toFixed(1)
        : '--';
    document.getElementById('gcsValue').textContent = latestVitals.gcs || '--';

    checkVitalAlerts(latestVitals);
}

function checkVitalAlerts(vitals) {
    document.getElementById('cardHR').classList.toggle('alert', vitals.heart_rate > 130 || vitals.heart_rate < 50);
    document.getElementById('cardBP').classList.toggle('alert', vitals.systolic_bp < 90);
    document.getElementById('cardSpO2').classList.toggle('alert', vitals.spo2 < 88);
    document.getElementById('cardLactate').classList.toggle('alert', vitals.lactate > 4.0);
}

function updateMedications(medications) {
    // Available for future enhancement
}

function updateAllergies(allergies) {
    // Available for future enhancement
}

function updateScores(scores) {
    if (scores.NEWS2) {
        document.getElementById('news2Value').textContent = Math.round(scores.NEWS2.value);
        document.getElementById('news2Interp').textContent = scores.NEWS2.interpretation;
        document.getElementById('news2Card').style.borderColor = getScoreColor(scores.NEWS2.risk_level);
    }

    if (scores.SOFA) {
        document.getElementById('sofaValue').textContent = Math.round(scores.SOFA.value);
        document.getElementById('sofaInterp').textContent = scores.SOFA.interpretation;
        document.getElementById('sofaCard').style.borderColor = getScoreColor(scores.SOFA.risk_level);
    }

    if (scores.qSOFA) {
        document.getElementById('qsofaValue').textContent = Math.round(scores.qSOFA.value);
        document.getElementById('qsofaInterp').textContent = scores.qSOFA.interpretation;
        document.getElementById('qsofaCard').style.borderColor = getScoreColor(scores.qSOFA.risk_level);
    }

    if (scores.SEPSIS_RISK !== undefined) {
        document.getElementById('sepsisValue').textContent = `${(scores.SEPSIS_RISK * 100).toFixed(0)}%`;
        document.getElementById('sepsisCard').style.borderColor = scores.SEPSIS_RISK > 0.5 ? '#ff3b4e' : '#6bff6b';
    }
}

function getScoreColor(riskLevel) {
    const colors = {
        'CRITICAL': '#ff3b4e',
        'HIGH': '#ff6b35',
        'MODERATE': '#ffd93d',
        'LOW': '#6bff6b',
    };
    return colors[riskLevel] || '#00d4aa';
}

function updateExplainability(analysis) {
    const container = document.getElementById('explainabilityContent');

    let html = `
        <div class="explain-section">
            <h4>Diagnosis Reasoning</h4>
            <p>Primary: ${analysis.diagnostic?.primary_diagnosis || 'N/A'}</p>
            <p>Confidence: ${analysis.diagnostic?.risk_prediction?.mortality_risk || 'N/A'}</p>
        </div>
        <div class="explain-section">
            <h4>Evidence</h4>
            <ul>
                ${(analysis.diagnostic?.differential || []).slice(0, 3).map(d => `
                    <li><strong>${d.name}</strong> (${(d.probability * 100).toFixed(0)}%)</li>
                `).join('')}
            </ul>
        </div>
        <div class="explain-section">
            <h4>Protocol: ${analysis.guideline?.protocol || 'N/A'}</h4>
            <p>Urgency: ${analysis.guideline?.urgency || 'N/A'}</p>
            <p>First intervention: ${analysis.guideline?.interventions?.[0]?.action || 'N/A'}</p>
        </div>
        <div class="explain-section">
            <h4>Escalation: ${analysis.coordinator?.level || 'N/A'}</h4>
            <p>${analysis.coordinator?.reason || 'N/A'}</p>
        </div>
    `;

    container.innerHTML = html;
}

function addAgentMessage(agentType, content, data = null) {
    const feed = document.getElementById('agentFeed');
    const badgeClass = agentType.toLowerCase().replace('agent', '');

    const messageEl = document.createElement('div');
    messageEl.className = 'agent-message';
    messageEl.innerHTML = `
        <span class="agent-badge ${badgeClass}">${agentType.toUpperCase()}</span>
        <div class="agent-content">${content}</div>
        <div class="agent-time">${new Date().toLocaleTimeString()}</div>
    `;

    feed.insertBefore(messageEl, feed.firstChild);

    while (feed.children.length > 50) {
        feed.removeChild(feed.lastChild);
    }
}

function addSystemMessage(content) {
    addAgentMessage('System', content);
}

function displayAlert(data) {
    const alertsList = document.getElementById('alertsList');
    const countEl = document.getElementById('alertCount');

    if (data.alerts && data.alerts.length > 0) {
        const noAlerts = alertsList.querySelector('.no-alerts');
        if (noAlerts) noAlerts.remove();

        data.alerts.forEach(alert => {
            const alertEl = document.createElement('div');
            alertEl.className = 'alert-item';
            alertEl.innerHTML = `
                <strong>${alert.title}</strong>
                <p>${alert.description}</p>
            `;
            alertsList.insertBefore(alertEl, alertsList.firstChild);
        });

        countEl.textContent = parseInt(countEl.textContent || 0) + data.alerts.length;
        addAgentMessage('Monitor', `ALERT: ${data.alerts[0].title} for patient ${data.mrn}`);
    }
}

function updateFooterStats() {
    const criticalCount = patients.filter(p => p.risk_level === 'CRITICAL' || p.risk_level === 'HIGH').length;
    document.getElementById('totalPatients').textContent = patients.length;
    document.getElementById('criticalCount').textContent = criticalCount;
}

function startWaveformSimulation() {
    const ecgCanvas = document.getElementById('ecgWaveform');
    const spo2Canvas = document.getElementById('spo2Waveform');
    if (!ecgCanvas || !spo2Canvas) return;

    const ecgCtx = ecgCanvas.getContext('2d');
    const spo2Ctx = spo2Canvas.getContext('2d');

    ecgCanvas.width = ecgCanvas.offsetWidth;
    ecgCanvas.height = 80;
    spo2Canvas.width = spo2Canvas.offsetWidth;
    spo2Canvas.height = 80;

    ecgData = [];
    spo2Data = [];

    for (let i = 0; i < ecgCanvas.width; i++) {
        ecgData.push(generateECGPoint(i));
        spo2Data.push(generateSpO2Point(i));
    }

    function generateECGPoint(x) {
        const period = 100;
        const pos = x % period;
        if (pos < 5) return 0.5;
        if (pos < 10) return 0.5 - (pos - 5) * 0.15;
        if (pos < 15) return 0.2 + (pos - 10) * 0.4;
        if (pos < 20) return 0.4 - (pos - 15) * 0.4;
        if (pos < 25) return 0;
        if (pos < 35) return (pos - 25) * 0.08;
        if (pos < 45) return 0.8 - (pos - 35) * 0.08;
        if (pos < 55) return 0;
        if (pos < 65) return (pos - 55) * 0.04;
        if (pos < 75) return 0.4 - (pos - 65) * 0.04;
        return 0.5;
    }

    function generateSpO2Point(x) {
        const period = 200;
        const pos = x % period;
        return 0.5 + Math.sin(pos * 0.05) * 0.05;
    }

    function drawWaveform(ctx, data, color) {
        ctx.fillStyle = '#0a0f14';
        ctx.fillRect(0, 0, ctx.canvas.width, ctx.canvas.height);

        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.shadowBlur = 10;
        ctx.shadowColor = color;
        ctx.beginPath();

        for (let i = 0; i < data.length; i++) {
            const y = data[i] * ctx.canvas.height;
            if (i === 0) {
                ctx.moveTo(i, y);
            } else {
                ctx.lineTo(i, y);
            }
        }
        ctx.stroke();
    }

    function animate() {
        ecgData.shift();
        ecgData.push(generateECGPoint(Date.now() * 0.1));

        spo2Data.shift();
        spo2Data.push(generateSpO2Point(Date.now() * 0.05));

        drawWaveform(ecgCtx, ecgData, '#ff3b4e');
        drawWaveform(spo2Ctx, spo2Data, '#4a9eff');

        requestAnimationFrame(animate);
    }

    animate();
}

document.getElementById('patientSearch').addEventListener('input', (e) => {
    const search = e.target.value.toLowerCase();
    const filtered = patients.filter(p =>
        p.mrn.toLowerCase().includes(search) ||
        p.first_name.toLowerCase().includes(search) ||
        p.last_name.toLowerCase().includes(search)
    );
    renderPatientList(filtered);
});

document.getElementById('unitFilter').addEventListener('change', (e) => {
    const unit = e.target.value;
    const filtered = unit
        ? patients.filter(p => p.unit_type === unit)
        : patients;
    renderPatientList(filtered);
});

document.getElementById('triggerDemo').addEventListener('click', async () => {
    document.getElementById('demoModal').classList.add('active');

    try {
        const data = await apiFetch('/demo/trigger', {method: 'POST'});

        if (data.status === 'demo_triggered') {
            await runDemoScenario(data);
        }
    } catch (error) {
        console.error('Demo failed:', error);
    }
});

document.getElementById('closeModal').addEventListener('click', () => {
    document.getElementById('demoModal').classList.remove('active');
});

async function handleDemoStart(data) {
    const content = document.getElementById('demoContent');
    content.innerHTML = `
        <div class="demo-step">
            <div class="demo-phase">DEMO INITIATED</div>
            <div class="demo-description">Patient: ${data.patient_name} (${data.mrn})</div>
        </div>
    `;
}

async function runDemoScenario(data) {
    const content = document.getElementById('demoContent');

    const phases = [
        {agent: 'Monitor', phase: 'PHASE 1: DETECTION', desc: 'Patient showing signs of clinical deterioration. Vitals degrading...'},
        {agent: 'Diagnostic', phase: 'PHASE 2: ANALYSIS', desc: 'Analyzing clinical picture... NEWS2: 12, qSOFA: 3, Lactate: 4.8'},
        {agent: 'Guideline', phase: 'PHASE 3: PROTOCOL', desc: 'Initiating 1-Hour Sepsis Bundle per Surviving Sepsis Campaign'},
        {agent: 'Coordinator', phase: 'PHASE 4: ESCALATION', desc: 'Page ICU team, physician notification, rapid response activated'},
        {agent: 'Documentation', phase: 'PHASE 5: DOCUMENTATION', desc: 'SOAP note generated, FHIR records updated, audit trail complete'},
    ];

    for (let i = 0; i < phases.length; i++) {
        const p = phases[i];
        content.innerHTML = `
            <div class="demo-step">
                <div class="demo-phase">${p.phase}</div>
                <div class="demo-description">${p.desc}</div>
            </div>
        `;
        addAgentMessage(p.agent, p.desc);
        await sleep(2500);
    }

    displayAlert({
        patient_id: data.patient_id,
        mrn: data.mrn,
        alerts: [{
            title: 'SEPTIC SHOCK DETECTED',
            description: 'Patient demonstrating signs of septic shock. Rapid Response activated.',
            severity: 'CRITICAL'
        }]
    });
}

function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

document.addEventListener('DOMContentLoaded', async () => {
    initClock();
    const authenticated = await checkAuth();
    if (authenticated) {
        initWebSocket();
        await loadPatients();
    } else {
        document.getElementById('patientList').innerHTML = '<div class="loading-indicator">Authentication failed. Please refresh.</div>';
    }
});

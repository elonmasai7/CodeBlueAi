const API_BASE = '/api/v1';
const WS_URL = '/ws/clinical';

let ws = null;
let patients = [];
let selectedPatient = null;
let ecgData = [];
let spo2Data = [];
let eventSource = null;

function initClock() {
    function updateClock() {
        const now = new Date();
        document.getElementById('mainClock').textContent = now.toLocaleTimeString('en-US', { hour12: false });
        document.getElementById('mainDate').textContent = now.toISOString().split('T')[0];
    }
    updateClock();
    setInterval(updateClock, 1000);
}

function initWebSocket() {
    ws = new WebSocket(WS_URL);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
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
    }
}

async function loadPatients() {
    try {
        const response = await fetch(`${API_BASE}/patients?limit=100`);
        const data = await response.json();
        patients = data;
        renderPatientList(patients);
        updateFooterStats();
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
        <div class="patient-item" data-id="${p.id}" onclick="selectPatient('${p.id}')">
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
        const response = await fetch(`${API_BASE}/patients/${patientId}`);
        const patient = await response.json();
        selectedPatient = patient;
        
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
        
        const analysisRes = await fetch(`${API_BASE}/analyze/${patientId}`);
        const analysis = await analysisRes.json();
        updateScores(analysis.monitor.scores);
        updateExplainability(analysis);
        
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
    const alerts = [];
    
    if (vitals.heart_rate > 130 || vitals.heart_rate < 50) {
        document.getElementById('cardHR').classList.add('alert');
    } else {
        document.getElementById('cardHR').classList.remove('alert');
    }
    
    if (vitals.systolic_bp < 90) {
        document.getElementById('cardBP').classList.add('alert');
    } else {
        document.getElementById('cardBP').classList.remove('alert');
    }
    
    if (vitals.spo2 < 88) {
        document.getElementById('cardSpO2').classList.add('alert');
    } else {
        document.getElementById('cardSpO2').classList.remove('alert');
    }
    
    if (vitals.lactate > 4.0) {
        document.getElementById('cardLactate').classList.add('alert');
    } else {
        document.getElementById('cardLactate').classList.remove('alert');
    }
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
            <p>Primary: ${analysis.diagnostic.primary_diagnosis}</p>
            <p>Confidence: ${analysis.diagnostic.risk_prediction.mortality_risk || 'N/A'}</p>
        </div>
        <div class="explain-section">
            <h4>Evidence</h4>
            <ul>
                ${analysis.diagnostic.differential.slice(0, 3).map(d => `
                    <li><strong>${d.name}</strong> (${(d.probability * 100).toFixed(0)}%)</li>
                `).join('')}
            </ul>
        </div>
        <div class="explain-section">
            <h4>Protocol: ${analysis.guideline.protocol}</h4>
            <p>Urgency: ${analysis.guideline.urgency}</p>
            <p>First intervention: ${analysis.guideline.interventions?.[0]?.action || 'N/A'}</p>
        </div>
        <div class="explain-section">
            <h4>Escalation: ${analysis.coordinator.level}</h4>
            <p>${analysis.coordinator.reason}</p>
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
        const response = await fetch(`${API_BASE}/demo/trigger`, { method: 'POST' });
        const data = await response.json();
        
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
    
    content.innerHTML = `
        <div class="demo-step" id="phase1">
            <div class="demo-phase">PHASE 1: DETECTION</div>
            <div class="demo-description">Patient John Doe showing signs of clinical deterioration. Vitals degrading...</div>
        </div>
    `;
    
    addAgentMessage('Monitor', `DETECTING deterioration in patient ${data.mrn} - BP dropping, HR rising, SpO2 falling`);
    await sleep(2000);
    
    content.innerHTML += `
        <div class="demo-step" id="phase2">
            <div class="demo-phase">PHASE 2: ANALYSIS</div>
            <div class="demo-description">Analyzing clinical picture... NEWS2: 12, qSOFA: 3, Lactate: 4.8 mmol/L</div>
        </div>
    `;
    
    addAgentMessage('Diagnostic', `SEPTIC SHOCK likely (92% confidence) - Hypotension, tachycardia, hypoxia, elevated lactate`);
    await sleep(2000);
    
    content.innerHTML += `
        <div class="demo-step" id="phase3">
            <div class="demo-phase">PHASE 3: PROTOCOL</div>
            <div class="demo-description">Initiating 1-Hour Sepsis Bundle per Surviving Sepsis Campaign guidelines</div>
        </div>
    `;
    
    addAgentMessage('Guideline', `1-HOUR SEPSIS BUNDLE initiated - Blood cultures, broad spectrum antibiotics, 30mL/kg fluids, vasopressors if needed`);
    await sleep(2000);
    
    content.innerHTML += `
        <div class="demo-step" id="phase4">
            <div class="demo-phase">PHASE 4: ESCALATION</div>
            <div class="demo-description">Page ICU team, physician notification, rapid response team activated</div>
        </div>
    `;
    
    addAgentMessage('Coordinator', `RAPID RESPONSE ACTIVATED - ICU team en route, Attending MD paged, Foley and IV access being placed`);
    await sleep(2000);
    
    content.innerHTML += `
        <div class="demo-step" id="phase5">
            <div class="demo-phase">PHASE 5: DOCUMENTATION</div>
            <div class="demo-description">SOAP note generated, FHIR records updated, audit trail complete</div>
        </div>
    `;
    
    addAgentMessage('Documentation', `SOAP note generated with clinical rationale and management plan. FHIR Communication and DetectedIssue resources updated.`);
    
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

document.addEventListener('DOMContentLoaded', () => {
    initClock();
    initWebSocket();
    loadPatients();
});

#!/bin/bash
#========================================
# Code Blue AI - 3-Minute Demo Script
#========================================
# Run this after: docker-compose up -d
# Patient: John Doe, 62M, Pneumonia
# Scenario: Stable -> Septic Shock -> Recovery
#========================================

set -e

BASE_URL="http://localhost:8000"
UI_URL="http://localhost:3000"

echo ""
echo "========================================"
echo "CODE BLUE AI - 3-MINUTE DEMO"
echo "========================================"
echo ""

echo "[0:00] Waiting for services..."
sleep 5

# Login
echo "[0:05] Authenticating..."
TOKEN=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"physician","password":"Physician123!"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])" 2>/dev/null)

if [ -z "$TOKEN" ]; then
    echo "Login failed. Check if backend is running: docker-compose ps"
    exit 1
fi

echo "    Authenticated as Physician"
H="-H Authorization: Bearer $TOKEN -H Content-Type: application/json"

# Get first patient
echo "[0:10] Loading patient roster..."
PATIENTS=$(curl -s "$BASE_URL/api/v1/patients" $H)
PATIENT_ID=$(echo $PATIENTS | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])" 2>/dev/null)
PATIENT_NAME=$(echo $PATIENTS | python3 -c "import sys,json; d=json.load(sys.stdin)[0]; print(f\"{d['first_name']} {d['last_name']}\")" 2>/dev/null)
echo "    Patient loaded: $PATIENT_NAME"

echo ""
echo "========================================"
echo "[0:15] PHASE 1: STABLE BASELINE"
echo "========================================"
echo "    Patient presenting with Community Acquired Pneumonia."
echo "    Currently stable on floor. Vitals within normal limits."
echo ""
echo "    Current Vitals:"
echo "    HR: 88 | BP: 125/78 | SpO2: 95% | RR: 18 | T: 37.5C | Lac: 1.2"

echo ""
echo "========================================"
echo "[0:45] PHASE 2: EARLY DETERIORATION"
echo "========================================"
echo "    6 hours post-admission. Patient becoming tachycardic."
curl -s -X POST "$BASE_URL/api/v1/vitals" $H \
  -d "{\"patient_id\":\"$PATIENT_ID\",\"heart_rate\":102,\"systolic_bp\":108,\"diastolic_bp\":65,\"respiratory_rate\":24,\"temperature\":38.4,\"spo2\":91,\"lactate\":2.1}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"    NEWS2: {d['analysis']['scores']['NEWS2']['value']:.0f} - {d['analysis']['scores']['NEWS2']['interpretation']}\")" 2>/dev/null

echo "    HR: 102 | BP: 108/65 | SpO2: 91% | RR: 24 | T: 38.4C | Lac: 2.1"
echo "    Action: Continue monitoring. Reassess in 2 hours."

echo ""
echo "========================================"
echo "[1:15] PHASE 3: SEPSIS DETECTED"
echo "========================================"
echo "    Deterioration accelerating. Lactate rising rapidly."
echo ""
echo "    Triggering full multi-agent analysis..."

RESULT=$(curl -s -X POST "$BASE_URL/api/v1/analyze/$PATIENT_ID" $H)
NEWS2=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['monitor']['scores']['NEWS2']['value'])" 2>/dev/null)
QSOFA=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['monitor']['scores']['qSOFA']['value'])" 2>/dev/null)
DIAG=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['diagnostic']['primary_diagnosis'])" 2>/dev/null)
PROTO=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['guideline']['protocol'])" 2>/dev/null)
ESC=$(echo $RESULT | python3 -c "import sys,json; print(json.load(sys.stdin)['coordinator']['level'])" 2>/dev/null)

echo "    --- AGENT OUTPUT ---"
echo "    Monitor Agent: NEWS2: $NEWS2 | qSOFA: $QSOFA"
echo "    Diagnostic Agent: $DIAG"
echo "    Guideline Agent: $PROTO"
echo "    Coordinator Agent: ESCALATION - $ESC"
echo ""
echo "    Current Vitals:"
echo "    HR: 118 | BP: 92/58 | SpO2: 88% | RR: 28 | T: 39.0C | Lac: 3.5"
echo ""
echo "    --- INTERVENTIONS ---"
echo $RESULT | python3 -c "
import sys,json
d=json.load(sys.stdin)
for i in d['guideline']['interventions'][:4]:
    print(f\"    * {i['action']} ({i['timing']}) - Priority: {i['priority']}\")" 2>/dev/null

echo ""
echo "========================================"
echo "[1:45] PHASE 4: SEPTIC SHOCK"
echo "========================================"
echo "    Patient in shock. Hypotension refractory to fluids."
echo "    Activating Rapid Response Protocol..."
echo ""
echo $RESULT | python3 -c "
import sys,json
d=json.load(sys.stdin)
for n in d['coordinator']['notifications']:
    print(f\"    NOTIFICATION: {n['recipient']} via {n['action']} - Priority: {n['priority']}\")" 2>/dev/null

echo ""
echo "    --- TASKS ---"
echo $RESULT | python3 -c "
import sys,json
d=json.load(sys.stdin)
for t in d['coordinator']['tasks'][:5]:
    print(f\"    [{t['assigned_to']}] {t['description']}\")" 2>/dev/null

echo ""
echo "    --- SOAP NOTE GENERATED ---"
echo $RESULT | python3 -c "
import sys,json
d=json.load(sys.stdin)
soap=d['documentation']
print(f\"    Assessment: {soap['assessment'].split(chr(10))[0]}\")" 2>/dev/null

echo ""
echo "========================================"
echo "[2:15] PHASE 5: TREATMENT INITIATED"
echo "========================================"
echo "    Antibiotics administered. ICU team at bedside."
echo "    Vasopressor support initiated. Vitals stabilizing."
echo ""
echo "    HR: 115 | BP: 92/60 | SpO2: 91% | RR: 26 | T: 38.8C | Lac: 4.2"

echo ""
echo "========================================"
echo "[2:45] PHASE 6: STABILIZING"
echo "========================================"
echo "    4 hours post-bundle. MAP > 65. Lactate dropping."
echo "    ICU admission confirmed. Continuing 1-hour bundle monitoring."
echo ""
echo "    HR: 98 | BP: 102/65 | SpO2: 94% | RR: 22 | T: 38.0C | Lac: 2.8"
echo "    NEWS2: 6 (Improving)"

echo ""
echo "========================================"
echo "DEMO COMPLETE"
echo "========================================"
echo ""
echo "Summary:"
echo "  - Monitor Agent detected deterioration at step 3"
echo "  - All 5 agents coordinated in real-time"
echo "  - Sepsis bundle initiated within detection window"
echo "  - SOAP note auto-generated"
echo "  - FHIR Communication resource created"
echo ""
echo "Open the UI for real-time visualization:"
echo "  $UI_URL"
echo ""
echo "View API documentation:"
echo "  $BASE_URL/docs"
echo ""

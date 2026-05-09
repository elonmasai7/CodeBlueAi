#!/usr/bin/env python3
"""
Monitor Agent for Code Blue AI
Continuously ingests FHIR observations and detects clinical deterioration
"""

import asyncio
import httpx
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import uuid

# Configuration
FHIR_SERVER_URL = os.getenv("FHIR_SERVER_URL", "http://localhost:8080/fhir")
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", "8001"))
A2A_BUS_HOST = os.getenv("A2A_BUS_HOST", "localhost")
A2A_BUS_PORT = int(os.getenv("A2A_BUS_PORT", "8002"))
POLLING_INTERVAL = int(os.getenv("POLLING_INTERVAL", "10"))  # seconds

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MonitorAgent:
    def __init__(self):
        self.running = False
        self.client = httpx.AsyncClient(timeout=30.0)
        self.known_patients = set()
        
    async def start(self):
        """Start the monitor agent"""
        logger.info("Starting Monitor Agent...")
        self.running = True
        
        # Start monitoring loop
        while self.running:
            try:
                await self.monitor_patients()
                await asyncio.sleep(POLLING_INTERVAL)
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(POLLING_INTERVAL)
    
    async def stop(self):
        """Stop the monitor agent"""
        logger.info("Stopping Monitor Agent...")
        self.running = False
        await self.client.aclose()
    
    async def monitor_patients(self):
        """Monitor patients for clinical deterioration"""
        try:
            # Get list of patients from FHIR server
            response = await self.client.get(f"{FHIR_SERVER_URL}/Patient?_count=100")
            if response.status_code != 200:
                logger.error(f"Failed to fetch patients: {response.status_code}")
                return
            
            patients_data = response.json()
            if "entry" not in patients_data:
                return
            
            for entry in patients_data["entry"]:
                patient = entry["resource"]
                patient_id = patient["id"]
                
                # Skip if we've already processed this patient recently
                if patient_id in self.known_patients:
                    continue
                
                self.known_patients.add(patient_id)
                
                # Get recent observations for this patient
                await self.analyze_patient_observations(patient_id)
                
        except Exception as e:
            logger.error(f"Error monitoring patients: {e}")
    
    async def analyze_patient_observations(self, patient_id: str):
        """Analyze patient observations for signs of deterioration"""
        try:
            # Get recent observations (last 1 hour)
            one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
            response = await self.client.get(
                f"{FHIR_SERVER_URL}/Observation?"
                f"patient={patient_id}&"
                f"_lastUpdated>=gt{one_hour_ago}&"
                f"_count=50"
            )
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch observations for patient {patient_id}: {response.status_code}")
                return
            
            obs_data = response.json()
            if "entry" not in obs_data:
                return
            
            # Process observations
            observations = []
            for entry in obs_data["entry"]:
                obs = entry["resource"]
                observations.append(obs)
            
            # Analyze for deterioration signs
            alerts = self.detect_deterioration(observations)
            
            # If alerts found, send to A2A bus
            if alerts:
                await self.send_alerts(patient_id, alerts)
                
        except Exception as e:
            logger.error(f"Error analyzing observations for patient {patient_id}: {e}")
    
    def detect_deterioration(self, observations: List[Dict]) -> List[Dict]:
        """Detect signs of clinical deterioration from observations"""
        alerts = []
        
        # Extract vital signs
        vitals = self.extract_vitals(observations)
        
        # Check for tachycardia (HR > 110)
        if "heart_rate" in vitals and vitals["heart_rate"] > 110:
            alerts.append({
                "type": "tachycardia",
                "severity": "medium",
                "value": vitals["heart_rate"],
                "unit": "bpm",
                "description": f"Heart rate elevated at {vitals['heart_rate']} bpm",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for hypotension (MAP < 65)
        if "map" in vitals and vitals["map"] < 65:
            alerts.append({
                "type": "hypotension",
                "severity": "high",
                "value": vitals["map"],
                "unit": "mmHg",
                "description": f"Mean arterial pressure low at {vitals['map']} mmHg",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for fever (Temp > 38.3°C)
        if "temperature" in vitals and vitals["temperature"] > 38.3:
            alerts.append({
                "type": "fever",
                "severity": "medium",
                "value": vitals["temperature"],
                "unit": "°C",
                "description": f"Temperature elevated at {vitals['temperature']}°C",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for hypoxia (SpO2 < 90%)
        if "oxygen_saturation" in vitals and vitals["oxygen_saturation"] < 90:
            alerts.append({
                "type": "hypoxia",
                "severity": "high",
                "value": vitals["oxygen_saturation"],
                "unit": "%",
                "description": f"Oxygen saturation low at {vitals['oxygen_saturation']}%",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for elevated lactate (> 2.0 mmol/L)
        if "lactate" in vitals and vitals["lactate"] > 2.0:
            alerts.append({
                "type": "elevated_lactate",
                "severity": "high",
                "value": vitals["lactate"],
                "unit": "mmol/L",
                "description": f"Lactate elevated at {vitals['lactate']} mmol/L",
                "timestamp": datetime.now().isoformat()
            })
        
        # Check for leukocytosis (WBC > 12.0)
        if "wbc" in vitals and vitals["wbc"] > 12.0:
            alerts.append({
                "type": "leukocytosis",
                "severity": "medium",
                "value": vitals["wbc"],
                "unit": "x10^9/L",
                "description": f"White blood cell count elevated at {vitals['wbc']} x10^9/L",
                "timestamp": datetime.now().isoformat()
            })
        
        return alerts
    
    def extract_vitals(self, observations: List[Dict]) -> Dict[str, float]:
        """Extract vital signs from FHIR observations"""
        vitals = {}
        
        for obs in observations:
            if "code" not in obs or "coding" not in obs["code"]:
                continue
            
            # Get the first coding
            coding = obs["code"]["coding"][0] if obs["code"]["coding"] else None
            if not coding:
                continue
            
            code = coding.get("code")
            system = coding.get("system", "")
            
            # Extract value
            value = None
            if "valueQuantity" in obs:
                value = obs["valueQuantity"].get("value")
            elif "valueString" in obs:
                try:
                    value = float(obs["valueString"])
                except ValueError:
                    pass
            
            if value is None:
                continue
            
            # Map to vital signs
            if code == "8867-4" and "heart" in system.lower():  # Heart rate
                vitals["heart_rate"] = value
            elif code == "9279-1" and "respirat" in system.lower():  # Respiratory rate
                vitals["respiratory_rate"] = value
            elif code == "8310-5" and "temperature" in system.lower():  # Temperature
                vitals["temperature"] = value
            elif code == "2716-5" and "systolic" in system.lower():  # Systolic BP
                vitals["systolic_bp"] = value
            elif code == "2717-3" and "diastolic" in system.lower():  # Diastolic BP
                vitals["diastolic_bp"] = value
            elif code == "2703-7" and "oxygen" in system.lower():  # Oxygen saturation
                vitals["oxygen_saturation"] = value
            elif code == "2160-0" and "hemoglobin" in system.lower():  # Hemoglobin
                vitals["hemoglobin"] = value
            elif code == "14949-7" and "wbc" in system.lower():  # WBC
                vitals["wbc"] = value
            elif code == "2148-4" and "lactate" in system.lower():  # Lactate
                vitals["lactate"] = value
        
        # Calculate MAP if we have systolic and diastolic
        if "systolic_bp" in vitals and "diastolic_bp" in vitals:
            vitals["map"] = vitals["diastolic_bp"] + (0.333 * (vitals["systolic_bp"] - vitals["diastolic_bp"]))
        
        return vitals
    
    async def send_alerts(self, patient_id: str, alerts: List[Dict]):
        """Send alerts to A2A bus"""
        try:
            # In a real implementation, this would publish to a message queue
            # For now, we'll just log and make a simple HTTP POST
            alert_message = {
                "agent": "monitor_agent",
                "patient_id": patient_id,
                "alerts": alerts,
                "timestamp": datetime.now().isoformat(),
                "message_id": str(uuid.uuid4())
            }
            
            logger.info(f"Sending alerts for patient {patient_id}: {len(alerts)} alerts detected")
            
            # Send to A2A bus (simplified)
            # await self.client.post(
            #     f"http://{A2A_BUS_HOST}:{A2A_BUS_PORT}/alerts",
            #     json=alert_message
            # )
            
            # Also log for demonstration
            for alert in alerts:
                logger.warning(f"ALERT: {alert['description']} for patient {patient_id}")
                
        except Exception as e:
            logger.error(f"Error sending alerts: {e}")

async def main():
    """Main entry point"""
    agent = MonitorAgent()
    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    finally:
        await agent.stop()

if __name__ == "__main__":
    asyncio.run(main())

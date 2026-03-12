import asyncio
import base64
import cv2
import numpy as np
import time
from datetime import datetime
import sqlite3
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import sys
import math
import json
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))

from src.vision_engine import VisionEngine
from src.database import DatabaseManager

# Try to import C++ module
CPP_AVAILABLE = False
try:
    import engagement_cpp
    CPP_AVAILABLE = True
except ImportError:
    try:
        from cpp_modules import engagement_cpp
        CPP_AVAILABLE = True
    except ImportError:
        pass

app = FastAPI(title="FocusFlow API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize engines
vision_engine = VisionEngine()
db = DatabaseManager()

# Mount frontend
frontend_path = Path(__file__).parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")

def sanitize_data(data):
    """Recursively replace NaN and Inf with 0.0. Handles numpy types and lists."""
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(v) for v in data]
    elif isinstance(data, (float, np.floating)):
        if math.isnan(data) or math.isinf(data):
            return 0.0
        return float(data)
    elif isinstance(data, (int, np.integer)):
        return int(data)
    elif isinstance(data, (bool, np.bool_)):
        return bool(data)
    elif isinstance(data, np.ndarray):
        return sanitize_data(data.tolist())
    return data

@app.get("/")
async def root():
    return FileResponse(str(frontend_path / "index.html"))

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/sessions")
async def get_sessions():
    """Get history of all sessions"""
    try:
        sessions_df = db.get_all_sessions()
        if sessions_df.empty:
            return {"sessions": []}
        
        # Clean up data for JSON
        records = sessions_df.to_dict(orient="records")
        return sanitize_data({"sessions": records})
    except Exception as e:
        print(f"Error getting sessions: {e}")
        return {"sessions": [], "error": str(e)}

@app.get("/api/history/meetings")
async def get_meeting_history():
    df = db.get_all_meetings()
    return {"meetings": df.to_dict(orient="records")}

@app.get("/api/stats/dashboard")
async def get_dashboard_stats():
    """Get summarized stats for the main dashboard"""
    return db.get_dashboard_summary()

@app.get("/meetings")
async def get_meetings():
    """Get history of meeting sessions"""
    try:
        meetings_df = db.get_all_meetings()
        if meetings_df.empty:
            return {"meetings": []}
        return sanitize_data({"meetings": meetings_df.to_dict(orient="records")})
    except Exception as e:
        print(f"Error getting meetings: {e}")
        return {"meetings": [], "error": str(e)}

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()
    
    session_id = None
    recording = False
    start_time = None
    session_mode = "individual" # Persist mode here
    
    # State tracking
    session_yawn_count = 0
    session_drowsy_count = 0
    yawn_in_progress = False
    drowsy_start_time = None
    drowsy_event_counted = False
    ear_threshold = 0.35
    calibrated = False
    calibration_samples = []
    
    print(f"WebSocket attempt from {websocket.client}")
    try:
        while True:
            # Receive data from frontend
            data = await websocket.receive_json()
            
            # Application logic
            action = data.get("action", "")
            if action != "frame": # Don't log frames to avoid spam
                print(f"WebSocket Action: {action}")
            
            if action == "start_session":
                recording = True
                session_mode = data.get("mode", "individual")
                title = data.get("title", "Live Analysis Session")
                
                if session_mode == "meeting":
                    session_id = db.create_meeting(title)
                else:
                    session_id = db.create_session(title)
                    
                start_time = time.time()
                session_yawn_count = 0
                session_drowsy_count = 0
                yawn_in_progress = False
                drowsy_start_time = None
                drowsy_event_counted = False
                ear_threshold = 0.35
                calibrated = False
                calibration_samples = []
                vision_engine.ear_threshold = ear_threshold
                if session_mode == "meeting":
                    vision_engine.set_meeting_mode(True)
                else:
                    vision_engine.set_meeting_mode(False)
                    
                await websocket.send_json({"type": "info", "message": f"{session_mode.capitalize()} started", "session_id": session_id, "mode": session_mode})
                continue
                
            elif action == "stop_session":
                stop_mode = data.get("mode", session_mode)
                if recording and session_id:
                    if stop_mode == "meeting":
                        db.end_meeting(session_id)
                    else:
                        db.end_session(session_id)
                recording = False
                session_id = None
                await websocket.send_json({"type": "info", "message": "Session stopped"})
                continue
            
            frame_data = data.get("frame")
            if not frame_data:
                continue
            
            response_payload = {
                "type": "metrics",
                "cpp_available": CPP_AVAILABLE,
                "face_detected": False,
            }

            # Decode frame
            try:
                header, encoded = frame_data.split(",", 1)
                img_bytes = base64.b64decode(encoded)
                np_arr = np.frombuffer(img_bytes, np.uint8)
                frame = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
                
                if frame is not None:
                    # use persisted session_mode
                    if session_mode == "meeting":
                        multi_faces = vision_engine.analyze_multi_faces(frame)
                        response_payload["face_detected"] = len(multi_faces) > 0
                        response_payload["participant_count"] = len(multi_faces)
                        
                        if multi_faces:
                            avg_eng = sum(f['engagement_score'] for f in multi_faces) / len(multi_faces)
                            distracted = sum(1 for f in multi_faces if f['attention'] < 0.4)
                            drowsy = sum(1 for f in multi_faces if f['is_drowsy'])
                            
                            response_payload.update({
                                "score": avg_eng,
                                "status_text": f"{len(multi_faces)} PARTICIPANTS",
                                "distracted_count": distracted,
                                "drowsy_count": drowsy,
                                "multi_faces": multi_faces # Send raw face data for potential UI markers
                            })
                            
                        if recording and session_id:
                            db.log_meeting(session_id, len(multi_faces), drowsy, distracted, avg_eng)
                        else:
                            response_payload.update({
                                "score": 0,
                                "status_text": "SEARCHING...",
                                "distracted_count": 0,
                                "drowsy_count": 0
                            })
                        
                        # Send aggregated response for meeting
                        await websocket.send_json(sanitize_data(response_payload))
                        continue

                    # Individual mode logic starts here
                    signals = vision_engine.analyze_frame(frame)
                    response_payload["face_detected"] = signals.get("face_detected", False)
                    
                    if signals['face_detected']:
                        # Core processing logic...
                        # (Keeping existing logic but wrapping it in the frame check)
                        vision_engine.ear_threshold = ear_threshold
                        
                        # Auto-calibration
                        if recording and not calibrated:
                            session_duration = time.time() - start_time
                            if session_duration < 3.0:
                                calibration_samples.append(signals['eye_openness'])
                                response_payload["calibration_status"] = f"Calibrating: {3.0 - session_duration:.1f}s remaining"
                            elif session_duration >= 3.0:
                                if calibration_samples:
                                    baseline_ear = sum(calibration_samples) / len(calibration_samples)
                                    ear_threshold = max(0.15, min(0.50, baseline_ear * 0.85))
                                    vision_engine.ear_threshold = ear_threshold
                                calibrated = True
                                response_payload["calibration_status"] = f"Calibrated (Threshold: {ear_threshold:.2f})"
                        
                        # Logic: Yawns & Drowsy count
                        if recording:
                            if signals['is_yawning']:
                                if not yawn_in_progress:
                                    session_yawn_count += 1
                                    yawn_in_progress = True
                            else:
                                yawn_in_progress = False
                                
                            if signals['is_drowsy']:
                                if drowsy_start_time is None:
                                    drowsy_start_time = time.time()
                                elif (time.time() - drowsy_start_time) > 5.0 and not drowsy_event_counted:
                                    session_drowsy_count += 1
                                    drowsy_event_counted = True
                            else:
                                drowsy_start_time = None
                                drowsy_event_counted = False
                                
                        # Score Calculation
                        attention = signals.get('attention_score', signals.get('gaze_score', 0))
                        stability = signals.get('head_stability', 0)
                        emotion_label = signals.get('emotion_label', 'Neutral')
                        
                        base_score = (attention * 0.45 + stability * 0.35 + signals.get('eye_openness', 0) * 0.2) * 100
                        emotion_bonus = 10 if emotion_label in ['Focused', 'Happy'] else (-5 if emotion_label in ['Sad', 'Angry', 'Tired'] else 0)
                        engagement = base_score + emotion_bonus
                        
                        if signals.get('is_yawning'): engagement -= 15
                        if signals.get('is_drowsy'): engagement -= 20
                        if signals.get('liveness_status') == "Suspicious": engagement = 0
                        engagement = max(0, min(100, engagement))
                        
                        if recording and session_id:
                            # Sanitize values specifically for SQLite storage
                            s_attention = float(sanitize_data(attention))
                            s_engagement = float(sanitize_data(engagement))
                            s_gaze = float(sanitize_data(signals.get('gaze_score', 0)))
                            s_emotion = float(sanitize_data(signals.get('emotion_score', 0)))
                            s_stability = float(sanitize_data(signals.get('head_stability', 0)))
                            
                            if session_mode == "meeting":
                                db.log_meeting(session_id, 1, 1 if signals['is_drowsy'] else 0, 1 if s_attention < 0.4 else 0, s_engagement)
                            else:
                                db.log_engagement(session_id, s_gaze, s_emotion, s_stability, s_engagement, True)
                        
                        status_text = "FOCUSED"
                        drowsy_duration = time.time() - drowsy_start_time if drowsy_start_time is not None else 0
                        if drowsy_duration > 5.0: status_text = "SLEEPING"
                        elif signals.get('is_yawning'): status_text = "YAWNING"
                        elif signals.get('is_drowsy'): status_text = "DROWSY"
                            
                        # Final response payload construction
                        response_payload.update({
                            "score": engagement,
                            "status_text": status_text,
                            "yawn_count": session_yawn_count,
                            "drowsy_count": session_drowsy_count,
                            "drowsy_duration": drowsy_duration,
                            "signals": signals,
                            "ear_threshold": ear_threshold
                        })
                    else:
                        # Face not detected in this frame
                        response_payload.update({
                            "score": 0,
                            "status_text": "SEARCHING...",
                            "yawn_count": session_yawn_count,
                            "drowsy_count": session_drowsy_count,
                            "signals": {"eye_openness": 0, "ear_threshold": ear_threshold}
                        })
                else:
                    print("Decoded frame is None")
                    # Frame was not decoded, or was empty.
                    # response_payload already has face_detected: False
                    response_payload.update({
                        "score": 0,
                        "status_text": "NO_FRAME",
                        "yawn_count": session_yawn_count,
                        "drowsy_count": session_drowsy_count,
                        "signals": {"eye_openness": 0, "ear_threshold": ear_threshold}
                    })
            except Exception as e:
                print(f"Frame Processing Error: {e}")
                response_payload["error"] = str(e)
                response_payload.update({
                    "score": 0,
                    "status_text": "ERROR",
                    "yawn_count": session_yawn_count,
                    "drowsy_count": session_drowsy_count,
                    "signals": {"eye_openness": 0, "ear_threshold": ear_threshold}
                })
            
            # ALWAYS send a response to unblock the frontend flow control
            await websocket.send_json(sanitize_data(response_payload))
            
    except Exception as e:
        print(f"WebSocket Error: {e}")
    finally:
        print("WebSocket closed")
        if recording and session_id:
            db.end_session(session_id)

if __name__ == "__main__":
    # Disable reload because writing to the database triggers a server restart loop
    uvicorn.run("src.main:app", host="0.0.0.0", port=8000, reload=False)

"""
Database Manager: SQLite Storage for Meeting Analytics
Stores engagement metrics and session data
"""

import sqlite3
import pandas as pd
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class DatabaseManager:
    """
    Manages SQLite database for storing meeting engagement data
    """
    
    def __init__(self, db_path: str = "data/meeting_logs.db"):
        self.db_path = db_path
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                avg_focus_score REAL,
                total_frames INTEGER DEFAULT 0,
                notes TEXT
            )
        """)
        
        # Engagement metrics table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS engagement_metrics (
                metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp TIMESTAMP NOT NULL,
                gaze_score REAL NOT NULL,
                emotion_score REAL NOT NULL,
                head_stability REAL NOT NULL,
                engagement_score REAL NOT NULL,
                face_detected BOOLEAN NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            )
        """)
        
        # Meeting Sessions table (New)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_sessions (
                meeting_id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_time TIMESTAMP NOT NULL,
                end_time TIMESTAMP,
                avg_engagement REAL,
                peak_participants INTEGER DEFAULT 0,
                notes TEXT
            )
        """)
        
        # Meeting Metrics table (New)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS meeting_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER NOT NULL,
                timestamp TIMESTAMP,
                participant_count INTEGER,
                drowsy_count INTEGER,
                distracted_count INTEGER,
                avg_engagement REAL,
                FOREIGN KEY (meeting_id) REFERENCES meeting_sessions(meeting_id)
            )
        """)
        
        conn.commit()
        conn.close()

    # --- Meeting Specific Methods ---

    def create_meeting(self, notes: str = "") -> int:
        """Start a new meeting session"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO meeting_sessions (start_time, notes) VALUES (?, ?)", (datetime.now(), notes))
        mid = cursor.lastrowid
        conn.commit()
        conn.close()
        return mid

    def log_meeting(self, meeting_id, participants, drowsy, distracted, engagement):
        """Log aggregate meeting stats"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO meeting_metrics (meeting_id, timestamp, participant_count, drowsy_count, distracted_count, avg_engagement)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (meeting_id, datetime.now(), participants, drowsy, distracted, engagement))
        conn.commit()
        conn.close()

    def end_meeting(self, meeting_id):
        """End meeting and calculate summary"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate averages and peak participants
        cursor.execute("""
            SELECT AVG(avg_engagement), MAX(participant_count)
            FROM meeting_metrics WHERE meeting_id = ?
        """, (meeting_id,))
        stats = cursor.fetchone()
        avg_eng = stats[0] if stats[0] else 0.0
        peak = stats[1] if stats[1] else 0
        
        cursor.execute("""
            UPDATE meeting_sessions 
            SET end_time = ?, avg_engagement = ?, peak_participants = ?
            WHERE meeting_id = ?
        """, (datetime.now(), avg_eng, peak, meeting_id))
        conn.commit()
        conn.close()

    def get_all_meetings(self):
        """Get meeting history"""
        conn = sqlite3.connect(self.db_path)
        df = pd.read_sql_query("SELECT * FROM meeting_sessions ORDER BY start_time DESC", conn)
        conn.close()
        return df
    
    def create_session(self, notes: str = "") -> int:
        """
        Start a new meeting session
        
        Returns:
            session_id
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO sessions (start_time, notes)
            VALUES (?, ?)
        """, (datetime.now(), notes))
        
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return session_id
    
    def end_session(self, session_id: int):
        """Mark session as ended and calculate statistics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Calculate average focus score
        cursor.execute("""
            SELECT AVG(engagement_score), COUNT(*)
            FROM engagement_metrics
            WHERE session_id = ?
        """, (session_id,))
        
        avg_score, total_frames = cursor.fetchone()
        
        # Update session
        cursor.execute("""
            UPDATE sessions
            SET end_time = ?,
                avg_focus_score = ?,
                total_frames = ?
            WHERE session_id = ?
        """, (datetime.now(), avg_score or 0.0, total_frames or 0, session_id))
        
        conn.commit()
        conn.close()
    
    def log_engagement(
        self,
        session_id: int,
        gaze_score: float,
        emotion_score: float,
        head_stability: float,
        engagement_score: float,
        face_detected: bool
    ):
        """Log a single frame's engagement metrics"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO engagement_metrics (
                session_id, timestamp, gaze_score, emotion_score,
                head_stability, engagement_score, face_detected
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id,
            datetime.now(),
            gaze_score,
            emotion_score,
            head_stability,
            engagement_score,
            face_detected
        ))
        
        conn.commit()
        conn.close()
    
    def get_session_data(self, session_id: int) -> pd.DataFrame:
        """Retrieve all metrics for a session as DataFrame"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT 
                timestamp,
                gaze_score,
                emotion_score,
                head_stability,
                engagement_score,
                face_detected
            FROM engagement_metrics
            WHERE session_id = ?
            ORDER BY timestamp
        """
        
        df = pd.read_sql_query(query, conn, params=(session_id,))
        conn.close()
        
        # Convert timestamp to datetime
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        return df
    
    def get_all_sessions(self) -> pd.DataFrame:
        """Get summary of all sessions"""
        conn = sqlite3.connect(self.db_path)
        
        query = """
            SELECT 
                session_id,
                start_time,
                end_time,
                avg_focus_score,
                total_frames,
                notes
            FROM sessions
            ORDER BY start_time DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        return df
    
    def get_dashboard_summary(self) -> Dict:
        """Get aggregate statistics for the dashboard"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Individual stats
        cursor.execute("SELECT COUNT(*), AVG(avg_focus_score) FROM sessions WHERE end_time IS NOT NULL")
        ind_count, ind_avg = cursor.fetchone()
        
        # Meeting stats
        cursor.execute("SELECT COUNT(*), AVG(avg_engagement) FROM meeting_sessions WHERE end_time IS NOT NULL")
        meet_count, meet_avg = cursor.fetchone()
        
        # Total "Focus Frames" (indicator of time spent)
        cursor.execute("SELECT SUM(total_frames) FROM sessions")
        total_frames = cursor.fetchone()[0] or 0
        
        conn.close()
        
        # Simple heuristic: assuming ~5 FPS, calculate approximate minutes
        focus_minutes = round(total_frames / (5 * 60))
        
        total_sessions = (ind_count or 0) + (meet_count or 0)
        
        # Average engagement (weighted if possible, but simple mean for now)
        scores = []
        if ind_avg: scores.append(ind_avg)
        if meet_avg: scores.append(meet_avg)
        avg_overall = sum(scores) / len(scores) if scores else 0
        
        return {
            "total_sessions": total_sessions,
            "avg_engagement": round(avg_overall),
            "focus_minutes": focus_minutes,
            "individual_sessions": ind_count or 0,
            "meeting_sessions": meet_count or 0
        }

    def calculate_rolling_focus(
        self,
        session_id: int,
        window_seconds: int = 30
    ) -> pd.DataFrame:
        """
        Calculate rolling average focus score
        
        PRODUCT LOGIC: Smooths out momentary distractions
        (e.g., looking away to drink water shouldn't tank the score)
        """
        df = self.get_session_data(session_id)
        
        if df.empty:
            return df
        
        # Set timestamp as index
        df.set_index('timestamp', inplace=True)
        
        # Calculate rolling mean
        df['rolling_focus'] = df['engagement_score'].rolling(
            window=f'{window_seconds}s'
        ).mean()
        
        return df.reset_index()

// script.js
document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const btnDashboard = document.getElementById('btn-dashboard');
    const btnLive = document.getElementById('btn-live');
    const btnMeeting = document.getElementById('btn-meeting');
    const btnHistory = document.getElementById('btn-history');
    
    const viewDashboard = document.getElementById('view-dashboard');
    const viewLive = document.getElementById('view-live');
    const viewMeeting = document.getElementById('view-meeting');
    const viewHistory = document.getElementById('view-history');
    const pageTitle = document.getElementById('page-title');
    const pageSubtitle = document.getElementById('page-subtitle');
    
    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const statusIndicator = document.getElementById('status-indicator');
    const recordingTime = document.getElementById('recording-time');
    const videoOverlay = document.getElementById('video-overlay');
    
    // Video elements
    const video = document.getElementById('webcam');
    const meetingVideo = document.getElementById('meeting-video'); // Meeting specific video
    const canvas = document.createElement('canvas'); // For grabbing frames
    const ctx = canvas.getContext('2d');
    
    // UI Panels
    const meetingSetup = document.getElementById('meeting-setup');
    const meetingActiveVideo = document.getElementById('meeting-active-video');
    
    // Metrics Elements
    const engagementScore = document.getElementById('engagement-score');
    const engagementBar = document.getElementById('engagement-bar');
    const statusText = document.getElementById('status-text');
    
    const yawnCount = document.getElementById('yawn-count');
    const drowsyCount = document.getElementById('drowsy-count');
    const earValue = document.getElementById('ear-value');
    const emotionLabel = document.getElementById('emotion-label');
    
    const gazeScore = document.getElementById('gaze-score');
    const stabilityScore = document.getElementById('stability-score');
    const qualityScore = document.getElementById('quality-score');
    const attentionScore = document.getElementById('attention-score');
    const alertBanner = document.getElementById('alert-banner');
    const historyList = document.getElementById('history-list');
    const btnShareScreen = document.getElementById('btn-share-screen');
    const btnStartMeeting = document.getElementById('btn-start-meeting');

    // UI Navigation
    function switchView(viewName) {
        // Reset all
        btnDashboard.classList.remove('active');
        btnLive.classList.remove('active');
        btnMeeting?.classList.remove('active');
        btnHistory.classList.remove('active');
        
        viewDashboard.classList.add('hidden');
        viewLive.classList.add('hidden');
        viewMeeting?.classList.add('hidden');
        viewHistory.classList.add('hidden');
        
        // Show target
        if (viewName === 'dashboard') {
            btnDashboard.classList.add('active');
            viewDashboard.classList.remove('hidden');
            pageTitle.textContent = "Dashboard";
            pageSubtitle.textContent = "Overview and Quick Start";
            updateDashboardStats();
        } else if (viewName === 'live') {
            btnLive.classList.add('active');
            viewLive.classList.remove('hidden');
            pageTitle.textContent = "Live Analysis";
            pageSubtitle.textContent = "Real-Time Engagement Tracking";
            sessionMode = "individual";
        } else if (viewName === 'meeting') {
            btnMeeting?.classList.add('active');
            viewMeeting?.classList.remove('hidden');
            pageTitle.textContent = "Meeting Intel";
            pageSubtitle.textContent = "Professional Group Analytics";
            sessionMode = "meeting";
        } else if (viewName === 'history') {
            btnHistory.classList.add('active');
            viewHistory.classList.remove('hidden');
            pageTitle.textContent = "History";
            pageSubtitle.textContent = "Review Your Progress";
            loadHistory();
        }
    }

    async function updateDashboardStats() {
        try {
            const resp = await fetch('/api/stats/dashboard');
            const data = await resp.json();
            
            document.getElementById('dash-total-sessions').textContent = data.total_sessions || 0;
            document.getElementById('dash-avg-focus').textContent = (data.avg_engagement || 0) + '%';
            document.getElementById('dash-focus-time').textContent = (data.focus_minutes || 0) + 'm';
            
            // If avg is high, use success color
            const avgElem = document.getElementById('dash-avg-focus');
            if (data.avg_engagement >= 80) avgElem.style.color = 'var(--status-success)';
            else if (data.avg_engagement < 50) avgElem.style.color = 'var(--status-danger)';
            else avgElem.style.color = 'var(--text-primary)';
            
        } catch (err) {
            console.error("Error fetching dashboard stats:", err);
        }
    }

    btnDashboard.addEventListener('click', () => switchView('dashboard'));
    btnLive.addEventListener('click', () => switchView('live'));
    btnMeeting?.addEventListener('click', () => switchView('meeting'));
    btnHistory.addEventListener('click', () => switchView('history'));

    // WebRTC & WebSockets
    let stream = null;
    let ws = null;
    let isRecording = false;
    let timerInterval = null;
    let startTime = null;
    let frameInterval = null;
    let backendReady = true; // Flow control
    let sessionMode = "individual"; 
    let captureSource = "camera"; // "camera" or "screen"

    // Format timer
    function formatTime(seconds) {
        const m = Math.floor(seconds / 60).toString().padStart(2, '0');
        const s = Math.floor(seconds % 60).toString().padStart(2, '0');
        return `${m}:${s}`;
    }

    function updateTimer() {
        if (!startTime) return;
        const now = Date.now();
        const diff = (now - startTime) / 1000;
        recordingTime.textContent = formatTime(diff);
    }

    async function startCamera() {
        try {
            captureSource = "camera";
            stream = await navigator.mediaDevices.getUserMedia({ 
                video: { width: 640, height: 480, frameRate: 10 } 
            });
            const currentVideo = sessionMode === "meeting" ? meetingVideo : video;
            currentVideo.srcObject = stream;
            videoOverlay.style.display = 'none';
            
            if (sessionMode === "meeting") {
                meetingSetup.classList.add('hidden');
                meetingActiveVideo.classList.remove('hidden');
            }
            
            // Add a small debug overlay on top of video container
            let debugOverlay = document.getElementById('camera-debug-info');
            if (!debugOverlay) {
                debugOverlay = document.createElement('div');
                debugOverlay.id = "camera-debug-info";
                debugOverlay.style = "position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.5); color:white; padding:5px 10px; border-radius:4px; font-family:monospace; font-size:12px; z-index:100; pointer-events:none;";
                const container = sessionMode === "meeting" ? meetingActiveVideo : document.querySelector('.video-container');
                container.appendChild(debugOverlay);
            }
            debugOverlay.innerHTML = "Initializing Camera...";
            return true;
        } catch (err) {
            console.error("Error accessing webcam: ", err);
            alert("Could not access webcam. Please ensure permissions are granted.");
            return false;
        }
    }

    async function startScreenShare() {
        try {
            captureSource = "screen";
            stream = await navigator.mediaDevices.getDisplayMedia({
                video: { frameRate: 5 }
            });
            const currentVideo = sessionMode === "meeting" ? meetingVideo : video;
            currentVideo.srcObject = stream;
            videoOverlay.style.display = 'none';
            
            if (sessionMode === "meeting") {
                meetingSetup.classList.add('hidden');
                meetingActiveVideo.classList.remove('hidden');
            }
            
            let debugOverlay = document.getElementById('camera-debug-info');
            if (!debugOverlay) {
                debugOverlay = document.createElement('div');
                debugOverlay.id = "camera-debug-info";
                debugOverlay.style = "position:absolute; top:10px; left:10px; background:rgba(0,0,0,0.5); color:white; padding:5px 10px; border-radius:4px; font-family:monospace; font-size:12px; z-index:100; pointer-events:none;";
                const container = sessionMode === "meeting" ? meetingActiveVideo : document.querySelector('.video-container');
                container.appendChild(debugOverlay);
            }
            debugOverlay.innerHTML = "Screen Sharing Active";
            
            // If the user stops sharing via browser UI
            stream.getVideoTracks()[0].onended = () => {
                if (isRecording) stopSession();
            };
            
            return true;
        } catch (err) {
            console.error("Error starting screen share:", err);
            return false;
        }
    }

    function stopCamera() {
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
                video.srcObject = null;
                if (meetingVideo) meetingVideo.srcObject = null;
            }
            videoOverlay.style.display = 'block';
            
            meetingSetup?.classList.remove('hidden');
            meetingActiveVideo?.classList.add('hidden');
        document.getElementById('camera-debug-info')?.remove();
    }

    function connectWebSocket() {
        // Dynamically detect protocol for secure environments (Hugging Face)
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/stream`;
        
        console.log(`Connecting to WebSocket: ${wsUrl}`);
        ws = new WebSocket(wsUrl);
        
        ws.onopen = () => {
            console.log("WebSocket connected");
            const title = sessionMode === "meeting" ? (document.getElementById('meeting-title')?.value || "Group Meeting") : "Live Analysis Session";
            ws.send(JSON.stringify({ 
                action: "start_session", 
                mode: sessionMode,
                title: title
            }));
        };
        
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.type === "info") {
                console.log("Server Info:", data.message);
                backendReady = true; 
                return;
            }
            
            if (data.type === "metrics") {
                updateUI(data);
                backendReady = true; 
            }
        };
        
        ws.onclose = (event) => {
            console.log("WebSocket disconnected", event.code, event.reason);
            if (isRecording) {
                if (event.code !== 1000) {
                    alertBanner.classList.remove('hidden');
                    alertBanner.querySelector('p').textContent = `Connection lost: ${event.reason || 'Server error'}. Please refresh.`;
                }
                stopSession();
            }
        };
        
        ws.onerror = (err) => {
            console.error("WebSocket Error:", err);
            alertBanner.classList.remove('hidden');
            alertBanner.querySelector('p').textContent = "WebSocket Connection Error. Check if server is running.";
            backendReady = true; 
        };
    }

    function sendFrame() {
        if (!isRecording || !ws || ws.readyState !== WebSocket.OPEN) return;
        if (!backendReady) return; // Wait for backend to finish previous frame
        
        const currentVideo = sessionMode === "meeting" ? meetingVideo : video;
        
        if (currentVideo && currentVideo.readyState === currentVideo.HAVE_ENOUGH_DATA) {
            canvas.width = currentVideo.videoWidth;
            canvas.height = currentVideo.videoHeight;
            ctx.drawImage(currentVideo, 0, 0, canvas.width, canvas.height);
            
            // Compress to JPEG for faster transmission
            const base64Data = canvas.toDataURL('image/jpeg', 0.5); 
            backendReady = false; // Block until we get a response
            ws.send(JSON.stringify({ frame: base64Data }));
        }
    }

    // UI Updates based on WebSockets
    function updateUI(data) {
        if (sessionMode === "meeting") {
            const avgScore = Math.round(data.score || 0);
            const meetingAvgScore = document.getElementById('meeting-avg-score');
            const pCount = document.getElementById('participant-count');
            const mWarnings = document.getElementById('meeting-warnings');
            
            if (meetingAvgScore) {
                meetingAvgScore.textContent = avgScore;
                meetingAvgScore.style.color = avgScore < 50 ? 'var(--danger)' : (avgScore < 80 ? 'var(--warning)' : 'var(--success)');
            }
            if (pCount) pCount.textContent = data.participant_count || 0;
            if (mWarnings) mWarnings.textContent = data.distracted_count || 0;
            
            // Still update statusText even in meeting mode
            if (statusText) statusText.textContent = data.status_text;
            return;
        }

        // Hero Score (Individual Mode)
        const score = Math.round(data.score);
        engagementScore.textContent = data.face_detected ? score : "--";
        engagementBar.style.width = data.face_detected ? `${score}%` : "0%";
        
        engagementScore.className = "score-value";
        if (score < 50) engagementScore.classList.add('danger');
        else if (score < 80) engagementScore.classList.add('warning');

        // Status Text
        statusText.textContent = data.face_detected ? data.status_text : "NO FACE DETECTED";
        statusText.className = "status-text";
        if (data.status_text === "SLEEPING") statusText.classList.add('danger');
        else if (data.status_text === "YAWNING" || data.status_text === "DROWSY") statusText.classList.add('warning');

        // Alerts
        if (data.status_text === "SLEEPING" || data.drowsy_duration > 5) {
            alertBanner.classList.remove('hidden');
        } else {
            alertBanner.classList.add('hidden');
        }

        // Stats
        yawnCount.textContent = data.yawn_count || 0;
        drowsyCount.textContent = data.drowsy_count || 0;
        
        if (data.signals && data.face_detected) {
            earValue.textContent = data.signals.eye_openness.toFixed(2);
            
            const emotionIcons = {
                'Happy': 'smile', 
                'Focused': 'crosshair', 
                'Neutral': 'meh', 
                'Tired': 'battery-low', 
                'Surprised': 'zap', 
                'Angry': 'frown', 
                'Sad': 'cloud-rain'
            };
            const elabel = data.signals.emotion_label || 'Neutral';
            document.getElementById('emotion-icon').innerHTML = `<i data-lucide="${emotionIcons[elabel] || 'meh'}"></i>`;
            emotionLabel.innerHTML = elabel;
            
            gazeScore.textContent = `${Math.round((data.signals.gaze_score || 0) * 100)}%`;
            stabilityScore.textContent = `${Math.round((data.signals.head_stability || 0) * 100)}%`;
            qualityScore.textContent = `${Math.round((data.signals.face_quality || 0) * 100)}%`;
            attentionScore.textContent = `${Math.round((data.signals.attention_score || data.signals.gaze_score || 0) * 100)}%`;
            
            // Update debug overlay
            const debug = document.getElementById('camera-debug-info');
            if (debug) {
                const sourcePrefix = captureSource === "screen" ? "🖥️ Screen" : "👤 Face";
                debug.innerHTML = `${sourcePrefix}: Detected | EAR: ${data.signals.eye_openness.toFixed(3)} | Yaw: ${data.signals.yaw.toFixed(1)}°`;
                debug.style.color = data.signals.eye_openness < (data.signals.ear_threshold || 0.22) ? '#ff5252' : '#4caf50';
            }
        } else {
            // Reset detail metrics
            earValue.textContent = "0.00";
            gazeScore.textContent = "--%";
            stabilityScore.textContent = "--%";
            qualityScore.textContent = "--%";
            attentionScore.textContent = "--%";
        }
    }

    async function startSession(mode = "individual", useScreen = false) {
        sessionMode = mode;
        
        // If it's an individual session started from elsewhere, switch to live view
        if (mode === "individual" && !viewLive.classList.contains('active')) {
            switchView('live');
        }
        
        const success = useScreen ? await startScreenShare() : await startCamera();
        if (!success) return;
        
        isRecording = true;
        btnStart.classList.add('hidden');
        btnStop.classList.remove('hidden');
        statusIndicator.querySelector('.dot').classList.add('red');
        
        startTime = Date.now();
        timerInterval = setInterval(updateTimer, 1000);
        
        connectWebSocket();
        
        // Send frames at 5 FPS roughly
        frameInterval = setInterval(sendFrame, 200);
    }

    function stopSession() {
        isRecording = false;
        btnStart.classList.remove('hidden');
        btnStop.classList.add('hidden');
        statusIndicator.querySelector('.dot').classList.remove('red');
        
        clearInterval(timerInterval);
        clearInterval(frameInterval);
        
        if (ws && ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ action: "stop_session", mode: sessionMode }));
            // Give it a moment to send before closing
            setTimeout(() => ws.close(), 100);
        }
        
        stopCamera();
        
        // Reset UI metrics
        engagementScore.textContent = "--";
        engagementBar.style.width = "0%";
        statusText.textContent = "FOCUSED";
        yawnCount.textContent = "0";
        drowsyCount.textContent = "0";
        earValue.textContent = "0.00";
        recordingTime.textContent = "00:00";
        alertBanner.classList.add('hidden');
        
        // Reset meeting cards
        if (document.getElementById('meeting-avg-score')) document.getElementById('meeting-avg-score').textContent = "--";
        if (document.getElementById('participant-count')) document.getElementById('participant-count').textContent = "0";
        if (document.getElementById('meeting-warnings')) document.getElementById('meeting-warnings').textContent = "0";
        
        // Small delay to allow DB update then jump to history
        setTimeout(() => {
            switchView('history');
            if (sessionMode === "meeting") {
                document.getElementById('tab-meetings').click();
            } else {
                document.getElementById('tab-individual').click();
            }
        }, 500);
    }

    async function loadHistory() {
        historyList.innerHTML = '<div class="text-center" style="padding: 40px; color: var(--text-muted)">Loading sessions...</div>';
        
        try {
            const res = await fetch('/sessions');
            const data = await res.json();
            
            if (data.sessions.length === 0) {
                historyList.innerHTML = `
                    <div style="text-center; padding: 40px; color: var(--text-muted);">
                        No sessions recorded yet. Go to Live Analysis to start one!
                    </div>
                `;
                return;
            }
            
            historyList.innerHTML = '';
            data.sessions.forEach(session => {
                const date = new Date(session.start_time);
                const formatter = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: 'numeric' });
                
                const score = Math.round(session.avg_focus_score || 0);
                let scoreColor = "var(--success)";
                if (score < 50) scoreColor = "var(--danger)";
                else if (score < 80) scoreColor = "var(--warning)";

                const el = document.createElement('div');
                el.className = 'history-item glass-panel mt-20';
                el.style.display = 'flex';
                el.style.justifyContent = 'space-between';
                el.style.alignItems = 'center';
                el.innerHTML = `
                    <div>
                        <div class="history-date">Session #${session.session_id} - ${formatter.format(date)}</div>
                        <div style="color: var(--text-muted); font-size: 14px; margin-top:5px;">Frames Analyzed: ${session.total_frames || 0}</div>
                    </div>
                    <div style="text-align: right;">
                        <div class="history-score" style="color:${scoreColor}; font-size: 24px; font-weight: bold; font-family: 'Playfair Display', serif;">${score}</div>
                        <div style="color: var(--text-muted); font-size: 10px; text-transform:uppercase;">Avg Score</div>
                    </div>
                `;
                historyList.appendChild(el);
            });
            
        } catch (error) {
            console.error("Failed to load history", error);
            historyList.innerHTML = '<div class="alert-banner">Failed to load history. Make sure the server is running.</div>';
        }
    }

    async function loadMeetings() {
        historyList.innerHTML = '<div class="text-center" style="padding: 40px; color: var(--text-muted)">Loading meetings...</div>';
        try {
            const res = await fetch('/meetings');
            const data = await res.json();
            
            if (data.meetings.length === 0) {
                historyList.innerHTML = '<div class="text-center" style="padding: 40px; color: var(--text-muted);">No meetings recorded yet.</div>';
                return;
            }
            
            historyList.innerHTML = '';
            data.meetings.forEach(meeting => {
                const date = new Date(meeting.start_time);
                const formatter = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric', hour: 'numeric', minute: 'numeric' });
                const score = Math.round(meeting.avg_engagement || 0);
                
                const el = document.createElement('div');
                el.className = 'history-item glass-panel mt-20';
                el.style.display = 'flex';
                el.style.justifyContent = 'space-between';
                el.style.alignItems = 'center';
                el.innerHTML = `
                    <div>
                        <div class="history-date">Meeting #${meeting.meeting_id} - ${meeting.notes || 'No Title'}</div>
                        <div style="color: var(--text-muted); font-size: 14px; margin-top:5px;">${formatter.format(date)} | Peak Participants: ${meeting.peak_participants || 0}</div>
                    </div>
                    <div style="text-align: right;">
                        <div class="history-score" style="color: var(--primary); font-size: 24px; font-weight: bold; font-family: 'Playfair Display', serif;">${score}</div>
                        <div style="color: var(--text-muted); font-size: 10px; text-transform:uppercase;">Group Avg</div>
                    </div>
                `;
                historyList.appendChild(el);
            });
        } catch (error) {
            console.error("Failed to load meetings", error);
        }
    }

    // Tab Listeners
    document.getElementById('tab-individual')?.addEventListener('click', () => {
        document.getElementById('tab-individual').classList.add('active');
        document.getElementById('tab-meetings').classList.remove('active');
        loadHistory();
    });
    document.getElementById('tab-meetings')?.addEventListener('click', () => {
        document.getElementById('tab-meetings').classList.add('active');
        document.getElementById('tab-individual').classList.remove('active');
        loadMeetings();
    });

    btnStartMeeting?.addEventListener('click', () => {
        startSession("meeting", false);
        btnShareScreen.classList.remove('hidden');
    });

    btnShareScreen?.addEventListener('click', async () => {
        if (!isRecording) {
            // Start a new meeting session with screen share
            startSession("meeting", true);
        } else {
            // If already recording, we need to switch the stream
            const success = await startScreenShare();
            if (success) {
                console.log("Switched to screen share");
            }
        }
    });

    // Event Listeners
    btnStart.addEventListener('click', () => {
        // Context-aware start: if we are on the meeting page, start a meeting
        if (!viewMeeting.classList.contains('hidden')) {
            startSession("meeting", false);
        } else {
            startSession("individual", false);
        }
    });
    btnStop.addEventListener('click', stopSession);
    
    // Default open View
    switchView('dashboard');
    lucide.createIcons();
});

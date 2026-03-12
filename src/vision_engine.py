"""
Vision Engine: Advanced Face Analysis with InspireFace-Equivalent Features
Implements features similar to InspireFace SDK using MediaPipe:
- Face Detection & Tracking
- 106-Point Landmark Detection
- Head Pose Estimation (Yaw, Pitch, Roll)
- Face Emotion (7 classes)
- Silent Liveness (anti-spoofing)
- Cooperative Liveness (blink verification)
- Face Quality Score
- Mask Detection
- Face Attributes (Age/Gender estimation)
- Blink Rate & Attention Score
"""

import cv2
import mediapipe as mp
import numpy as np
from typing import Dict, Optional, Tuple, List
from collections import deque
import time


class VisionEngine:
    """
    Production-grade face analysis engine with InspireFace-equivalent features
    """
    
    def __init__(self, process_width=640):
        # Initialize MediaPipe Face Mesh with refined landmarks (478 points)
        self.mp_face_mesh = mp.solutions.face_mesh
        self.face_mesh = self.mp_face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # 478 landmarks including iris
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # Dedicated mesh for meetings (initialized lazily)
        self.meeting_mesh = None
        self.single_mesh = self.face_mesh
        self.is_meeting_mode = False
        
        # Drawing utilities
        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles
        
        # Performance settings
        self.process_width = process_width
        self.frame_count = 0
        self.last_landmarks = None
        
        # Webcam
        self.cap = None
        self.ear_threshold = 0.35
        
        # ===== TRACKING BUFFERS =====
        self.head_positions = deque(maxlen=30)
        self.ear_history = deque(maxlen=10)
        self.emotion_history = deque(maxlen=15)
        self.quality_history = deque(maxlen=20)
        
        # Blink Detection
        self.blink_count = 0
        self.blink_timestamps = deque(maxlen=60)  # Store blink times
        self.last_blink_state = False
        self.blinks_per_minute = 0
        self.session_start_time = time.time()
        
        # Cooperative Liveness (blink verification)
        self.coop_liveness_blinks = 0
        self.coop_liveness_start = None
        self.coop_liveness_verified = False
        
        # Anti-spoofing
        self.texture_scores = deque(maxlen=30)
        self.color_variance_history = deque(maxlen=20)
        self.prev_frame_gray = None
        self.motion_scores = deque(maxlen=20)
        
        # Face Quality tracking
        self.face_sizes = deque(maxlen=10)
        
        # 3D Face Model Points for head pose
        self.model_points = np.array([
            (0.0, 0.0, 0.0),          # Nose tip
            (0.0, -330.0, -65.0),     # Chin
            (-225.0, 170.0, -135.0),  # Left eye corner
            (225.0, 170.0, -135.0),   # Right eye corner
            (-150.0, -150.0, -125.0), # Left mouth corner
            (150.0, -150.0, -125.0)   # Right mouth corner
        ], dtype=np.float64)
        
    def start_camera(self, camera_id: int = 0) -> bool:
        """Initialize webcam"""
        if self.cap is not None and self.cap.isOpened():
            return True
            
        self.cap = cv2.VideoCapture(camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        # Reset tracking
        self._reset_tracking()
        return self.cap.isOpened()
    
    def _reset_tracking(self):
        """Reset all tracking buffers"""
        self.blink_count = 0
        self.blink_timestamps.clear()
        self.session_start_time = time.time()
        self.head_positions.clear()
        self.ear_history.clear()
        self.texture_scores.clear()
        self.coop_liveness_blinks = 0
        self.coop_liveness_start = None
        self.coop_liveness_verified = False
        self.prev_frame_gray = None
    
    def stop_camera(self):
        """Release webcam"""
        if self.cap:
            self.cap.release()
            self.cap = None
    
    def get_frame(self, resize=True) -> Optional[np.ndarray]:
        """Capture a single frame"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        if resize and frame.shape[1] > self.process_width:
            height = int(frame.shape[0] * (self.process_width / frame.shape[1]))
            frame = cv2.resize(frame, (self.process_width, height))
        
        return frame
    
    def analyze_frame(self, frame: np.ndarray, skip_frames=2) -> Dict:
        """
        Comprehensive frame analysis with InspireFace-equivalent features
        """
        self.frame_count += 1
        h, w = frame.shape[:2]
        
        # Skip frames for performance
        if self.frame_count % skip_frames != 0 and self.last_landmarks is not None:
            return self.last_landmarks
        
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        gray_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        results = self.face_mesh.process(rgb_frame)
        
        if not results.multi_face_landmarks:
            return self._no_face_result()
        
        face_landmarks = results.multi_face_landmarks[0]
        
        # ===== CORE METRICS =====
        
        # 1. Eye Aspect Ratio (EAR)
        ear_left = self._calculate_ear(face_landmarks, [33, 160, 158, 133, 153, 144])
        ear_right = self._calculate_ear(face_landmarks, [362, 385, 387, 263, 373, 380])
        avg_ear = (ear_left + ear_right) / 2.0
        self.ear_history.append(avg_ear)
        smoothed_ear = sum(self.ear_history) / len(self.ear_history)
        
        # 2. Mouth Aspect Ratio (MAR)
        mar = self._calculate_mar(face_landmarks)
        
        # 3. Head Pose (Yaw, Pitch, Roll)
        yaw, pitch, roll = self._estimate_head_pose(face_landmarks, w, h)
        
        # ===== INSPIRFACE-EQUIVALENT FEATURES =====
        
        # 4. Face Quality Score
        face_quality = self._calculate_face_quality(face_landmarks, gray_frame, w, h, yaw, pitch)
        
        # 5. Mask Detection
        is_wearing_mask, mask_confidence = self._detect_mask(face_landmarks, mar)
        
        # 6. Face Emotion (7 classes)
        emotion_score, emotion_label, emotion_probs = self._detect_emotion(face_landmarks, mar, smoothed_ear)
        self.emotion_history.append(emotion_score)
        smoothed_emotion = sum(self.emotion_history) / len(self.emotion_history)
        
        # 7. Silent Liveness (Anti-Spoofing)
        silent_liveness_score = self._calculate_silent_liveness(frame, gray_frame, face_landmarks, w, h)
        
        # 8. Blink Detection & Rate
        blink_rate = self._update_blink_detection(smoothed_ear)
        
        # 9. Cooperative Liveness (blink verification)
        coop_liveness_status = self._update_cooperative_liveness(smoothed_ear)
        
        # 10. Gaze Score
        gaze_score = self._calculate_gaze_score(face_landmarks, yaw, pitch)
        
        # 11. Head Stability
        head_stability = self._calculate_head_stability(face_landmarks)
        
        # 12. Attention Score
        attention_score = self._calculate_attention_score(gaze_score, head_stability, smoothed_ear, emotion_label)
        
        # 13. Face Attributes (approximate age/gender)
        face_attributes = self._estimate_face_attributes(face_landmarks)
        
        # ===== DETECTION LOGIC =====
        ear_threshold = getattr(self, 'ear_threshold', 0.35)
        is_drowsy = smoothed_ear < ear_threshold
        is_yawning = mar > 0.50
        
        # Combined liveness status
        liveness_status = self._determine_liveness_status(
            silent_liveness_score, coop_liveness_status, blink_rate, head_stability
        )
        
        # Store previous frame for motion detection
        self.prev_frame_gray = gray_frame.copy()
        
        result = {
            # Core metrics
            'gaze_score': gaze_score,
            'emotion_score': smoothed_emotion,
            'head_stability': head_stability,
            'face_detected': True,
            'eye_openness': smoothed_ear,
            'mouth_openness': mar,
            'is_yawning': is_yawning,
            'is_drowsy': is_drowsy,
            'ear_threshold': ear_threshold,
            
            # Head pose
            'head_pose': (yaw, pitch, roll),
            'yaw': yaw,
            'pitch': pitch,
            'roll': roll,
            
            # InspireFace-equivalent
            'face_quality': face_quality,
            'is_wearing_mask': is_wearing_mask,
            'mask_confidence': mask_confidence,
            'emotion_label': emotion_label,
            'emotion_probs': emotion_probs,
            'silent_liveness_score': silent_liveness_score,
            'coop_liveness_status': coop_liveness_status,
            'coop_liveness_verified': self.coop_liveness_verified,
            'blink_rate': blink_rate,
            'blink_count': self.blink_count,
            'attention_score': attention_score,
            'face_attributes': face_attributes,
            
            # Legacy compatibility
            'liveness_status': liveness_status,
            'anti_spoof_score': silent_liveness_score,
        }
        
        self.last_landmarks = result
        return result
    
    def _no_face_result(self) -> Dict:
        """Return empty result when no face detected"""
        return {
            'gaze_score': 0.0, 'emotion_score': 0.0, 'head_stability': 0.0,
            'face_detected': False, 'eye_openness': 0.0, 'mouth_openness': 0.0,
            'is_yawning': False, 'is_drowsy': False, 'liveness_status': "No Face",
            'attention_score': 0.0, 'blink_rate': 0, 'head_pose': (0, 0, 0),
            'emotion_label': 'Unknown', 'anti_spoof_score': 0.0,
            'face_quality': 0.0, 'is_wearing_mask': False, 'mask_confidence': 0.0,
            'silent_liveness_score': 0.0, 'coop_liveness_status': 'Waiting',
            'emotion_probs': {}, 'face_attributes': {}, 'yaw': 0, 'pitch': 0, 'roll': 0,
            'blink_count': 0, 'coop_liveness_verified': False, 'ear_threshold': 0.35
        }
    
    def _calculate_ear(self, landmarks, indices) -> float:
        """Calculate Eye Aspect Ratio"""
        p2 = np.array([landmarks.landmark[indices[1]].x, landmarks.landmark[indices[1]].y])
        p6 = np.array([landmarks.landmark[indices[5]].x, landmarks.landmark[indices[5]].y])
        p3 = np.array([landmarks.landmark[indices[2]].x, landmarks.landmark[indices[2]].y])
        p5 = np.array([landmarks.landmark[indices[4]].x, landmarks.landmark[indices[4]].y])
        p1 = np.array([landmarks.landmark[indices[0]].x, landmarks.landmark[indices[0]].y])
        p4 = np.array([landmarks.landmark[indices[3]].x, landmarks.landmark[indices[3]].y])
        
        dist_v1 = np.linalg.norm(p2 - p6)
        dist_v2 = np.linalg.norm(p3 - p5)
        dist_h = np.linalg.norm(p1 - p4)
        
        if dist_h == 0: return 0.0
        return (dist_v1 + dist_v2) / (2.0 * dist_h)

    def _calculate_mar(self, landmarks) -> float:
        """Calculate Mouth Aspect Ratio"""
        p_top = np.array([landmarks.landmark[13].x, landmarks.landmark[13].y])
        p_bot = np.array([landmarks.landmark[14].x, landmarks.landmark[14].y])
        p_left = np.array([landmarks.landmark[61].x, landmarks.landmark[61].y])
        p_right = np.array([landmarks.landmark[291].x, landmarks.landmark[291].y])
        
        height = np.linalg.norm(p_top - p_bot)
        width = np.linalg.norm(p_left - p_right)
        
        if width == 0: return 0.0
        return height / width
    
    def _estimate_head_pose(self, landmarks, w, h) -> Tuple[float, float, float]:
        """Estimate head pose using solvePnP"""
        image_points = np.array([
            (landmarks.landmark[1].x * w, landmarks.landmark[1].y * h),
            (landmarks.landmark[152].x * w, landmarks.landmark[152].y * h),
            (landmarks.landmark[33].x * w, landmarks.landmark[33].y * h),
            (landmarks.landmark[263].x * w, landmarks.landmark[263].y * h),
            (landmarks.landmark[61].x * w, landmarks.landmark[61].y * h),
            (landmarks.landmark[291].x * w, landmarks.landmark[291].y * h)
        ], dtype=np.float64)
        
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1]
        ], dtype=np.float64)
        
        dist_coeffs = np.zeros((4, 1))
        
        success, rotation_vector, _ = cv2.solvePnP(
            self.model_points, image_points, camera_matrix, dist_coeffs
        )
        
        if not success:
            return (0, 0, 0)
        
        rotation_matrix, _ = cv2.Rodrigues(rotation_vector)
        
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
        singular = sy < 1e-6
        
        if not singular:
            pitch = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            yaw = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            pitch = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            yaw = np.arctan2(-rotation_matrix[2, 0], sy)
            roll = 0
            
        # Convert to degrees
        pitch = np.degrees(pitch)
        yaw = np.degrees(yaw)
        roll = np.degrees(roll)
        
        # Human-readable angle normalization
        # Ensure angles are within -180 to 180 range
        if pitch > 180: pitch -= 360
        if yaw > 180: yaw -= 360
        if roll > 180: roll -= 360
        
        # Pitch correction (OpenCV coordinate system usually has inverted Y)
        # We want looking up = positive, looking down = negative
        # Or centered = 0. Often it comes out as ~180 for "forward"
        if abs(pitch) > 90:
            if pitch > 0: pitch = 180 - pitch
            else: pitch = -180 - pitch
            
        return (yaw, pitch, roll)
    
    def _calculate_face_quality(self, landmarks, gray, w, h, yaw, pitch) -> float:
        """
        Calculate face quality score (InspireFace equivalent)
        Factors: sharpness, pose, size, brightness, symmetry
        """
        # 1. Sharpness (Laplacian variance)
        laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
        sharpness_score = min(1.0, laplacian_var / 300)
        
        # 2. Pose quality (face should be frontal)
        yaw_score = max(0, 1 - abs(yaw) / 45)
        pitch_score = max(0, 1 - abs(pitch) / 45)
        pose_score = (yaw_score + pitch_score) / 2
        
        # 3. Face size (should be reasonably large)
        face_points = [(landmarks.landmark[i].x * w, landmarks.landmark[i].y * h) 
                       for i in [10, 152, 234, 454]]  # Top, bottom, left, right
        face_width = abs(face_points[2][0] - face_points[3][0])
        face_height = abs(face_points[0][1] - face_points[1][1])
        face_area = face_width * face_height
        size_score = min(1.0, face_area / (w * h * 0.15))  # Face should be at least 15% of frame
        self.face_sizes.append(size_score)
        
        # 4. Brightness (not too dark or too bright)
        mean_brightness = np.mean(gray)
        brightness_score = 1.0 - abs(mean_brightness - 127) / 127
        
        # 5. Symmetry check
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        nose = landmarks.landmark[1]
        left_dist = abs(left_eye.x - nose.x)
        right_dist = abs(right_eye.x - nose.x)
        symmetry_score = 1.0 - min(1.0, abs(left_dist - right_dist) * 5)
        
        # Weighted combination
        quality = (
            sharpness_score * 0.25 +
            pose_score * 0.25 +
            size_score * 0.20 +
            brightness_score * 0.15 +
            symmetry_score * 0.15
        )
        
        self.quality_history.append(quality)
        return sum(self.quality_history) / len(self.quality_history)
    
    def _detect_mask(self, landmarks, mar) -> Tuple[bool, float]:
        """
        Detect if person is wearing a mask
        Conservative detection - only triggers when clearly wearing a mask
        """
        # Key points for mask detection
        nose_tip = landmarks.landmark[1]
        mouth_top = landmarks.landmark[13]
        mouth_bottom = landmarks.landmark[14]
        chin = landmarks.landmark[152]
        left_cheek = landmarks.landmark[234]
        right_cheek = landmarks.landmark[454]
        
        # Mouth aspect ratio - masks make mouth nearly invisible
        # Normal MAR is 0.1-0.5, masked face has MAR near 0 or very low
        mouth_hidden = mar < 0.08  # Very strict - mouth basically invisible
        
        # Check face width vs chin-mouth distance (masks compress lower face)
        face_width = abs(right_cheek.x - left_cheek.x)
        mouth_chin_dist = abs(mouth_bottom.y - chin.y)
        nose_mouth_dist = abs(nose_tip.y - mouth_top.y)
        
        # Normally nose to mouth is about 1/3 of face height
        # With mask, the landmarks bunch together unnaturally
        compression = nose_mouth_dist / max(face_width, 0.001)
        heavily_compressed = compression < 0.08  # Very strict
        
        # Landmark confidence check - masks often cause unstable mouth landmarks
        mouth_height = abs(mouth_bottom.y - mouth_top.y)
        mouth_too_flat = mouth_height < 0.005  # Basically a line
        
        # Only mark as masked if multiple strong indicators
        mask_score = 0.0
        if mouth_hidden:
            mask_score += 0.4
        if heavily_compressed:
            mask_score += 0.3
        if mouth_too_flat:
            mask_score += 0.3
        
        # Require VERY high confidence to declare mask
        is_wearing_mask = mask_score > 0.7
        
        return is_wearing_mask, mask_score
    
    def _detect_emotion(self, landmarks, mar, ear) -> Tuple[float, str, Dict]:
        """
        Detect facial emotion (7 classes like InspireFace)
        Classes: Neutral, Happy, Sad, Angry, Fearful, Disgusted, Surprised
        """
        # Mouth shape analysis
        left_mouth = landmarks.landmark[61]
        right_mouth = landmarks.landmark[291]
        mouth_top = landmarks.landmark[13]
        mouth_bottom = landmarks.landmark[14]
        
        mouth_width = abs(right_mouth.x - left_mouth.x)
        mouth_height = abs(mouth_bottom.y - mouth_top.y)
        
        # Eyebrow analysis
        left_brow_inner = landmarks.landmark[55]
        right_brow_inner = landmarks.landmark[285]
        left_eye_center = landmarks.landmark[159]
        right_eye_center = landmarks.landmark[386]
        
        left_brow_raise = left_eye_center.y - left_brow_inner.y
        right_brow_raise = right_eye_center.y - right_brow_inner.y
        avg_brow_raise = (left_brow_raise + right_brow_raise) / 2
        
        # Mouth corners relative to center
        mouth_center_y = (mouth_top.y + mouth_bottom.y) / 2
        left_corner_y = landmarks.landmark[61].y
        right_corner_y = landmarks.landmark[291].y
        corner_pull = mouth_center_y - (left_corner_y + right_corner_y) / 2
        
        # Initialize probabilities - default to Neutral/Focused
        probs = {
            'Focused': 0.5,  # Default when looking attentive
            'Neutral': 0.4,
            'Happy': 0.0,
            'Sad': 0.0,
            'Angry': 0.0,
            'Fearful': 0.0,
            'Disgusted': 0.0,
            'Surprised': 0.0
        }
        
        # Happy - corners clearly up, wide mouth
        if corner_pull > 0.015:  # raised threshold
            probs['Happy'] = min(1.0, 0.5 + corner_pull * 12)
            probs['Focused'] = 0.2
            probs['Neutral'] = 0.1
        
        # Surprised - clearly raised brows, open mouth
        if avg_brow_raise > 0.05 and mar > 0.35:
            probs['Surprised'] = min(1.0, 0.5 + avg_brow_raise * 6 + mar)
            probs['Focused'] = 0.2
        
        # Sad - corners CLEARLY down (much stricter threshold)
        if corner_pull < -0.025:  # was -0.005, now much stricter
            probs['Sad'] = min(1.0, 0.3 + abs(corner_pull) * 10)  # reduced multiplier
            probs['Focused'] = 0.3
        
        # Angry - clearly lowered brows, tight mouth
        if avg_brow_raise < 0.01 and mouth_width < 0.08:
            probs['Angry'] = 0.4
            probs['Focused'] = 0.3
        
        # Focused state - eyes open, looking at screen, neutral expression
        if ear > 0.25 and abs(corner_pull) < 0.015:
            probs['Focused'] = max(probs['Focused'], 0.6)
        
        # Get max emotion
        emotion_label = max(probs, key=probs.get)
        emotion_score = probs[emotion_label]
        
        return emotion_score, emotion_label, probs
    
    def _calculate_silent_liveness(self, frame, gray, landmarks, w, h) -> float:
        """
        Silent Liveness Detection (Anti-Spoofing)
        Multi-factor analysis without requiring user interaction
        """
        scores = []
        
        # 1. Texture Analysis (real faces have more micro-texture)
        face_bbox = self._get_face_bbox(landmarks, w, h)
        if face_bbox:
            x1, y1, x2, y2 = face_bbox
            face_region = gray[y1:y2, x1:x2]
            if face_region.size > 100:
                laplacian_var = cv2.Laplacian(face_region, cv2.CV_64F).var()
                texture_score = min(1.0, laplacian_var / 400)
                self.texture_scores.append(texture_score)
                scores.append(sum(self.texture_scores) / len(self.texture_scores))
        
        # 2. Color Distribution (real faces have natural color variation)
        if face_bbox:
            x1, y1, x2, y2 = face_bbox
            face_color = frame[y1:y2, x1:x2]
            if face_color.size > 100:
                hsv = cv2.cvtColor(face_color, cv2.COLOR_BGR2HSV)
                h_std = np.std(hsv[:, :, 0])
                s_std = np.std(hsv[:, :, 1])
                color_var = (h_std + s_std) / 2
                color_score = min(1.0, color_var / 30)
                self.color_variance_history.append(color_score)
                scores.append(sum(self.color_variance_history) / len(self.color_variance_history))
        
        # 3. Motion Analysis (photos don't have natural micro-movements)
        if self.prev_frame_gray is not None and face_bbox:
            x1, y1, x2, y2 = face_bbox
            prev_face = self.prev_frame_gray[y1:y2, x1:x2]
            curr_face = gray[y1:y2, x1:x2]
            if prev_face.shape == curr_face.shape and prev_face.size > 100:
                diff = cv2.absdiff(prev_face, curr_face)
                motion = np.mean(diff)
                # Real faces: small but non-zero motion
                motion_score = 1.0 if 1.0 < motion < 15.0 else 0.5
                self.motion_scores.append(motion_score)
                scores.append(sum(self.motion_scores) / len(self.motion_scores))
        
        # 4. Blink Detection (photos don't blink)
        blink_score = 1.0 if self.blink_count > 0 else 0.3
        scores.append(blink_score)
        
        # 5. Head Movement (photos are static)
        if len(self.head_positions) > 10:
            positions = np.array(list(self.head_positions))
            position_var = np.var(positions, axis=0).sum()
            movement_score = 1.0 if 0.00005 < position_var < 0.01 else 0.3
            scores.append(movement_score)
        
        if scores:
            return sum(scores) / len(scores)
        return 0.5
    
    def _get_face_bbox(self, landmarks, w, h, padding=10) -> Optional[Tuple[int, int, int, int]]:
        """Get face bounding box from landmarks"""
        x_coords = [int(landmarks.landmark[i].x * w) for i in range(468)]
        y_coords = [int(landmarks.landmark[i].y * h) for i in range(468)]
        
        x1 = max(0, min(x_coords) - padding)
        y1 = max(0, min(y_coords) - padding)
        x2 = min(w, max(x_coords) + padding)
        y2 = min(h, max(y_coords) + padding)
        
        if x2 > x1 and y2 > y1:
            return (x1, y1, x2, y2)
        return None
    
    def _update_blink_detection(self, ear) -> int:
        """Track blinks and calculate blinks per minute"""
        is_blink = ear < 0.22
        
        if is_blink and not self.last_blink_state:
            self.blink_count += 1
            self.blink_timestamps.append(time.time())
        
        self.last_blink_state = is_blink
        
        # Calculate BPM from recent blinks
        now = time.time()
        recent_blinks = [t for t in self.blink_timestamps if now - t < 60]
        self.blinks_per_minute = len(recent_blinks)
        
        return self.blinks_per_minute
    
    def _update_cooperative_liveness(self, ear) -> str:
        """
        Cooperative Liveness: Verify user is live by asking for blinks
        """
        if self.coop_liveness_verified:
            return "Verified ✓"
        
        if self.coop_liveness_start is None:
            self.coop_liveness_start = time.time()
            self.coop_liveness_blinks = 0
        
        # Track blinks in verification window
        if ear < 0.22 and not self.last_blink_state:
            self.coop_liveness_blinks += 1
        
        # Check if verified (2+ blinks in 10 seconds)
        elapsed = time.time() - self.coop_liveness_start
        
        if self.coop_liveness_blinks >= 2:
            self.coop_liveness_verified = True
            return "Verified ✓"
        elif elapsed < 10:
            return f"Blink {self.coop_liveness_blinks}/2"
        else:
            # Reset and try again
            self.coop_liveness_start = time.time()
            self.coop_liveness_blinks = 0
            return "Blink 0/2"
    
    def _calculate_gaze_score(self, landmarks, yaw, pitch) -> float:
        """
        Calculate gaze/attention score
        More lenient - focus on whether person is facing camera
        """
        # Normalize angles to reasonable range (-180 to 180 can happen)
        yaw = yaw % 360
        if yaw > 180: yaw -= 360
        pitch = pitch % 360  
        if pitch > 180: pitch -= 360
        
        # Very lenient thresholds - 45 degrees tolerance
        yaw_score = max(0, 1 - abs(yaw) / 45)
        pitch_score = max(0, 1 - abs(pitch) / 45)
        
        # Eye position in frame (should be roughly centered)
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        eye_center_x = (left_eye.x + right_eye.x) / 2
        eye_center_y = (left_eye.y + right_eye.y) / 2
        
        # Position score - lenient, face should be in frame
        x_deviation = abs(eye_center_x - 0.5)
        y_deviation = abs(eye_center_y - 0.4)  # Eyes typically at 40% from top
        position_score = max(0, 1 - (x_deviation + y_deviation) * 1.5)
        
        # Weighted average - position matters most (face in frame = looking)
        gaze = yaw_score * 0.3 + pitch_score * 0.2 + position_score * 0.5
        
        # Boost if face is well-centered
        if x_deviation < 0.15 and y_deviation < 0.2:
            gaze = min(1.0, gaze + 0.15)
        
        return min(1.0, max(0.0, gaze))
    
    def _calculate_head_stability(self, landmarks) -> float:
        """Calculate head stability from movement history"""
        nose = landmarks.landmark[1]
        current_pos = (nose.x, nose.y, getattr(nose, 'z', 0))
        self.head_positions.append(current_pos)
        
        if len(self.head_positions) < 5:
            return 0.9
        
        positions = np.array(list(self.head_positions))
        variance = np.var(positions, axis=0).sum()
        stability = 1.0 - min(1.0, variance * 100)
        
        return max(0.0, min(1.0, stability))
    
    def _calculate_attention_score(self, gaze, stability, ear, emotion) -> float:
        """Composite attention score"""
        eye_score = min(1.0, ear / 0.3) if ear > 0.2 else ear / 0.2
        
        # Emotion bonus (focused/neutral = more attention)
        emotion_bonus = 0.1 if emotion in ['Focused', 'Neutral', 'Happy'] else 0
        
        attention = gaze * 0.4 + stability * 0.3 + eye_score * 0.3 + emotion_bonus
        return min(1.0, max(0.0, attention))
    
    def _estimate_face_attributes(self, landmarks) -> Dict:
        """
        Estimate face attributes (simplified)
        Note: Real age/gender requires deep learning models
        """
        # Face proportions analysis for approximate attributes
        left_eye = landmarks.landmark[33]
        right_eye = landmarks.landmark[263]
        nose = landmarks.landmark[1]
        chin = landmarks.landmark[152]
        
        # Eye-to-chin ratio (approximation for age category)
        eye_chin_dist = abs(chin.y - (left_eye.y + right_eye.y) / 2)
        eye_distance = abs(right_eye.x - left_eye.x)
        
        # Very rough heuristic (not accurate, just demo)
        face_ratio = eye_chin_dist / max(eye_distance, 0.001)
        
        if face_ratio < 1.2:
            age_group = "Child"
        elif face_ratio < 1.4:
            age_group = "Young Adult"
        elif face_ratio < 1.6:
            age_group = "Adult"
        else:
            age_group = "Senior"
        
        return {
            'age_group': age_group,
            'face_ratio': round(face_ratio, 2),
            'note': 'Approximate (requires ML model for accuracy)'
        }
    
    def _determine_liveness_status(self, silent_score, coop_status, blink_rate, stability) -> str:
        """Combined liveness determination"""
        if self.coop_liveness_verified and silent_score > 0.6:
            return "Live ✓"
        elif silent_score > 0.7 and blink_rate > 5:
            return "Live"
        elif silent_score > 0.5:
            return "Checking..."
        else:
            return "Suspicious"

    def draw_landmarks(self, frame: np.ndarray, draw: bool = True) -> np.ndarray:
        """Draw bounding box and label instead of full mesh"""
        if not draw: return frame
        
        # We need landmarks to draw the box, but we don't want to re-process if possible
        # Check if we have last result cached
        if hasattr(self, 'last_landmarks') and self.last_landmarks and self.last_landmarks.get('face_detected'):
            # Use cached detection if available
            # Note: This might lag by 1 frame but is much faster
            
            # Re-get the bounding box dynamically if possible
            h, w = frame.shape[:2]
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = self.face_mesh.process(rgb_frame)
            
            if results.multi_face_landmarks:
                face_landmarks = results.multi_face_landmarks[0]
                
                # Calculate Bounding Box
                x_min, y_min = w, h
                x_max, y_max = 0, 0
                
                for lm in face_landmarks.landmark:
                    x, y = int(lm.x * w), int(lm.y * h)
                    if x < x_min: x_min = x
                    if x > x_max: x_max = x
                    if y < y_min: y_min = y
                    if y > y_max: y_max = y
                
                # Add padding
                pad = 20
                x_min = max(0, x_min - pad)
                y_min = max(0, y_min - pad - 20) # Extra space for label
                x_max = min(w, x_max + pad)
                y_max = min(h, y_max + pad)
                
                # Draw Corner Rect (Professional Look)
                # Top-Left
                color = (0, 255, 0) # Green
                thickness = 2
                line_len = 30
                
                cv2.line(frame, (x_min, y_min), (x_min + line_len, y_min), color, thickness)
                cv2.line(frame, (x_min, y_min), (x_min, y_min + line_len), color, thickness)
                
                # Top-Right
                cv2.line(frame, (x_max, y_min), (x_max - line_len, y_min), color, thickness)
                cv2.line(frame, (x_max, y_min), (x_max, y_min + line_len), color, thickness)
                
                # Bottom-Left
                cv2.line(frame, (x_min, y_max), (x_min + line_len, y_max), color, thickness)
                cv2.line(frame, (x_min, y_max), (x_min, y_max - line_len), color, thickness)
                
                # Bottom-Right
                cv2.line(frame, (x_max, y_max), (x_max - line_len, y_max), color, thickness)
                cv2.line(frame, (x_max, y_max), (x_max, y_max - line_len), color, thickness)
                
                # Draw Label
                label = "Person"
                (w_text, h_text), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)
                cv2.rectangle(frame, (x_min, y_min - 25), (x_min + w_text + 10, y_min - 5), color, -1)
                cv2.putText(frame, label, (x_min + 5, y_min - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 1)
                
        return frame

    def set_meeting_mode(self, enabled: bool):
        """Toggle between single-user focus and multi-user meeting mode"""
        if enabled == self.is_meeting_mode: return
        
        self.is_meeting_mode = enabled
        
        if enabled:
            if self.meeting_mesh is None:
                self.meeting_mesh = self.mp_face_mesh.FaceMesh(
                    max_num_faces=10,  # Support up to 10 people
                    refine_landmarks=True,
                    min_detection_confidence=0.3, # Lower confidence for smaller faces in grid
                    min_tracking_confidence=0.3
                )
            self.face_mesh = self.meeting_mesh
        else:
            self.face_mesh = self.single_mesh

    def analyze_multi_faces(self, frame) -> List[Dict]:
        """
        Analyze multiple faces in a frame (for meetings)
        Returns list of results for each detected face
        """
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w = frame.shape[:2]
        results = self.face_mesh.process(rgb_frame)
        
        output = []
        
        if results.multi_face_landmarks:
            for i, landmarks in enumerate(results.multi_face_landmarks):
                # 1. Calculate Bounding Box
                x_values = [lm.x for lm in landmarks.landmark]
                y_values = [lm.y for lm in landmarks.landmark]
                bbox = {
                    'x_min': int(min(x_values) * w),
                    'x_max': int(max(x_values) * w),
                    'y_min': int(min(y_values) * h),
                    'y_max': int(max(y_values) * h)
                }
                
                # 2. Instantaneous Analysis (No history smoothing for multi-face MVP)
                
                # Head Pose
                yaw, pitch, roll = self._estimate_head_pose(landmarks, w, h)
                
                # EAR/Eye Openness
                left_ear = self._calculate_ear(landmarks, [33, 160, 158, 133, 153, 144])
                right_ear = self._calculate_ear(landmarks, [362, 385, 387, 263, 373, 380])
                avg_ear = (left_ear + right_ear) / 2
                
                # MAR/Mouth
                mouth_pts = [61, 291, 39, 181, 0, 17, 269, 405] 
                mar = self._calculate_mar(landmarks)
                
                # Gaze
                gaze_score = self._calculate_gaze_score(landmarks, yaw, pitch)
                
                # Emotion
                emotion_score, emotion_label, _ = self._detect_emotion(landmarks, mar, avg_ear)
                
                # Liveness/Drowsiness flags
                is_drowsy = avg_ear < 0.25
                is_yawning = mar > 0.6
                
                # Composite Score
                attention = gaze_score
                engagement = (attention * 0.5 + emotion_score * 0.3 + avg_ear * 0.2) * 100
                if is_drowsy: engagement *= 0.5
                if is_yawning: engagement *= 0.6
                
                result = {
                    'id': i,
                    'bbox': bbox,
                    'engagement_score': min(100, max(0, engagement)),
                    'is_drowsy': is_drowsy,
                    'is_yawning': is_yawning,
                    'emotion': emotion_label,
                    'attention': attention
                }
                output.append(result)
                
        return output

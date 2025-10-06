from flask import Flask, render_template, request, jsonify, session
import time
import statistics
import json
import os
from datetime import timedelta
import secrets

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)

class KeystrokeAuthenticator:
    def __init__(self, profile_file='keystroke_profile.json'):
        self.profile_file = profile_file
        self.profiles = self.load_profiles()
        
    def load_profiles(self):
        if os.path.exists(self.profile_file):
            with open(self.profile_file, 'r') as f:
                return json.load(f)
        return {}
    
    def save_profiles(self):
        with open(self.profile_file, 'w') as f:
            json.dump(self.profiles, f, indent=2)
    
    def calculate_timing_features(self, timings):
        if len(timings) < 2:
            return None
        
        features = {
            'mean': statistics.mean(timings),
            'median': statistics.median(timings),
            'stdev': statistics.stdev(timings) if len(timings) > 1 else 0,
            'min': min(timings),
            'max': max(timings),
            'total_time': sum(timings)
        }
        return features
    
    def compare_timing_profiles(self, profile1, profile2):
        if not profile1 or not profile2:
            return 0
        
        diffs = []
        weights = {'mean': 0.3, 'median': 0.2, 'stdev': 0.2, 'total_time': 0.3}
        
        for key in weights:
            if profile1[key] == 0 and profile2[key] == 0:
                diffs.append(0)
            elif profile1[key] == 0 or profile2[key] == 0:
                diffs.append(1)
            else:
                diff = abs(profile1[key] - profile2[key]) / max(profile1[key], profile2[key])
                diffs.append(diff * weights[key])
        
        total_diff = sum(diffs)
        similarity = 1 - total_diff
        
        return max(0, similarity)
    
    def enroll_user(self, username, password, all_timings):
        if len(all_timings) < 3:
            return False, "Need at least 3 samples"
        
        avg_features = {}
        feature_keys = ['mean', 'median', 'stdev', 'min', 'max', 'total_time']
        
        for key in feature_keys:
            values = []
            for timings in all_timings:
                features = self.calculate_timing_features(timings)
                if features:
                    values.append(features[key])
            if values:
                avg_features[key] = statistics.mean(values)
        
        self.profiles[username] = {
            'password': password,
            'timing_profile': avg_features,
            'password_length': len(password)
        }
        
        self.save_profiles()
        return True, "User enrolled successfully"
    
    def authenticate_user(self, username, password, timings):
        if username not in self.profiles:
            return False, "User not found", 0
        
        profile = self.profiles[username]
        
        if password != profile['password']:
            return False, "Incorrect password", 0
        
        current_features = self.calculate_timing_features(timings)
        if not current_features:
            return False, "Insufficient timing data", 0
        
        similarity = self.compare_timing_profiles(
            profile['timing_profile'], 
            current_features
        )
        
        if similarity >= 0.60:
            return True, "Authentication successful", similarity
        else:
            return False, "Typing pattern mismatch", similarity
    
    def list_users(self):
        return list(self.profiles.keys())
    
    def delete_user(self, username):
        if username in self.profiles:
            del self.profiles[username]
            self.save_profiles()
            return True
        return False

auth = KeystrokeAuthenticator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/enroll', methods=['POST'])
def enroll():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    all_timings = data.get('timings', [])
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    if username in auth.profiles:
        return jsonify({'success': False, 'message': 'User already exists'})
    
    success, message = auth.enroll_user(username, password, all_timings)
    return jsonify({'success': success, 'message': message})

@app.route('/api/authenticate', methods=['POST'])
def authenticate():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    timings = data.get('timings', [])
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password required'})
    
    success, message, similarity = auth.authenticate_user(username, password, timings)
    
    if success:
        session['username'] = username
        session.permanent = True
    
    return jsonify({
        'success': success, 
        'message': message,
        'similarity': round(similarity * 100, 1)
    })

@app.route('/api/users', methods=['GET'])
def list_users():
    users = auth.list_users()
    return jsonify({'users': users})

@app.route('/api/delete', methods=['POST'])
def delete_user():
    data = request.json
    username = data.get('username')
    
    if not username:
        return jsonify({'success': False, 'message': 'Username required'})
    
    success = auth.delete_user(username)
    message = 'User deleted' if success else 'User not found'
    return jsonify({'success': success, 'message': message})

@app.route('/api/logout', methods=['POST'])
def logout():
    session.pop('username', None)
    return jsonify({'success': True})

@app.route('/api/session', methods=['GET'])
def get_session():
    username = session.get('username')
    return jsonify({'logged_in': username is not None, 'username': username})

if __name__ == '__main__':
    # Create templates directory if it doesn't exist
    os.makedirs('templates', exist_ok=True)
    
    # Create HTML template
    html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Keystroke Dynamics Authentication</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 20px;
        }
        
        .container {
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 500px;
            width: 100%;
        }
        
        h1 {
            color: #667eea;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }
        
        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }
        
        .tabs {
            display: flex;
            gap: 10px;
            margin-bottom: 30px;
        }
        
        .tab {
            flex: 1;
            padding: 12px;
            background: #f0f0f0;
            border: none;
            border-radius: 10px;
            cursor: pointer;
            font-size: 14px;
            font-weight: 600;
            transition: all 0.3s;
        }
        
        .tab.active {
            background: #667eea;
            color: white;
        }
        
        .tab-content {
            display: none;
        }
        
        .tab-content.active {
            display: block;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        label {
            display: block;
            margin-bottom: 8px;
            color: #333;
            font-weight: 600;
            font-size: 14px;
        }
        
        input {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            font-size: 14px;
            transition: border-color 0.3s;
        }
        
        input:focus {
            outline: none;
            border-color: #667eea;
        }
        
        button {
            width: 100%;
            padding: 14px;
            background: #667eea;
            color: white;
            border: none;
            border-radius: 10px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        button:hover {
            background: #5568d3;
        }
        
        button:disabled {
            background: #ccc;
            cursor: not-allowed;
        }
        
        .message {
            padding: 12px;
            border-radius: 10px;
            margin-bottom: 20px;
            text-align: center;
            font-size: 14px;
        }
        
        .success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        
        .error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        
        .info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        
        .enrollment-progress {
            margin-bottom: 20px;
        }
        
        .progress-step {
            padding: 10px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 10px;
            font-size: 14px;
        }
        
        .progress-step.completed {
            background: #d4edda;
            color: #155724;
        }
        
        .progress-step.active {
            background: #fff3cd;
            color: #856404;
        }
        
        .user-list {
            max-height: 200px;
            overflow-y: auto;
            margin-bottom: 20px;
        }
        
        .user-item {
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            margin-bottom: 10px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .delete-btn {
            padding: 6px 12px;
            background: #dc3545;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-size: 12px;
        }
        
        .delete-btn:hover {
            background: #c82333;
        }
        
        .similarity-score {
            margin-top: 15px;
            padding: 12px;
            background: #f8f9fa;
            border-radius: 8px;
            text-align: center;
        }
        
        .similarity-bar {
            width: 100%;
            height: 30px;
            background: #e0e0e0;
            border-radius: 15px;
            overflow: hidden;
            margin-top: 10px;
        }
        
        .similarity-fill {
            height: 100%;
            background: linear-gradient(90deg, #28a745, #20c997);
            transition: width 0.5s ease;
            display: flex;
            align-items: center;
            justify-content: center;
            color: white;
            font-weight: bold;
        }
        
        .logged-in-user {
            text-align: center;
            padding: 15px;
            background: #d4edda;
            border-radius: 10px;
            margin-bottom: 20px;
        }
        
        .logout-btn {
            margin-top: 10px;
            background: #6c757d;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 Keystroke Authentication</h1>
        <p class="subtitle">Biometric security using typing patterns</p>
        
        <div id="loggedInSection" style="display: none;">
            <div class="logged-in-user">
                <strong>Logged in as: <span id="currentUser"></span></strong>
                <button class="logout-btn" onclick="logout()">Logout</button>
            </div>
        </div>
        
        <div class="tabs">
            <button class="tab active" onclick="switchTab('login')">Login</button>
            <button class="tab" onclick="switchTab('enroll')">Enroll</button>
            <button class="tab" onclick="switchTab('manage')">Manage</button>
        </div>
        
        <div id="messageBox"></div>
        
        <!-- Login Tab -->
        <div id="login" class="tab-content active">
            <form onsubmit="login(event)">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="loginUsername" required>
                </div>
                <div class="form-group">
                    <label>Password</label>
                    <input type="password" id="loginPassword" required>
                </div>
                <button type="submit">Authenticate</button>
            </form>
            <div id="loginSimilarity"></div>
        </div>
        
        <!-- Enroll Tab -->
        <div id="enroll" class="tab-content">
            <div class="enrollment-progress" id="enrollProgress"></div>
            <form onsubmit="handleEnrollSubmit(event)">
                <div class="form-group">
                    <label>Username</label>
                    <input type="text" id="enrollUsername" required>
                </div>
                <div class="form-group">
                    <label>Password (Sample <span id="sampleNum">1</span>/3)</label>
                    <input type="password" id="enrollPassword" required>
                </div>
                <button type="submit" id="enrollBtn">Submit Sample</button>
            </form>
        </div>
        
        <!-- Manage Tab -->
        <div id="manage" class="tab-content">
            <h3 style="margin-bottom: 15px; color: #333;">Registered Users</h3>
            <div class="user-list" id="userList"></div>
            <button onclick="loadUsers()">Refresh List</button>
        </div>
    </div>
    
    <script>
        let keystrokeTimes = [];
        let lastKeyTime = 0;
        let enrollmentData = {
            username: '',
            password: '',
            samples: [],
            currentSample: 1
        };
        
        // Check session on load
        checkSession();
        
        function checkSession() {
            fetch('/api/session')
                .then(r => r.json())
                .then(data => {
                    if (data.logged_in) {
                        document.getElementById('loggedInSection').style.display = 'block';
                        document.getElementById('currentUser').textContent = data.username;
                    }
                });
        }
        
        function logout() {
            fetch('/api/logout', {method: 'POST'})
                .then(() => {
                    document.getElementById('loggedInSection').style.display = 'none';
                    showMessage('Logged out successfully', 'info');
                });
        }
        
        function switchTab(tabName) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            event.target.classList.add('active');
            document.getElementById(tabName).classList.add('active');
            
            clearMessage();
            
            if (tabName === 'manage') {
                loadUsers();
            } else if (tabName === 'enroll') {
                resetEnrollment();
            }
        }
        
        function captureKeystroke(inputId) {
            const input = document.getElementById(inputId);
            
            input.addEventListener('keydown', (e) => {
                if (e.key.length === 1 || e.key === 'Backspace') {
                    const currentTime = performance.now();
                    if (lastKeyTime > 0) {
                        const interval = (currentTime - lastKeyTime) / 1000;
                        keystrokeTimes.push(interval);
                    }
                    lastKeyTime = currentTime;
                }
            });
            
            input.addEventListener('focus', () => {
                keystrokeTimes = [];
                lastKeyTime = 0;
            });
        }
        
        captureKeystroke('loginPassword');
        captureKeystroke('enrollPassword');
        
        function login(e) {
            e.preventDefault();
            
            const username = document.getElementById('loginUsername').value;
            const password = document.getElementById('loginPassword').value;
            
            fetch('/api/authenticate', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: username,
                    password: password,
                    timings: keystrokeTimes
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showMessage('✅ ' + data.message, 'success');
                    displaySimilarity(data.similarity);
                    checkSession();
                } else {
                    showMessage('❌ ' + data.message, 'error');
                    if (data.similarity > 0) {
                        displaySimilarity(data.similarity);
                    }
                }
                
                document.getElementById('loginPassword').value = '';
                keystrokeTimes = [];
            });
        }
        
        function displaySimilarity(score) {
            const html = `
                <div class="similarity-score">
                    <strong>Keystroke Pattern Similarity</strong>
                    <div class="similarity-bar">
                        <div class="similarity-fill" style="width: ${score}%">${score}%</div>
                    </div>
                </div>
            `;
            document.getElementById('loginSimilarity').innerHTML = html;
        }
        
        function handleEnrollSubmit(e) {
            e.preventDefault();
            
            const username = document.getElementById('enrollUsername').value;
            const password = document.getElementById('enrollPassword').value;
            
            if (enrollmentData.currentSample === 1) {
                enrollmentData.username = username;
                enrollmentData.password = password;
            } else if (password !== enrollmentData.password) {
                showMessage('❌ Password mismatch! Please start over.', 'error');
                resetEnrollment();
                return;
            }
            
            enrollmentData.samples.push([...keystrokeTimes]);
            updateEnrollProgress();
            
            if (enrollmentData.currentSample >= 3) {
                completeEnrollment();
            } else {
                enrollmentData.currentSample++;
                document.getElementById('sampleNum').textContent = enrollmentData.currentSample;
                document.getElementById('enrollPassword').value = '';
                keystrokeTimes = [];
            }
        }
        
        function updateEnrollProgress() {
            let html = '';
            for (let i = 1; i <= 3; i++) {
                let className = 'progress-step';
                let status = '';
                if (i < enrollmentData.currentSample) {
                    className += ' completed';
                    status = '✅ Completed';
                } else if (i === enrollmentData.currentSample) {
                    className += ' active';
                    status = '⏳ In Progress';
                } else {
                    status = '⭕ Pending';
                }
                html += `<div class="${className}">Sample ${i}: ${status}</div>`;
            }
            document.getElementById('enrollProgress').innerHTML = html;
        }
        
        function completeEnrollment() {
            fetch('/api/enroll', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    username: enrollmentData.username,
                    password: enrollmentData.password,
                    timings: enrollmentData.samples
                })
            })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    showMessage('✅ ' + data.message, 'success');
                    resetEnrollment();
                } else {
                    showMessage('❌ ' + data.message, 'error');
                }
            });
        }
        
        function resetEnrollment() {
            enrollmentData = {
                username: '',
                password: '',
                samples: [],
                currentSample: 1
            };
            document.getElementById('enrollUsername').value = '';
            document.getElementById('enrollPassword').value = '';
            document.getElementById('sampleNum').textContent = '1';
            document.getElementById('enrollProgress').innerHTML = '';
            keystrokeTimes = [];
        }
        
        function loadUsers() {
            fetch('/api/users')
                .then(r => r.json())
                .then(data => {
                    const listDiv = document.getElementById('userList');
                    if (data.users.length === 0) {
                        listDiv.innerHTML = '<p style="text-align: center; color: #666;">No users enrolled</p>';
                    } else {
                        listDiv.innerHTML = data.users.map(user => `
                            <div class="user-item">
                                <span><strong>${user}</strong></span>
                                <button class="delete-btn" onclick="deleteUser('${user}')">Delete</button>
                            </div>
                        `).join('');
                    }
                });
        }
        
        function deleteUser(username) {
            if (confirm(`Delete user "${username}"?`)) {
                fetch('/api/delete', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({username: username})
                })
                .then(r => r.json())
                .then(data => {
                    showMessage(data.success ? '✅ User deleted' : '❌ ' + data.message, 
                               data.success ? 'success' : 'error');
                    loadUsers();
                });
            }
        }
        
        function showMessage(text, type) {
            const box = document.getElementById('messageBox');
            box.innerHTML = `<div class="message ${type}">${text}</div>`;
        }
        
        function clearMessage() {
            document.getElementById('messageBox').innerHTML = '';
        }
    </script>
</body>
</html>'''
    
    # Write HTML template
    with open('templates/index.html', 'w') as f:
        f.write(html_content)
    
    print("🚀 Starting Keystroke Dynamics Web Application")
    print("📍 Open your browser and navigate to: http://127.0.0.1:5000")
    print("\n✨ Features:")
    print("   - Real-time keystroke timing capture")
    print("   - Visual similarity scoring")
    print("   - User management interface")
    print("   - Session management\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)

import os
import sqlite3
import uuid
import time
import json
import hashlib
from flask import Flask, request, jsonify, g, make_response
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})  # 允许所有域跨域访问
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_here')
app.config['DATABASE'] = 'user_data.db'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 限制上传文件大小 16MB

# =============== 数据库辅助函数 ===============
def get_db():
    if 'db' not in g:
        g.db = sqlite3.connect(app.config['DATABASE'])
        g.db.row_factory = sqlite3.Row
    return g.db

@app.teardown_appcontext
def close_db(error):
    if hasattr(g, 'db'):
        g.db.close()

def init_db():
    with app.app_context():
        db = get_db()
        cursor = db.cursor()
        
        # 创建用户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                email TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # 创建用户设置表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                last_played TEXT,
                volume INTEGER DEFAULT 80,
                theme TEXT DEFAULT 'default',
                equalizer_settings TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 创建播放列表表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlists (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_smart BOOLEAN DEFAULT 0,
                smart_rules TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 创建播放列表歌曲表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS playlist_songs (
                playlist_id INTEGER,
                song_path TEXT NOT NULL,
                song_name TEXT,
                position INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (playlist_id, song_path),
                FOREIGN KEY(playlist_id) REFERENCES playlists(id)
            )
        ''')
        
        # 创建设备同步令牌表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS device_tokens (
                user_id INTEGER,
                device_id TEXT NOT NULL,
                token TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                PRIMARY KEY (user_id, device_id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 创建音乐室表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS music_rooms (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                owner_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                max_users INTEGER DEFAULT 10,
                current_song TEXT,
                current_position INTEGER DEFAULT 0,
                is_playing BOOLEAN DEFAULT 0,
                FOREIGN KEY(owner_id) REFERENCES users(id)
            )
        ''')
        
        # 创建音乐室成员表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_members (
                room_id INTEGER,
                user_id INTEGER,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_moderator BOOLEAN DEFAULT 0,
                PRIMARY KEY (room_id, user_id),
                FOREIGN KEY(room_id) REFERENCES music_rooms(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        # 创建音乐室消息表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS room_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_id INTEGER,
                user_id INTEGER,
                message TEXT NOT NULL,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(room_id) REFERENCES music_rooms(id),
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
        ''')
        
        db.commit()

# 初始化数据库
init_db()

# =============== 辅助函数 ===============
def generate_token(user_id):
    """生成访问令牌"""
    return str(uuid.uuid4())

def hash_password(password):
    """生成密码哈希"""
    return generate_password_hash(password)

def verify_password(password_hash, password):
    """验证密码"""
    return check_password_hash(password_hash, password)

def token_required(f):
    """令牌验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # 从请求头获取令牌
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1] if " " in request.headers['Authorization'] else request.headers['Authorization']
        
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
            
        db = get_db()
        cursor = db.cursor()
        
        # 这里简化处理，实际应用中应使用JWT等更安全的机制
        # 检查令牌是否有效
        cursor.execute('SELECT user_id FROM device_tokens WHERE token = ? AND expires_at > datetime("now")', (token,))
        token_data = cursor.fetchone()
        
        if not token_data:
            return jsonify({'message': 'Token is invalid or expired'}), 401
        
        user_id = token_data['user_id']
        g.current_user_id = user_id
        
        return f(*args, **kwargs)
    return decorated

# =============== 用户认证API ===============
@app.route('/api/register', methods=['POST'])
def register_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 检查用户名是否已存在
    cursor.execute('SELECT id FROM users WHERE username = ?', (username,))
    if cursor.fetchone():
        return jsonify({'error': 'Username already exists'}), 400
    
    # 创建用户
    password_hash = hash_password(password)
    cursor.execute(
        'INSERT INTO users (username, password_hash, email) VALUES (?, ?, ?)',
        (username, password_hash, email)
    )
    user_id = cursor.lastrowid
    
    # 创建默认设置
    cursor.execute(
        'INSERT INTO user_settings (user_id) VALUES (?)',
        (user_id,)
    )
    
    # 创建默认播放列表
    cursor.execute(
        'INSERT INTO playlists (user_id, name) VALUES (?, ?)',
        (user_id, '默认播放列表')
    )
    
    db.commit()
    
    # 生成令牌
    token = generate_token(user_id)
    cursor.execute(
        'INSERT INTO device_tokens (user_id, device_id, token, expires_at) VALUES (?, ?, ?, datetime("now", "+7 days"))',
        (user_id, 'default', token)
    )
    db.commit()
    
    return jsonify({
        'message': 'User registered successfully',
        'user_id': user_id,
        'token': token
    }), 201

@app.route('/api/login', methods=['POST'])
def login_user():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    device_id = data.get('device_id', 'default')
    
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 获取用户
    cursor.execute('SELECT id, password_hash FROM users WHERE username = ?', (username,))
    user = cursor.fetchone()
    if not user:
        return jsonify({'error': 'Invalid username or password'}), 401
    
    # 验证密码
    if not verify_password(user['password_hash'], password):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    user_id = user['id']
    
    # 更新最后登录时间
    cursor.execute('UPDATE users SET last_login = datetime("now") WHERE id = ?', (user_id,))
    
    # 生成新令牌
    token = generate_token(user_id)
    
    # 保存设备令牌
    cursor.execute(
        'INSERT OR REPLACE INTO device_tokens (user_id, device_id, token, expires_at) VALUES (?, ?, ?, datetime("now", "+7 days"))',
        (user_id, device_id, token)
    )
    
    db.commit()
    
    return jsonify({
        'message': 'Login successful',
        'user_id': user_id,
        'token': token
    })

# =============== 用户数据API ===============
@app.route('/api/user/settings', methods=['GET'])
@token_required
def get_user_settings():
    user_id = g.current_user_id
    db = get_db()
    cursor = db.cursor()
    
    cursor.execute('SELECT * FROM user_settings WHERE user_id = ?', (user_id,))
    settings = cursor.fetchone()
    
    if not settings:
        return jsonify({'error': 'Settings not found'}), 404
    
    # 将设置转换为字典
    settings_dict = dict(settings)
    if settings_dict.get('equalizer_settings'):
        settings_dict['equalizer_settings'] = json.loads(settings_dict['equalizer_settings'])
    
    return jsonify(settings_dict)

@app.route('/api/user/settings', methods=['PUT'])
@token_required
def update_user_settings():
    user_id = g.current_user_id
    data = request.get_json()
    
    db = get_db()
    cursor = db.cursor()
    
    # 准备更新数据
    update_data = {}
    if 'last_played' in data:
        update_data['last_played'] = data['last_played']
    if 'volume' in data:
        update_data['volume'] = data['volume']
    if 'theme' in data:
        update_data['theme'] = data['theme']
    if 'equalizer_settings' in data:
        update_data['equalizer_settings'] = json.dumps(data['equalizer_settings'])
    
    if not update_data:
        return jsonify({'error': 'No data to update'}), 400
    
    # 构建更新语句
    set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(user_id)
    
    cursor.execute(
        f'UPDATE user_settings SET {set_clause} WHERE user_id = ?',
        values
    )
    
    db.commit()
    
    return jsonify({'message': 'Settings updated successfully'})

# =============== 播放列表API ===============
@app.route('/api/playlists', methods=['GET'])
@token_required
def get_playlists():
    user_id = g.current_user_id
    db = get_db()
    cursor = db.cursor()
    
    # 获取所有播放列表
    cursor.execute('SELECT * FROM playlists WHERE user_id = ?', (user_id,))
    playlists = [dict(row) for row in cursor.fetchall()]
    
    # 为每个播放列表获取歌曲
    for playlist in playlists:
        cursor.execute(
            'SELECT song_path, song_name, position FROM playlist_songs '
            'WHERE playlist_id = ? ORDER BY position',
            (playlist['id'],)
        )
        songs = [dict(row) for row in cursor.fetchall()]
        playlist['songs'] = songs
        playlist['song_count'] = len(songs)
        
        if playlist.get('smart_rules'):
            playlist['smart_rules'] = json.loads(playlist['smart_rules'])
    
    return jsonify(playlists)

@app.route('/api/playlists', methods=['POST'])
@token_required
def create_playlist():
    user_id = g.current_user_id
    data = request.get_json()
    name = data.get('name')
    is_smart = data.get('is_smart', False)
    smart_rules = data.get('smart_rules')
    
    if not name:
        return jsonify({'error': 'Playlist name is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 创建播放列表
    cursor.execute(
        'INSERT INTO playlists (user_id, name, is_smart, smart_rules) VALUES (?, ?, ?, ?)',
        (user_id, name, is_smart, json.dumps(smart_rules) if smart_rules else None)
    )
    playlist_id = cursor.lastrowid
    
    # 如果是智能播放列表，应用规则添加歌曲
    if is_smart and smart_rules:
        # 这里需要实现根据规则获取歌曲的逻辑
        # 简化处理：返回空播放列表
        pass
    
    db.commit()
    
    return jsonify({
        'message': 'Playlist created successfully',
        'playlist_id': playlist_id
    }), 201

@app.route('/api/playlists/<int:playlist_id>', methods=['PUT'])
@token_required
def update_playlist(playlist_id):
    user_id = g.current_user_id
    data = request.get_json()
    
    db = get_db()
    cursor = db.cursor()
    
    # 验证用户是否拥有此播放列表
    cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Playlist not found or access denied'}), 404
    
    # 准备更新数据
    update_data = {}
    if 'name' in data:
        update_data['name'] = data['name']
    if 'is_smart' in data:
        update_data['is_smart'] = data['is_smart']
    if 'smart_rules' in data:
        update_data['smart_rules'] = json.dumps(data['smart_rules'])
    
    if not update_data:
        return jsonify({'error': 'No data to update'}), 400
    
    # 构建更新语句
    set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(playlist_id)
    
    cursor.execute(
        f'UPDATE playlists SET {set_clause} WHERE id = ?',
        values
    )
    
    db.commit()
    
    return jsonify({'message': 'Playlist updated successfully'})

@app.route('/api/playlists/<int:playlist_id>', methods=['DELETE'])
@token_required
def delete_playlist(playlist_id):
    user_id = g.current_user_id
    
    db = get_db()
    cursor = db.cursor()
    
    # 验证用户是否拥有此播放列表
    cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Playlist not found or access denied'}), 404
    
    # 删除播放列表歌曲
    cursor.execute('DELETE FROM playlist_songs WHERE playlist_id = ?', (playlist_id,))
    
    # 删除播放列表
    cursor.execute('DELETE FROM playlists WHERE id = ?', (playlist_id,))
    
    db.commit()
    
    return jsonify({'message': 'Playlist deleted successfully'})

@app.route('/api/playlists/<int:playlist_id>/songs', methods=['POST'])
@token_required
def add_song_to_playlist(playlist_id):
    user_id = g.current_user_id
    data = request.get_json()
    song_path = data.get('song_path')
    song_name = data.get('song_name', os.path.basename(song_path))
    
    if not song_path:
        return jsonify({'error': 'Song path is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 验证用户是否拥有此播放列表
    cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Playlist not found or access denied'}), 404
    
    # 获取当前最大位置
    cursor.execute('SELECT MAX(position) as max_position FROM playlist_songs WHERE playlist_id = ?', (playlist_id,))
    max_position = cursor.fetchone()['max_position'] or 0
    new_position = max_position + 1
    
    # 添加歌曲到播放列表
    try:
        cursor.execute(
            'INSERT INTO playlist_songs (playlist_id, song_path, song_name, position) '
            'VALUES (?, ?, ?, ?)',
            (playlist_id, song_path, song_name, new_position)
        )
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Song already in playlist'}), 400
    
    db.commit()
    
    return jsonify({
        'message': 'Song added to playlist',
        'position': new_position
    }), 201

@app.route('/api/playlists/<int:playlist_id>/songs/<path:song_path>', methods=['DELETE'])
@token_required
def remove_song_from_playlist(playlist_id, song_path):
    user_id = g.current_user_id
    
    db = get_db()
    cursor = db.cursor()
    
    # 验证用户是否拥有此播放列表
    cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Playlist not found or access denied'}), 404
    
    # 删除歌曲
    cursor.execute(
        'DELETE FROM playlist_songs WHERE playlist_id = ? AND song_path = ?',
        (playlist_id, song_path)
    )
    
    if cursor.rowcount == 0:
        return jsonify({'error': 'Song not found in playlist'}), 404
    
    db.commit()
    
    return jsonify({'message': 'Song removed from playlist'})

# =============== 音乐室API ===============
@app.route('/api/music-rooms', methods=['GET'])
@token_required
def get_music_rooms():
    user_id = g.current_user_id
    db = get_db()
    cursor = db.cursor()
    
    # 获取用户加入的音乐室
    cursor.execute(
        'SELECT mr.* FROM music_rooms mr '
        'JOIN room_members rm ON mr.id = rm.room_id '
        'WHERE rm.user_id = ?',
        (user_id,)
    )
    rooms = [dict(row) for row in cursor.fetchall()]
    
    # 为每个音乐室添加成员和当前播放信息
    for room in rooms:
        # 获取成员
        cursor.execute(
            'SELECT u.id, u.username FROM room_members rm '
            'JOIN users u ON rm.user_id = u.id '
            'WHERE rm.room_id = ?',
            (room['id'],)
        )
        members = [dict(row) for row in cursor.fetchall()]
        room['members'] = members
        room['member_count'] = len(members)
        
        # 获取最后几条消息
        cursor.execute(
            'SELECT rm.id, u.username, rm.message, rm.sent_at '
            'FROM room_messages rm '
            'JOIN users u ON rm.user_id = u.id '
            'WHERE rm.room_id = ? '
            'ORDER BY rm.sent_at DESC LIMIT 20',
            (room['id'],)
        )
        messages = [dict(row) for row in cursor.fetchall()]
        room['recent_messages'] = messages
    
    return jsonify(rooms)

@app.route('/api/music-rooms', methods=['POST'])
@token_required
def create_music_room():
    user_id = g.current_user_id
    data = request.get_json()
    name = data.get('name')
    max_users = data.get('max_users', 10)
    
    if not name:
        return jsonify({'error': 'Room name is required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 创建音乐室
    cursor.execute(
        'INSERT INTO music_rooms (name, owner_id, max_users) VALUES (?, ?, ?)',
        (name, user_id, max_users)
    )
    room_id = cursor.lastrowid
    
    # 将创建者添加为成员
    cursor.execute(
        'INSERT INTO room_members (room_id, user_id, is_moderator) VALUES (?, ?, 1)',
        (room_id, user_id)
    )
    
    db.commit()
    
    return jsonify({
        'message': 'Music room created successfully',
        'room_id': room_id
    }), 201

@app.route('/api/music-rooms/<int:room_id>/join', methods=['POST'])
@token_required
def join_music_room(room_id):
    user_id = g.current_user_id
    db = get_db()
    cursor = db.cursor()
    
    # 获取音乐室信息
    cursor.execute('SELECT id, max_users FROM music_rooms WHERE id = ?', (room_id,))
    room = cursor.fetchone()
    if not room:
        return jsonify({'error': 'Room not found'}), 404
    
    # 检查是否已满
    cursor.execute('SELECT COUNT(*) FROM room_members WHERE room_id = ?', (room_id,))
    member_count = cursor.fetchone()[0]
    if member_count >= room['max_users']:
        return jsonify({'error': 'Room is full'}), 400
    
    # 检查是否已经是成员
    cursor.execute('SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?', (room_id, user_id))
    if cursor.fetchone():
        return jsonify({'error': 'Already a member of this room'}), 400
    
    # 加入音乐室
    cursor.execute(
        'INSERT INTO room_members (room_id, user_id) VALUES (?, ?)',
        (room_id, user_id)
    )
    
    db.commit()
    
    return jsonify({'message': 'Joined music room successfully'})

@app.route('/api/music-rooms/<int:room_id>/leave', methods=['POST'])
@token_required
def leave_music_room(room_id):
    user_id = g.current_user_id
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否是成员
    cursor.execute('SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?', (room_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Not a member of this room'}), 400
    
    # 离开音乐室
    cursor.execute(
        'DELETE FROM room_members WHERE room_id = ? AND user_id = ?',
        (room_id, user_id)
    )
    
    # 如果房间为空，删除房间
    cursor.execute('SELECT COUNT(*) FROM room_members WHERE room_id = ?', (room_id,))
    if cursor.fetchone()[0] == 0:
        cursor.execute('DELETE FROM music_rooms WHERE id = ?', (room_id,))
    
    db.commit()
    
    return jsonify({'message': 'Left music room successfully'})

@app.route('/api/music-rooms/<int:room_id>/messages', methods=['POST'])
@token_required
def send_room_message(room_id):
    user_id = g.current_user_id
    data = request.get_json()
    message = data.get('message')
    
    if not message or len(message) > 500:
        return jsonify({'error': 'Invalid message'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否是成员
    cursor.execute('SELECT 1 FROM room_members WHERE room_id = ? AND user_id = ?', (room_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Not a member of this room'}), 403
    
    # 发送消息
    cursor.execute(
        'INSERT INTO room_messages (room_id, user_id, message) VALUES (?, ?, ?)',
        (room_id, user_id, message)
    )
    
    db.commit()
    
    return jsonify({'message': 'Message sent successfully'})

@app.route('/api/music-rooms/<int:room_id>/playback', methods=['POST'])
@token_required
def update_room_playback(room_id):
    user_id = g.current_user_id
    data = request.get_json()
    
    db = get_db()
    cursor = db.cursor()
    
    # 检查是否是成员且有权限
    cursor.execute(
        'SELECT is_moderator FROM room_members WHERE room_id = ? AND user_id = ?',
        (room_id, user_id)
    )
    member = cursor.fetchone()
    if not member:
        return jsonify({'error': 'Not a member of this room'}), 403
    
    # 只有房主或管理员才能控制播放
    if not member['is_moderator']:
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    # 准备更新数据
    update_data = {}
    if 'current_song' in data:
        update_data['current_song'] = data['current_song']
    if 'current_position' in data:
        update_data['current_position'] = data['current_position']
    if 'is_playing' in data:
        update_data['is_playing'] = data['is_playing']
    
    if not update_data:
        return jsonify({'error': 'No playback data provided'}), 400
    
    # 构建更新语句
    set_clause = ', '.join([f"{key} = ?" for key in update_data.keys()])
    values = list(update_data.values())
    values.append(room_id)
    
    cursor.execute(
        f'UPDATE music_rooms SET {set_clause} WHERE id = ?',
        values
    )
    
    db.commit()
    
    return jsonify({'message': 'Playback state updated'})

# =============== 数据同步API ===============
@app.route('/api/sync/playlist', methods=['POST'])
@token_required
def sync_playlist():
    user_id = g.current_user_id
    data = request.get_json()
    playlist_id = data.get('playlist_id')
    playlist_data = data.get('playlist')
    
    if not playlist_id or not playlist_data:
        return jsonify({'error': 'Playlist ID and data are required'}), 400
    
    db = get_db()
    cursor = db.cursor()
    
    # 验证用户是否拥有此播放列表
    cursor.execute('SELECT id FROM playlists WHERE id = ? AND user_id = ?', (playlist_id, user_id))
    if not cursor.fetchone():
        return jsonify({'error': 'Playlist not found or access denied'}), 404
    
    # 删除现有歌曲
    cursor.execute('DELETE FROM playlist_songs WHERE playlist_id = ?', (playlist_id,))
    
    # 添加新歌曲
    for i, song in enumerate(playlist_data.get('songs', [])):
        cursor.execute(
            'INSERT INTO playlist_songs (playlist_id, song_path, song_name, position) '
            'VALUES (?, ?, ?, ?)',
            (playlist_id, song.get('path'), song.get('name'), i)
        )
    
    # 更新播放列表元数据
    if playlist_data.get('name'):
        cursor.execute(
            'UPDATE playlists SET name = ? WHERE id = ?',
            (playlist_data['name'], playlist_id)
        )
    
    db.commit()
    
    return jsonify({'message': 'Playlist synchronized successfully'})

# =============== 错误处理 ===============
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found'}), 404

@app.errorhandler(400)
def bad_request(error):
    return jsonify({'error': 'Bad request'}), 400

@app.errorhandler(500)
def internal_error(error):
    return jsonify({'error': 'Internal server error'}), 500

# =============== 服务器启动 ===============
if __name__ == '__main__':
    # 创建数据库（如果不存在）
    if not os.path.exists(app.config['DATABASE']):
        init_db()
    
    # 启动服务器
    app.run(host='0.0.0.0', port=25565, debug=True)
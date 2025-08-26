# music_room_server.py
import asyncio
import json
import time
import uuid
from collections import defaultdict
import websockets

class MusicRoomServer:
    def __init__(self):
        self.rooms = {}
        self.user_rooms = {}
        self.connections = defaultdict(dict)
        
    async def handle_connection(self, websocket):
        """处理客户端连接"""
        user_id = None
        room_id = None
        
        try:
            async for message in websocket:
                data = json.loads(message)
                message_type = data.get("type")
                
                if message_type == "auth":
                    user_id = data.get("user_id", str(uuid.uuid4()))
                    self.connections[user_id] = websocket
                    await self.send_room_list(user_id)
                    
                elif message_type == "create_room":
                    room_name = data.get("name", "未命名房间")
                    room_id = str(uuid.uuid4())
                    self.rooms[room_id] = {
                        "id": room_id,
                        "name": room_name,
                        "owner": user_id,
                        "users": [user_id]
                    }
                    self.user_rooms[user_id] = room_id
                    await self.broadcast_room_list()
                    await self.notify_room_update(room_id, "created", user_id)
                    
                elif message_type == "join_room":
                    room_id = data.get("room_id")
                    if room_id in self.rooms:
                        self.rooms[room_id]["users"].append(user_id)
                        self.user_rooms[user_id] = room_id
                        await self.broadcast_room_list()
                        await self.notify_room_update(room_id, "user_joined", user_id)
                        
                elif message_type == "leave_room":
                    if user_id in self.user_rooms:
                        room_id = self.user_rooms[user_id]
                        if room_id in self.rooms:
                            if user_id in self.rooms[room_id]["users"]:
                                self.rooms[room_id]["users"].remove(user_id)
                            del self.user_rooms[user_id]
                            
                            # 如果房间为空，关闭房间
                            if not self.rooms[room_id]["users"]:
                                del self.rooms[room_id]
                                await self.broadcast_room_list()
                                await self.notify_room_update(room_id, "closed", user_id)
                            else:
                                await self.broadcast_room_list()
                                await self.notify_room_update(room_id, "user_left", user_id)
                    
                elif message_type == "chat":
                    if user_id in self.user_rooms:
                        room_id = self.user_rooms[user_id]
                        await self.broadcast_message(room_id, {
                            "type": "chat",
                            "user_id": user_id,
                            "message": data.get("message", ""),
                            "timestamp": int(time.time())
                        })
                        
                elif message_type == "playback":
                    if user_id in self.user_rooms:
                        room_id = self.user_rooms[user_id]
                        await self.broadcast_message(room_id, {
                            "type": "playback",
                            "user_id": user_id,
                            "command": data.get("command"),
                            "position": data.get("position"),
                            "volume": data.get("volume"),
                            "song_path": data.get("song_path")
                        }, exclude_user=user_id)
                        
                elif message_type == "request_room_list":
                    await self.send_room_list(user_id)
                    
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            # 清理连接
            if user_id and user_id in self.connections:
                del self.connections[user_id]
                
            # 用户离开房间
            if user_id and user_id in self.user_rooms:
                room_id = self.user_rooms[user_id]
                if room_id in self.rooms:
                    if user_id in self.rooms[room_id]["users"]:
                        self.rooms[room_id]["users"].remove(user_id)
                    del self.user_rooms[user_id]
                    
                    # 如果房间为空，关闭房间
                    if not self.rooms[room_id]["users"]:
                        del self.rooms[room_id]
                        await self.broadcast_room_list()
                        await self.notify_room_update(room_id, "closed", user_id)
                    else:
                        await self.broadcast_room_list()
                        await self.notify_room_update(room_id, "user_left", user_id)
    
    async def send_room_list(self, user_id):
        """发送房间列表给指定用户"""
        if user_id in self.connections:
            room_list = list(self.rooms.values())
            await self.connections[user_id].send(json.dumps({
                "type": "room_list",
                "rooms": room_list
            }))
    
    async def broadcast_room_list(self):
        """广播房间列表给所有用户"""
        room_list = list(self.rooms.values())
        message = json.dumps({
            "type": "room_list",
            "rooms": room_list
        })
        
        for user_id, ws in self.connections.items():
            try:
                await ws.send(message)
            except:
                pass
    
    async def notify_room_update(self, room_id, action, user_id):
        """通知房间更新"""
        if room_id not in self.rooms:
            return
            
        message = json.dumps({
            "type": "room_update",
            "room_id": room_id,
            "action": action,
            "user_id": user_id,
            "users": self.rooms[room_id]["users"]
        })
        
        for room_user_id in self.rooms[room_id]["users"]:
            if room_user_id in self.connections:
                try:
                    await self.connections[room_user_id].send(message)
                except:
                    pass
    
    async def broadcast_message(self, room_id, message, exclude_user=None):
        """广播消息给房间内所有用户"""
        if room_id not in self.rooms:
            return
            
        message_json = json.dumps(message)
        
        for user_id in self.rooms[room_id]["users"]:
            if user_id == exclude_user:
                continue
                
            if user_id in self.connections:
                try:
                    await self.connections[user_id].send(message_json)
                except:
                    pass

async def main():
    server = MusicRoomServer()
    async with websockets.serve(server.handle_connection, "127.0.0.1", 5001):
        print("音乐室服务器已启动，监听 ws://127.0.0.1:5001")
        await asyncio.Future()  # 永久运行

if __name__ == "__main__":
    asyncio.run(main())
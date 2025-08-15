import asyncio
import datetime
import hashlib
import io
import json
import logging
import os
import sqlite3
import random
import re
import socket
import subprocess
import sys
import time
import traceback
import urllib.parse
import webbrowser
from pathlib import Path
import aiofiles
import aiohttp
import httpx
import requests
import threading
import numpy as np
import websockets  # 添加这行
import uuid        # 添加这行
from flask import Flask, request, jsonify, send_from_directory
from bs4 import BeautifulSoup
from PyQt5.QtWebSockets import QWebSocket
from bilibili_api import Credential, video
from bilibili_api.video import VideoDownloadURLDataDetecter
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtCore import (
    QByteArray, QObject, QPoint, QSize, Qt, QThread, QTimer, QUrl, pyqtSignal, QEvent
)
from PyQt5.QtGui import (
    QColor, QDesktopServices, QFont, QFontDatabase, QIcon, QImage, 
    QPalette, QPixmap, QCursor
)
from PyQt5.QtMultimedia import QMediaContent, QMediaMetaData, QMediaPlayer
from PyQt5.QtWidgets import (
    QAbstractItemView, QAction, QApplication, QCheckBox, QColorDialog,
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFontDialog, QFormLayout, QFrame,
    QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLayout,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMenu, QMenuBar,
    QMessageBox, QPlainTextEdit, QProgressBar, QProgressDialog, QPushButton,
    QScrollArea, QSlider, QSpinBox, QStatusBar, QTabWidget, QTableWidget,
    QTableWidgetItem, QTextEdit, QTreeWidget, QVBoxLayout, QWidget, QTreeWidget
)
try:
    import librosa
    import librosa.feature
    import librosa.beat
    from sklearn.metrics.pairwise import cosine_similarity
    AUDIO_FEATURES_ENABLED = True
except ImportError:
    AUDIO_FEATURES_ENABLED = False
    logging.warning("librosa or scikit-learn not installed, audio feature extraction disabled")

# =============== 自定义事件类 ===============
class PlayEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self):
        super().__init__(PlayEvent.event_type)

class PauseEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self):
        super().__init__(PauseEvent.event_type)

class StopEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self):
        super().__init__(StopEvent.event_type)

class VolumeEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, volume):
        super().__init__(VolumeEvent.event_type)
        self.volume = volume

class NextEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self):
        super().__init__(NextEvent.event_type)

class PrevEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self):
        super().__init__(PrevEvent.event_type)

class PlayFileEvent(QEvent):
    event_type = QEvent.Type(QEvent.registerEventType())
    def __init__(self, file_path):
        super().__init__(PlayFileEvent.event_type)
        self.file_path = file_path

# =============== 设置管理功能 ===============
def get_settings_path():
    """获取设置文件路径"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    settings_path = os.path.join(base_dir, "settings.json")
    logging.info(f"设置文件路径: {settings_path}")
    return settings_path

def load_default_settings():
    """加载默认设置"""
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))
    
    return {
        "save_paths": {
            "music": os.path.join(base_dir, "songs"),
            "cache": os.path.join(base_dir, "pics"),
            "videos": os.path.join(os.path.expanduser("~"), "Videos")
        },
        "sources": {
            "active_source": "QQ音乐",
            "sources_list": [
                {
                    "name": "QQ音乐",
                    "url": "https://music.txqq.pro/",
                    "params": {"input": "{query}", "filter": "name", "type": "qq", "page": 1},
                    "method": "POST",
                    "api_key": "",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
                        "Accept": "application/json, text/javascript, */*; q=0.01",
                        "X-Requested-With": "XMLHttpRequest"
                    }
                },
                {
                    "name": "网易云音乐",
                    "url": "https://music.163.com",
                    "params": {
                        "s": "{query}",
                        "type": 1,
                        "limit": 20,
                        "offset": 0
                    },
                    "method": "POST",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Referer": "https://music.163.com/",
                        "Origin": "https://music.163.com",
                        "Content-Type": "application/x-www-form-urlencoded"
                    }
                },
                {
                    "name": "酷狗音乐",
                    "url": "https://wwwapi.kugou.com/yy/index.php",
                    "params": {
                        "r": "play/getdata",
                        "hash": "",
                        "mid": "1",
                        "platid": "4",
                        "album_id": "",
                        "_": str(int(time.time() * 1000))
                    },
                    "search_params": {
                        "r": "search/song",
                        "keyword": "{query}",
                        "pagesize": 20,
                        "page": 1
                    },
                    "method": "GET",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                        "Referer": "https://www.kugou.com/",
                        "Origin": "https://www.kugou.com",
                        "Accept": "application/json, text/plain, */*"
                    }
                },
                {
                    "name": "公共音乐API",
                    "url": "https://api.railgun.live/music/search",
                    "params": {
                        "keyword": "{query}",
                        "source": "kugou",
                        "page": 1,
                        "limit": 20
                    },
                    "method": "GET",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                    }
                }
            ]
        },
        "bilibili": {
            "cookie": "",
            "max_duration": 600
        },
        "other": {
            "max_results": 20,
            "auto_play": True,
            "playback_mode": "list",
            "repeat_mode": "none"
        },
        "background_image": "",
        "custom_tools": []
    }

def load_settings():
    """加载设置"""
    settings_path = get_settings_path()
    os.makedirs(os.path.dirname(settings_path), exist_ok=True)
    
    if not os.path.exists(settings_path):
        logger.info("创建默认设置文件")
        default_settings = load_default_settings()
        save_settings(default_settings)
        return default_settings
    
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
            if "bilibili" not in settings:
                settings["bilibili"] = {
                    "cookie": "",
                    "max_duration": 600
                }
            if "save_paths" not in settings:
                settings["save_paths"] = load_default_settings()["save_paths"]
            elif "videos" not in settings["save_paths"]:
                settings["save_paths"]["videos"] = os.path.join(os.path.expanduser("~"), "Videos")
            if "custom_tools" not in settings:
                settings["custom_tools"] = []   
            if "sources" not in settings:
                settings["sources"] = load_default_settings()["sources"]
            elif "sources_list" not in settings["sources"]:
                settings["sources"]["sources_list"] = load_default_settings()["sources"]["sources_list"]
    
            return settings
    except Exception as e:
        logging.error(f"加载设置失败: {str(e)}，使用默认设置")
        return load_default_settings()

def save_settings(settings):
    """保存设置"""
    settings_path = get_settings_path()
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        logger.info(f"设置已保存到: {settings_path}")
        return True
    except Exception as e:
        logging.error(f"保存设置失败: {str(e)}")
        return False

def get_active_source_config():
    """获取当前激活的音源配置"""
    settings = load_settings()
    active_source = settings["sources"]["active_source"]
    for source in settings["sources"]["sources_list"]:
        if source["name"] == active_source:
            return source
    return settings["sources"]["sources_list"][0]

def get_source_names():
    """获取所有音源名称"""
    settings = load_settings()
    return [source["name"] for source in settings["sources"]["sources_list"]]

def ensure_settings_file_exists():
    """确保设置文件存在"""
    settings_path = get_settings_path()
    if not os.path.exists(settings_path):
        logger.warning("settings.json 文件不存在，创建默认设置")
        save_settings(load_default_settings())

# =============== 设置管理功能结束 ===============

# =============== 日志配置 ===============
class UTF8StreamHandler(logging.StreamHandler):
    """确保日志输出使用UTF-8编码"""
    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg.encode('utf-8').decode('utf-8'))
            stream.write(self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("music_app.log", encoding='utf-8'),
        UTF8StreamHandler()
    ]
)
logger = logging.getLogger("MusicApp")

# =============== Bilibili视频搜索插件整合 ===============
class VideoAPI(QObject):
    """视频API类"""
    download_progress = pyqtSignal(int)
    
    def __init__(self, cookie: str, parent=None):
        super().__init__(parent)
        self.BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
        self.BILIBILI_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Referer": "https://www.bilibili.com",
            "Origin": "https://www.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie,
        }

    async def search_video(self, keyword: str, page: int = 1) -> list[dict] | None:
        """搜索视频"""
        params = {"search_type": "video", "keyword": keyword, "page": page}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.BILIBILI_SEARCH_API, 
                    params=params, 
                    headers=self.BILIBILI_HEADER
                )
                response.raise_for_status()
                data = response.json()

                if data["code"] == 0:
                    video_list = data["data"].get("result", [])
                    return video_list
            except Exception as e:
                logging.error(f"Bilibili搜索发生错误: {e}")
                return []

    async def download_video(self, video_id: str, temp_dir: str) -> str | None:
        """下载视频"""
        os.makedirs(temp_dir, exist_ok=True)
        v = video.Video(video_id, credential=Credential(sessdata=""))
        download_url_data = await v.get_download_url(page_index=0)
        detector = VideoDownloadURLDataDetecter(download_url_data)
        streams = detector.detect_best_streams()
        video_url, audio_url = streams[0].url, streams[1].url

        video_file = os.path.join(temp_dir, f"{video_id}-video.m4s")
        audio_file = os.path.join(temp_dir, f"{video_id}-audio.m4s")
        output_file = os.path.join(temp_dir, f"{video_id}-res.mp4")

        try:
            await asyncio.gather(
                self._download_b_file(video_url, video_file),
                self._download_b_file(audio_url, audio_file),
            )
            if not os.path.exists(video_file) or not os.path.exists(audio_file):
                logging.error(f"临时文件下载失败：{video_file} 或 {audio_file} 不存在")
                return None

            await self._merge_file_to_mp4(video_file, audio_file, output_file)
            if not os.path.exists(output_file):
                logging.error(f"合并失败，输出文件不存在：{output_file}")
                return None

            return output_file
        except Exception as e:
            logging.error(f"视频/音频下载失败: {e}")
            return None
        finally:
            for file in [video_file, audio_file]:
                if os.path.exists(file):
                    try:
                        os.remove(file)
                    except Exception as e:
                        logging.warning(f"删除临时文件失败: {e}")

    async def _download_b_file(self, url: str, full_file_name: str):
        """下载文件并显示进度"""
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, headers=self.BILIBILI_HEADER) as resp:
                current_len = 0
                total_len = int(resp.headers.get("content-length", 0))
                last_percent = -1

                async with aiofiles.open(full_file_name, "wb") as f:
                    async for chunk in resp.aiter_bytes():
                        if self.thread() and self.thread().isInterruptionRequested():
                            logging.info("下载被中断")
                            return
                        
                        current_len += len(chunk)
                        await f.write(chunk)

                        percent = int(current_len / total_len * 100)
                        if percent != last_percent:
                            last_percent = percent
                            self.download_progress.emit(percent)
    
    async def _merge_file_to_mp4(self, v_full_file_name: str, a_full_file_name: str, output_file_name: str):
        """合并视频文件和音频文件"""
        command = f'ffmpeg -y -i "{v_full_file_name}" -i "{a_full_file_name}" -c copy "{output_file_name}"'
        process = await asyncio.create_subprocess_shell(
            command, 
            stdout=asyncio.subprocess.PIPE, 
            stderr=asyncio.subprocess.PIPE
        )
        await process.communicate()


class VideoSearchDialog(QDialog):
    """Bilibili视频搜索对话框"""
    def __init__(self, parent=None, cookie=""):
        super().__init__(parent)
        self.setWindowTitle("Bilibili视频搜索")
        self.setGeometry(200, 200, 800, 600)
        
        self.video_api = VideoAPI(cookie, parent=self)
        self.video_api.download_progress.connect(self.update_progress)
        self.temp_dir = os.path.abspath(os.path.join("data", "bilibili_video_cache"))
        os.makedirs(self.temp_dir, exist_ok=True)
        self.selected_video = None
        self.search_thread = None
        self.download_thread = None
        self.threads = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入视频关键词...")
        self.search_input.setStyleSheet("padding: 8px; font-size: 14px;")
        self.search_input.returnPressed.connect(self.search_videos)
        
        search_button = QPushButton("搜索")
        search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_input, 5)
        search_layout.addWidget(search_button, 1)
        layout.addLayout(search_layout)
        
        # 结果区域
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px;")
        self.results_list.setIconSize(QSize(100, 100))
        self.results_list.itemDoubleClicked.connect(self.video_selected)
        layout.addWidget(self.results_list, 4)
        
        # 信息区域
        self.info_label = QLabel("选择视频查看详情")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd;")
        layout.addWidget(self.info_label, 1)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("下载视频")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_video)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)
        
    def remove_search_thread(self):
        if self.search_thread in self.threads:
            self.threads.remove(self.search_thread)
        self.search_thread = None
        
    def remove_download_thread(self):
        if self.download_thread in self.threads:
            self.threads.remove(self.download_thread)
        self.download_thread = None
        
    def closeEvent(self, event):
        try:
            self.video_api.download_progress.disconnect(self.update_progress)
        except:
            pass
        self.terminate_all_threads()
        event.accept()
        
    def terminate_all_threads(self):
        threads = []
        if self.search_thread:
            threads.append(self.search_thread)
        if self.download_thread:
            threads.append(self.download_thread)
        
        for thread in threads:
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
        
    def search_videos(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
            
        self.results_list.clear()
        self.info_label.setText("搜索中...")
        self.download_button.setEnabled(False)
        self.search_thread = VideoSearchThread(keyword, self.video_api)
        self.threads.append(self.search_thread)
        self.search_thread.results_ready.connect(self.display_results)
        self.search_thread.error_occurred.connect(self.display_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.search_thread.start()
        
    def display_results(self, videos):
        if not videos:
            self.info_label.setText("未找到相关视频")
            return
            
        self.info_label.setText(f"找到 {len(videos)} 个视频")
        for video in videos:
            title = BeautifulSoup(video["title"], "html.parser").get_text()
            author = video.get("author", "未知作者")
            duration = video.get("duration", "未知时长")
            item_text = f"{title} - {author} ({duration})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, video)
            self.results_list.addItem(item)
            
    def display_error(self, error):
        self.info_label.setText(f"搜索失败: {error}")
        
    def video_selected(self, item):
        video_data = item.data(Qt.UserRole)
        self.selected_video = video_data
        title = BeautifulSoup(video_data["title"], "html.parser").get_text()
        author = video_data.get("author", "未知作者")
        duration = video_data.get("duration", "未知时长")
        play_count = video_data.get("play", "未知播放量")
        
        info = f"<b>标题:</b> {title}<br>"
        info += f"<b>作者:</b> {author}<br>"
        info += f"<b>时长:</b> {duration}<br>"
        info += f"<b>播放量:</b> {play_count}"
        self.info_label.setText(info)
        self.download_button.setEnabled(True)
        
    def download_video(self):
        if not self.selected_video:
            return
        video_id = self.selected_video.get("bvid", "")
        if not video_id:
            QMessageBox.warning(self, "错误", "无效的视频ID")
            return
            
        title = BeautifulSoup(self.selected_video["title"], "html.parser").get_text()
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
        settings = load_settings()
        video_dir = settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos"))
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存视频", 
            os.path.join(video_dir, f"{safe_title}.mp4"), 
            "MP4文件 (*.mp4)"
        )
        if not file_path:
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        self.download_thread = VideoDownloadThread(video_id, file_path, self.temp_dir, self.video_api)
        self.threads.append(self.download_thread)
        self.download_thread.download_complete.connect(self.download_finished)
        self.download_thread.error_occurred.connect(self.download_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.download_thread.start()
        
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
        
    def download_finished(self, file_path):
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", f"视频已下载到:\n{file_path}")
        self.accept()
        
    def download_error(self, error):
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
        QMessageBox.critical(self, "错误", f"下载失败: {error}")


class VideoSearchThread(QThread):
    """视频搜索线程"""
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, keyword, video_api):
        super().__init__()
        self.keyword = keyword
        self.video_api = video_api
        
    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if self.isInterruptionRequested():
                return
            results = loop.run_until_complete(self.video_api.search_video(self.keyword))
            if self.isInterruptionRequested():
                return
            self.results_ready.emit(results or [])
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()


class VideoDownloadThread(QThread):
    """视频下载线程"""
    download_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, video_id, file_path, temp_dir, video_api):
        super().__init__()
        self.video_id = video_id
        self.file_path = file_path
        self.temp_dir = temp_dir
        self.video_api = video_api
        
    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if self.isInterruptionRequested():
                return
            temp_file = loop.run_until_complete(
                self.video_api.download_video(self.video_id, self.temp_dir)
            )
            if self.isInterruptionRequested():
                return
            if temp_file:
                os.replace(temp_file, self.file_path)
                self.download_complete.emit(self.file_path)
            else:
                self.error_occurred.emit("下载失败，未获取到文件")
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()

# =============== Bilibili音频下载插件整合 ===============
class AudioAPI(QObject):
    """B站音频API类"""
    download_progress = pyqtSignal(int)
    
    def __init__(self, cookie: str, parent=None):
        super().__init__(parent)
        self.BILIBILI_SEARCH_API = "https://api.bilibili.com/x/web-interface/search/type"
        self.BILIBILI_HEADER = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.127 Safari/537.36",
            "Referer": "https://www.bilibili.com",
            "Origin": "https://www.bilibili.com",
            "Accept": "application/json, text/plain, */*",
            "Cookie": cookie,
        }
        self.audio_info_cache = {}

    async def search_video(self, keyword: str, page: int = 1) -> list[dict] | None:
        """搜索视频"""
        params = {"search_type": "video", "keyword": keyword, "page": page}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    self.BILIBILI_SEARCH_API, 
                    params=params, 
                    headers=self.BILIBILI_HEADER
                )
                response.raise_for_status()
                data = response.json()

                if data["code"] == 0:
                    video_list = data["data"].get("result", [])
                    return video_list
            except Exception as e:
                logging.error(f"Bilibili搜索发生错误: {e}")
                return []

    async def get_audio_info(self, bvid: str) -> dict | None:
        """获取音频信息（包含真实音频URL）"""
        if bvid in self.audio_info_cache:
            return self.audio_info_cache[bvid]
        try:
            video_info_url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
            async with httpx.AsyncClient() as client:
                response = await client.get(video_info_url, headers=self.BILIBILI_HEADER)
                data = response.json()
                if data["code"] != 0:
                    return None
                cid = data["data"]["cid"]
                title = data["data"]["title"]
                author = data["data"]["owner"]["name"]
                duration = data["data"]["duration"]
                cover_url = data["data"]["pic"]
                
                audio_url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=0&fnval=16"
                response = await client.get(audio_url, headers=self.BILIBILI_HEADER)
                data = response.json()
                if data["code"] != 0:
                    return None
                    
                audio_url = data["data"]["dash"]["audio"][0]["baseUrl"]
                audio_info = {
                    "title": title,
                    "author": author,
                    "duration": duration,
                    "cover_url": cover_url,
                    "audio_url": audio_url
                }
                self.audio_info_cache[bvid] = audio_info
                return audio_info
        except Exception as e:
            logging.error(f"获取音频信息失败: {e}")
            return None

    async def download_audio(self, bvid: str, file_path: str):
        """下载音频文件"""
        try:
            audio_info = await self.get_audio_info(bvid)
            if not audio_info:
                return False
            audio_url = audio_info["audio_url"]
            
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", audio_url, headers=self.BILIBILI_HEADER) as response:
                    if response.status_code != 200:
                        return False
                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    
                    async with aiofiles.open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            if self.thread() and self.thread().isInterruptionRequested():
                                logging.info("下载被中断")
                                return False
                            await f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                progress = int(100 * downloaded / total_size)
                                self.download_progress.emit(progress)
            return True
        except Exception as e:
            logging.error(f"音频下载失败: {e}")
            return False


class AudioSearchDialog(QDialog):
    """Bilibili音频搜索对话框"""
    def __init__(self, parent=None, cookie=""):
        super().__init__(parent)
        self.setWindowTitle("Bilibili音频搜索")
        self.setGeometry(200, 200, 800, 600)
        
        self.audio_api = AudioAPI(cookie, parent=self)
        self.audio_api.download_progress.connect(self.update_progress)
        self.temp_dir = os.path.abspath(os.path.join("data", "bilibili_audio_cache"))
        os.makedirs(self.temp_dir, exist_ok=True)
        self.selected_video = None
        self.search_thread = None
        self.download_thread = None
        self.threads = []
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入视频关键词...")
        self.search_input.setStyleSheet("padding: 8px; font-size: 14px;")
        self.search_input.returnPressed.connect(self.search_videos)
        
        search_button = QPushButton("搜索")
        search_button.clicked.connect(self.search_videos)
        search_layout.addWidget(self.search_input, 5)
        search_layout.addWidget(search_button, 1)
        layout.addLayout(search_layout)
        
        # 结果区域
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px;")
        self.results_list.setIconSize(QSize(100, 100))
        self.results_list.itemDoubleClicked.connect(self.video_selected)
        layout.addWidget(self.results_list, 4)
        
        # 信息区域
        self.info_label = QLabel("选择视频查看详情")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd;")
        layout.addWidget(self.info_label, 1)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("下载音频")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_audio)
        
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.cancel_button)
        layout.addLayout(button_layout)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)
        self.setLayout(layout)

    def remove_search_thread(self):
        if self.search_thread in self.threads:
            self.threads.remove(self.search_thread)
        self.search_thread = None
        
    def remove_download_thread(self):
        if self.download_thread in self.threads:
            self.threads.remove(self.download_thread)
        self.download_thread = None

    def closeEvent(self, event):
        try:
            self.audio_api.download_progress.disconnect(self.update_progress)
        except:
            pass
        self.terminate_all_threads()
        event.accept()
        
    def terminate_all_threads(self):
        threads = []
        if self.search_thread:
            threads.append(self.search_thread)
        if self.download_thread:
            threads.append(self.download_thread)
        
        for thread in threads:
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
        
    def search_videos(self):
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
            
        self.results_list.clear()
        self.info_label.setText("搜索中...")
        self.download_button.setEnabled(False)
        self.search_thread = AudioSearchThread(keyword, self.audio_api)
        self.threads.append(self.search_thread)
        self.search_thread.results_ready.connect(self.display_results)
        self.search_thread.error_occurred.connect(self.display_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.search_thread.start()
        
    def display_results(self, videos):
        if not videos:
            self.info_label.setText("未找到相关视频")
            return
        self.info_label.setText(f"找到 {len(videos)} 个视频")
        for video in videos:
            title = BeautifulSoup(video["title"], "html.parser").get_text()
            author = video.get("author", "未知作者")
            duration = video.get("duration", "未知时长")
            item_text = f"{title} - {author} ({duration})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, video)
            self.results_list.addItem(item)
            
    def display_error(self, error):
        self.info_label.setText(f"搜索失败: {error}")
        
    def video_selected(self, item):
        video_data = item.data(Qt.UserRole)
        self.selected_video = video_data
        title = BeautifulSoup(video_data["title"], "html.parser").get_text()
        author = video_data.get("author", "未知作者")
        duration = video_data.get("duration", "未知时长")
        play_count = video_data.get("play", "未知播放量")
        
        info = f"<b>标题:</b> {title}<br>"
        info += f"<b>作者:</b> {author}<br>"
        info += f"<b>时长:</b> {duration}<br>"
        info += f"<b>播放量:</b> {play_count}"
        self.info_label.setText(info)
        self.download_button.setEnabled(True)
        
    def download_audio(self):
        if not self.selected_video:
            return
        bvid = self.selected_video.get("bvid", "")
        if not bvid:
            QMessageBox.warning(self, "错误", "无效的视频ID")
            return
            
        title = BeautifulSoup(self.selected_video["title"], "html.parser").get_text()
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]
        settings = load_settings()
        audio_dir = settings["save_paths"].get("music", os.path.join(os.path.expanduser("~"), "Music"))
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存音频", 
            os.path.join(audio_dir, f"{safe_title}.mp3"), 
            "MP3文件 (*.mp3)"
        )
        if not file_path:
            return
            
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        self.download_thread = AudioDownloadThread(bvid, file_path, self.audio_api)
        self.threads.append(self.download_thread)
        self.download_thread.download_complete.connect(self.download_finished)
        self.download_thread.error_occurred.connect(self.download_error)
        self.download_thread.finished.connect(self.remove_download_thread)
        self.download_thread.start()
        
    def update_progress(self, progress):
        self.progress_bar.setValue(progress)
        
    def download_finished(self, file_path):
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", f"音频已下载到:\n{file_path}")
        self.accept()
        
    def download_error(self, error):
        self.progress_bar.setVisible(False)
        self.download_button.setEnabled(True)
        QMessageBox.critical(self, "错误", f"下载失败: {error}")


class AudioSearchThread(QThread):
    """音频搜索线程"""
    results_ready = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, keyword, audio_api):
        super().__init__()
        self.keyword = keyword
        self.audio_api = audio_api
        
    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if self.isInterruptionRequested():
                return
            results = loop.run_until_complete(self.audio_api.search_video(self.keyword))
            if self.isInterruptionRequested():
                return
            self.results_ready.emit(results or [])
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()


class AudioDownloadThread(QThread):
    """音频下载线程"""
    download_complete = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, bvid, file_path, audio_api):
        super().__init__()
        self.bvid = bvid
        self.file_path = file_path
        self.audio_api = audio_api
        
    def run(self):
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if self.isInterruptionRequested():
                return
            success = loop.run_until_complete(
                self.audio_api.download_audio(self.bvid, self.file_path)
            )
            if self.isInterruptionRequested():
                return
            if success:
                self.download_complete.emit(self.file_path)
            else:
                self.error_occurred.emit("音频下载失败")
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()

# =============== 播放列表管理 ===============
class PlaylistManager:
    def __init__(self):
        self.playlists = {}
        self.current_playlist = None
        self.playlist_file = "playlists.json"
        self.load_playlists()
        
    def load_playlists(self):
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    self.playlists = json.load(f)
                    logger.info(f"加载播放列表: {self.playlist_file}")
            except Exception as e:
                logger.error(f"加载播放列表失败: {str(e)}")
                self.playlists = {}
        else:
            self.playlists = {"default": []}
            self.save_playlists()
            logger.info(f"创建新的播放列表文件: {self.playlist_file}")
    
    def save_playlists(self):
        try:
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump(self.playlists, f, ensure_ascii=False, indent=4)
            logger.info(f"播放列表已保存到: {self.playlist_file}")
            return True
        except Exception as e:
            logger.error(f"保存播放列表失败: {str(e)}")
            return False
        
    def create_playlist(self, name):
        if name not in self.playlists:
            self.playlists[name] = []
            self.save_playlists()
            return True
        return False
        
    def add_to_playlist(self, playlist_name, song_path):
        if playlist_name in self.playlists:
            if song_path not in self.playlists[playlist_name]:
                self.playlists[playlist_name].append(song_path)
                self.save_playlists()
                return True
        return False
        
    def remove_from_playlist(self, playlist_name, song_path):
        if playlist_name in self.playlists and song_path in self.playlists[playlist_name]:
            self.playlists[playlist_name].remove(song_path)
            self.save_playlists()
            return True
        return False
        
    def play_playlist(self, playlist_name):
        if playlist_name in self.playlists:
            self.playlist = self.playlists[playlist_name]
            self.current_play_index = -1
            if self.settings["other"].get("playback_mode", "list") == "random":
                self.play_song_by_index(random.randint(0, len(self.playlist) - 1))
            else:
                self.play_song_by_index(0)


class PlaylistDialog(QDialog):
    def __init__(self, playlist_manager, parent=None):
        super().__init__(parent)
        self.playlist_manager = playlist_manager
        self.setWindowTitle("播放列表管理")
        self.setGeometry(300, 300, 600, 400)
        layout = QVBoxLayout()
        
        # 播放列表选择
        playlist_layout = QHBoxLayout()
        playlist_layout.addWidget(QLabel("选择播放列表:"))
        self.playlist_combo = QComboBox()
        self.playlist_combo.addItems(self.playlist_manager.playlists.keys())
        self.playlist_combo.currentTextChanged.connect(self.update_song_list)
        playlist_layout.addWidget(self.playlist_combo)
        
        # 创建新播放列表
        new_playlist_layout = QHBoxLayout()
        new_playlist_layout.addWidget(QLabel("新建播放列表:"))
        self.new_playlist_input = QLineEdit()
        self.new_playlist_button = QPushButton("创建")
        self.new_playlist_button.clicked.connect(self.create_playlist)
        new_playlist_layout.addWidget(self.new_playlist_input)
        new_playlist_layout.addWidget(self.new_playlist_button)
        
        layout.addLayout(playlist_layout)
        layout.addLayout(new_playlist_layout)
        
        # 歌曲列表
        self.song_list = QListWidget()
        layout.addWidget(QLabel("播放列表歌曲:"))
        layout.addWidget(self.song_list)
        
        # 按钮区域
        button_layout = QHBoxLayout()
        self.add_button = QPushButton("添加歌曲")
        self.add_button.clicked.connect(self.add_song)
        self.remove_button = QPushButton("移除歌曲")
        self.remove_button.clicked.connect(self.remove_song)
        self.play_button = QPushButton("播放列表")
        self.play_button.clicked.connect(self.play_playlist)
        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.play_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
        if self.playlist_combo.count() > 0:
            self.update_song_list(self.playlist_combo.currentText())

    def update_song_list(self, playlist_name):
        self.song_list.clear()
        if playlist_name in self.playlist_manager.playlists:
            for song_path in self.playlist_manager.playlists[playlist_name]:
                song_name = os.path.basename(song_path)
                self.song_list.addItem(song_name)
                
    def play_playlist(self):
        playlist_name = self.playlist_combo.currentText()
        if playlist_name:
            parent = self.parent()
            if parent and hasattr(parent, 'play_playlist'):
                parent.play_playlist(playlist_name)
                self.accept()
    
    def create_playlist(self):
        name = self.new_playlist_input.text().strip()
        if name:
            if self.playlist_manager.create_playlist(name):
                self.playlist_combo.addItem(name)
                self.playlist_combo.setCurrentText(name)
                self.new_playlist_input.clear()
                self.update_song_list(name)
            else:
                QMessageBox.warning(self, "错误", "播放列表已存在")
                
    def add_song(self):
        playlist_name = self.playlist_combo.currentText()
        if playlist_name:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择歌曲", "", "音频文件 (*.mp3 *.wav *.flac *.m4a)"
            )
            if file_path:
                if self.playlist_manager.add_to_playlist(playlist_name, file_path):
                    self.update_song_list(playlist_name)
                    
    def remove_song(self):
        playlist_name = self.playlist_combo.currentText()
        selected_item = self.song_list.currentItem()
        if playlist_name and selected_item:
            song_name = selected_item.text()
            song_path = next(
                (path for path in self.playlist_manager.playlists[playlist_name] 
                 if os.path.basename(path) == song_name),
                None
            )
            if song_path:
                if self.playlist_manager.remove_from_playlist(playlist_name, song_path):
                    self.update_song_list(playlist_name)

# =============== 歌词同步 ===============
class LyricsSync(QObject):
    def __init__(self, media_player, external_lyrics):
        super().__init__()
        self.media_player = media_player
        self.external_lyrics = external_lyrics
        self.lyrics_data = []  # 存储(开始时间, 结束时间, 文本)
        self.current_line_index = -1
        self.enabled = True
        self.word_positions = []  # 存储每个字的开始和结束时间
        self.karaoke_progress = 0  # 卡拉OK效果的当前进度
        self.normal_color = QColor("#FFFFFF")  # 白色
        self.highlight_color = QColor("#000000")  # 黑色
        self.next_line_color = QColor("#AAAAAA")  # 灰色
        self.translation_data = []  # (开始时间, 结束时间, 翻译文本)
        self.show_translation = True  # 是否显示翻译
        
    def parse_lyrics(self, lyrics_text):
        """解析歌词文本为结构化的歌词数据"""
        if not lyrics_text:
            return []
            
        lines = lyrics_text.splitlines()
        lyrics_data = []
        pattern = re.compile(r'\[(\d+):(\d+\.\d+)\](.*)')
        
        # 收集所有时间点
        time_points = []
        for line in lines:
            match = pattern.match(line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                time_ms = int((minutes * 60 + seconds) * 1000)
                text = match.group(3).strip()
                time_points.append((time_ms, text))
        
        # 按时间排序
        time_points.sort(key=lambda x: x[0])
        
        # 为每行计算结束时间（下一行的开始时间）
        for i, (start_time, text) in enumerate(time_points):
            if i < len(time_points) - 1:
                end_time = time_points[i+1][0]
            else:
                # 最后一行：如果没有下一行，使用歌曲剩余时间或默认10秒
                end_time = start_time + 10000  # 默认10秒
            lyrics_data.append((start_time, end_time, text))
        
        return lyrics_data
        
    def load_lyrics(self, lyrics_text, translation_text=""):
        """加载歌词文本并解析"""
        self.lyrics_data = self.parse_lyrics(lyrics_text)
        # 解析翻译歌词
        if translation_text:
            self.translation_data = self.parse_lyrics(translation_text)
        else:
            self.translation_data = []
        self.current_line_index = -1
        self.word_positions = []
        
        if not lyrics_text:
            return
            
        lines = lyrics_text.splitlines()
        pattern = re.compile(r'\[(\d+):(\d+\.\d+)\](.*)')
        
        # 第一遍：收集所有时间戳
        time_points = []
        for line in lines:
            match = pattern.match(line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                time_ms = int((minutes * 60 + seconds) * 1000)
                text = match.group(3).strip()
                time_points.append((time_ms, text))
        
        # 按时间排序
        time_points.sort(key=lambda x: x[0])
        
        # 为每行计算结束时间（下一行的开始时间）
        for i in range(len(time_points)):
            start_time, text = time_points[i]
            if i < len(time_points) - 1:
                end_time = time_points[i+1][0]
            else:
                # 最后一行：如果没有下一行，使用歌曲剩余时间或默认10秒
                end_time = start_time + 10000  # 默认10秒
            self.lyrics_data.append((start_time, end_time, text))
    
    def update_position(self, position):
        """根据播放位置更新歌词显示（添加渐变色效果）"""
        if not self.enabled or not self.lyrics_data:
            return
            
        # 使用二分查找提高查找效率
        low, high = 0, len(self.lyrics_data) - 1
        current_line_idx = -1
        
        while low <= high:
            mid = (low + high) // 2
            start_time, end_time, text = self.lyrics_data[mid]
            
            if start_time <= position < end_time:
                current_line_idx = mid
                break
            elif position < start_time:
                high = mid - 1
            else:
                low = mid + 1
        
        # 如果没有找到匹配行
        if current_line_idx == -1:
            self.external_lyrics.update_lyrics("", "", 0)  # 传递三个参数
            self.current_line_index = -1
            return
            
        # 如果是新行，重置卡拉OK效果
        if current_line_idx != self.current_line_index:
            self.current_line_index = current_line_idx
            self.calculate_word_positions(
                self.lyrics_data[current_line_idx][2], 
                self.lyrics_data[current_line_idx][0]
            )
        
        # 更新当前行内的卡拉OK效果
        self.update_karaoke_effect(position)

         # 获取翻译行
        translation_line = ""
        if self.show_translation and self.translation_data and current_line_idx < len(self.translation_data):
            translation_line = self.get_styled_text(
                self.translation_data[current_line_idx][2],  # 使用 current_line_idx
                position
            )
        
        # 准备下一行歌词
        next_text = ""
        if current_line_idx + 1 < len(self.lyrics_data):
            next_text = self.lyrics_data[current_line_idx + 1][2]
            
        # 获取当前行的卡拉OK效果文本
        current_text = self.get_styled_text(
            self.lyrics_data[current_line_idx][2], 
            position
        )
        
        # 更新歌词窗口
        self.external_lyrics.update_lyrics(current_text, next_text, translation_line)
        # 在更新歌词后，确保当前行在视图中可见
        if hasattr(self.external_lyrics, 'scroll_area') and self.external_lyrics.scroll_area:
            # 计算当前行在滚动区域中的位置
            label_pos = self.external_lyrics.current_line_label.pos()
            scroll_pos = self.external_lyrics.scroll_area.verticalScrollBar().value()
            label_height = self.external_lyrics.current_line_label.height()
            
            # 如果当前行不在视图中心，则滚动到中心
            if label_pos.y() < scroll_pos or label_pos.y() + label_height > scroll_pos + self.external_lyrics.scroll_area.height():
                target_pos = max(0, label_pos.y() - self.external_lyrics.scroll_area.height() // 2)
                self.external_lyrics.scroll_area.verticalScrollBar().setValue(target_pos)

    def calculate_word_positions(self, text, position):
        """计算歌词中每个字的位置和持续时间（用于渐变色效果）"""
        self.word_positions = []
        if not text:
            return
        
        # 假设每个字平均分配时间
        start_time = self.lyrics_data[self.current_line_index][0]
        end_time = self.lyrics_data[self.current_line_index][1]
        
        total_chars = len(text)
        duration_per_char = (end_time - start_time) / max(1, total_chars)
        
        for i in range(total_chars):
            char_start = start_time + i * duration_per_char
            char_end = char_start + duration_per_char
            self.word_positions.append((char_start, char_end))
    
    def update_karaoke_effect(self, position):
        """更新卡拉OK效果（渐变着色）"""
        if not self.word_positions:
            return
        
        # 找出当前播放到的字符位置
        current_char_idx = 0
        for i, (char_start, char_end) in enumerate(self.word_positions):
            if position >= char_start:
                current_char_idx = i
            else:
                break
        
        # 保存当前字符索引
        self.karaoke_progress = current_char_idx
    
    def get_styled_text(self, text, position):
        """获取带样式的歌词文本（卡拉OK效果）"""
        if not self.word_positions or len(self.word_positions) != len(text):
            return text
        
        # 找出当前播放到的字符位置
        current_char_idx = 0
        for i, (char_start, char_end) in enumerate(self.word_positions):
            if position >= char_start:
                current_char_idx = i
            else:
                break
        
        # 创建带样式的HTML
        styled_text = ""
        for i, char in enumerate(text):
            if i < current_char_idx:
                # 已播放部分 - 高亮颜色
                styled_text += f'<span style="color: #000000;">{char}</span>'
            elif i == current_char_idx:
                # 当前播放字 - 添加过渡效果
                # 计算当前字内的进度 (0-1)
                char_start, char_end = self.word_positions[i]
                if char_end > char_start:
                    progress = (position - char_start) / (char_end - char_start)
                    progress = max(0, min(1, progress))  # 限制在0-1范围
                    
                    # 创建渐变效果 (从高亮色到普通色)
                    r1, g1, b1 = 255, 87, 34  # 橙色 (FF5722)
                    r2, g2, b2 = 255, 255, 255  # 白色
                    
                    r = int(r1 + (r2 - r1) * progress)
                    g = int(g1 + (g2 - g1) * progress)
                    b = int(b1 + (b2 - b1) * progress)
                    color = f"rgb({r},{g},{b})"
                    
                    styled_text += f'<span style="color: {color};">{char}</span>'
                else:
                    styled_text += f'<span style="color: #FF5722;">{char}</span>'
            else:
                # 未播放部分 - 普通颜色
                styled_text += f'<span style="color: #FFFFFF;">{char}</span>'
        
        return styled_text

# =============== 睡眠定时器 ===============
class SleepTimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("睡眠定时器")
        self.setGeometry(300, 300, 300, 150)
        layout = QVBoxLayout()
        
        # 时间选择
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("定时关闭时间:"))
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 120)
        self.minutes_spin.setValue(30)
        time_layout.addWidget(self.minutes_spin)
        time_layout.addWidget(QLabel("分钟"))
        
        # 操作按钮
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("启动")
        self.start_button.clicked.connect(self.start_timer)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_timer)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
        
        # 状态显示
        self.status_label = QLabel("未启动")
        layout.addLayout(time_layout)
        layout.addLayout(button_layout)
        layout.addWidget(self.status_label)
        self.setLayout(layout)
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_finished)
        self.remaining_time = 0
        
    def start_timer(self):
        minutes = self.minutes_spin.value()
        self.remaining_time = minutes * 60
        self.timer.start(1000)
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.update_status()
        
    def cancel_timer(self):
        self.timer.stop()
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("已取消")
        
    def timer_finished(self):
        self.remaining_time -= 1
        if self.remaining_time <= 0:
            self.timer.stop()
            if self.parent().media_player.state() == QMediaPlayer.PlayingState:
                self.parent().media_player.stop()
            self.status_label.setText("已停止播放")
            self.start_button.setEnabled(True)
            self.cancel_button.setEnabled(False)
        else:
            self.update_status()
            
    def update_status(self):
        minutes = self.remaining_time // 60
        seconds = self.remaining_time % 60
        self.status_label.setText(f"将在 {minutes:02d}:{seconds:02d} 后停止播放")

# =============== 均衡器设置 ===============
class EqualizerDialog(QDialog):
    def __init__(self, media_player, parent=None):
        super().__init__(parent)
        self.setWindowTitle("均衡器设置")
        self.setGeometry(300, 300, 400, 400)
        self.media_player = media_player
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 预设选择
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["默认", "流行", "摇滚", "古典", "爵士", "电子"])
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo)
        layout.addLayout(preset_layout)
        
        # 频段滑块
        self.sliders = {}
        frequencies = ["60Hz", "230Hz", "910Hz", "3.6kHz", "14kHz"]
        
        for freq in frequencies:
            slider_layout = QHBoxLayout()
            slider_layout.addWidget(QLabel(freq))
            slider = QSlider(Qt.Horizontal)
            slider.setRange(-12, 12)
            slider.setValue(0)
            slider.valueChanged.connect(self.update_equalizer)
            value_label = QLabel("0 dB")
            slider.valueChanged.connect(lambda v, lbl=value_label: lbl.setText(f"{v} dB"))
            slider_layout.addWidget(slider)
            slider_layout.addWidget(value_label)
            layout.addLayout(slider_layout)
            self.sliders[freq] = slider
        
        # 保存/加载预设按钮
        button_layout = QHBoxLayout()
        save_button = QPushButton("保存预设")
        save_button.clicked.connect(self.save_preset)
        load_button = QPushButton("加载预设")
        load_button.clicked.connect(self.load_preset)
        button_layout.addWidget(save_button)
        button_layout.addWidget(load_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def apply_preset(self, preset_name):
        if preset_name == "流行":
            self.sliders["60Hz"].setValue(4)
            self.sliders["230Hz"].setValue(2)
            self.sliders["910Hz"].setValue(0)
            self.sliders["3.6kHz"].setValue(3)
            self.sliders["14kHz"].setValue(4)
        elif preset_name == "摇滚":
            self.sliders["60Hz"].setValue(6)
            self.sliders["230Hz"].setValue(4)
            self.sliders["910Hz"].setValue(2)
            self.sliders["3.6kHz"].setValue(4)
            self.sliders["14kHz"].setValue(3)
        elif preset_name == "古典":
            self.sliders["60Hz"].setValue(2)
            self.sliders["230Hz"].setValue(1)
            self.sliders["910Hz"].setValue(0)
            self.sliders["3.6kHz"].setValue(1)
            self.sliders["14kHz"].setValue(2)
        elif preset_name == "爵士":
            self.sliders["60Hz"].setValue(3)
            self.sliders["230Hz"].setValue(2)
            self.sliders["910Hz"].setValue(1)
            self.sliders["3.6kHz"].setValue(2)
            self.sliders["14kHz"].setValue(3)
        elif preset_name == "电子":
            self.sliders["60Hz"].setValue(5)
            self.sliders["230Hz"].setValue(3)
            self.sliders["910Hz"].setValue(0)
            self.sliders["3.6kHz"].setValue(4)
            self.sliders["14kHz"].setValue(5)
        else:
            for slider in self.sliders.values():
                slider.setValue(0)
        self.update_equalizer()
        
    def update_equalizer(self):
        values = {freq: slider.value() for freq, slider in self.sliders.items()}
        logger.info(f"均衡器设置更新: {values}")
        
    def save_preset(self):
        name, ok = QInputDialog.getText(self, "保存预设", "输入预设名称:")
        if ok and name:
            values = {freq: slider.value() for freq, slider in self.sliders.items()}
            settings = load_settings()
            if "equalizer_presets" not in settings:
                settings["equalizer_presets"] = {}
            settings["equalizer_presets"][name] = values
            save_settings(settings)
            self.preset_combo.addItem(name)
            self.preset_combo.setCurrentText(name)
            QMessageBox.information(self, "成功", f"预设 '{name}' 已保存")
            
    def load_preset(self):
        settings = load_settings()
        presets = settings.get("equalizer_presets", {})
        if not presets:
            QMessageBox.information(self, "提示", "没有保存的预设")
            return
        preset_names = list(presets.keys())
        preset, ok = QInputDialog.getItem(
            self, "加载预设", "选择预设:", preset_names, 0, False
        )
        if ok and preset:
            values = presets[preset]
            for freq, value in values.items():
                if freq in self.sliders:
                    self.sliders[freq].setValue(value)
            self.update_equalizer()
            self.preset_combo.setCurrentText(preset)

# =============== 日志控制台 ===============
class LogConsoleDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志控制台")
        self.setGeometry(200, 200, 800, 600)
        layout = QVBoxLayout()
        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QPlainTextEdit {
                background-color: #1e1e1e;
                color: #d4d4d4;
                font-family: Consolas, 'Courier New', monospace;
                font-size: 12px;
            }
        """)
        layout.addWidget(self.log_text)
        button_layout = QHBoxLayout()
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self.load_logs)
        self.close_button = QPushButton("关闭")
        self.close_button.clicked.connect(self.close)
        button_layout.addStretch()
        button_layout.addWidget(self.refresh_button)
        button_layout.addWidget(self.close_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        self.load_logs()
    
    def load_logs(self):
        log_file = "music_app.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.log_text.setPlainText(content)
                    self.log_text.verticalScrollBar().setValue(
                        self.log_text.verticalScrollBar().maximum()
                    )
            except Exception as e:
                self.log_text.setPlainText(f"无法读取日志文件: {str(e)}")
        else:
            self.log_text.setPlainText("日志文件不存在")

# =============== 网易云音乐API ===============
class NetEaseMusicAPI:
    """音乐捕捉器create bilibili by:Railgun_lover"""
    
    def __init__(self):
        self.header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            "Referer": "https://music.163.com/",
            "Origin": "https://music.163.com"
        }
        self.cookies = {
            "appver": "2.0.2",
            "os": "pc"
        }
        self.params = "D33zyir4L/58v1qGPcIPjSee79KCzxBIBy507IYDB8EL7jEnp41aDIqpHBhowfQ6iT1Xoka8jD+0p44nRKNKUA0dv+n5RWPOO57dZLVrd+T1J/sNrTdzUhdHhoKRIgegVcXYjYu+CshdtCBe6WEJozBRlaHyLeJtGrABfMOEb4PqgI3h/uELC82S05NtewlbLZ3TOR/TIIhNV6hVTtqHDVHjkekrvEmJzT5pk1UY6r0="
        self.enc_sec_key = "45c8bcb07e69c6b545d3045559bd300db897509b8720ee2b45a72bf2d3b216ddc77fb10daec4ca54b466f2da1ffac1e67e245fea9d842589dc402b92b262d3495b12165a721aed880bf09a0a99ff94c959d04e49085dc21c78bbbe8e3331827c0ef0035519e89f097511065643120cbc478f9c0af96400ba4649265781fc9079"

    def fetch_data(self, keyword: str, limit=5) -> list[dict]:
        """搜索歌曲"""
        logger.info(f"搜索歌曲: {keyword}")
        url = "https://music.163.com/api/cloudsearch/pc"
        data = {
            "s": keyword,
            "type": 1,
            "limit": limit,
            "offset": 0
        }
        try:
            response = requests.post(url, headers=self.header, cookies=self.cookies, data=data)
            response.encoding = 'utf-8' if 'utf-8' in response.headers.get('content-type', '').lower() else 'gbk'
            logger.debug(f"搜索响应状态码: {response.status_code}")
            result = response.json()
            
            if result["code"] != 200:
                logger.error(f"搜索失败: {result.get('message')}")
                return []
                
            songs = result["result"]["songs"]
            logger.info(f"找到 {len(songs)} 首歌曲")
            
            return [
                {
                    "id": song["id"],
                    "name": song["name"],
                    "artists": "、".join(artist["name"] for artist in song["ar"]),
                    "duration": song["dt"],
                    "album": song["al"]["name"]
                }
                for song in songs[:limit]
            ]
        except Exception as e:
            logger.error(f"搜索歌曲失败: {str(e)}")
            return []

    def fetch_lyrics(self, song_id, with_translation=False):
        """获取歌词"""
        logger.info(f"获取歌词: ID={song_id}")
        url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
        try:
            response = requests.get(url, headers=self.header, cookies=self.cookies)
            result = response.json()
            
            if "lrc" in result and "lyric" in result["lrc"]:
                logger.info("歌词获取成功")
                lyric = result["lrc"]["lyric"]
                translation = result["tlyric"]["lyric"] if "tlyric" in result else ""
                return lyric, translation
            else:
                logger.warning("未找到歌词")
                return "歌词未找到"
        except Exception as e:
            logger.error(f"获取歌词失败: {str(e)}")
            return "歌词获取失败"
        

    def fetch_extra(self, song_id: str | int) -> dict[str, str]:
        """获取额外信息 - 使用官方API"""
        logger.info(f"获取歌曲额外信息: ID={song_id}")
        url = f"https://music.163.com/api/song/detail?ids=[{song_id}]"
        try:
            response = requests.get(url, headers=self.header, cookies=self.cookies)
            result = response.json()
            
            if result["code"] != 200 or not result["songs"]:
                logger.error(f"获取歌曲详情失败: {result.get('message')}")
                return {}
                
            song = result["songs"][0]
            logger.info(f"获取到歌曲额外信息: {song.get('name')}")
            
            # 安全获取专辑信息
            album_info = song.get("al", {})
            cover_url = album_info.get("picUrl", "") if album_info else ""
            
            return {
                "title": song.get("name", "未知歌曲"),
                "author": "、".join(artist.get("name", "未知") for artist in song.get("ar", [])),
                "cover_url": cover_url,
                "audio_url": f"https://music.163.com/song/media/outer/url?id={song_id}",
            }
        except Exception as e:
            logger.error(f"获取歌曲额外信息失败: {str(e)}")
            return {}
    
    def download_song(self, audio_url: str, file_path: str) -> bool:
        """下载歌曲文件"""
        logger.info(f"开始下载歌曲: {file_path}")
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Origin": "https://music.163.com"
            }
            
            response = requests.get(audio_url, headers=headers, stream=True)
            if response.status_code != 200:
                logger.error(f"下载失败: HTTP状态码 {response.status_code}")
                return False
                
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        progress = int(100 * downloaded / total_size) if total_size > 0 else 0
                        
                        self.download_progress.emit(progress)
            
            logger.info(f"歌曲下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载歌曲失败: {str(e)}")
            return False


class NetEaseWorker(QThread):
    """网易云音乐专用工作线程"""
    search_finished = pyqtSignal(list)
    details_ready = pyqtSignal(dict) 
    error_occurred = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.api = NetEaseMusicAPI()
        self.mode = None
        self.keyword = None
        self.song_id = None
        
    def search_songs(self, keyword):
        self.mode = "search"
        self.keyword = keyword
        self.start()
        
    def fetch_details(self, song_id):
        self.mode = "details"
        self.song_id = song_id
        self.start()
        
    def run(self):
        try:
            if self.mode == "search":
                songs = self.api.fetch_data(self.keyword)
                self.search_finished.emit(songs)
            elif self.mode == "details":
                song_info = self.api.fetch_extra(self.song_id)
                self.details_ready.emit(song_info)
        except Exception as e:
            error_msg = f"网易云API错误: {str(e)}\n{traceback.format_exc()}"
            self.error_occurred.emit(error_msg)

# =============== 音乐工作线程 ===============
class MusicWorker(QThread):
    search_finished = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.mode = None
        self.keyword = None
        self.song = None
        self.audio_url = None
        self.file_path = None
        
    def search_songs(self, keyword):
        self.mode = "search"
        self.keyword = keyword
        self.start()
        
    def download_song(self, audio_url, file_path):
        self.mode = "download"
        self.audio_url = audio_url
        self.file_path = file_path
        self.start()
        
    def run(self):
        try:
            if self.mode == "search":
                ensure_settings_file_exists()
                config = get_active_source_config()
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                    "Connection": "keep-alive",
                    "Referer": "https://music.163.com/",
                    "Origin": "https://music.163.com",
                    "X-Requested-With": "XMLHttpRequest",
                    **config.get("headers", {})
                }

                params = config.get("params", {}).copy()
                max_results = load_settings()["other"]["max_results"]
                
                # 替换查询参数中的占位符
                for key, value in params.items():
                    if isinstance(value, str) and "{query}" in value:
                        params[key] = value.replace("{query}", self.keyword)
                
                api_key = config.get("api_key", "")
                if api_key:
                    if "Authorization" in headers:
                        headers["Authorization"] = f"Bearer {api_key}"
                    else:
                        params["api_key"] = api_key
                
                method = config.get("method", "GET").upper()
                url = config["url"]
                timeout = 30
                max_retries = 3
                retry_count = 0
                
                while retry_count < max_retries:
                    try:
                        if method == "GET":
                            response = requests.get(url, params=params, headers=headers, timeout=timeout)
                        else:
                            response = requests.post(url, data=params, headers=headers, timeout=timeout)

                        # 检查响应状态码
                        if response.status_code != 200:
                            logger.warning(f"API返回非200状态码: {response.status_code}, 尝试重试...")
                            retry_count += 1
                            time.sleep(1)
                            continue
                            
                        # 检查响应内容是否为空
                        if not response.text.strip():
                            logger.warning("API返回空响应, 尝试重试...")
                            retry_count += 1
                            time.sleep(1)
                            continue

                        # 检查是否被重定向到验证页面
                        if "verify" in response.url or "captcha" in response.url:
                            logger.error("API请求被重定向到验证页面")
                            self.error_occurred.emit("请求被拦截，可能需要解决验证码")
                            return
                        
                        # 检查内容类型
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' not in content_type:
                            logger.warning(f"API返回非JSON内容: {content_type}, 原始内容: {response.text[:200]}")
                            
                            # 尝试解析可能的错误信息
                            if 'text/html' in content_type:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                title = soup.title.string if soup.title else "未知错误"
                                self.error_occurred.emit(f"API返回HTML页面: {title}")
                                return
                            
                        # 尝试解析JSON
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            logger.error(f"无法解析JSON响应, 原始内容: {response.text[:200]}")
                            self.error_occurred.emit(f"API返回了无效的JSON数据: {response.text[:100]}...")
                            return
                            
                        # 成功获取数据，跳出重试循环
                        break

                    except requests.exceptions.Timeout:
                        logger.warning(f"API请求超时, 尝试重试 ({retry_count+1}/{max_retries})")
                        retry_count += 1
                        time.sleep(2)
                    except requests.exceptions.ConnectionError:
                        logger.warning(f"网络连接错误, 尝试重试 ({retry_count+1}/{max_retries})")
                        retry_count += 1
                        time.sleep(2)
                
                # 如果重试后仍然失败
                if retry_count >= max_retries:
                    self.error_occurred.emit("API请求失败，请检查网络连接或稍后再试")
                    return

                # 根据音源名称使用不同的解析方式
                active_source_name = config.get("name", "")
                if active_source_name == "网易云音乐":
                    if data["code"] == 200:
                        songs = data["result"]["songs"]
                        formatted_songs = []
                        for song in songs:
                            # 解析艺术家信息
                            artists = "、".join([ar["name"] for ar in song.get("ar", [])])
                            
                            # 解析专辑信息
                            album_info = song.get("al", {})
                            album_name = album_info.get("name", "未知专辑")
                            
                            # 构建歌曲信息
                            formatted_songs.append({
                                "id": song["id"],
                                "name": song["name"],
                                "artists": artists,
                                "duration": song["dt"],
                                "album": album_name,
                                "url": f"https://music.163.com/song/media/outer/url?id={song['id']}",
                                "pic": album_info.get("picUrl", ""),
                            })
                        video_list = formatted_songs
                    else:
                        formatted_songs = []
                        video_list = []

                elif active_source_name == "酷狗音乐":
                    search_response = response.json()
                    if search_response.get("status") == 1 and search_response.get("data"):
                        items = search_response["data"].get("lists", [])
                        formatted_songs = []
                    
                        # 对于每个搜索结果，获取完整信息
                        for item in items:
                            # 获取歌曲hash
                            song_hash = item.get("FileHash", "")
                        
                            # 使用hash获取完整信息
                            if song_hash:
                                # 构建获取完整信息的URL
                                params = config.get("params", {}).copy()
                                params["hash"] = song_hash
                                full_info_url = config["url"] + "?" + urllib.parse.urlencode(params)
                            
                                # 请求完整信息
                                full_info_response = requests.get(full_info_url, headers=headers, timeout=30)
                                if full_info_response.status_code == 200:
                                    full_info = full_info_response.json()
                                
                                    # 提取所需信息
                                    if full_info.get("status") == 1 and full_info.get("data"):
                                        song_data = full_info["data"]
                                        formatted_songs.append({
                                            "id": song_data.get("hash", ""),
                                            "name": song_data.get("song_name", "未知歌曲"),
                                            "artists": song_data.get("author_name", "未知艺术家"),
                                            "duration": int(song_data.get("timelength", 0)),
                                            "album": song_data.get("album_name", "未知专辑"),
                                            "url": song_data.get("play_url", ""),
                                            "pic": song_data.get("img", ""),
                                            "lrc": song_data.get("lyrics", "")
                                        })
                        video_list = formatted_songs
                    else:
                        video_list = []

                elif active_source_name == "公共音乐API":
                    if data.get("code") == 200:
                        error_msg = data.get("message", "未知错误")
                        logger.error(f"公共音乐API错误: {error_msg}")
                        self.error_occurred.emit(f"公共音乐API错误: {error_msg}")
                        video_list = []
                    else:
                        # 成功获取数据
                        video_list = data.get("data", [])
                        # 确保所有歌曲都有必要字段
                        for song in video_list:
                            if "id" not in song:
                                song["id"] = hashlib.md5(song["url"].encode()).hexdigest()
                            if "duration" not in song:
                                song["duration"] = 0
                            if "artists" not in song:
                                song["artists"] = "未知艺术家"
                            if "album" not in song:
                                song["album"] = "未知专辑"
                else:
                    video_list = data.get("data", [])
                    if not isinstance(video_list, list):
                        logger.warning(f"音源 {active_source_name} 返回的 data 字段不是列表")
                        video_list = []
                    
                    formatted_songs = []
                    for song in video_list:
                        formatted_songs.append({
                            "id": song.get("songid", ""),
                            "name": song.get("title", "未知歌曲"),
                            "artists": song.get("author", "未知艺术家"),
                            "duration": self.parse_duration(song.get("duration", "00:00")),
                            "album": song.get("album", "未知专辑"),
                            "url": song.get("url", ""),
                            "pic": song.get("pic", ""),
                            "lrc": song.get("lrc", "")
                        })
                    video_list = formatted_songs
                
                # 限制结果数量
                if len(video_list) > max_results:
                    video_list = video_list[:max_results]
                
                self.search_finished.emit(video_list)

            elif self.mode == "download":
                success = self.download_file(self.audio_url, self.file_path)
                if success:
                    self.download_finished.emit(self.file_path)
                else:
                    self.error_occurred.emit("歌曲下载失败")
        except requests.exceptions.ConnectionError as e:
            error_msg = f"网络连接失败: {str(e)}。请检查网络连接或尝试更换音源。"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
        except Exception as e:
            error_msg = f"发生错误: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
    
    def download_file(self, url, file_path):
        try:
            # 公共音乐API有特殊的下载URL结构
            if "api.railgun.live" in url:
                download_url = url.replace("/info/", "/download/")
                if not download_url.endswith(".mp3"):
                    download_url += ".mp3"
            else:
                download_url = url

            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
                "Referer": "https://music.163.com/",
                "Origin": "https://music.163.com"
            }
            response = requests.get(url, headers=headers, stream=True, timeout=30)
            if response.status_code != 200:
                logger.error(f"下载失败: HTTP状态码 {response.status_code}")
                return False
                
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0
            
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if self.isInterruptionRequested():
                        logger.info("下载被中断")
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        progress = int(100 * downloaded / total_size) if total_size > 0 else 0
                        self.download_progress.emit(progress)
            
            logger.info(f"歌曲下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载歌曲失败: {str(e)}")
            return False
    
    def parse_duration(self, duration_val):
        """解析不同格式的时长"""
        # 如果是整数，假设是毫秒
        if isinstance(duration_val, int):
            return duration_val
    
        # 如果是字符串，尝试解析 "mm:ss" 格式
        if isinstance(duration_val, str) and ':' in duration_val:
            try:
                parts = duration_val.split(':')
                if len(parts) == 2:
                    minutes, seconds = parts
                    return (int(minutes) * 60 + int(seconds)) * 1000
                elif len(parts) == 3:
                    hours, minutes, seconds = parts
                    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
            except:
                return 0
    
        # 默认返回0
        return 0

# =============== 设置对话框 ===============
class SettingsDialog(QDialog):
    lyrics_settings_updated = pyqtSignal()
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 700, 500)
        self.settings = load_settings()
        self.parent = parent
        self.show_translation_check = QCheckBox("显示歌词翻译")
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
        
        # 第一页：保存位置
        save_tab = QWidget()
        save_layout = QVBoxLayout()
        save_group = QGroupBox("保存位置设置")
        save_form = QFormLayout()
        
        self.music_dir_edit = QLineEdit()
        self.music_dir_btn = QPushButton("浏览...")
        self.music_dir_btn.clicked.connect(lambda: self.select_directory(self.music_dir_edit))
        
        self.cache_dir_edit = QLineEdit()
        self.cache_dir_btn = QPushButton("浏览...")
        self.cache_dir_btn.clicked.connect(lambda: self.select_directory(self.cache_dir_edit))
        
        self.video_dir_edit = QLineEdit()
        self.video_dir_btn = QPushButton("浏览...")
        self.video_dir_btn.clicked.connect(lambda: self.select_directory(self.video_dir_edit))
        
        save_form.addRow("音乐保存位置:", self.create_dir_row(self.music_dir_edit, self.music_dir_btn))
        save_form.addRow("缓存文件位置:", self.create_dir_row(self.cache_dir_edit, self.cache_dir_btn))
        save_form.addRow("视频保存位置:", self.create_dir_row(self.video_dir_edit, self.video_dir_btn))
        save_group.setLayout(save_form)
        
        # 背景图片设置
        bg_group = QGroupBox("背景设置")
        bg_layout = QVBoxLayout()
        self.bg_image_edit = QLineEdit()
        self.bg_image_btn = QPushButton("浏览...")
        self.bg_image_btn.clicked.connect(lambda: self.select_image(self.bg_image_edit))
        self.bg_preview_btn = QPushButton("预览")
        self.bg_preview_btn.clicked.connect(self.preview_background)
        bg_row = QHBoxLayout()
        bg_row.addWidget(self.bg_image_edit)
        bg_row.addWidget(self.bg_image_btn)
        bg_row.addWidget(self.bg_preview_btn)
        bg_layout.addLayout(bg_row)
        bg_group.setLayout(bg_layout)
        
        # 其他设置
        other_group = QGroupBox("其他设置")
        other_form = QFormLayout()
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(5, 100)
        self.auto_play_check = QCheckBox("下载后自动播放")
        other_form.addRow("最大获取数量:", self.max_results_spin)
        other_form.addRow(self.auto_play_check)
        other_group.setLayout(other_form)
        other_form.addRow(self.show_translation_check)
        save_layout.addWidget(save_group)
        save_layout.addWidget(bg_group)
        save_layout.addWidget(other_group)
        save_layout.addStretch()
        save_tab.setLayout(save_layout)
        
        # 第二页：音源设置
        source_tab = QWidget()
        source_layout = QVBoxLayout()
        source_group = QGroupBox("当前音源")
        source_form = QFormLayout()
        source_management_layout = QHBoxLayout()
        self.add_source_button = QPushButton("添加音源")
        self.add_source_button.clicked.connect(self.add_music_source)
        self.remove_source_button = QPushButton("移除音源")
        self.remove_source_button.clicked.connect(self.remove_music_source)
        source_management_layout.addWidget(self.add_source_button)
        source_management_layout.addWidget(self.remove_source_button)
        source_layout.addLayout(source_management_layout)

        # 音源选择
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_source_names())
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("如需API密钥请在此输入")
        source_form.addRow("选择音源:", self.source_combo)
        source_form.addRow("API密钥:", self.api_key_edit)
        source_group.setLayout(source_form)
        source_layout.addWidget(source_group)
        
        # 测试连接和DNS刷新按钮
        test_button = QPushButton("测试连接")
        test_button.clicked.connect(self.test_api_connection)
        source_form.addRow(test_button)
        
        dns_button = QPushButton("刷新DNS缓存")
        dns_button.clicked.connect(self.refresh_dns_cache)
        source_form.addRow(dns_button)
                
        source_tab.setLayout(source_layout)
        
        # 第三页：Bilibili设置
        bilibili_tab = QWidget()
        bilibili_layout = QVBoxLayout()
        bilibili_group = QGroupBox("Bilibili设置")
        bilibili_form = QFormLayout()
        self.bilibili_cookie_edit = QLineEdit()
        self.bilibili_cookie_edit.setPlaceholderText("输入Bilibili Cookie（可选）")
        self.max_duration_spin = QSpinBox()
        self.max_duration_spin.setRange(60, 3600)
        self.max_duration_spin.setSuffix("秒")
        bilibili_form.addRow("Cookie:", self.bilibili_cookie_edit)
        bilibili_form.addRow("最大下载时长:", self.max_duration_spin)
        bilibili_group.setLayout(bilibili_form)
        bilibili_layout.addWidget(bilibili_group)
        
        # Bilibili视频搜索按钮
        bilibili_button_layout = QHBoxLayout()
        self.bilibili_video_button = QPushButton("搜索B站视频")
        self.bilibili_video_button.setStyleSheet("padding: 8px; background-color: rgba(219, 68, 83, 200); color: white; font-weight: bold;")
        self.bilibili_video_button.clicked.connect(self.open_bilibili_video_search)
        bilibili_button_layout.addWidget(self.bilibili_video_button)
        bilibili_layout.addLayout(bilibili_button_layout)
        bilibili_tab.setLayout(bilibili_layout)
        
        # 第四页：作者主页
        author_tab = QWidget()
        author_layout = QVBoxLayout()   
        author_info = QLabel("欢迎使用Railgun_lover的音乐项目！")
        author_info.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        author_layout.addWidget(author_info, alignment=Qt.AlignCenter)

        # 按钮布局
        button_layout = QHBoxLayout()
        bilibili_button = QPushButton("访问B站主页")
        bilibili_button.setStyleSheet("""
            QPushButton {
                padding: 12px;
                font-size: 14px;
                background-color: #FB7299;
                color: white;
                border-radius: 6px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #FF85AD;
            }
        """)
        bilibili_button.setCursor(QCursor(Qt.PointingHandCursor))
        bilibili_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://space.bilibili.com/1411318075?spm_id_from=333.1007.0.0"
        )))
        
        github_button = QPushButton("访问GitHub项目")
        github_button.setStyleSheet("""
            QPushButton {
                padding: 12px;
                font-size: 14px;
                background-color: #6e5494;
                color: white;
                border-radius: 6px;
                min-width: 150px;
            }
            QPushButton:hover {
                background-color: #836EAA;
            }
        """)
        github_button.setCursor(QCursor(Qt.PointingHandCursor))
        github_button.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
            "https://github.com/MISAKAMIYO/Music_Player"
        )))
        
        button_layout.addWidget(bilibili_button)
        button_layout.addStretch()
        button_layout.addWidget(github_button)
        author_layout.addLayout(button_layout)
    
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setLineWidth(1)
        author_layout.addWidget(separator)
    
        # 联系信息
        contact_info = QLabel("项目开源免费，欢迎使用和交流！")
        contact_info.setStyleSheet("font-size: 14px; color: #888888; margin-top: 15px;")
        contact_info.setAlignment(Qt.AlignCenter)
        author_layout.addWidget(contact_info)
        author_tab.setLayout(author_layout)
        
        # 添加标签页
        self.tabs.addTab(save_tab, "保存设置")
        self.tabs.addTab(source_tab, "音源设置")
        self.tabs.addTab(bilibili_tab, "Bilibili设置")
        self.tabs.addTab(author_tab, "作者主页")
        
        # 按钮
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def test_api_connection(self):
        """测试当前音源API是否可用"""
        config = get_active_source_config()
        url = config["url"]
        
        # 对于公共音乐API，使用特殊的测试参数
        if config["name"] == "公共音乐API":
            test_url = "https://api.railgun.live/music/search?keyword=test&source=kugou&page=1&limit=1"
            try:
                response = requests.get(test_url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == 200 and data.get("data"):
                        QMessageBox.information(self, "测试成功", "公共音乐API连接正常！")
                    else:
                        QMessageBox.warning(self, "测试失败", f"API返回错误: {data.get('message', '未知错误')}")
                else:
                    QMessageBox.warning(self, "测试失败", f"API返回状态码: {response.status_code}")
            except Exception as e:
                QMessageBox.critical(self, "测试失败", f"无法连接到API: {str(e)}")
        else:
            # 其他音源的测试逻辑
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    QMessageBox.information(self, "测试成功", f"API连接正常: {url}")
                else:
                    QMessageBox.warning(self, "测试失败", f"API返回状态码: {response.status_code}")
            except Exception as e:
                QMessageBox.critical(self, "测试失败", f"无法连接到API: {str(e)}")
        
    def add_music_source(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("添加新音源")
        layout = QFormLayout()
        
        name_edit = QLineEdit()
        url_edit = QLineEdit()
        method_combo = QComboBox()
        method_combo.addItems(["GET", "POST"])
        
        # 新增源类型选择
        type_label = QLabel("源类型:")
        type_combo = QComboBox()
        type_combo.addItems(["标准API", "公共音乐API"])
    
        layout.addRow("名称:", name_edit)
        layout.addRow("URL:", url_edit)
        layout.addRow("请求方法:", method_combo)
    
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
    
        layout.addWidget(button_box)
        dialog.setLayout(layout)
    
        if dialog.exec_() == QDialog.Accepted:
            source_type = type_combo.currentText()
            
            # 根据不同源类型设置不同的默认参数
            if source_type == "公共音乐API":
                new_source = {
                    "name": name_edit.text(),
                    "url": "https://api.railgun.live/music/search",
                    "params": {
                        "keyword": "{query}",
                        "source": "kugou",
                        "page": 1,
                        "limit": 20
                    },
                    "method": "GET",
                    "headers": {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
                    }
                }
            else:
                new_source = {
                    "name": name_edit.text(),
                    "url": url_edit.text(),
                    "method": method_combo.currentText(),
                    "params": {},
                    "headers": {}
                }
                
            self.settings["sources"]["sources_list"].append(new_source)
            self.source_combo.addItem(new_source["name"])
            # 立即设置为当前音源
            self.settings["sources"]["active_source"] = new_source["name"]
            self.source_combo.setCurrentText(new_source["name"])


    def remove_music_source(self):
        current_source = self.source_combo.currentText()
        if current_source and current_source != "QQ音乐" and current_source != "网易云音乐" and current_source != "酷狗音乐":
            reply = QMessageBox.question(
                self, 
                "确认删除",
                f"确定要移除音源 '{current_source}' 吗？",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                # 从设置中移除
                self.settings["sources"]["sources_list"] = [
                    s for s in self.settings["sources"]["sources_list"]
                    if s["name"] != current_source
                ]
                # 从下拉框中移除
                self.source_combo.removeItem(self.source_combo.currentIndex())
        
    def refresh_dns_cache(self):
        try:
            if sys.platform == "win32":
                os.system("ipconfig /flushdns")
            elif sys.platform == "darwin":
                os.system("sudo killall -HUP mDNSResponder")
            else:
                os.system("sudo systemd-resolve --flush-caches")
            QMessageBox.information(self, "成功", "DNS缓存已刷新")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"刷新DNS缓存失败: {str(e)}")
    

    def open_bilibili_video_search(self):
        cookie = self.bilibili_cookie_edit.text().strip()
        dialog = VideoSearchDialog(self, cookie)
        dialog.exec_()
        
    def create_dir_row(self, edit, btn):
        row_layout = QHBoxLayout()
        row_layout.addWidget(edit)
        row_layout.addWidget(btn)
        widget = QWidget()
        widget.setLayout(row_layout)
        return widget
        
    def select_directory(self, edit):
        directory = QFileDialog.getExistingDirectory(self, "选择目录")
        if directory:
            edit.setText(directory)
            
    def select_image(self, edit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp)"
        )
        if file_path:
            edit.setText(file_path)

    def preview_background(self):
        image_path = self.bg_image_edit.text()
        if image_path and os.path.exists(image_path):
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle("背景预览")
            preview_dialog.setGeometry(300, 300, 600, 400)
            layout = QVBoxLayout()
            image_label = QLabel()
            pixmap = QPixmap(image_path)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(550, 350, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                image_label.setPixmap(pixmap)
                image_label.setAlignment(Qt.AlignCenter)
            layout.addWidget(image_label)
            preview_dialog.setLayout(layout)
            preview_dialog.exec_()
        else:
            QMessageBox.warning(self, "错误", "图片路径无效或文件不存在")
            
    def load_settings(self):
        self.music_dir_edit.setText(self.settings["save_paths"]["music"])
        self.cache_dir_edit.setText(self.settings["save_paths"]["cache"])
        self.video_dir_edit.setText(self.settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos")))
        self.bg_image_edit.setText(self.settings.get("background_image", ""))
        self.max_results_spin.setValue(self.settings["other"]["max_results"])
        self.auto_play_check.setChecked(self.settings["other"]["auto_play"])
        self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
        active_source = get_active_source_config()
        self.api_key_edit.setText(active_source.get("api_key", ""))
        self.bilibili_cookie_edit.setText(self.settings["bilibili"].get("cookie", ""))
        self.max_duration_spin.setValue(self.settings["bilibili"].get("max_duration", 600))

    def save_settings(self):
        self.settings["save_paths"]["music"] = self.music_dir_edit.text()
        self.settings["save_paths"]["cache"] = self.cache_dir_edit.text()
        self.settings["save_paths"]["videos"] = self.video_dir_edit.text()
        self.settings["background_image"] = self.bg_image_edit.text()
        self.settings["other"]["max_results"] = self.max_results_spin.value()
        self.settings["other"]["auto_play"] = self.auto_play_check.isChecked()
        active_source = self.source_combo.currentText()
        self.settings["sources"]["active_source"] = active_source
        
        # 更新API密钥
        for source in self.settings["sources"]["sources_list"]:
            if source["name"] == active_source:
                source["api_key"] = self.api_key_edit.text()
                break
        
        # 更新Bilibili设置
        if "bilibili" not in self.settings:
            self.settings["bilibili"] = {}
        self.settings["bilibili"]["cookie"] = self.bilibili_cookie_edit.text()
        self.settings["bilibili"]["max_duration"] = self.max_duration_spin.value()
        
        if save_settings(self.settings):
            if self.parent:
               self.parent.refresh_source_combo()
            self.lyrics_settings_updated.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "保存设置失败，请检查日志")
        
        # 更新歌词设置（直接从控件获取值）
        lyrics_settings = {
            "font": self.font_combo.currentText(),
            "color": self.color_button.text(),
            "opacity": self.opacity_slider.value(),
            "effect_type": self.effect_combo.currentText()
        }
        self.settings["lyrics"] = lyrics_settings
        
        # 保存设置
        if save_settings(self.settings):
            if self.parent:
               self.parent.refresh_source_combo()
            self.lyrics_settings_updated.emit()
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "保存设置失败，请检查日志")

# =============== 工具对话框 ===============
class ToolsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("实用工具")
        self.setGeometry(300, 300, 600, 400)
        self.parent = parent
        self.settings = load_settings()
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 歌词工具标签页
        lyrics_tab = QWidget()
        lyrics_layout = QVBoxLayout()
        
        lyrics_label = QLabel("输入歌词（支持LRC格式）：")
        lyrics_layout.addWidget(lyrics_label)
        
        self.lyrics_input = QTextEdit()
        self.lyrics_input.setPlaceholderText("输入歌词内容...")
        lyrics_layout.addWidget(self.lyrics_input)
        
        # 图片设置
        settings_layout = QHBoxLayout()
        
        size_layout = QHBoxLayout()
        size_label = QLabel("图片宽度:")
        self.width_spin = QSpinBox()
        self.width_spin.setRange(500, 2000)
        self.width_spin.setValue(1000)
        size_layout.addWidget(size_label)
        size_layout.addWidget(self.width_spin)
        settings_layout.addLayout(size_layout)
        
        font_layout = QHBoxLayout()
        font_label = QLabel("字体大小:")
        self.font_size = QSpinBox()
        self.font_size.setRange(10, 50)
        self.font_size.setValue(30)
        font_layout.addWidget(font_label)
        font_layout.addWidget(self.font_size)
        settings_layout.addLayout(font_layout)
        
        lyrics_layout.addLayout(settings_layout)
        
        # 生成按钮
        generate_btn = QPushButton("生成歌词图片")
        generate_btn.clicked.connect(self.generate_lyrics_image)
        lyrics_layout.addWidget(generate_btn)
        
        # 预览区域
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        lyrics_layout.addWidget(self.preview_label)
        
        lyrics_tab.setLayout(lyrics_layout)
        
        # 格式转换标签页
        convert_tab = QWidget()
        convert_layout = QVBoxLayout()
        
        # 选择文件区域
        file_layout = QHBoxLayout()
        
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择音频文件...")
        
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.select_audio_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_btn)
        convert_layout.addLayout(file_layout)
        
        # 输出格式选择
        format_layout = QHBoxLayout()
        format_label = QLabel("输出格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP3", "WAV", "FLAC", "M4A"])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        convert_layout.addLayout(format_layout)
        
        # 转换按钮
        convert_btn = QPushButton("开始转换")
        convert_btn.clicked.connect(self.convert_audio)
        convert_layout.addWidget(convert_btn)
        
        # 转换状态
        self.convert_status = QLabel("")
        self.convert_status.setAlignment(Qt.AlignCenter)
        convert_layout.addWidget(self.convert_status)
        
        convert_tab.setLayout(convert_layout)
        
        # 清理工具标签页
        clean_tab = QWidget()
        clean_layout = QVBoxLayout()
        
        clean_label = QLabel("清理缓存和临时文件:")
        clean_layout.addWidget(clean_label)
        
        # 清理选项
        cache_check = QCheckBox("清理歌曲缓存")
        cache_check.setChecked(True)
        self.cache_check = cache_check
        
        temp_check = QCheckBox("清理临时文件")
        temp_check.setChecked(True)
        self.temp_check = temp_check
        
        preview_check = QCheckBox("清理预览图片")
        preview_check.setChecked(True)
        self.preview_check = preview_check
        
        clean_layout.addWidget(cache_check)
        clean_layout.addWidget(temp_check)
        clean_layout.addWidget(preview_check)
        
        # 清理按钮
        clean_btn = QPushButton("开始清理")
        clean_btn.clicked.connect(self.clean_files)
        clean_layout.addWidget(clean_btn)
        
        # 清理状态
        self.clean_status = QLabel("")
        self.clean_status.setAlignment(Qt.AlignCenter)
        clean_layout.addWidget(self.clean_status)
        
        clean_tab.setLayout(clean_layout)
        
        # 批量下载标签页
        batch_tab = QWidget()
        batch_layout = QVBoxLayout()
        
        batch_label = QLabel("批量下载歌曲:")
        batch_layout.addWidget(batch_label)
        
        # 歌曲列表
        self.song_list = QTextEdit()
        self.song_list.setPlaceholderText("每行输入一首歌曲名称")
        batch_layout.addWidget(self.song_list)
        
        # 下载按钮
        download_btn = QPushButton("开始下载")
        download_btn.clicked.connect(self.batch_download)
        batch_layout.addWidget(download_btn)
        
        # 下载状态
        self.download_status = QLabel("")
        self.download_status.setAlignment(Qt.AlignCenter)
        batch_layout.addWidget(self.download_status)
        
        batch_tab.setLayout(batch_layout)
        
        # 添加标签页
        self.tabs.addTab(lyrics_tab, "歌词工具")
        self.tabs.addTab(convert_tab, "格式转换")
        self.tabs.addTab(clean_tab, "清理工具")
        self.tabs.addTab(batch_tab, "批量下载")
        
        layout.addWidget(self.tabs)
        self.setLayout(layout)
        
    def select_audio_file(self):
        """选择音频文件"""
        music_dir = self.settings["save_paths"]["music"]
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择音频文件", music_dir, 
            "音频文件 (*.mp3 *.wav *.flac *.m4a);;所有文件 (*.*)"
        )
        
        if file_path:
            self.file_path_edit.setText(file_path)
            
    def generate_lyrics_image(self):
        """生成歌词图片"""
        lyrics = self.lyrics_input.toPlainText().strip()
        if not lyrics:
            QMessageBox.warning(self, "提示", "请输入歌词内容")
            return
            
        width = self.width_spin.value()
        font_size = self.font_size.value()
        
        try:
            img_data = draw_lyrics(lyrics, image_width=width, font_size=font_size)
            
            # 创建预览
            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(550, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
            else:
                QMessageBox.warning(self, "错误", "生成预览失败")
                return
                
            # 保存图片
            cache_dir = self.settings["save_paths"]["cache"]
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存歌词图片", 
                os.path.join(cache_dir, "lyrics.jpg"), 
                "JPEG图片 (*.jpg)"
            )
            
            if file_path:
                with open(file_path, "wb") as f:
                    f.write(img_data)
                QMessageBox.information(self, "成功", f"歌词图片已保存到:\n{file_path}")
                
        except Exception as e:
            logger.error(f"生成歌词图片失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"生成失败: {str(e)}")
            
    def convert_audio(self):
        """转换音频格式"""
        input_path = self.file_path_edit.text().strip()
        if not input_path or not os.path.exists(input_path):
            QMessageBox.warning(self, "错误", "请选择有效的音频文件")
            return
            
        output_format = self.format_combo.currentText().lower()
        output_dir = os.path.dirname(input_path)
        filename = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(output_dir, f"{filename}.{output_format}")
        
        try:
            self.convert_status.setText("正在转换...")
            QApplication.processEvents()
            
            # 实际转换逻辑
            if sys.platform == "win32":
                command = f'ffmpeg -i "{input_path}" "{output_path}"'
                subprocess.run(command, shell=True, check=True)
            else:
                command = ['ffmpeg', '-i', input_path, output_path]
                subprocess.run(command, check=True)
                
            self.convert_status.setText(f"转换成功: {output_path}")
            QMessageBox.information(self, "成功", f"文件已转换为 {output_format.upper()} 格式:\n{output_path}")
            
        except subprocess.CalledProcessError as e:
            logger.error(f"音频转换失败: {str(e)}")
            self.convert_status.setText(f"转换失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"转换失败: {str(e)}")
        except Exception as e:
            logger.error(f"音频转换失败: {str(e)}")
            self.convert_status.setText(f"转换失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"转换失败: {str(e)}")
            
    def clean_files(self):
        """清理缓存和临时文件"""
        try:
            cache_dir = self.settings["save_paths"]["cache"]
            temp_dir = os.path.abspath(os.path.join("data", "temp"))
            
            total_size = 0
            file_count = 0
            
            # 清理歌曲缓存
            if self.cache_check.isChecked():
                for file in Path(cache_dir).glob("*.*"):
                    if file.is_file():
                        total_size += file.stat().st_size
                        file.unlink()
                        file_count += 1
            
            # 清理临时文件
            if self.temp_check.isChecked() and os.path.exists(temp_dir):
                for file in Path(temp_dir).rglob("*.*"):
                    if file.is_file():
                        total_size += file.stat().st_size
                        file.unlink()
                        file_count += 1
            
            # 清理预览图片
            if self.preview_check.isChecked():
                preview_dir = os.path.abspath(os.path.join("data", "previews"))
                if os.path.exists(preview_dir):
                    for file in Path(preview_dir).rglob("*.*"):
                        if file.is_file():
                            total_size += file.stat().st_size
                            file.unlink()
                            file_count += 1
            
            # 显示清理结果
            size_mb = total_size / (1024 * 1024)
            self.clean_status.setText(f"已清理 {file_count} 个文件，释放 {size_mb:.2f} MB 空间")
            QMessageBox.information(self, "成功", f"清理完成:\n已清理 {file_count} 个文件\n释放 {size_mb:.2f} MB 空间")
            
        except Exception as e:
            logger.error(f"清理文件失败: {str(e)}")
            self.clean_status.setText(f"清理失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"清理失败: {str(e)}")
            
    def batch_download(self):
        """批量下载歌曲"""
        song_names = self.song_list.toPlainText().strip().splitlines()
        if not song_names:
            QMessageBox.warning(self, "提示", "请输入歌曲名称")
            return
            
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("批量下载歌曲...", "取消", 0, len(song_names), self)
        self.progress_dialog.setWindowTitle("批量下载")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_batch_download)
        self.progress_dialog.show()
        
        # 创建工作线程
        self.batch_worker = BatchDownloadWorker(song_names)
        self.batch_worker.progress_updated.connect(self.update_batch_progress)
        self.batch_worker.finished.connect(self.batch_download_completed)
        self.batch_worker.start()
        
    def update_batch_progress(self, current, total, song_name):
        """更新批量下载进度"""
        self.progress_dialog.setValue(current)
        self.progress_dialog.setLabelText(f"正在下载: {song_name}\n进度: {current}/{total}")
        
    def batch_download_completed(self):
        """批量下载完成"""
        self.progress_dialog.close()
        self.download_status.setText(f"批量下载完成: {self.batch_worker.success_count} 首成功, {self.batch_worker.fail_count} 首失败")
        QMessageBox.information(self, "完成", f"批量下载完成:\n成功: {self.batch_worker.success_count} 首\n失败: {self.batch_worker.fail_count} 首")
        
    def cancel_batch_download(self):
        """取消批量下载"""
        if hasattr(self, 'batch_worker') and self.batch_worker.isRunning():
            self.batch_worker.requestInterruption()
            self.download_status.setText("批量下载已取消")
            
            
class BatchDownloadWorker(QThread):
    """批量下载歌曲的工作线程"""
    progress_updated = pyqtSignal(int, int, str)
    
    def __init__(self, song_names):
        super().__init__()
        self.song_names = song_names
        self.success_count = 0
        self.fail_count = 0
        self._stop_requested = False
        
    def run(self):
        self.success_count = 0
        self.fail_count = 0
        
        for i, song_name in enumerate(self.song_names):
            if self._stop_requested:
                break
                
            if not song_name.strip():
                continue
                
            self.progress_updated.emit(i+1, len(self.song_names), song_name)
            
            try:
                # 这里添加实际的下载逻辑
                # 简化示例：模拟下载过程
                self.msleep(1000)  # 模拟下载延迟
                self.success_count += 1
            except Exception:
                self.fail_count += 1
                
    def requestInterruption(self):
        """请求停止下载"""
        self._stop_requested = True
        
# =============== 外置歌词窗口 ===============
class ExternalLyricsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowOpacity(0.9)
        self.setWindowTitle("歌词 - Railgun_lover")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(800, 200)
        
        # 中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 歌词标签 - 使用双行显示
        self.lyrics_layout = QVBoxLayout()
        self.lyrics_layout.setSpacing(10)
        self.lyrics_layout.setContentsMargins(20, 20, 20, 20)

        # 创建翻译标签
        self.translation_label = QLabel("")
        self.translation_label.setAlignment(Qt.AlignCenter)
        self.translation_label.setStyleSheet("font-size: 20px; color: #AAAAAA;")
        self.translation_label.setWordWrap(True)
        
        # 将翻译标签添加到布局
        self.lyrics_layout.addWidget(self.translation_label)
        
        # 当前行标签
        self.current_line_label = QLabel("")
        self.current_line_label.setAlignment(Qt.AlignCenter)
        self.current_line_label.setStyleSheet("font-size: 36px; font-weight: bold; color: white;")
        
        # 下一行标签
        self.next_line_label = QLabel("")
        self.next_line_label.setAlignment(Qt.AlignCenter)
        self.next_line_label.setStyleSheet("font-size: 24px; color: #AAAAAA;")
        
        # 添加标签到布局
        self.lyrics_layout.addWidget(self.current_line_label)
        self.lyrics_layout.addWidget(self.next_line_label)
        layout.addLayout(self.lyrics_layout)
        
        # 初始位置（屏幕底部中央）
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(
            (screen_geometry.width() - 800) // 2,
            screen_geometry.height() - 200,  # 降低位置
            800,
            200  # 增加高度以适应双行歌词
        )
        
        # 右键菜单
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

        # 歌词数据
        self.lyrics_data = []
        self.current_line_index = -1
        self.word_positions = []
        self.karaoke_progress = 0

        # 添加默认样式属性
        self.normal_color = QColor("#FFFFFF")
        self.highlight_color = QColor("#000000")
        self.next_line_color = QColor("#AAAAAA")
        self.font = QFont("Microsoft YaHei", 36)

        # 添加歌词设置属性
        self.lyrics_settings = {}
        
        # 应用保存的样式设置
        self.apply_style_settings()

        # 添加锁定状态属性
        self.locked = False
        
    def update_style(self, font=None, color=None, opacity=None):
        """更新歌词样式"""
        # 应用字体
        if font:
            self.font = font
            self.current_line_label.setFont(font)
            
            # 调整下一行字体大小
            smaller_font = QFont(font)
            smaller_font.setPointSize(int(font.pointSize() * 0.8))
            self.next_line_label.setFont(smaller_font)
        
        # 应用颜色
        if color:
            self.normal_color = QColor(color)
            self.current_line_label.setStyleSheet(f"color: {color};")
            # 下一行使用较浅的颜色
            self.next_line_color = QColor(self.normal_color)
            self.next_line_color.setAlpha(180)  # 设置透明度
            self.next_line_label.setStyleSheet(f"color: {self.next_line_color.name()};")
        
        # 应用透明度
        if opacity is not None:
            self.setWindowOpacity(opacity / 100.0)
        
        # 保存设置
        self.save_lyrics_settings()
    
    def apply_preset(self, preset_name):
        """应用预设主题"""
        presets = {
            "default": {
                "normal_color": "#FFFFFF",
                "highlight_color": "#FF5722",
                "next_line_color": "#AAAAAA",
                "effect_type": "fill"
            },
            "dark": {
                "normal_color": "#CCCCCC",
                "highlight_color": "#4CAF50",
                "next_line_color": "#888888",
                "effect_type": "outline",
                "outline_size": 3
            },
            "vibrant": {
                "normal_color": "#FFFFFF",
                "highlight_color": "#FF4081",
                "next_line_color": "#B39DDB",
                "effect_type": "glow",
                "glow_size": 15
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            self.lyrics_settings.update(preset)
            self.apply_style_settings()
            self.save_lyrics_settings()
    
    def toggle_lock(self):
        """切换窗口锁定状态"""
        self.locked = not self.locked
        self.lyrics_settings["locked"] = self.locked
        self.save_lyrics_settings()
    
    def set_effect(self, effect_type):
        """设置歌词效果"""
        self.effect_type = effect_type
        self.lyrics_settings["effect_type"] = effect_type
        
        # 保存效果参数
        if effect_type == "outline":
            size, ok = QInputDialog.getInt(self, "描边大小", "输入描边大小(1-5):", 
                                          self.lyrics_settings.get("outline_size", 2), 1, 5)
            if ok:
                self.outline_size = size
                self.lyrics_settings["outline_size"] = size
        elif effect_type == "glow":
            size, ok = QInputDialog.getInt(self, "发光大小", "输入发光大小(5-20):", 
                                          self.lyrics_settings.get("glow_size", 10), 5, 20)
            if ok:
                self.glow_size = size
                self.lyrics_settings["glow_size"] = size
        
        self.apply_style_settings()
        self.save_lyrics_settings()
    
    def set_opacity(self):
        """设置歌词窗口透明度"""
        current_opacity = int(self.windowOpacity() * 100)
        opacity, ok = QInputDialog.getInt(self, "设置透明度", "透明度 (0-100):", 
                                         current_opacity, 0, 100)
        if ok:
            self.setWindowOpacity(opacity / 100.0)
            self.lyrics_settings["opacity"] = opacity
            self.save_lyrics_settings()
    
    def reset_position(self):
        """重置歌词窗口位置到屏幕底部中央"""
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(
            (screen_geometry.width() - 800) // 2,
            screen_geometry.height() - 200,
            800,
            200
        )
        self.save_lyrics_settings()
    
    def save_lyrics_settings(self):
        """保存歌词窗口设置"""
        settings = load_settings()
        lyrics_settings = settings.get("external_lyrics", {})
        
        # 保存几何信息
        lyrics_settings["geometry"] = self.saveGeometry().toHex().data().decode()
        
        # 保存字体信息（使用当前行标签的字体）
        lyrics_settings["font"] = self.current_line_label.font().toString()
        
        # 保存颜色信息（这里保存的是当前行标签的颜色）
        lyrics_settings["color"] = self.current_line_label.palette().color(QPalette.WindowText).name()
        
        # 保存透明度
        lyrics_settings["opacity"] = int(self.windowOpacity() * 100)
        
        # 保存显示状态
        lyrics_settings["show_lyrics"] = self.isVisible()

        settings["external_lyrics"] = lyrics_settings
        save_settings(settings)
    
    def apply_style_settings(self):
        """应用保存的样式设置"""
        settings = load_settings()
        self.lyrics_settings = settings.get("external_lyrics", {})
        
        # 加载字体信息
        font_str = self.lyrics_settings.get("font", "Microsoft YaHei,36")
        self.font = QFont()
        self.font.fromString(font_str)
        # 应用字体
        self.current_line_label.setFont(self.font)
        # 调整下一行字体大小
        smaller_font = QFont(self.font)
        smaller_font.setPointSize(int(self.font.pointSize() * 0.8))
        self.next_line_label.setFont(smaller_font)
        
        # 加载颜色信息
        self.normal_color = QColor(self.lyrics_settings.get("normal_color", "#FFFFFF"))
        self.highlight_color = QColor(self.lyrics_settings.get("highlight_color", "#000000"))
        self.next_line_color = QColor(self.lyrics_settings.get("next_line_color", "#AAAAAA"))
        
        # 加载效果设置
        self.effect_type = self.lyrics_settings.get("effect_type", "fill")  # fill, outline, glow
        self.outline_size = self.lyrics_settings.get("outline_size", 2)
        self.glow_size = self.lyrics_settings.get("glow_size", 10)
        
        # 加载锁定状态
        self.locked = self.lyrics_settings.get("locked", False)
        
        # 应用样式
        self.apply_font_style()
        
        # 窗口透明度
        opacity = self.lyrics_settings.get("opacity", 80) / 100.0
        self.setWindowOpacity(opacity)

    def apply_font_style(self):
        """应用字体样式到标签"""
        # 当前行样式
        if self.effect_type == "fill":
            style = f"""
                QLabel {{
                    font-family: '{self.font.family()}';
                    font-size: {self.font.pointSize()}px;
                    font-weight: bold;
                    color: {self.highlight_color.name()};
                    background-color: transparent;
                }}
            """
        elif self.effect_type == "outline":
            style = f"""
                QLabel {{
                    font-family: '{self.font.family()}';
                    font-size: {self.font.pointSize()}px;
                    font-weight: bold;
                    color: {self.highlight_color.name()};
                    background-color: transparent;
                    text-outline: {self.outline_size}px {self.normal_color.name()};
                }}
            """
        else:  # glow
            style = f"""
                QLabel {{
                    font-family: '{self.font.family()}';
                    font-size: {self.font.pointSize()}px;
                    font-weight: bold;
                    color: {self.highlight_color.name()};
                    background-color: transparent;
                    text-shadow: 0px 0px {self.glow_size}px {self.normal_color.name()};
                }}
            """
        self.current_line_label.setStyleSheet(style)
        
        # 下一行样式
        self.next_line_label.setStyleSheet(f"""
            QLabel {{
                font-family: '{self.font.family()}';
                font-size: {int(self.font.pointSize() * 0.8)}px;
                color: {self.next_line_color.name()};
                background-color: transparent;
            }}
        """)

    def show_context_menu(self, pos):
        """显示歌词窗口的右键菜单"""
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
        """)
        
        # 字体设置
        font_action = QAction("设置字体", self)
        font_action.triggered.connect(self.set_font)
        menu.addAction(font_action)
        
        # 颜色设置
        color_menu = QMenu("设置颜色", self)
        
        normal_color_action = QAction("普通颜色", self)
        normal_color_action.triggered.connect(lambda: self.set_color("normal"))
        
        highlight_color_action = QAction("高亮颜色", self)
        highlight_color_action.triggered.connect(lambda: self.set_color("highlight"))
        
        next_line_color_action = QAction("下一行颜色", self)
        next_line_color_action.triggered.connect(lambda: self.set_color("next_line"))
        
        color_menu.addAction(normal_color_action)
        color_menu.addAction(highlight_color_action)
        color_menu.addAction(next_line_color_action)
        menu.addMenu(color_menu)
        
        # 效果设置
        effect_menu = QMenu("设置效果", self)
        
        fill_effect_action = QAction("填充效果", self)
        fill_effect_action.triggered.connect(lambda: self.set_effect("fill"))
        
        outline_effect_action = QAction("描边效果", self)
        outline_effect_action.triggered.connect(lambda: self.set_effect("outline"))
        
        glow_effect_action = QAction("发光效果", self)
        glow_effect_action.triggered.connect(lambda: self.set_effect("glow"))
        
        effect_menu.addAction(fill_effect_action)
        effect_menu.addAction(outline_effect_action)
        effect_menu.addAction(glow_effect_action)
        menu.addMenu(effect_menu)
        
        # 透明度设置
        opacity_action = QAction("设置透明度", self)
        opacity_action.triggered.connect(self.set_opacity)
        menu.addAction(opacity_action)
        
        # 锁定/解锁
        lock_action = QAction("锁定位置" if not self.locked else "解锁位置", self)
        lock_action.triggered.connect(self.toggle_lock)
        menu.addAction(lock_action)
        
        # 预设主题
        preset_menu = QMenu("预设主题", self)
        
        default_preset = QAction("默认主题", self)
        default_preset.triggered.connect(lambda: self.apply_preset("default"))
        
        dark_preset = QAction("暗黑主题", self)
        dark_preset.triggered.connect(lambda: self.apply_preset("dark"))
        
        vibrant_preset = QAction("活力主题", self)
        vibrant_preset.triggered.connect(lambda: self.apply_preset("vibrant"))
        
        preset_menu.addAction(default_preset)
        preset_menu.addAction(dark_preset)
        preset_menu.addAction(vibrant_preset)
        menu.addMenu(preset_menu)
        
        menu.addSeparator()
        
        # 重置位置
        reset_action = QAction("重置位置", self)
        reset_action.triggered.connect(self.reset_position)
        menu.addAction(reset_action)
        
        menu.exec_(self.mapToGlobal(pos))
    
    def apply_preset(self, preset_name):
        """应用预设主题"""
        presets = {
            "default": {
                "normal_color": "#FFFFFF",
                "highlight_color": "#FF5722",
                "next_line_color": "#AAAAAA",
                "effect_type": "fill"
            },
            "dark": {
                "normal_color": "#CCCCCC",
                "highlight_color": "#4CAF50",
                "next_line_color": "#888888",
                "effect_type": "outline",
                "outline_size": 3
            },
            "vibrant": {
                "normal_color": "#FFFFFF",
                "highlight_color": "#FF4081",
                "next_line_color": "#B39DDB",
                "effect_type": "glow",
                "glow_size": 15
            }
        }
        
        if preset_name in presets:
            preset = presets[preset_name]
            self.lyrics_settings.update(preset)
            self.apply_style_settings()
            self.save_lyrics_settings()
    
    def toggle_lock(self):
        """切换窗口锁定状态"""
        self.locked = not self.locked
        self.lyrics_settings["locked"] = self.locked
        self.save_lyrics_settings()
    
    def set_font(self):
        """设置歌词字体"""
        # 获取当前字体
        current_font = self.current_line_label.font()
    
        # 打开字体对话框
        font, ok = QFontDialog.getFont(current_font, self, "选择歌词字体")
    
        if ok:
            # 用户点击了OK，应用新字体
            self.font = font
            self.current_line_label.setFont(font)
        
            # 调整下一行字体大小
            smaller_font = QFont(font)
            smaller_font.setPointSize(int(font.pointSize() * 0.8))
            self.next_line_label.setFont(smaller_font)
        
            # 保存设置
            self.save_lyrics_settings()
        
    def set_color(self, color_type):
        """设置特定类型的歌词颜色"""
        if color_type == "normal":
            current_color = QColor(self.normal_color)
            dialog_title = "选择普通歌词颜色"
        elif color_type == "highlight":
            current_color = QColor(self.highlight_color)
            dialog_title = "选择高亮歌词颜色"
        else:  # next_line
            current_color = QColor(self.next_line_color)
            dialog_title = "选择下一行歌词颜色"
        
        color = QColorDialog.getColor(current_color, self, dialog_title)
        if color.isValid():
            if color_type == "normal":
                self.normal_color = color
                self.lyrics_settings["normal_color"] = color.name()
            elif color_type == "highlight":
                self.highlight_color = color
                self.lyrics_settings["highlight_color"] = color.name()
            else:  # next_line
                self.next_line_color = color
                self.lyrics_settings["next_line_color"] = color.name()
            
            self.apply_style_settings()
            self.save_lyrics_settings()
    
    def set_effect(self, effect_type, outline_size=None, glow_size=None):
        """设置歌词效果"""
        self.effect_type = effect_type
        self.lyrics_settings["effect_type"] = effect_type
        if outline_size:
            self.outline_size = outline_size
        if glow_size:
            self.glow_size = glow_size
        self.apply_font_style()
        
        # 保存效果参数
        if effect_type == "outline":
            size, ok = QInputDialog.getInt(self, "描边大小", "输入描边大小(1-5):", 
                                          self.lyrics_settings.get("outline_size", 2), 1, 5)
            if ok:
                self.outline_size = size
                self.lyrics_settings["outline_size"] = size
        elif effect_type == "glow":
            size, ok = QInputDialog.getInt(self, "发光大小", "输入发光大小(5-20):", 
                                          self.lyrics_settings.get("glow_size", 10), 5, 20)
            if ok:
                self.glow_size = size
                self.lyrics_settings["glow_size"] = size
        
        self.apply_style_settings()
        self.save_lyrics_settings()
    
    def set_opacity(self):
        """设置歌词窗口透明度"""
        current_opacity = int(self.windowOpacity() * 100)
        opacity, ok = QInputDialog.getInt(self, "设置透明度", "透明度 (0-100):", 
                                         current_opacity, 0, 100)
        if ok:
            self.setWindowOpacity(opacity / 100.0)
            self.lyrics_settings["opacity"] = opacity
            self.save_lyrics_settings()
    
    def reset_position(self):
        """重置歌词窗口位置到屏幕底部中央"""
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(
            (screen_geometry.width() - self.width()) // 2,
            screen_geometry.height() - self.height(),
            self.width(),
            self.height()
        )
        self.save_lyrics_settings()
    
    def load_lyrics(self, lyrics_text):
        """加载歌词并解析时间标签"""
        self.lyrics_data = []
        lines = lyrics_text.splitlines()
        pattern = re.compile(r'\[(\d+):(\d+\.\d+)\](.*)')
        
        for line in lines:
            match = pattern.match(line)
            if match:
                minutes = int(match.group(1))
                seconds = float(match.group(2))
                time_ms = int((minutes * 60 + seconds) * 1000)
                text = match.group(3).strip()
                self.lyrics_data.append((time_ms, text))
        
        # 按时间排序
        self.lyrics_data.sort(key=lambda x: x[0])
        self.current_line_index = -1
        self.word_positions = []

    def update_lyrics(self, current_line, next_line="", translation_line=""):
        """更新歌词显示"""
        # 检查标签对象是否仍然存在
        if not self.current_line_label or not self.next_line_label:
            return
            
        try:
            self.current_line_label.setText(current_line)
            # 翻译行
            if translation_line:
                self.translation_label.setText(translation_line)
                self.translation_label.show()
            else:
                self.translation_label.hide()
            self.next_line_label.setText(next_line)
            
            # 如果歌词为空，隐藏窗口
            if not current_line:
                self.hide()
            else:
                self.show()
        except RuntimeError as e:
            # 如果对象已被删除，则重新创建标签
            if "wrapped C/C++ object" in str(e):
                logger.warning("歌词标签对象已被删除，重新初始化")
                self.init_ui()
            else:
                logger.error(f"更新歌词失败: {str(e)}")
    
    def calculate_word_positions(self, text, position):
        """计算歌词中每个字的位置和持续时间（简化版）"""
        self.word_positions = []
        if not text:
            return
        
        # 假设每个字平均分配时间
        start_time = self.lyrics_data[self.current_line_index][0]
        end_time = self.lyrics_data[self.current_line_index + 1][0] if self.current_line_index + 1 < len(self.lyrics_data) else start_time + 5000
        
        total_chars = len(text)
        duration_per_char = (end_time - start_time) / max(1, total_chars)
        
        for i in range(total_chars):
            char_start = start_time + i * duration_per_char
            char_end = char_start + duration_per_char
            self.word_positions.append((char_start, char_end))
    
    def update_karaoke_effect(self, position):
        """更新卡拉OK效果"""
        if not self.word_positions:
            return
        
        current_text = self.lyrics_data[self.current_line_index][1]
        styled_text = self.get_styled_text(current_text, position)
        self.current_line_label.setText(styled_text)
    
    def get_styled_text(self, text, position):
        """获取带样式的歌词文本（卡拉OK效果）"""
        if not self.word_positions or len(self.word_positions) != len(text):
            return text
        
        # 找出当前播放到的字符位置
        current_char_idx = 0
        for i, (char_start, char_end) in enumerate(self.word_positions):
            if position >= char_start:
                current_char_idx = i
            else:
                break
        
        # 创建带样式的HTML
        styled_text = ""
        for i, char in enumerate(text):
            if i < current_char_idx:
                # 已播放部分 - 高亮颜色
                styled_text += f'<span style="color: {self.highlight_color.name()};">{char}</span>'
            elif i == current_char_idx:
                # 当前播放字 - 添加过渡效果
                # 计算当前字内的进度 (0-1)
                char_start, char_end = self.word_positions[i]
                if char_end > char_start:
                    progress = (position - char_start) / (char_end - char_start)
                    progress = max(0, min(1, progress))  # 限制在0-1范围
                    
                    # 创建渐变效果 (从高亮色到普通色)
                    r1, g1, b1, _ = self.highlight_color.getRgb()
                    r2, g2, b2, _ = self.normal_color.getRgb()
                    
                    r = int(r1 + (r2 - r1) * progress)
                    g = int(g1 + (g2 - g1) * progress)
                    b = int(b1 + (b2 - b1) * progress)
                    color = QColor(r, g, b)
                    
                    styled_text += f'<span style="color: {color.name()};">{char}</span>'
                else:
                    styled_text += f'<span style="color: {self.highlight_color.name()};">{char}</span>'
            else:
                # 未播放部分 - 普通颜色
                styled_text += f'<span style="color: {self.normal_color.name()};">{char}</span>'
        
        return styled_text
        
        # 设置更大的初始尺寸以容纳长歌词
        self.setMinimumSize(1000, 300)

    # =============== 事件处理 ===============
    def mousePressEvent(self, event):
        """鼠标按下事件 - 开始拖拽"""
        if event.button() == Qt.LeftButton and not self.locked:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件 - 拖拽窗口"""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position') and not self.locked:
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        """鼠标双击事件 - 切换锁定状态"""
        self.toggle_lock()
    
    def closeEvent(self, event):
        """重写关闭事件，确保窗口能被完全关闭"""
        logger.info("外置歌词窗口关闭")
        self.save_lyrics_settings()
        event.accept()

class SQLiteDatabase:
    """简化的SQLite数据库封装类"""
    def __init__(self, db_path):
        self.conn = sqlite3.connect(db_path)
        self.cursor = self.conn.cursor()
        
    def create_table(self, sql):
        self.cursor.execute(sql)
        self.conn.commit()
        
    def execute(self, sql, params=()):
        self.cursor.execute(sql, params)
        self.conn.commit()
        
    def query(self, sql, params=()):
        self.cursor.execute(sql, params)
        return self.cursor.fetchall()
        
    def __del__(self):
        self.conn.close()

class UserBehaviorAnalyzer:
    def __init__(self):
        self.db = SQLiteDatabase("user_behavior.db")
        self.db.create_table("""
            CREATE TABLE IF NOT EXISTS user_behavior (
                id INTEGER PRIMARY KEY,
                user_id TEXT NOT NULL,
                song_id TEXT NOT NULL,
                action_type TEXT NOT NULL,  -- PLAY, LIKE, SKIP, DOWNLOAD
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                play_duration INTEGER  -- 播放时长(毫秒)
            )
        """)
    
    def log_behavior(self, user_id, song_id, action, duration=0):
        # 记录用户行为
        self.db.execute(
            "INSERT INTO user_behavior (user_id, song_id, action_type, play_duration) VALUES (?, ?, ?, ?)",
            (user_id, song_id, action, duration)
        )
    
    def get_user_preferences(self, user_id):
        # 分析用户偏好
        result = self.db.query("""
            SELECT songs.genre, songs.artist, AVG(play_duration) as avg_duration, 
                   COUNT(*) as play_count
            FROM user_behavior
            JOIN songs ON user_behavior.song_id = songs.id
            WHERE user_id = ? AND action_type = 'PLAY'
            GROUP BY songs.genre, songs.artist
            ORDER BY play_count DESC, avg_duration DESC
            LIMIT 5
        """, (user_id,))
        return result
    
class AudioFeatureExtractor:
    """音频特征提取器"""
    def extract_features(self, audio_path):
        """提取音频特征"""
        if not AUDIO_FEATURES_ENABLED:
            return {}
        
        # 使用librosa分析音频特征
        y, sr = librosa.load(audio_path)
        
        return {
            "tempo": librosa.beat.tempo(y=y, sr=sr)[0],
            "key": librosa.feature.tonnetz(y=y, sr=sr).mean(axis=1),
            "energy": librosa.feature.rms(y=y).mean(),
            "danceability": librosa.feature.tempogram(y=y, sr=sr).mean(),
            "mood": self.detect_mood(y, sr)
        }
    
    def detect_mood(self, audio, sr):
        """检测情绪"""
        if not AUDIO_FEATURES_ENABLED:
            return "unknown"
        
        # 简化实现，实际应使用预训练模型
        return "neutral"
    
class RecommendationEngine:
    def __init__(self):
        self.analyzer = UserBehaviorAnalyzer()
        self.feature_extractor = AudioFeatureExtractor()
    
    def recommend_songs(self, user_id, current_song=None, limit=10):
        # 1. 基于用户偏好
        preferences = self.analyzer.get_user_preferences(user_id)
        pref_recommendations = self.get_recommendations_by_preferences(preferences, limit//2)
        
        # 2. 基于当前歌曲
        context_recommendations = []
        if current_song:
            current_features = self.feature_extractor.extract_features(current_song.path)
            context_recommendations = self.get_similar_songs(current_features, limit//2)
        
        # 3. 混合推荐结果
        combined = list(set(pref_recommendations + context_recommendations))
        return combined[:limit]
    
    def get_recommendations_by_preferences(self, preferences, limit):
        # 根据用户偏好查询数据库
        # 实际实现应使用更复杂的算法
        return random.sample(self.song_database, limit)
    
    def get_similar_songs(self, features, limit):
        # 使用余弦相似度查找相似歌曲
        similarities = []
        for song in self.song_database:
            sim = cosine_similarity(features, song.features)
            similarities.append((song, sim))
        
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [song for song, _ in similarities[:limit]]

class RecommendationTab(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.layout = QVBoxLayout()
        
        # 推荐类型选择
        self.recommend_type = QComboBox()
        self.recommend_type.addItems(["为你推荐", "相似歌曲", "新歌推荐", "经典歌曲"])
        self.layout.addWidget(self.recommend_type)
        
        # 推荐结果列表
        self.recommend_list = QListWidget()
        self.recommend_list.itemClicked.connect(self.play_recommended)
        self.layout.addWidget(self.recommend_list)
        
        # 刷新按钮
        self.refresh_btn = QPushButton("刷新推荐")
        self.refresh_btn.clicked.connect(self.refresh_recommendations)
        self.layout.addWidget(self.refresh_btn)
        
        self.setLayout(self.layout)
    
    def refresh_recommendations(self):
        user_id = self.parent().current_user
        recommendations = self.parent().recommend_engine.recommend_songs(user_id)
        
        self.recommend_list.clear()
        for song in recommendations:
            item = QListWidgetItem(f"{song.name} - {song.artist}")
            item.setData(Qt.UserRole, song)
            self.recommend_list.addItem(item)
    
    def play_recommended(self, item):
        song = item.data(Qt.UserRole)
        self.parent().play_song(song)

class SmartPlaylistManager:
    """智能播放列表管理器"""
    
    class SmartPlaylist:
        """智能播放列表类"""
        def __init__(self, name, rules):
            self.name = name
            self.rules = rules
            self.songs = []
            self.last_updated = None
            
        def update(self):
            """根据规则更新播放列表"""
            # 这里需要实现实际的查询逻辑
            # 示例：从数据库查询符合条件的歌曲
            query = "SELECT * FROM songs WHERE "
            conditions = []
            params = []
            
            for field, operator, value in self.rules:
                if operator == "==":
                    conditions.append(f"{field} = ?")
                elif operator == ">":
                    conditions.append(f"{field} > ?")
                elif operator == "<":
                    conditions.append(f"{field} < ?")
                elif operator == "contains":
                    conditions.append(f"{field} LIKE ?")
                    value = f"%{value}%"
                
                params.append(value)
            
            query += " AND ".join(conditions)
            # 实际应用中需要连接数据库执行查询
            # self.songs = database.query(query, params)
            self.last_updated = datetime.now()
    
    def __init__(self):
        self.playlists = {}
        self.current_playlist = None
        self.playlist_file = "playlists.json"
        # 创建数据库连接
        self.db = self.create_database_connection()
        self.load_playlists()
        
    def create_database_connection(self):
        """创建数据库连接"""
        # 这里简化实现，实际应使用SQLite或其它数据库
        return {
            "query": lambda sql, params: []
        }
        
    def create_smart_playlist(self, name, rules):
        """创建智能播放列表"""
        playlist = self.SmartPlaylist(name, rules)
        self.playlists[name] = playlist
        self.save_playlists()
        return playlist

class AdvancedPlaylistDialog(QDialog):
    def __init__(self, playlist_manager):
        super().__init__()
        self.setWindowTitle("高级播放列表管理")
        self.setMinimumSize(800, 600)
        
        layout = QVBoxLayout()
        
        # 播放列表标签页
        self.tabs = QTabWidget()
        self.playlist_tab = self.create_playlist_tab()
        self.smart_playlist_tab = self.create_smart_playlist_tab()
        self.tabs.addTab(self.playlist_tab, "普通列表")
        self.tabs.addTab(self.smart_playlist_tab, "智能列表")
        layout.addWidget(self.tabs)
        
        # 按钮区域
        btn_layout = QHBoxLayout()
        self.export_btn = QPushButton("导出播放列表")
        self.import_btn = QPushButton("导入播放列表")
        self.sync_btn = QPushButton("云同步")
        btn_layout.addWidget(self.export_btn)
        btn_layout.addWidget(self.import_btn)
        btn_layout.addWidget(self.sync_btn)
        layout.addLayout(btn_layout)
        
        self.setLayout(layout)
    
    def create_playlist_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 播放列表树状视图
        self.playlist_tree = QTreeWidget()
        self.playlist_tree.setHeaderLabels(["播放列表", "歌曲数量", "类型"])
        self.playlist_tree.itemDoubleClicked.connect(self.edit_playlist)
        layout.addWidget(self.playlist_tree)
        
        # 列表操作按钮
        btn_row = QHBoxLayout()
        self.new_btn = QPushButton("新建列表")
        self.edit_btn = QPushButton("编辑列表")
        self.delete_btn = QPushButton("删除列表")
        self.auto_cat_btn = QPushButton("自动分类")
        btn_row.addWidget(self.new_btn)
        btn_row.addWidget(self.edit_btn)
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.auto_cat_btn)
        layout.addLayout(btn_row)
        
        widget.setLayout(layout)
        return widget
    
    def create_smart_playlist_tab(self):
        widget = QWidget()
        layout = QVBoxLayout()
        
        # 规则表格
        self.rules_table = QTableWidget(0, 4)
        self.rules_table.setHorizontalHeaderLabels(["字段", "运算符", "值", "操作"])
        layout.addWidget(self.rules_table)
        
        # 添加规则按钮
        self.add_rule_btn = QPushButton("添加规则")
        self.add_rule_btn.clicked.connect(self.add_rule_row)
        layout.addWidget(self.add_rule_btn)
        
        # 智能列表预览
        self.preview_list = QListWidget()
        layout.addWidget(self.preview_list)
        
        widget.setLayout(layout)
        return widget
    
    def add_rule_row(self):
        row = self.rules_table.rowCount()
        self.rules_table.insertRow(row)
        
        # 字段下拉框
        field_combo = QComboBox()
        field_combo.addItems(["风格", "艺术家", "专辑", "年份", "播放次数", "评分"])
        self.rules_table.setCellWidget(row, 0, field_combo)
        
        # 运算符下拉框
        op_combo = QComboBox()
        op_combo.addItems(["==", "!=", ">", "<", "包含", "不包含"])
        self.rules_table.setCellWidget(row, 1, op_combo)
        
        # 值输入框
        value_edit = QLineEdit()
        self.rules_table.setCellWidget(row, 2, value_edit)
        
        # 删除按钮
        del_btn = QPushButton("删除")
        del_btn.clicked.connect(lambda: self.delete_rule_row(row))
        self.rules_table.setCellWidget(row, 3, del_btn)
    
    def delete_rule_row(self, row):
        self.rules_table.removeRow(row)
    
    def update_preview(self):
        """根据当前规则更新预览列表"""
        rules = []
        for row in range(self.rules_table.rowCount()):
            field = self.rules_table.cellWidget(row, 0).currentText()
            op = self.rules_table.cellWidget(row, 1).currentText()
            value = self.rules_table.cellWidget(row, 2).text()
            rules.append((field, op, value))
        
        playlist = self.playlist_manager.create_temp_smart_playlist("预览", rules)
        playlist.update()
        
        self.preview_list.clear()
        for song in playlist.songs:
            self.preview_list.addItem(f"{song.name} - {song.artist}")

# =============== 音乐室功能实现 ===============
class MusicRoomManager:
    """音乐室管理器"""
    def __init__(self, parent):
        self.parent = parent
        self.current_room = None
        self.server_url = "ws://127.0.0.1:5001"  # 使用本地IP和端口
        self.websocket = None
        self.connected = False
        self.room_list = []
        self.user_list = []
        
    def connect_to_server(self):
        """连接到音乐室服务器"""
        if self.connected:
            return True
            
        try:
            self.websocket = QWebSocket()
            self.websocket.connected.connect(self.on_connected)
            self.websocket.disconnected.connect(self.on_disconnected)
            self.websocket.textMessageReceived.connect(self.on_message_received)
            self.websocket.error.connect(self.on_error)
            self.websocket.open(QUrl(self.server_url))
            return True
        except Exception as e:
            logger.error(f"连接音乐室服务器失败: {str(e)}")
            return False
    
    def on_connected(self):
        """连接成功回调"""
        self.connected = True
        logger.info("成功连接到音乐室服务器")
        self.parent.status_bar.showMessage("已连接到音乐室服务器")
        
        # 发送用户身份信息
        user_id = self.parent.settings.get("user_id", "anonymous")
        message = {
            "type": "auth",
            "user_id": user_id
        }
        self.send_message(json.dumps(message))
    
    def on_disconnected(self):
        """连接断开回调"""
        self.connected = False
        logger.warning("与音乐室服务器的连接已断开")
        self.parent.status_bar.showMessage("音乐室连接已断开")
    
    def on_error(self, error):
        """错误处理"""
        logger.error(f"音乐室连接错误: {str(error)}")
        self.parent.status_bar.showMessage(f"音乐室错误: {str(error)}")
    
    def on_message_received(self, message):
        """处理接收到的消息"""
        try:
            data = json.loads(message)
            message_type = data.get("type")
            
            if message_type == "room_list":
                self.room_list = data.get("rooms", [])
                self.parent.update_room_list(self.room_list)
                
            elif message_type == "user_list":
                self.user_list = data.get("users", [])
                self.parent.update_user_list(self.user_list)
                
            elif message_type == "room_update":
                self.handle_room_update(data)
                
            elif message_type == "chat":
                self.parent.add_chat_message(
                    data.get("user_id", "未知用户"),
                    data.get("message", ""),
                    data.get("timestamp", int(time.time()))
                )
                
            elif message_type == "playback":
                self.handle_playback_command(data)
                
            elif message_type == "error":
                logger.error(f"音乐室错误: {data.get('message', '未知错误')}")
                self.parent.status_bar.showMessage(f"音乐室错误: {data.get('message', '未知错误')}")
                
        except Exception as e:
            logger.error(f"处理音乐室消息失败: {str(e)}")
    
    def handle_room_update(self, data):
        """处理房间更新"""
        room_id = data.get("room_id")
        action = data.get("action")
        
        if action == "created":
            self.room_list.append({
                "id": room_id,
                "name": data.get("name", "未命名房间"),
                "owner": data.get("owner", "未知"),
                "users": data.get("users", [])
            })
            self.parent.update_room_list(self.room_list)
            
        elif action == "closed":
            self.room_list = [r for r in self.room_list if r["id"] != room_id]
            self.parent.update_room_list(self.room_list)
            
            # 如果当前房间关闭
            if self.current_room and self.current_room["id"] == room_id:
                self.current_room = None
                self.parent.leave_room()
                
        elif action == "user_joined":
            for room in self.room_list:
                if room["id"] == room_id:
                    if data["user_id"] not in room["users"]:
                        room["users"].append(data["user_id"])
                    self.parent.update_room_list(self.room_list)
                    break
                    
        elif action == "user_left":
            for room in self.room_list:
                if room["id"] == room_id:
                    if data["user_id"] in room["users"]:
                        room["users"].remove(data["user_id"])
                    self.parent.update_room_list(self.room_list)
                    break
    
    def handle_playback_command(self, data):
        """处理播放控制命令"""
        if not self.current_room or self.current_room["id"] != data.get("room_id"):
            return
            
        command = data.get("command")
        user_id = data.get("user_id")
        
        if user_id == self.parent.settings.get("user_id"):
            return  # 忽略自己发送的命令
            
        if command == "play":
            self.parent.media_player.play()
        elif command == "pause":
            self.parent.media_player.pause()
        elif command == "stop":
            self.parent.media_player.stop()
        elif command == "next":
            self.parent.play_next()
        elif command == "prev":
            self.parent.play_previous()
        elif command == "seek":
            position = data.get("position", 0)
            self.parent.media_player.setPosition(position)
        elif command == "volume":
            volume = data.get("volume", 50)
            self.parent.media_player.setVolume(volume)
        elif command == "load_song":
            song_path = data.get("song_path")
            if song_path and os.path.exists(song_path):
                self.parent.play_file(song_path)
    
    def send_message(self, message):
        """发送消息到服务器"""
        if self.connected and self.websocket:
            self.websocket.sendTextMessage(message)
    
    def create_room(self, room_name):
        """创建听歌房"""
        if not self.connected:
            return False
            
        message = {
            "type": "create_room",
            "name": room_name,
            "user_id": self.parent.settings.get("user_id", "anonymous")
        }
        self.send_message(json.dumps(message))
        return True
    
    def join_room(self, room_id):
        """加入听歌房"""
        if not self.connected:
            return False
            
        # 获取当前房间信息
        room = next((r for r in self.room_list if r["id"] == room_id), None)
        if not room:
            return False
            
        message = {
            "type": "join_room",
            "room_id": room_id,
            "user_id": self.parent.settings.get("user_id", "anonymous")
        }
        self.send_message(json.dumps(message))
        
        # 更新当前房间
        self.current_room = room
        return True
    
    def leave_room(self):
        """离开当前房间"""
        if not self.connected or not self.current_room:
            return False
            
        message = {
            "type": "leave_room",
            "room_id": self.current_room["id"],
            "user_id": self.parent.settings.get("user_id", "anonymous")
        }
        self.send_message(json.dumps(message))
        
        self.current_room = None
        return True
    
    def send_chat_message(self, message):
        """发送聊天消息"""
        if not self.connected or not self.current_room:
            return False
            
        msg_data = {
            "type": "chat",
            "room_id": self.current_room["id"],
            "user_id": self.parent.settings.get("user_id", "anonymous"),
            "message": message,
            "timestamp": int(time.time())
        }
        self.send_message(json.dumps(msg_data))
        return True
    
    def send_playback_command(self, command, **kwargs):
        """发送播放控制命令"""
        if not self.connected or not self.current_room:
            return False
            
        msg_data = {
            "type": "playback",
            "room_id": self.current_room["id"],
            "user_id": self.parent.settings.get("user_id", "anonymous"),
            "command": command
        }
        msg_data.update(kwargs)
        self.send_message(json.dumps(msg_data))
        return True


class MusicRoomDialog(QDialog):
    """音乐室对话框"""
    def __init__(self, parent):
        super().__init__(parent)
        self.setWindowTitle("音乐室")
        self.setGeometry(200, 200, 800, 600)
        self.parent = parent
        self.room_manager = parent.room_manager
        self.current_room = None
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 连接状态
        self.status_label = QLabel("未连接")
        layout.addWidget(self.status_label)
        
        # 房间列表
        room_group = QGroupBox("听歌房")
        room_layout = QVBoxLayout()
        
        self.room_list = QListWidget()
        self.room_list.itemDoubleClicked.connect(self.join_selected_room)
        room_layout.addWidget(self.room_list)
        
        # 房间操作按钮
        room_btn_layout = QHBoxLayout()
        self.refresh_btn = QPushButton("刷新")
        self.refresh_btn.clicked.connect(self.refresh_room_list)
        room_btn_layout.addWidget(self.refresh_btn)
        
        self.create_btn = QPushButton("创建房间")
        self.create_btn.clicked.connect(self.create_room)
        room_btn_layout.addWidget(self.create_btn)
        
        self.join_btn = QPushButton("加入房间")
        self.join_btn.setEnabled(False)
        self.join_btn.clicked.connect(self.join_selected_room)
        room_btn_layout.addWidget(self.join_btn)
        
        room_layout.addLayout(room_btn_layout)
        room_group.setLayout(room_layout)
        layout.addWidget(room_group)
        
        # 房间信息
        self.room_info = QGroupBox("房间信息")
        room_info_layout = QVBoxLayout()
        
        self.room_name_label = QLabel("未加入房间")
        room_info_layout.addWidget(self.room_name_label)
        
        self.user_list = QListWidget()
        room_info_layout.addWidget(self.user_list)
        
        self.leave_btn = QPushButton("离开房间")
        self.leave_btn.setEnabled(False)
        self.leave_btn.clicked.connect(self.leave_room)
        room_info_layout.addWidget(self.leave_btn)
        
        self.room_info.setLayout(room_info_layout)
        layout.addWidget(self.room_info)
        
        # 聊天区域
        chat_group = QGroupBox("聊天")
        chat_layout = QVBoxLayout()
        
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        chat_layout.addWidget(self.chat_display)
        
        chat_input_layout = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("输入消息...")
        self.chat_input.returnPressed.connect(self.send_chat)
        chat_input_layout.addWidget(self.chat_input)
        
        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_chat)
        chat_input_layout.addWidget(self.send_btn)
        
        chat_layout.addLayout(chat_input_layout)
        chat_group.setLayout(chat_layout)
        layout.addWidget(chat_group)
        
        # 控制按钮
        control_group = QGroupBox("控制")
        control_layout = QGridLayout()
        
        self.play_btn = QPushButton("播放")
        self.play_btn.clicked.connect(lambda: self.send_play_command("play"))
        control_layout.addWidget(self.play_btn, 0, 0)
        
        self.pause_btn = QPushButton("暂停")
        self.pause_btn.clicked.connect(lambda: self.send_play_command("pause"))
        control_layout.addWidget(self.pause_btn, 0, 1)
        
        self.stop_btn = QPushButton("停止")
        self.stop_btn.clicked.connect(lambda: self.send_play_command("stop"))
        control_layout.addWidget(self.stop_btn, 0, 2)
        
        self.prev_btn = QPushButton("上一首")
        self.prev_btn.clicked.connect(lambda: self.send_play_command("prev"))
        control_layout.addWidget(self.prev_btn, 1, 0)
        
        self.next_btn = QPushButton("下一首")
        self.next_btn.clicked.connect(lambda: self.send_play_command("next"))
        control_layout.addWidget(self.next_btn, 1, 1)
        
        self.volume_label = QLabel("音量:")
        control_layout.addWidget(self.volume_label, 1, 2)
        
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(50)
        self.volume_slider.valueChanged.connect(self.send_volume)
        control_layout.addWidget(self.volume_slider, 1, 3)
        
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)
        
        self.setLayout(layout)
        
        # 连接管理器
        self.connect_to_server()
    
    def connect_to_server(self):
        """连接到服务器"""
        if self.room_manager.connect_to_server():
            self.status_label.setText("正在连接...")
        else:
            self.status_label.setText("连接失败，请重试")
    
    def update_status(self, status):
        """更新连接状态"""
        self.status_label.setText(status)
    
    def update_room_list(self, rooms):
        """更新房间列表"""
        self.room_list.clear()
        for room in rooms:
            item = QListWidgetItem(f"{room['name']} (用户数: {len(room['users'])})")
            item.setData(Qt.UserRole, room["id"])
            self.room_list.addItem(item)
        if hasattr(self, 'music_room_dialog') and self.music_room_dialog:
            self.music_room_dialog.update_room_list(rooms)
        self.join_btn.setEnabled(self.room_list.count() > 0)
    
    def update_user_list(self, users):
        """更新用户列表"""
        if hasattr(self, 'music_room_dialog') and self.music_room_dialog:
            self.music_room_dialog.update_user_list(users)
    
    def add_chat_message(self, user_id, message, timestamp):
        """添加聊天消息"""
        time_str = time.strftime("%H:%M:%S", time.localtime(timestamp))
        self.chat_display.append(f"[{time_str}] {user_id}: {message}")
    
    def refresh_room_list(self):
        """刷新房间列表"""
        if self.room_manager.connected:
            message = {
                "type": "request_room_list"
            }
            self.room_manager.send_message(json.dumps(message))
    
    def create_room(self):
        """创建新房间"""
        room_name, ok = QInputDialog.getText(
            self, "创建房间", "输入房间名称:"
        )
        if ok and room_name:
            if self.room_manager.create_room(room_name):
                QMessageBox.information(self, "成功", f"房间 '{room_name}' 已创建")
            else:
                QMessageBox.warning(self, "错误", "创建房间失败")
    
    def join_selected_room(self):
        """加入选中的房间"""
        selected_item = self.room_list.currentItem()
        if not selected_item:
            return
            
        room_id = selected_item.data(Qt.UserRole)
        if self.room_manager.join_room(room_id):
            self.current_room = next(
                (r for r in self.room_manager.room_list if r["id"] == room_id), 
                None
            )
            if self.current_room:
                self.room_name_label.setText(f"房间: {self.current_room['name']}")
                self.leave_btn.setEnabled(True)
                # 更新用户列表
                self.user_list.clear()
                for user in self.current_room["users"]:
                    self.user_list.addItem(user)
    
    def leave_room(self):
        """离开当前房间"""
        if self.room_manager.leave_room():
            self.current_room = None
            self.room_name_label.setText("未加入房间")
            self.leave_btn.setEnabled(False)
            self.user_list.clear()
    
    def play_file(self, file_path):
        """播放文件（重写以支持音乐室同步）"""
        if self.room_manager.current_room:
            # 如果当前在房间中，通知房间其他成员
            self.room_manager.send_playback_command("load_song", song_path=file_path)
    
    def send_chat(self):
        """发送聊天消息"""
        message = self.chat_input.text().strip()
        if not message:
            return
            
        if self.room_manager.send_chat_message(message):
            self.chat_input.clear()
    
    def send_play_command(self, command):
        """发送播放控制命令"""
        if not self.current_room:
            return
            
        # 如果是加载歌曲命令，需要特殊处理
        if command == "load_song":
            file_path = self.parent.current_song_path
            if not file_path:
                return
            self.room_manager.send_playback_command("load_song", song_path=file_path)
        else:
            self.room_manager.send_playback_command(command)
    
    def send_volume(self, value):
        """发送音量控制命令"""
        if not self.current_room:
            return
            
        self.room_manager.send_playback_command("volume", volume=value)
    

# =============== 主应用程序 ===============
class MusicPlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = None
        self.current_song = None
        self.current_song_info = None
        self.search_results = []
        self.settings = load_settings()
        self.media_player = QMediaPlayer()
        self.media_player.setNotifyInterval(10)
        self.current_song_path = None
        self.log_console = None
        self.active_threads = []
        self.tools_menu = None 
        # 设置初始窗口大小
        self.resize(1280, 900)  
        self.playlist_manager = PlaylistManager()
        # 播放模式（0:顺序播放, 1:随机播放, 2:单曲循环）
        self.play_mode = 0
        # 当前播放索引
        self.current_play_index = -1
        # 播放列表
        self.playlist = []
        self.current_play_index = -1
        self.is_random_play = False
        self.repeat_mode = "none"
        self.create_necessary_dirs()  
        self.netease_worker = NetEaseWorker()  # 网易云专用worker
        self.setup_netease_connections()  # 连接网易云信号
        self.setup_connections()
        self.init_ui()
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)
        logger.info("应用程序启动")
        self.playlist_file = "playlists.json"
        self.ensure_playlist_exists()
        self.load_playlist_on_startup()
        
        self.room_manager = MusicRoomManager(self)
        # 添加音乐室服务器
        self.music_room_server = None
        self.server_thread = None
        
        # 创建外置歌词窗口
        self.external_lyrics = ExternalLyricsWindow(self)
        self.external_lyrics.setWindowTitle("歌词 - Railgun_lover")
        
        # 创建歌词同步对象
        self.lyrics_sync = LyricsSync(self.media_player, self.external_lyrics)
        
        # 连接信号
        self.media_player.positionChanged.connect(self.lyrics_sync.update_position)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)
        
        # 进度条控制
        self.progress_slider.sliderMoved.connect(self.seek_position)
        
        # 音量控制
        self.volume_slider.valueChanged.connect(self.set_volume)
        
        # 初始化歌词窗口状态
        self.update_lyrics_visibility()
        
        # 初始化播放列表
        self.update_current_playlist()
        
        # 初始化播放模式
        self.play_mode_combo.setCurrentIndex(0)
        self.change_play_mode(0)
        
        # 设置初始音量
        self.media_player.setVolume(80)
        
        # 加载背景
        self.set_background()
        
        # 初始化状态栏
        self.status_bar.showMessage("就绪")
        
        # 初始化按钮状态
        self.play_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        self.stop_button.setEnabled(False)
        self.download_button.setEnabled(False)
        
        # 初始化歌词按钮状态
        self.update_lyrics_button_state()
        
        # 初始化时间显示
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        
        # 初始化进度条
        self.progress_slider.setValue(0)
        
        # 初始化歌词同步
        self.lyrics_sync.load_lyrics("")
        
        # 初始化播放列表
        self.playlist_widget.setCurrentRow(-1)

        # 添加远程控制服务器
        self.remote_server = self.RemoteControlServer(self, port=5000)
        self.remote_server.start()
        
        # 创建二维码按钮
        self.remote_button = QPushButton("手机遥控")
        self.remote_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(70, 130, 180, 200);")
        self.remote_button.clicked.connect(self.show_remote_options)
        
        # 网络状态检测定时器
        self.network_timer = QTimer(self)
        self.network_timer.timeout.connect(self.update_network_status)
        self.network_timer.start(10000)  # 每10秒检测一次
        
        logger.info("应用程序初始化完成")

    def toggle_music_room_server(self):
        """切换音乐室服务器的启动状态"""
        if self.music_room_server and self.music_room_server.is_running():
            self.stop_music_room_server()
        else:
            self.start_music_room_server()

    def start_music_room_server(self):
        """启动音乐室服务器"""
        if self.music_room_server and self.music_room_server.is_running():
            return
        async def start_music_room_server(self):
            self.music_room_server = MusicRoomServer()
            await websockets.serve(
                self.music_room_server.handle_connection,
                "0.0.0.0",
                self.music_room_server.port
            )
        try:
            self.server_status_label.setText("音乐室服务器: 启动中...")
            QApplication.processEvents()
            
            # 创建服务器对象
            self.music_room_server = MusicRoomServer()
            
            # 在独立线程中运行服务器
            self.server_thread = QThread()
            self.music_room_server.moveToThread(self.server_thread)
            self.server_thread.started.connect(self.music_room_server.run)
            
            # 连接服务器信号
            self.music_room_server.started.connect(self.on_server_started)
            self.music_room_server.stopped.connect(self.on_server_stopped)
            self.music_room_server.error_occurred.connect(self.on_server_error)
            
            # 启动线程
            self.server_thread.start()

            
        except Exception as e:
            self.server_status_label.setText(f"音乐室服务器: 启动失败 - {str(e)}")
            logger.error(f"启动音乐室服务器失败: {str(e)}")

    def stop_music_room_server(self):
        """停止音乐室服务器"""
        if self.music_room_server:
            self.music_room_server.stop()
            self.server_status_label.setText("音乐室服务器: 停止中...")
            QApplication.processEvents()

            # 等待服务器线程结束
            if self.server_thread and self.server_thread.isRunning():
                self.server_thread.quit()
                if not self.server_thread.wait(3000):  # 等待3秒
                    self.server_thread.terminate()
                    self.server_thread.wait()

    def on_server_started(self, port):
        """服务器启动成功回调"""
        ip = self.get_ip_address()
        self.server_status_label.setText(f"音乐室服务器: 已启动 (访问地址: ws://{ip}:{port})")
        logger.info(f"音乐室服务器已启动, 端口: {port}")

    def on_server_stopped(self):
        """服务器停止回调"""
        self.server_status_label.setText("音乐室服务器: 已停止")
        logger.info("音乐室服务器已停止")
        
        # 清理线程
        if self.server_thread and self.server_thread.isRunning():
            self.server_thread.quit()
            self.server_thread.wait()
            self.server_thread = None
            
        self.music_room_server = None

    def on_server_error(self, error):
        """服务器错误回调"""
        self.server_status_label.setText(f"音乐室服务器错误: {error}")
        logger.error(f"音乐室服务器错误: {error}")

    def create_necessary_dirs(self):
        """创建必要的目录"""
        music_dir = self.settings["save_paths"]["music"]
        cache_dir = self.settings["save_paths"]["cache"]
        video_dir = self.settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos"))
        for directory in [music_dir, cache_dir, video_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"创建目录: {directory}")

    def ensure_playlist_exists(self):
        """确保播放列表文件存在，如果不存在则创建"""
        if not os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'w', encoding='utf-8') as f:
                    json.dump({"default": []}, f, ensure_ascii=False, indent=4)
                logger.info(f"创建播放列表文件: {self.playlist_file}")
            except Exception as e:
                logger.error(f"创建播放列表文件失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"无法创建播放列表文件:\n{str(e)}")
    
    def load_playlist_on_startup(self):
        """启动时加载播放列表"""
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    playlists = json.load(f)
                
                # 加载默认播放列表
                default_playlist = playlists.get("default", [])
                self.playlist_widget.clear()
                
                for song_info in default_playlist:
                    song_path = song_info.get("path", "")
                    song_name = song_info.get("name", os.path.basename(song_path))
                    
                    if os.path.exists(song_path):
                        item = QListWidgetItem(song_name)
                        item.setData(Qt.UserRole, song_path)
                        self.playlist_widget.addItem(item)
                        try:
                            logger.info(f"加载到播放列表: {song_name}")
                        except UnicodeEncodeError:
                            logger.info("加载到播放列表: [包含非ASCII字符的歌曲名称]")
                    else:
                        logger.warning(f"文件不存在，跳过加载: {song_path}")
                
                self.status_bar.showMessage(f"已加载 {self.playlist_widget.count()} 首歌曲")
                logger.info(f"成功加载播放列表: {self.playlist_file}")
                
            except Exception as e:
                logger.error(f"加载播放列表失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"加载播放列表失败:\n{str(e)}")

    def setup_netease_connections(self):
        """设置网易云专用信号连接"""
        self.netease_worker.search_finished.connect(self.display_netease_search_results)
        self.netease_worker.details_ready.connect(self.display_netease_details)
        self.netease_worker.error_occurred.connect(self.display_error)

    def update_lyrics_visibility(self):
        """根据设置更新歌词窗口的显示状态"""
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
        show_lyrics = lyrics_settings.get("show_lyrics", True)
        # 获取样式设置
        font_str = lyrics_settings.get("font", "Microsoft YaHei,36")
        font = QFont()
        font.fromString(font_str)  # 从字符串恢复字体
        
        color = lyrics_settings.get("color", "#000000")
        opacity = lyrics_settings.get("opacity", 80)

        # 确保歌词同步对象存在
        if not hasattr(self, 'lyrics_sync'):
            self.lyrics_sync = LyricsSync(self.media_player, self.external_lyrics)
    
        # 根据设置显示或隐藏歌词窗口
        if show_lyrics:
            self.external_lyrics.show()
        else:
            self.external_lyrics.hide()
    
        # 设置歌词同步状态
        self.lyrics_sync.enabled = show_lyrics

    def update_lyrics_style(self):
        """更新歌词窗口样式"""
        logger.info("更新歌词窗口样式")
        try:
            # 获取最新设置
            settings = load_settings()
            lyrics_settings = settings.get("external_lyrics", {})
            
            # 应用字体
            font_str = lyrics_settings.get("font", "Microsoft YaHei,36")
            font = QFont()
            font.fromString(font_str)
            self.external_lyrics.set_font(font)
            
            # 应用颜色
            normal_color = QColor(lyrics_settings.get("normal_color", "#FFFFFF"))
            highlight_color = QColor(lyrics_settings.get("highlight_color", "#000000"))
            next_line_color = QColor(lyrics_settings.get("next_line_color", "#AAAAAA"))
            self.external_lyrics.set_colors(normal_color, highlight_color, next_line_color)
            
            # 应用透明度
            opacity = lyrics_settings.get("opacity", 80) / 100.0
            self.external_lyrics.setWindowOpacity(opacity)
            
            # 应用效果
            effect_type = lyrics_settings.get("effect_type", "fill")
            outline_size = lyrics_settings.get("outline_size", 2)
            glow_size = lyrics_settings.get("glow_size", 10)
            self.external_lyrics.set_effect(effect_type, outline_size, glow_size)
            
            # 应用位置
            geometry_hex = lyrics_settings.get("geometry", "")
            if geometry_hex:
                byte_array = QByteArray.fromHex(geometry_hex.encode())
                self.external_lyrics.restoreGeometry(byte_array)
            
            # 应用锁定状态
            locked = lyrics_settings.get("locked", False)
            self.external_lyrics.set_locked(locked)
            
            # 强制重绘
            self.external_lyrics.repaint()
            logger.info("歌词窗口样式更新完成")
            
        except Exception as e:
            logger.error(f"更新歌词样式失败: {str(e)}")

    def update_lyrics_button_state(self):
        """根据歌词显示状态更新按钮"""
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
        show_lyrics = lyrics_settings.get("show_lyrics", True)
    
        # 更新按钮状态和文本
        self.lyrics_button.setChecked(show_lyrics)
        if show_lyrics:
            self.lyrics_button.setText("歌词:开")
        else:
            self.lyrics_button.setText("歌词:关")
                
    def open_app_directory(self):
        app_path = os.path.dirname(os.path.abspath(__file__))
        try:
            if sys.platform == "win32":
                os.startfile(app_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", app_path])
            else:
                subprocess.Popen(["xdg-open", app_path])
            logger.info(f"已打开程序目录: {app_path}")
        except Exception as e:
            logger.error(f"打开程序目录失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开程序目录:\n{str(e)}")
            
    def play_custom_file(self):
        settings = load_settings()
        music_dir = settings["save_paths"]["music"]
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            music_dir,
            "音频文件 (*.mp3 *.wav *.flac *.m4a);;所有文件 (*.*)"
        )
        if not file_path:
            return
        if file_path.endswith('.lrc'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                    self.lyrics_sync.load_lyrics(lyrics)
                return
            except Exception as e:
                logger.error(f"加载歌词失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"无法加载歌词文件:\n{str(e)}")
                return
        try:
            if self.media_player.state() == QMediaPlayer.PlayingState:
                self.media_player.stop()
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
            filename = os.path.basename(file_path)
            self.status_bar.showMessage(f"正在播放: {filename}")
            self.song_info.setText(f"<b>正在播放:</b> {filename}")
            self.external_lyrics.update_lyrics("")
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
            logger.info(f"播放文件: {file_path}")
        except Exception as e:
            logger.error(f"播放文件失败: {str(e)}")
            QMessageBox.critical(self, "播放错误", f"无法播放文件:\n{str(e)}")
        self.add_to_playlist(file_path)


    def load_lyrics_for_song(self, song_path):
        """尝试加载歌曲对应的歌词文件"""
        # 确保当前歌曲信息存在
        if not hasattr(self, 'current_song_info') or self.current_song_info is None:
            self.current_song_info = {
                'path': song_path,
                'name': os.path.basename(song_path),
                'lrc': ''
            }
    
        # 检查歌词窗口是否仍然存在
        if not hasattr(self, 'external_lyrics') or not self.external_lyrics:
            return
            
        # 获取歌词设置
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})

        # 首先尝试用户指定的歌词文件
        lyrics_text = ""
        if self.check_and_load_local_lyrics(song_path):
            return            
        if lyrics_settings.get("lyrics_path") and os.path.exists(lyrics_settings["lyrics_path"]):
            try:
                with open(lyrics_settings["lyrics_path"], 'r', encoding='utf-8') as f:
                    lyrics_text = f.read()
                logger.info(f"从用户指定文件加载歌词: {lyrics_settings['lyrics_path']}")
            except Exception as e:
                logger.error(f"加载用户指定歌词失败: {str(e)}")
        else:
            # 其次尝试同目录下的.lrc文件
            lrc_path = os.path.splitext(song_path)[0] + '.lrc'
            if os.path.exists(lrc_path):
                try:
                    with open(lrc_path, 'r', encoding='utf-8') as f:
                        lyrics_text = f.read()
                    logger.info(f"从本地文件加载歌词: {lrc_path}")
                except Exception as e:
                    logger.error(f"加载歌词文件失败: {lrc_path} - {str(e)}")
    
        # 如果没有本地歌词文件，尝试从网络获取（如果有的话）
        if not lyrics_text and hasattr(self, 'current_song_info'):
            lyrics_text = self.current_song_info.get('lrc', '')
            if lyrics_text:
                logger.info("从网络获取歌词内容")
            
                # 如果设置了自动保存歌词，保存到本地
                if lyrics_settings.get("auto_save", True):
                    lrc_path = os.path.splitext(song_path)[0] + '.lrc'
                    try:
                        with open(lrc_path, 'w', encoding='utf-8') as f:
                            f.write(lyrics_text)
                        logger.info(f"歌词已保存到: {lrc_path}")
                    except Exception as e:
                        logger.error(f"保存歌词文件失败: {str(e)}")
    
        # 加载歌词
        self.lyrics_sync.load_lyrics(lyrics_text)

        # 重置歌词显示
        if hasattr(self, 'external_lyrics') and self.external_lyrics:
            self.external_lyrics.update_lyrics("", "")

    def load_lyrics_from_network(self, song_info=None):
        """尝试从网络加载歌词"""
        if not song_info and self.current_song_info:
            song_info = self.current_song_info
    
        if song_info and 'id' in song_info:
            try:
                # 使用网易云API获取歌词
                api = NetEaseMusicAPI()
                lyrics = api.fetch_lyrics(song_info['id'])
                if lyrics and "歌词未找到" not in lyrics:
                    self.lyrics_sync.load_lyrics(lyrics)
                    self.external_lyrics.update_lyrics("网络歌词已加载")
                    return True
            except Exception as e:
                logger.error(f"从网络加载歌词失败: {str(e)}")
        return False
    
    def seek_position(self, value):
        """跳转到指定播放位置"""
        if self.media_player.duration() > 0:
            position = int(value * self.media_player.duration() / 1000)
            self.media_player.setPosition(position)

    def get_file_browser_content(self, path):
        """获取文件浏览器内容"""
        try:
            if not os.path.exists(path):
                path = self.settings["save_paths"]["music"]
                
            items = []
            
            # 添加返回上级目录项
            if os.path.dirname(path) != path:  # 不是根目录
                items.append({
                    "name": "..",
                    "path": os.path.dirname(path),
                    "type": "directory",
                    "icon": "fas fa-arrow-left"
                })
            
            # 遍历目录内容
            for entry in os.listdir(path):
                full_path = os.path.join(path, entry)
                if os.path.isdir(full_path):
                    items.append({
                        "name": entry,
                        "path": full_path,
                        "type": "directory",
                        "icon": "fas fa-folder"
                    })
                elif entry.lower().endswith(('.mp3', '.wav', '.flac', '.m4a')):
                    items.append({
                        "name": entry,
                        "path": full_path,
                        "type": "file",
                        "icon": "fas fa-file-audio"
                    })
            
            return {
                "current_path": path,
                "items": items
            }
        except Exception as e:
            logger.error(f"文件浏览错误: {str(e)}")
            return {"error": str(e)}
        
    def get_playlist_content(self):
        """获取当前播放列表内容"""
        playlist = []
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            file_path = item.data(Qt.UserRole)
            
            # 尝试获取歌曲元数据
            try:
                media = QMediaContent(QUrl.fromLocalFile(file_path))
                metadata = self.media_player.metaData(media)
                
                title = metadata.get(QMediaMetaData.Title, os.path.basename(file_path))
                artist = metadata.get(QMediaMetaData.AlbumArtist, "未知艺术家")
                duration = metadata.get(QMediaMetaData.Duration, 0)
            except:
                title = os.path.splitext(os.path.basename(file_path))[0]
                artist = "未知艺术家"
                duration = 0
                
            playlist.append({
                "index": i + 1,
                "title": title,
                "artist": artist,
                "duration": duration,
                "path": file_path,
                "current": (i == self.current_play_index)
            })
            
        return playlist
    
    def get_player_status(self):
        """获取播放器完整状态"""
        return {
            "current_song": {
                "title": self.current_song_info.get("name", ""),
                "artist": self.current_song_info.get("artists", ""),
                "album": self.current_song_info.get("album", ""),
                "duration": self.media_player.duration(),
                "position": self.media_player.position(),
                "path": self.current_song_path
            } if self.current_song_path else None,
            "state": "playing" if self.media_player.state() == QMediaPlayer.PlayingState else "paused",
            "volume": self.media_player.volume(),
            "playlist": self.get_playlist_content(),
            "ip_address": self.get_ip_address(),
            "connection_status": "connected"
        }
    
    def open_music_room(self):
        """打开音乐室对话框"""
        dialog = MusicRoomDialog(self)
        dialog.exec_()

    def show_login_dialog(self):
        """显示登录对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("登录音乐室")
        layout = QVBoxLayout()
    
        form_layout = QFormLayout()
    
        username_edit = QLineEdit()
        password_edit = QLineEdit()
        password_edit.setEchoMode(QLineEdit.Password)
    
        form_layout.addRow("用户名:", username_edit)
        form_layout.addRow("密码:", password_edit)
    
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(lambda: self.handle_login(username_edit.text(), password_edit.text(), dialog))
        button_box.rejected.connect(dialog.reject)
    
        layout.addLayout(form_layout)
        layout.addWidget(button_box)
        dialog.setLayout(layout)
        dialog.exec_()

    def handle_login(self, username, password, dialog):
        """处理登录请求"""
        if self.social_manager.login(username, password):
            dialog.accept()
            self.music_room_panel.update_user_info(self.social_manager.current_user)
            QMessageBox.information(self, "登录成功", "欢迎进入音乐室!")
        else:
            QMessageBox.warning(self, "登录失败", "用户名或密码错误")
    
    def init_ui(self):
        self.setWindowTitle("音乐捕捉器 create bilibili by:Railgun_lover")
        self.setGeometry(100, 100, 1000, 800)
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(53, 53, 53, 180);
                color: white;
            }
            QMenuBar::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
            QMenu {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
        """)
        file_menu = menu_bar.addMenu("文件")
        menu_bar = self.menuBar()
        file_menu.setIcon(QIcon.fromTheme("document"))
        self.tools_menu = menu_bar.addMenu("工具")                
        sleep_timer_action = QAction("睡眠定时器", self)
        sleep_timer_action.triggered.connect(self.open_sleep_timer)
        self.tools_menu.addAction(sleep_timer_action)
        equalizer_action = QAction("均衡器设置", self)
        equalizer_action.triggered.connect(self.open_equalizer)
        self.tools_menu.addAction(equalizer_action)
        music_server_action = QAction("启动音乐室服务器", self)
        music_server_action.setCheckable(True)  # 设置为可选中状态
        music_server_action.triggered.connect(self.toggle_music_room_server)
        self.tools_menu.addAction(music_server_action) 
        open_dir_action = QAction(QIcon.fromTheme("folder"), "打开程序目录", self)
        open_dir_action.setShortcut("Ctrl+O")
        open_dir_action.triggered.connect(self.open_app_directory)
        file_menu.addAction(open_dir_action)
        log_action = QAction(QIcon.fromTheme("text-plain"), "日志控制台", self)
        log_action.setShortcut("Ctrl+L")
        log_action.triggered.connect(self.open_log_console)
        file_menu.addAction(log_action)
        file_menu.addSeparator()
        exit_action = QAction(QIcon.fromTheme("application-exit"), "退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        main_widget = QWidget()
        main_widget.setObjectName("centralWidget")
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        self.set_background()
        toolbar_layout = QHBoxLayout()
        tools_layout = QHBoxLayout()
        layout = QVBoxLayout()
        
        # 添加服务器状态标签
        self.server_status_label = QLabel("音乐室服务器: 已停止")
        self.server_status_label.setStyleSheet("color: #FF5722; font-weight: bold;")
        layout.addWidget(self.server_status_label)
        self.tools_button = QPushButton("小工具")
        self.tools_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(70, 130, 180, 200); color: white; font-weight: bold;")
        self.tools_button.clicked.connect(self.open_tools_dialog)
        tools_layout.addWidget(self.tools_button)
        play_file_button = QPushButton("播放文件")
        play_file_button.setIcon(QIcon.fromTheme("media-playback-start"))
        play_file_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-size: 14px;
                background-color: rgba(46, 139, 87, 200);
                color: white;
                font-weight: bold;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: rgba(56, 159, 107, 200);
            }
        """)
        play_file_button.setCursor(QCursor(Qt.PointingHandCursor))
        play_file_button.clicked.connect(self.play_custom_file)
        tools_layout.addWidget(play_file_button)
        toolbar_layout.addLayout(tools_layout)
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入歌曲名称...")
        self.search_input.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        self.search_input.returnPressed.connect(self.start_search)
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_source_names())
        self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
        self.source_combo.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        self.source_combo.setFixedWidth(150)
        search_button = QPushButton("搜索")
        search_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        search_button.clicked.connect(self.start_search)
        settings_button = QPushButton("设置")
        settings_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        settings_button.clicked.connect(self.open_settings)
        log_button = QPushButton("日志控制台")
        log_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(70, 130, 180, 200);")
        log_button.clicked.connect(self.open_log_console)
        bilibili_audio_button = QPushButton("B站音乐")
        bilibili_audio_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(219, 68, 83, 200);")
        bilibili_audio_button.clicked.connect(self.open_bilibili_audio_search)
        self.music_room_button = QPushButton("音乐室")
        self.music_room_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(70, 130, 180, 200); color: white; font-weight: bold;")
        self.music_room_button.clicked.connect(self.open_music_room)
        tools_layout.addWidget(self.music_room_button)
        search_layout.addWidget(self.search_input, 5)
        search_layout.addWidget(self.source_combo, 2)
        search_layout.addWidget(search_button, 1)
        search_layout.addWidget(settings_button, 1)
        search_layout.addWidget(log_button, 1)
        search_layout.addWidget(bilibili_audio_button, 1)
        toolbar_layout.addLayout(search_layout)
        main_layout.addLayout(toolbar_layout)
        results_layout = QHBoxLayout()
        results_list_layout = QVBoxLayout()
        results_label = QLabel("搜索结果")
        results_label.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        results_list_layout.addWidget(results_label)
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        self.results_list.setIconSize(QSize(100, 100))
        self.results_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.results_list.customContextMenuRequested.connect(self.show_context_menu)
        self.results_list.itemClicked.connect(self.song_selected)
        results_list_layout.addWidget(self.results_list)
        results_layout.addLayout(results_list_layout, 3)
        details_layout = QVBoxLayout()
        info_layout = QVBoxLayout()
        info_label = QLabel("歌曲信息")
        info_label.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        info_layout.addWidget(info_label)
        self.song_info = QTextEdit()
        self.song_info.setReadOnly(True)
        self.song_info.setStyleSheet("font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        info_layout.addWidget(self.song_info)
        button_layout = QHBoxLayout()
        self.download_button = QPushButton("下载歌曲")
        self.download_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(46, 139, 87, 200); color: white; font-weight: bold;")
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_current_song)
        button_layout.addWidget(self.download_button)
        info_layout.addLayout(button_layout)
        control_layout = QHBoxLayout()
        self.prev_button = QPushButton("上一首")
        self.prev_button.setEnabled(True)
        self.prev_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.prev_button.clicked.connect(self.play_previous)
        control_layout.addWidget(self.prev_button)
        self.play_button = QPushButton("播放")
        self.play_button.setEnabled(True)
        self.play_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.play_button.clicked.connect(self.play_song)
        control_layout.addWidget(self.play_button)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(True)
        self.pause_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.pause_button.clicked.connect(self.pause_song)
        control_layout.addWidget(self.pause_button)
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(True)
        self.stop_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.stop_button.clicked.connect(self.stop_song)
        control_layout.addWidget(self.stop_button)
        self.next_button = QPushButton("下一首")
        self.next_button.setEnabled(True)
        self.next_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.next_button.clicked.connect(self.play_next)
        control_layout.addWidget(self.next_button)
        control_layout.addWidget(self.play_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.stop_button)
        info_layout.addLayout(control_layout)
        details_layout.addLayout(info_layout, 2)
        results_layout.addLayout(details_layout, 1)
        playlist_layout = QVBoxLayout()
        open_playlist_action = QAction(QIcon.fromTheme("folder"), "打开播放列表", self)
        open_playlist_action.setShortcut("Ctrl+P")
        open_playlist_action.triggered.connect(self.open_playlist_file)
        file_menu.addAction(open_playlist_action)
        progress_layout = QVBoxLayout()
        self.lyrics_button = QPushButton("歌词:关")
        self.lyrics_button.setCheckable(True)  # 设置为可切换状态
        self.lyrics_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-size: 14px;
                background-color: rgba(150, 150, 150, 200);
                color: white;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: rgba(46, 139, 87, 200);
            }
            QPushButton:hover {
                background-color: rgba(170, 170, 170, 200);
            }
            QPushButton:checked:hover {
                background-color: rgba(56, 159, 107, 200);
            }
        """)
        self.lyrics_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.lyrics_button.clicked.connect(self.toggle_lyrics_window)
        tools_layout.addWidget(self.lyrics_button)

        # 根据设置初始化按钮状态
        self.update_lyrics_button_state()

        # 时间显示
        time_layout = QHBoxLayout()
        self.current_time_label = QLabel("00:00")
        self.current_time_label.setStyleSheet("color: white; font-size: 12px;")
        self.total_time_label = QLabel("00:00")
        self.total_time_label.setStyleSheet("color: white; font-size: 12px;")
        self.total_time_label.setAlignment(Qt.AlignRight)
        
        time_layout.addWidget(self.current_time_label)
        time_layout.addStretch()
        time_layout.addWidget(self.total_time_label)
        progress_layout.addLayout(time_layout)
        
        # 进度条
        self.progress_slider = QSlider(Qt.Horizontal)
        self.progress_slider.setRange(0, 1000)
        self.progress_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 5px;
                background: rgba(100, 100, 100, 100);
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #FF5722;
                border: 1px solid #444;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #FF5722;
            }
        """)
        self.progress_slider.sliderPressed.connect(self.progress_pressed)
        self.progress_slider.sliderReleased.connect(self.progress_released)
        self.progress_slider.sliderMoved.connect(self.progress_moved)
        progress_layout.addWidget(self.progress_slider)
        
        # 将进度控制添加到主布局
        control_layout.addLayout(progress_layout)  # 添加到原有的控制按钮布局中
        
        # 新增：音量控制
        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("音量:"))
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 100)
        self.volume_slider.setValue(80)
        self.volume_slider.setFixedWidth(100)
        self.volume_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 5px;
                background: rgba(100, 100, 100, 100);
                margin: 2px 0;
            }
            QSlider::handle:horizontal {
                background: #4A235A;
                border: 1px solid #444;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #4A235A;
            }
        """)
        self.volume_slider.valueChanged.connect(self.set_volume)
        volume_layout.addWidget(self.volume_slider)
        control_layout.addLayout(volume_layout)

        
        # 播放列表栏
        playlist_header = QWidget()
        playlist_header_layout = QHBoxLayout(playlist_header)
        playlist_label = QLabel("播放列表")
        playlist_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #FF5722;")
        playlist_header_layout.addWidget(playlist_label)
        playlist_header_layout.addStretch()
        
        # 操作按钮
        clear_button = QPushButton("清空")
        clear_button.setFixedSize(60, 25)
        clear_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(74, 35, 90, 200);
                color: white;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(94, 55, 110, 200);
            }
        """)
        clear_button.clicked.connect(self.clear_playlist)
    
        save_button = QPushButton("保存")
        save_button.setFixedSize(60, 25)
        save_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(46, 139, 87, 200);
                color: white;
                border-radius: 3px;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: rgba(66, 159, 107, 200);
            }
       """)
        save_button.clicked.connect(self.save_playlist)
    
        playlist_header_layout.addWidget(clear_button)
        playlist_header_layout.addWidget(save_button)
        playlist_header_layout.setContentsMargins(5, 5, 5, 5)
    
        playlist_layout.addWidget(playlist_header)
        
         # 播放列表控件
        self.playlist_widget = QListWidget()
        self.playlist_widget.setStyleSheet("""
            QListWidget {
                background-color: rgba(37, 37, 37, 200);
                border: 1px solid #555;
                font-size: 14px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #444;
            }
            QListWidget::item:selected {
                background-color: rgba(74, 35, 90, 200);
                color: white;
            }
        """)
        self.playlist_widget.setAlternatingRowColors(True)
        self.playlist_widget.setIconSize(QSize(40, 40))
        self.playlist_widget.setSpacing(2)
        self.playlist_widget.itemDoubleClicked.connect(self.play_playlist_item)
        
        # 右键菜单
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_playlist_menu)
        
        playlist_layout.addWidget(self.playlist_widget, 1)
        
        # 播放控制按钮
        playlist_controls = QWidget()
        playlist_controls_layout = QHBoxLayout(playlist_controls)
        
        # 播放模式选择
        self.play_mode_combo = QComboBox()
        self.play_mode_combo.addItems(["顺序播放", "随机播放", "单曲循环"])
        self.play_mode_combo.setStyleSheet("""
            QComboBox {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                padding: 5px;
                border: 1px solid #555;
                border-radius: 3px;
                font-size: 12px;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        self.play_mode_combo.setFixedWidth(90)
        self.play_mode_combo.currentIndexChanged.connect(self.change_play_mode)
        playlist_controls_layout.addWidget(self.play_mode_combo)
        
        # 控制按钮
        prev_button = QPushButton()
        prev_button.setIcon(QIcon.fromTheme("media-skip-backward"))
        prev_button.setFixedSize(30, 30)
        prev_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(74, 35, 90, 200);
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(94, 55, 110, 200);
            }
        """)
        prev_button.clicked.connect(self.play_previous)
        
        play_button = QPushButton()
        play_button.setIcon(QIcon.fromTheme("media-playback-start"))
        play_button.setFixedSize(40, 40)
        play_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(219, 68, 83, 200);
                border-radius: 20px;
            }
            QPushButton:hover {
                background-color: rgba(239, 88, 103, 200);
            }
        """)
        play_button.clicked.connect(self.play_song)
        
        next_button = QPushButton()
        next_button.setIcon(QIcon.fromTheme("media-skip-forward"))
        next_button.setFixedSize(30, 30)
        next_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(74, 35, 90, 200);
                border-radius: 15px;
            }
            QPushButton:hover {
                background-color: rgba(94, 55, 110, 200);
            }
        """)
        next_button.clicked.connect(self.play_next)
        
        playlist_controls_layout.addStretch()
        playlist_controls_layout.addWidget(prev_button)
        playlist_controls_layout.addWidget(play_button)
        playlist_controls_layout.addWidget(next_button)
        playlist_controls_layout.addStretch()
        
        playlist_layout.addWidget(playlist_controls)
        results_layout.addLayout(playlist_layout, 1)  # 占比1
        
        main_layout.addLayout(results_layout, 5)

        main_layout.addLayout(results_layout, 5)
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        search_button.clicked.connect(self.start_search)

    def toggle_lyrics_window(self):
        """切换歌词窗口的显示状态"""
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
    
        # 切换显示状态
        current_state = lyrics_settings.get("show_lyrics", True)
        lyrics_settings["show_lyrics"] = not current_state
    
        # 保存设置
        settings["lyrics"] = lyrics_settings
        save_settings(settings)
    
        # 更新歌词窗口
        self.update_lyrics_visibility()

        # 更新按钮状态
        self.update_lyrics_button_state()
    
        # 更新状态栏消息
        new_state = "显示" if lyrics_settings["show_lyrics"] else "隐藏"
        self.status_bar.showMessage(f"歌词窗口已{new_state}")

    def download_current_song(self):
        if self.source_combo.currentText() == "网易云音乐" and self.current_song_info:
            # 使用网易云API下载
            file_path = ...  # 文件路径选择逻辑
            self.api = NetEaseMusicAPI()
            self.api.download_song(self.current_song_info['audio_url'], file_path)
        else:
            # 原有下载逻辑
            pass
        if not self.current_song_info or 'url' not in self.current_song_info:
            self.status_bar.showMessage("没有可下载的歌曲")
            logger.warning("下载请求: 没有可下载的歌曲")
            return
        
        # 创建lrc目录
        lrc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lrc")
        if not os.path.exists(lrc_dir):
            os.makedirs(lrc_dir, exist_ok=True)
            logger.info(f"创建歌词目录: {lrc_dir}")
    
        # 获取歌曲信息
        song_name = self.current_song_info.get('name', '未知歌曲')
        safe_song_name = re.sub(r'[\\/*?:"<>|]', "", song_name)
        default_name = f"{safe_song_name}.mp3"
    
        # 获取歌词URL
        lrc_url = self.current_song_info.get('lrc_url', '')
    
        # 保存文件对话框
        settings = load_settings()
        music_dir = settings["save_paths"]["music"]
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存歌曲", 
            os.path.join(music_dir, default_name), 
            "MP3文件 (*.mp3)"
        )
        if not file_path:
            logger.info("下载取消: 用户未选择保存路径")
            return
        
        # 生成歌词文件路径
        base_path = os.path.splitext(file_path)[0]
        lrc_path = os.path.join(lrc_dir, f"{safe_song_name}.lrc")
    
        logger.info(f"开始下载歌曲到: {file_path}")
        self.progress_dialog = QProgressDialog("下载歌曲...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("下载进度")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
    
        # 创建下载线程
        self.download_worker = MusicWorker()
        self.download_worker.current_song_info = self.current_song_info
        self.active_threads.append(self.download_worker)
        self.download_worker.download_progress.connect(self.update_download_progress)
        self.download_worker.download_finished.connect(self.download_completed)
        self.download_worker.error_occurred.connect(self.display_error)
        self.download_worker.finished.connect(self.remove_download_worker)
    
        # 设置歌词下载路径
        self.download_worker.lrc_path = lrc_path
        self.download_worker.lrc_url = lrc_url
    
       # 开始下载
        self.download_worker.download_song(self.current_song_info['url'], file_path)
        
    def progress_pressed(self):
        self.was_playing = self.media_player.state() == QMediaPlayer.PlayingState
        if self.was_playing:
            self.media_player.pause()

    def progress_released(self):
        if hasattr(self, 'was_playing') and self.was_playing:
            self.media_player.play()

    def progress_moved(self, position):
        if self.media_player.duration() > 0:
            new_position = int(position * self.media_player.duration() / 1000)
            self.media_player.setPosition(new_position)
            self.update_time_display(new_position)

    def update_time_display(self, position):
        total_time = self.media_player.duration()
        # 使用类名调用静态方法
        self.current_time_label.setText(MusicPlayerApp.format_time(position))
        self.total_time_label.setText(MusicPlayerApp.format_time(total_time))

    def refresh_source_combo(self):
        """刷新音源选择下拉框"""
        self.source_combo.clear()
    
        # 从设置中获取最新音源列表
        settings = load_settings()
        source_names = [source["name"] for source in settings["sources"]["sources_list"]]
        self.source_combo.addItems(source_names)
    
        # 设置当前选择的音源
        current_source = settings["sources"]["active_source"]
        if current_source in source_names:
            self.source_combo.setCurrentText(current_source)
        elif source_names:
            self.source_combo.setCurrentIndex(0)

    # 音量控制
    def set_volume(self, value):
        """设置音量（重写以支持音乐室同步）"""
        if self.room_manager.current_room:
            self.room_manager.send_playback_command("volume", volume=value)
        self.media_player.setVolume(value)

    def add_to_playlist(self, song_path, song_info=None):
        """添加歌曲到播放列表"""
        if not os.path.exists(song_path):
            logger.warning(f"无法添加到播放列表，文件不存在: {song_path}")
            return
            
        # 检查是否已在播放列表中
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            if item.data(Qt.UserRole) == song_path:
                logger.info(f"歌曲已在播放列表中: {song_path}")
                return
                
        if song_info is None:
            # 从文件路径解析歌曲信息
            filename = os.path.basename(song_path)
            song_name = os.path.splitext(filename)[0]
            song_info = {"name": song_name, "artists": "未知艺术家"}
        else:
            song_name = f"{song_info.get('name', '未知歌曲')} - {song_info.get('artists', '未知艺术家')}"
        
        item = QListWidgetItem(song_name)
        item.setData(Qt.UserRole, song_path)
        
        # 尝试加载专辑封面
        if song_info and song_info.get("pic"):
            cache_dir = self.settings["save_paths"]["cache"]
            pic_url = song_info["pic"]
            try:
                songid = song_info.get("id", f"song_{hashlib.md5(song_path.encode()).hexdigest()}")
                safe_songid = re.sub(r'[\\/*?:"<>|]', "", songid)
                image_path = os.path.join(cache_dir, f"{safe_songid}.jpg")
                
                if not os.path.exists(image_path):
                    logger.info(f"下载专辑封面: {pic_url}")
                    response = requests.get(pic_url, stream=True, timeout=10)
                    if response.status_code == 200:
                        with open(image_path, 'wb') as f:
                            for chunk in response.iter_content(1024):
                                f.write(chunk)
                        logger.info(f"封面保存到: {image_path}")
                    else:
                        logger.warning(f"封面下载失败: HTTP {response.status_code}")
                
                if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                    pixmap = QPixmap(image_path)
                    if not pixmap.isNull():
                        pixmap = pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                        item.setIcon(QIcon(pixmap))
            except Exception as e:
                logger.error(f"加载专辑封面失败: {str(e)}")
        
        self.playlist_widget.addItem(item)
        logger.info(f"已添加到播放列表: {song_name}")
        self.save_playlist_to_json()


    
    
    def save_playlist_to_json(self):
        """保存播放列表到JSON文件"""
        try:
            playlist_data = {"default": []}
            
            # 收集当前播放列表中的所有歌曲
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                song_path = item.data(Qt.UserRole)
                song_name = item.text()
                playlist_data["default"].append({
                    "name": song_name,
                    "path": song_path
                })
            
            # 保存到文件
            with open(self.playlist_file, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, ensure_ascii=False, indent=4)
                
            logger.info(f"播放列表已保存到: {self.playlist_file}")
            return True
        except Exception as e:
            logger.error(f"保存播放列表失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存播放列表失败:\n{str(e)}")
            return False
        
    def save_playlist(self):
        """保存播放列表到文件"""
        if self.playlist_widget.count() == 0:
            QMessageBox.information(self, "提示", "播放列表为空")
            return
            
        settings = load_settings()
        playlist_dir = settings["save_paths"].get("music", os.path.join(os.path.expanduser("~"), "Music"))
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存播放列表", 
            os.path.join(playlist_dir, "我的播放列表.json"), 
            "JSON播放列表 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            playlist_data = {"default": []}
            
            # 收集当前播放列表中的所有歌曲
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                song_path = item.data(Qt.UserRole)
                song_name = item.text()
                playlist_data["default"].append({
                    "name": song_name,
                    "path": song_path
                })
            
            # 保存到文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(playlist_data, f, ensure_ascii=False, indent=4)
                
            QMessageBox.information(self, "成功", f"播放列表已保存到:\n{file_path}")
            logger.info(f"播放列表已保存: {file_path}")
        except Exception as e:
            logger.error(f"保存播放列表失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"保存播放列表失败:\n{str(e)}")

            
    def clear_playlist(self):
        """清空播放列表"""
        self.playlist_widget.clear()
        self.media_player.stop()
        self.status_bar.showMessage("播放列表已清空")
        logger.info("播放列表已清空")
        self.save_playlist_to_json()
    
    def open_playlist_file(self):
        """打开播放列表文件对话框"""
        settings = load_settings()
        playlist_dir = settings["save_paths"].get("music", os.path.join(os.path.expanduser("~"), "Music"))
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "打开播放列表", 
            playlist_dir, 
            "JSON播放列表 (*.json);;所有文件 (*.*)"
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                playlists = json.load(f)
            
            # 加载播放列表
            default_playlist = playlists.get("default", [])
            self.playlist_widget.clear()
            
            for song_info in default_playlist:
                song_path = song_info.get("path", "")
                song_name = song_info.get("name", os.path.basename(song_path))
                
                if os.path.exists(song_path):
                    item = QListWidgetItem(song_name)
                    item.setData(Qt.UserRole, song_path)
                    self.playlist_widget.addItem(item)
                    try:
                        logger.info(f"加载到播放列表: {song_name}")
                    except UnicodeEncodeError:
                        logger.info("加载到播放列表: [包含非ASCII字符的歌曲名称]")
                else:
                    logger.warning(f"文件不存在，跳过加载: {song_path}")
            
            self.status_bar.showMessage(f"已加载 {self.playlist_widget.count()} 首歌曲")
            QMessageBox.information(self, "成功", f"播放列表已加载:\n{file_path}")
            logger.info(f"成功加载播放列表: {file_path}")
            
            # 设置当前播放列表文件
            self.playlist_file = file_path
            
        except Exception as e:
            logger.error(f"加载播放列表失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载播放列表失败:\n{str(e)}")
    
    
    def play_playlist_item(self, item):
        """播放播放列表中的歌曲"""
        # 获取行号并保存为当前播放索引
        self.current_play_index = self.playlist_widget.row(item)
        song_path = item.data(Qt.UserRole)
        self.update_current_playlist()
        # 重置进度条
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        # +++ 新增: 清除当前歌词 +++
        self.reset_lyrics()
        if not os.path.exists(song_path):
            QMessageBox.warning(self, "错误", "文件不存在，可能已被移动或删除")
            self.playlist_widget.takeItem(self.playlist_widget.row(item))
            self.save_playlist_to_json()
            return
            
        try:
            self.current_song_path = song_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(song_path)))
            self.media_player.setNotifyInterval(10)
            self.media_player.play()
            
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)

            # 重置进度条
            self.progress_slider.setValue(0)
            self.current_time_label.setText("00:00")
            self.total_time_label.setText("00:00")
            
            song_name = os.path.basename(song_path)
            self.status_bar.showMessage(f"正在播放: {song_name}")
            self.song_info.setText(f"<b>正在播放:</b> {song_name}")

            # 高亮当前播放项
            self.playlist_widget.setCurrentRow(self.current_play_index)

            # 设置当前歌曲信息
            self.current_song_info = {
                'path': song_path,
                'name': song_name,
                'lrc': ''  # 初始化为空，后面会尝试加载本地歌词
            }
        
            # +++ 新增: 检查本地歌词文件 +++
            self.check_and_load_local_lyrics(song_path)
            
            logger.info(f"播放播放列表歌曲: {song_path}")
        except Exception as e:
            logger.error(f"播放文件失败: {str(e)}")
            QMessageBox.critical(self, "播放错误", f"无法播放文件:\n{str(e)}")
        
    def reset_lyrics(self):
        """重置歌词状态"""
        self.lyrics_sync.load_lyrics("")  # 清空歌词同步对象
        self.external_lyrics.update_lyrics("")  # 清空歌词窗口显示

    def update_current_playlist(self):
        """更新当前播放列表状态"""
        self.playlist = []
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            song_path = item.data(Qt.UserRole)
            song_name = item.text()
            self.playlist.append({
                'path': song_path,
                'name': song_name,
                'artists': "未知艺术家"  # 播放列表中的歌曲可能没有艺术家信息
            })

    def get_next_song_index(self):
        """根据播放模式获取下一首歌曲的索引"""
        if self.playlist_widget.count() == 0:
            return -1
        
        if self.play_mode == 2:  # 单曲循环
            return self.current_play_index
        elif self.play_mode == 1:  # 随机播放
            return random.randint(0, self.playlist_widget.count() - 1)
        else:  # 顺序播放
            next_index = self.current_play_index + 1
            return next_index if next_index < self.playlist_widget.count() else 0
        
    def get_prev_song_index(self):
        """根据播放模式获取上一首歌曲的索引"""
        if self.playlist_widget.count() == 0:
            return -1
        
        if self.play_mode == 2:  # 单曲循环
            return self.current_play_index
        elif self.play_mode == 1:  # 随机播放
            return random.randint(0, self.playlist_widget.count() - 1)
        else:  # 顺序播放
            prev_index = self.current_play_index - 1
            return prev_index if prev_index >= 0 else self.playlist_widget.count() - 1
        
    def play_previous(self):
        """播放上一首歌曲"""
        if self.playlist_widget.count() == 0:
            return
            
        prev_index = self.get_prev_song_index()
        if 0 <= prev_index < self.playlist_widget.count():
            item = self.playlist_widget.item(prev_index)
            self.play_playlist_item(item)

    
    def play_next(self):
        """播放下一首歌曲"""
        if self.playlist_widget.count() == 0:
            return
            
        next_index = self.get_next_song_index()
        if 0 <= next_index < self.playlist_widget.count():
            item = self.playlist_widget.item(next_index)
            self.play_playlist_item(item)

    def handle_media_status_changed(self, status):
        """处理媒体状态变化"""
        if status == QMediaPlayer.LoadedMedia:
            # 当媒体加载完成时，尝试加载歌词
            if self.current_song_path:
                self.load_lyrics_for_song(self.current_song_path)
        elif status == QMediaPlayer.EndOfMedia:
            # 播放完成，自动播放下一首
            self.play_next()

    def change_play_mode(self, index):
        """更改播放模式"""
        self.play_mode = index
        modes = ["顺序播放", "随机播放", "单曲循环"]
        self.status_bar.showMessage(f"播放模式已切换为: {modes[index]}")
        logger.info(f"播放模式切换: {modes[index]}")

    def check_and_load_local_lyrics(self, song_path):
        """检查并加载与歌曲同目录的歌词文件，并验证是否匹配"""
        try:
            # 清空现有歌词
            self.reset_lyrics()
            # 检查是否存在同名的.lrc文件
            base_path = os.path.splitext(song_path)[0]
            lrc_path = f"{base_path}.lrc"
            
            if os.path.exists(lrc_path):
                logger.info(f"检测到本地歌词文件: {lrc_path}")
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lyrics_text = f.read()
                    self.lyrics_sync.load_lyrics(lyrics_text)
                    logger.info(f"成功加载本地歌词文件: {lrc_path}")
                    return True
            else:
                logger.info(f"未找到本地歌词文件: {lrc_path}")
                # 尝试从网络获取歌词（如果歌曲信息中有歌词内容）
                if hasattr(self, 'current_song_info') and 'lrc' in self.current_song_info:
                    self.lyrics_sync.load_lyrics(self.current_song_info['lrc'])
                    return True
                return False
                
        except Exception as e:
            logger.error(f"加载本地歌词失败: {str(e)}")
            self.external_lyrics.update_lyrics(f"歌词加载错误: {str(e)}")
            return False
        
    def is_lyrics_valid_for_song(self, lyrics_text, song_hash):
        """
        验证歌词是否属于当前歌曲
        策略：检查歌词中是否包含歌曲名或艺术家名
        """
        if not hasattr(self, 'current_song_info') or not self.current_song_info:
            return False
            
        # 从歌词中提取可能的歌曲标识信息
        song_name = self.current_song_info.get('name', '').lower()
        artist_name = self.current_song_info.get('artists', '').lower()
        
        # 如果歌曲名或艺术家名为空，认为匹配
        if not song_name and not artist_name:
            return True
            
        # 检查歌词中是否包含歌曲名或艺术家名
        lyrics_lower = lyrics_text.lower()
        
        # 如果歌词中包含歌曲名，认为匹配
        if song_name and song_name in lyrics_lower:
            return True
            
        # 如果歌词中包含艺术家名，认为匹配
        if artist_name and artist_name in lyrics_lower:
            return True
            
        # 都不包含，则认为不匹配
        return False

    def show_playlist_menu(self, pos):
        """显示播放列表的右键菜单"""
        item = self.playlist_widget.itemAt(pos)
        if not item:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
        """)
        
        play_action = QAction("播放", self)
        play_action.triggered.connect(lambda: self.play_playlist_item(item))
        menu.addAction(play_action)
        
        remove_action = QAction("移除", self)
        remove_action.triggered.connect(lambda: self.remove_playlist_item(item))
        menu.addAction(remove_action)
        
        menu.addSeparator()
        
        open_folder_action = QAction("打开所在文件夹", self)
        open_folder_action.triggered.connect(lambda: self.open_song_folder(item))
        menu.addAction(open_folder_action)
        
        menu.exec_(self.playlist_widget.mapToGlobal(pos))
    
    def remove_playlist_item(self, item):
        """从播放列表中移除歌曲"""
        row = self.playlist_widget.row(item)
        self.playlist_widget.takeItem(row)
        logger.info(f"从播放列表移除: {item.text()}")
        self.save_playlist_to_json()
    
    def open_song_folder(self, item):
        """打开歌曲所在文件夹"""
        song_path = item.data(Qt.UserRole)
        folder_path = os.path.dirname(song_path)
        
        if os.path.exists(folder_path):
            try:
                if sys.platform == "win32":
                    os.startfile(folder_path)
                elif sys.platform == "darwin":
                    subprocess.Popen(["open", folder_path])
                else:
                    subprocess.Popen(["xdg-open", folder_path])
                logger.info(f"已打开文件夹: {folder_path}")
            except Exception as e:
                logger.error(f"打开文件夹失败: {str(e)}")
                QMessageBox.critical(self, "错误", f"无法打开文件夹:\n{str(e)}")
        else:
            QMessageBox.warning(self, "错误", "文件夹不存在")

    def open_playlist_manager(self):
        dialog = PlaylistDialog(self.playlist_manager, self)
        dialog.exec_()
        
    def open_equalizer(self):
        dialog = EqualizerDialog(self.media_player, self)
        dialog.exec_()
        
    def open_sleep_timer(self):
        dialog = SleepTimerDialog(self)
        dialog.exec_()   
        
    def open_tools_dialog(self):
        dialog = ToolsDialog(self)
        dialog.exec_()

    def remove_search_worker(self):
        if self.search_worker in self.active_threads:
            self.active_threads.remove(self.search_worker)
        self.search_worker = None
        
    def remove_download_worker(self):
        if self.download_worker in self.active_threads:
            self.active_threads.remove(self.download_worker)
        self.download_worker = None   

    def closeEvent(self, event):
        """重写关闭事件，确保窗口能被完全关闭"""
        logger.info("外置歌词窗口关闭")
        
        # 保存歌词窗口位置
        settings = load_settings()
        lyrics_settings = settings.get("external_lyrics", {})
    
        # 使用QByteArray保存几何信息
        lyrics_settings["geometry"] = self.saveGeometry().toHex().data().decode()
    
        # 保存字体信息（使用当前行标签的字体）
        lyrics_settings["font"] = self.current_time_label.font().toString()  # 修改这里
    
        # 保存颜色信息（这里保存的是当前行标签的颜色）
        lyrics_settings["color"] = self.current_time_label.palette().color(QPalette.WindowText).name()  # 修改这里
    
        # 保存透明度
        lyrics_settings["opacity"] = int(self.windowOpacity() * 100)
    
        # 保存显示状态
        lyrics_settings["show_lyrics"] = self.isVisible()

        settings["external_lyrics"] = lyrics_settings
        save_settings(settings)

        # 先断开所有信号连接
        try:
            self.media_player.positionChanged.disconnect(self.lyrics_sync.update_position)
        except:
            pass
            
        try:
            self.media_player.mediaStatusChanged.disconnect(self.handle_media_status_changed)
        except:
            pass

        # 关闭歌词窗口前断开信号连接
        if hasattr(self, 'lyrics_sync'):
            try:
                self.media_player.positionChanged.disconnect(self.lyrics_sync.update_position)
            except:
                pass
            
        # 关闭歌词窗口
        if hasattr(self, 'external_lyrics') and self.external_lyrics.isVisible():
            logger.info("关闭外置歌词窗口")
            self.external_lyrics.close()
            self.external_lyrics.deleteLater()
            self.external_lyrics = None
            
        # 终止所有线程
        self.terminate_all_threads()
        
        # 停止媒体播放器
        self.media_player.stop()

        if self.music_room_server and self.music_room_server.is_running():
            self.stop_music_room_server()
        
        # 关闭日志控制台（如果存在）
        if hasattr(self, 'log_console') and self.log_console:
            self.log_console.close()
     
        # 保存播放列表
        self.save_playlist_to_json()
    
        event.accept()
   
    def terminate_all_threads(self):
        """终止所有运行中的线程"""
        logger.info("终止所有运行中的线程")
        threads_to_terminate = self.active_threads.copy()
        for thread in threads_to_terminate:
            if thread and thread.isRunning():
                logger.debug(f"终止线程: {thread.__class__.__name__}")
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):
                    thread.terminate()
                    thread.wait()
                if thread in self.active_threads:
                    self.active_threads.remove(thread)
        
    def open_log_console(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("日志控制台")
        dialog.setGeometry(100, 100, 800, 600)
        layout = QVBoxLayout()
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px;")
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_app.log")
        try:
            # 尝试UTF-8解码（主要编码）
            with open(log_path, "r", encoding="utf-8") as log_file:
                log_content = log_file.read()
        except UnicodeDecodeError:
            try:
                # 尝试GBK解码（中文系统常用）
                with open(log_path, "r", encoding="gbk") as log_file:
                    log_content = log_file.read()
            except:
                try:
                    # 尝试使用chardet自动检测编码
                    import chardet
                    with open(log_path, "rb") as log_file:
                        raw_data = log_file.read()
                        encoding = chardet.detect(raw_data)['encoding']
                        log_content = raw_data.decode(encoding or 'utf-8', errors='replace')
                except Exception as e:
                    # 最终回退方案
                    log_content = f"读取日志文件失败: {str(e)}"
        except Exception as e:
            log_content = f"读取日志文件失败: {str(e)}"
        log_text.setPlainText(log_content)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(lambda: self.refresh_log_content(log_text))
        layout.addWidget(log_text)
        layout.addWidget(refresh_button, alignment=Qt.AlignRight)
        dialog.setLayout(layout)
        dialog.exec_()

    def refresh_log_content(self, log_text_widget):
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_app.log")
    
        # 同样的改进编码处理
        try:
            with open(log_path, "r", encoding="utf-8") as log_file:
                log_content = log_file.read()
        except UnicodeDecodeError:
            try:
                with open(log_path, "r", encoding="gbk") as log_file:
                    log_content = log_file.read()
            except:
                try:
                    import chardet
                    with open(log_path, "rb") as log_file:
                        raw_data = log_file.read()
                        encoding = chardet.detect(raw_data)['encoding']
                        log_content = raw_data.decode(encoding or 'utf-8', errors='replace')
                except Exception as e:
                    log_content = f"读取日志文件失败: {str(e)}"
        except Exception as e:
            log_content = f"读取日志文件失败: {str(e)}"
    
        log_text_widget.setPlainText(log_content)
        
    def open_bilibili_audio_search(self):
        cookie = self.settings.get("bilibili", {}).get("cookie", "")
        search_dialog = AudioSearchDialog(self, cookie)
        search_dialog.exec_()
        
    def open_bilibili_search(self):
        if not self.current_song_info:
            self.status_bar.showMessage("没有选中的歌曲")
            return
        cookie = self.settings.get("bilibili", {}).get("cookie", "")
        search_dialog = VideoSearchDialog(self, cookie)
        search_dialog.exec_()
        
    def set_background(self):
        bg_image = self.settings.get("background_image", "")
        if bg_image and os.path.exists(bg_image):
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-image: url({bg_image});
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }}
            """)
    
    def show_context_menu(self, pos):
        item = self.results_list.itemAt(pos)
        if not item:
            return
        menu = QMenu()
        menu.setStyleSheet("""
            QMenu {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                border: 1px solid #555;
            }
            QMenu::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
        """)
        download_action = QAction("下载歌曲", self)
        download_action.triggered.connect(lambda: self.download_selected_song(item))
        menu.addAction(download_action)
        info_action = QAction("查看详情", self)
        info_action.triggered.connect(lambda: self.show_song_info(item))
        menu.addAction(info_action)
        bilibili_action = QAction("在B站搜索", self)
        bilibili_action.triggered.connect(lambda: self.bilibili_search_selected(item))
        menu.addAction(bilibili_action)
        menu.exec_(self.results_list.mapToGlobal(pos))
        
    def bilibili_search_selected(self, item):
        index = self.results_list.row(item)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            self.display_song_info(self.current_song)
            self.open_bilibili_search()
    
    def download_selected_song(self, item):
        index = self.results_list.row(item)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            self.display_song_info(self.current_song)
            self.download_current_song()
    
    def show_song_info(self, item):
        index = self.results_list.row(item)
        if index < len(self.search_results):
            song = self.search_results[index]
            info = f"歌曲名称: {song.get('name', '未知')}\n"
            info += f"艺术家: {song.get('artists', '未知')}\n"
            info += f"专辑: {song.get('album', '未知')}\n"
            info += f"时长: {self.format_time(song.get('duration', 0))}"
            QMessageBox.information(self, "歌曲详情", info)

    def update_button_states(self, state):
        """根据播放状态更新按钮状态"""
        self.play_button.setEnabled(state != QMediaPlayer.PlayingState)
        self.pause_button.setEnabled(state == QMediaPlayer.PlayingState)
        self.stop_button.setEnabled(state != QMediaPlayer.StoppedState)

    def open_settings(self):
        dialog = SettingsDialog(self)

        # 连接歌词设置更新信号
        dialog.lyrics_settings_updated.connect(self.update_lyrics_style)

        if dialog.exec_() == QDialog.Accepted:
            self.settings = load_settings()
            self.source_combo.clear()
            self.source_combo.addItems(get_source_names())
            self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
            self.set_background()
            self.create_necessary_dirs()
            QMessageBox.information(self, "设置", "设置已保存！")
        
    def setup_connections(self):
        self.media_player.stateChanged.connect(self.update_button_states)
        self.media_player.positionChanged.connect(self.update_progress)
        self.media_player.stateChanged.connect(self.handle_player_state_changed)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)

    def remove_thread(self, thread):
        """安全地从活动线程列表中移除线程"""
        try:
            if thread and thread in self.active_threads:
                self.active_threads.remove(thread)
        except ValueError:
            # 线程可能已经被移除
            logger.debug(f"尝试移除不在列表中的线程: {thread}")
        except Exception as e:
            logger.error(f"移除线程时出错: {str(e)}")
    
    def remove_search_worker(self):
        """移除搜索线程"""
        if self.search_worker:
            self.remove_thread(self.search_worker)
            self.search_worker = None

    def start_search(self):
        keyword = self.search_input.text().strip()
        if self.source_combo.currentText() == "网易云音乐":
            self.status_bar.showMessage("网易云搜索中...")
            self.netease_worker.search_songs(keyword)
        else:
            pass
        if not keyword:
            self.status_bar.showMessage("请输入歌曲名称")
            logger.warning("搜索请求: 未输入关键词")
            return
        self.playlist = self.search_results if self.search_results else []
        self.settings["sources"]["active_source"] = self.source_combo.currentText()
        save_settings(self.settings)
        logger.info(f"开始搜索: {keyword}")
        self.status_bar.showMessage("搜索中...")
        self.results_list.clear()
        self.song_info.clear()
        self.external_lyrics.update_lyrics("")
        self.download_button.setEnabled(False)
        self.search_worker = MusicWorker()
        self.active_threads.append(self.search_worker)
        self.search_worker.search_finished.connect(self.display_search_results)
        self.search_worker.error_occurred.connect(self.display_error)
        self.search_worker.finished.connect(lambda: self.remove_thread(self.search_worker)) 
        self.search_worker.search_songs(keyword)

    def update_progress(self, position):
        """更新进度条显示"""
        if self.room_manager.current_room:
            # 每5秒同步一次进度
            if position % 5000 < 100:
                self.room_manager.send_playback_command("seek", position=position)
        if self.media_player.duration() > 0:
            # 计算当前播放进度的百分比（0-1000）
            progress = int(1000 * position / self.media_player.duration())
            self.progress_slider.setValue(progress)
        
            # 更新时间显示
            self.current_time_label.setText(self.format_time(position))
            self.total_time_label.setText(self.format_time(self.media_player.duration()))

        
    def display_search_results(self, songs):
        if not songs:
            self.status_bar.showMessage("未找到相关歌曲")
            logger.warning("搜索结果: 未找到相关歌曲")
            return
        logger.info(f"显示搜索结果: 共 {len(songs)} 首")
        self.status_bar.showMessage(f"找到 {len(songs)} 首歌曲")
        self.search_results = songs
        self.results_list.clear()

        # 获取当前音源
        current_source = self.source_combo.currentText()

        if current_source == "网易云音乐":
            logger.info("网易云音源 - 跳过专辑封面获取")
            for i, song in enumerate(songs):
                duration = self.format_time(song["duration"])
                item_text = f"{i+1}. {song['name']} - {song['artists']} ({duration})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, i)
                self.results_list.addItem(item)
        else:

            cache_dir = self.settings["save_paths"]["cache"]
            if not os.path.exists(cache_dir):
                os.makedirs(cache_dir, exist_ok=True)
                logger.info(f"创建缓存目录: {cache_dir}")
            for i, song in enumerate(songs):
                duration = self.format_time(song["duration"])
                item_text = f"{i+1}. {song['name']} - {song['artists']} ({duration})"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, i)
                pic_url = song.get("pic", "")
                if pic_url:
                    try:
                        songid = song.get("id", f"song_{i}")
                        safe_songid = re.sub(r'[\\/*?:"<>|]', "", songid)
                        image_path = os.path.join(cache_dir, f"{safe_songid}.jpg")
                        if not os.path.exists(image_path):
                            logger.info(f"下载专辑封面: {pic_url}")
                            response = requests.get(pic_url, stream=True, timeout=10)
                            if response.status_code == 200:
                                with open(image_path, 'wb') as f:
                                    for chunk in response.iter_content(1024):
                                        f.write(chunk)
                                logger.info(f"封面保存到: {image_path}")
                            else:
                                logger.warning(f"封面下载失败: HTTP {response.status_code}")
                        if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                            pixmap = QPixmap(image_path)
                            if not pixmap.isNull():
                                pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                                item.setIcon(QIcon(pixmap))
                            else:
                                logger.warning(f"无效的图片文件: {image_path}")
                        else:
                            logger.warning(f"图片文件不存在或为空: {image_path}")
                    except Exception as e:
                        logger.error(f"加载专辑封面失败: {str(e)}")
                self.results_list.addItem(item)
            
    def song_selected(self, item):
        index = item.data(Qt.UserRole)
        if self.source_combo.currentText() == "网易云音乐":
            song_id = item.data(Qt.UserRole)  
            self.netease_worker.fetch_details(song_id)
        else:
            # 原有逻辑
            pass
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            logger.info(f"选择歌曲: {self.current_song['name']}")
            self.status_bar.showMessage(f"正在获取歌曲详情: {self.current_song['name']}")
            self.display_song_info(self.current_song)
            
    def display_song_info(self, song):
        if not song:
            self.song_info.setText("未能获取歌曲信息")
            self.download_button.setEnabled(False)            
            logger.warning("歌曲信息: 获取失败")
            return
        self.current_song_info = song
        self.download_button.setEnabled(True)        
        logger.info(f"显示歌曲信息: {song.get('name', '未知')}")
        info_text = (
            f"<b>歌曲名称:</b> {song.get('name', '未知')}<br>"
            f"<b>艺术家:</b> {song.get('artists', '未知')}<br>"
            f"<b>专辑:</b> {song.get('album', '未知')}<br>"
            f"<b>时长:</b> {self.format_time(song.get('duration', 0))}<br>"
            f"<b>下载链接:</b> <a href='{song.get('url', '')}'>{song.get('url', '')}</a>"
        )
        self.song_info.setHtml(info_text)
        self.lyrics_sync.load_lyrics(song.get("lrc", ""))
        self.status_bar.showMessage("歌曲信息加载完成")
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def display_netease_search_results(self, songs):
        """显示网易云搜索结果"""
        self.results_list.clear()
        for song in songs:
            duration = self.format_time(song["duration"])
            item_text = f"{song['name']} - {song['artists']} ({duration})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, song["id"])  # 存储歌曲ID
            self.results_list.addItem(item)
            
    def display_netease_details(self, details):
        """显示网易云歌曲详情"""
        info_text = (
            f"<b>歌曲名称:</b> {details.get('title', '未知')}<br>"
            f"<b>艺术家:</b> {details.get('author', '未知')}<br>"
            f"<b>播放链接:</b> <a href='{details.get('audio_url', '')}'>{details.get('audio_url', '')}</a>"
        )
        self.song_info.setHtml(info_text)
        self.download_button.setEnabled(True)
        self.current_song_info = details

    def handle_player_state_changed(self, state):
        """处理播放状态变化（重写以支持音乐室同步）"""
        if self.room_manager.current_room:
            if state == QMediaPlayer.PlayingState:
                self.room_manager.send_playback_command("播放")
            elif state == QMediaPlayer.PausedState:
                self.room_manager.send_playback_command("暂停")
            elif state == QMediaPlayer.StoppedState:
                self.room_manager.send_playback_command("停止")
    
    def play_next_song(self):
        if not self.playlist:
            return
        if self.repeat_mode == "single":
            self.play_song_by_index(self.current_play_index)
            return
        if self.is_random_play:
            next_index = random.randint(0, len(self.playlist) - 1)
        else:
            next_index = self.current_play_index + 1
            if next_index >= len(self.playlist):
                if self.repeat_mode == "list":
                    next_index = 0
                else:
                    self.stop_song()
                    return
        self.play_song_by_index(next_index)
    
    def play_song_by_index(self, index):
        if index < 0 or index >= len(self.playlist):
            return
        self.current_play_index = index
        song = self.playlist[index]
        self.current_song_info = song
        self.download_current_song_for_playback()
    
    def download_current_song_for_playback(self):
        if not self.current_song_info or 'url' not in self.current_song_info:
            return
        default_name = f"{self.current_song_info['name']}.mp3".replace("/", "_").replace("\\", "_")
        file_path = os.path.join(self.settings["save_paths"]["music"], default_name)
        if not os.path.exists(file_path):
            self.download_worker = MusicWorker()
            self.active_threads.append(self.download_worker)
            self.download_worker.download_finished.connect(self.handle_download_for_playback)
            self.download_worker.error_occurred.connect(self.display_error)
            self.download_worker.download_song(self.current_song_info['url'], file_path)
        else:
            self.play_downloaded_song(file_path)
    
    def handle_download_for_playback(self, file_path):
        self.play_downloaded_song(file_path)
    
    def play_downloaded_song(self, file_path):
        self.current_song_path = file_path
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.media_player.play()
        
        # 重置进度条
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        
        song = self.playlist[self.current_play_index]
        self.song_info.setText(f"<b>正在播放:</b> {song.get('name', '未知')} - {song.get('artists', '未知')}")
        self.results_list.setCurrentRow(self.current_play_index)
        
        # 显示外置歌词窗口
        self.external_lyrics.show()

    def display_error(self, error_msg):
        logger.error(f"显示错误: {error_msg}")
        self.status_bar.showMessage("发生错误")
        self.song_info.setText(f"错误信息:\n{error_msg}")
        QMessageBox.critical(self, "错误", f"操作失败:\n{error_msg}")
        
    def download_current_song(self):
        if not self.current_song_info or 'url' not in self.current_song_info:
            self.status_bar.showMessage("没有可下载的歌曲")
            logger.warning("下载请求: 没有可下载的歌曲")
            return
        if self.settings["other"]["auto_play"] and len(self.playlist) > 0 and self.playlist[0] == self.current_song_info:
            self.play_song_by_index(0)
        default_name = f"{self.current_song_info['name']}.mp3".replace("/", "_").replace("\\", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存歌曲", 
            os.path.join(self.settings["save_paths"]["music"], default_name), 
            "MP3文件 (*.mp3)"
        )
        if not file_path:
            logger.info("下载取消: 用户未选择保存路径")
            return
        logger.info(f"开始下载歌曲到: {file_path}")
        self.progress_dialog = QProgressDialog("下载歌曲...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("下载进度")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
        self.download_worker = MusicWorker()
        self.active_threads.append(self.download_worker)
        self.download_worker.download_progress.connect(self.update_download_progress)
        self.download_worker.download_finished.connect(self.download_completed)
        self.download_worker.finished.connect(lambda: self.remove_thread(self.download_worker))
        self.download_worker.finished.connect(self.remove_download_worker)
        self.download_worker.download_song(self.current_song_info['url'], file_path)
        
    def update_download_progress(self, progress):
        self.progress_dialog.setValue(progress)
        
    def cancel_download(self):
        logger.warning("下载取消: 用户取消")
        if hasattr(self, 'download_worker') and self.download_worker and self.download_worker.isRunning():
            self.download_worker.requestInterruption()
            self.download_worker.quit()
            self.download_worker.wait(1000)
            if self.download_worker.isRunning():
                self.download_worker.terminate()
                self.download_worker.wait()
        self.status_bar.showMessage("下载已取消")
        
    def download_completed(self, file_path):
        self.progress_dialog.close()
        self.status_bar.showMessage(f"歌曲下载完成: {file_path}")
        logger.info(f"下载完成: {file_path}")
        QMessageBox.information(self, "下载完成", f"歌曲已成功保存到:\n{file_path}")
        self.load_lyrics_for_song(file_path)
        if self.settings["other"]["auto_play"]:
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
            self.status_bar.showMessage("正在播放歌曲...")
        self.add_to_playlist(file_path, self.current_song_info)
            
    def play_song(self):
        if self.current_song_path:
            self.media_player.play()
            self.status_bar.showMessage("播放中...")

    def pause_song(self):
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.status_bar.showMessage("已暂停")

    def stop_song(self):
        self.media_player.stop()
        self.status_bar.showMessage("已停止")

    @staticmethod
    def format_time(duration_ms):
        duration = duration_ms // 1000
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"
        
    class RemoteControlServer(QObject):
        def __init__(self, app_instance, port=5000):
            super().__init__()
            self.app = Flask(__name__)
            self.port = port
            self.server_thread = None
            self.running = False
            self.main_window = app_instance
            self.setup_routes()
            
            # 日志配置
            logging.basicConfig(level=logging.INFO)
            self.logger = logging.getLogger("RemoteServer")

        def setup_routes(self):
            """设置API端点"""
            # 播放控制
            @self.app.route('/api/play', methods=['POST'])
            def api_play():
                self.logger.info("接收到播放命令")
                self.post_event(PlayEvent())
                return jsonify(status="success", message="播放命令已发送")

            @self.app.route('/api/pause', methods=['POST'])
            def api_pause():
                self.logger.info("接收到暂停命令")
                self.post_event(PauseEvent())
                return jsonify(status="success", message="暂停命令已发送")

            @self.app.route('/api/stop', methods=['POST'])
            def api_stop():
                self.logger.info("接收到停止命令")
                self.post_event(StopEvent())
                return jsonify(status="success", message="停止命令已发送")

            # 音量控制
            @self.app.route('/api/volume', methods=['POST'])
            def set_volume():
                data = request.json
                volume = data.get('volume')
                self.logger.info(f"设置音量: {volume}")
                self.post_event(VolumeEvent(volume))
                return jsonify(status="success", message=f"音量设置为 {volume}")

            # 歌曲切换
            @self.app.route('/api/next', methods=['POST'])
            def next_song():
                self.logger.info("切换到下一首")
                self.post_event(NextEvent())
                return jsonify(status="success", message="切换到下一首命令已发送")

            @self.app.route('/api/prev', methods=['POST'])
            def prev_song():
                self.logger.info("切换到上一首")
                self.post_event(PrevEvent())
                return jsonify(status="success", message="切换到上一首命令已发送")

            # 获取当前状态
            @self.app.route('/api/status', methods=['GET'])
            def get_status():
                self.logger.info("请求播放状态")
                return jsonify(self.main_window.get_remote_status())

            @self.app.route('/api/files', methods=['GET'])
            def get_files():
                path = request.args.get('path', self.main_window.settings["save_paths"]["music"])
                return jsonify(self.main_window.get_file_browser_content(path))
            
            # 播放指定文件
            @self.app.route('/api/play-file', methods=['POST'])
            def play_file():
                data = request.json
                file_path = data.get('path')
                self.logger.info(f"播放文件: {file_path}")
                self.post_event(PlayFileEvent(file_path))
                return jsonify(status="success", message=f"正在播放: {file_path}")

            # 遥控界面
            @self.app.route('/')
            def remote_control():
                return send_from_directory('static', 'remote.html')

            # 静态文件服务
            @self.app.route('/static/<path:path>')
            def static_files(path):
                return send_from_directory('static', path)

        def post_event(self, event):
            """向主线程发送事件"""
            if self.main_window:
                QApplication.postEvent(self.main_window, event)

        def start(self):
            """启动HTTP服务器"""
            if self.running:
                return
                
            def run_server():
                try:
                    self.logger.info(f"启动远程控制服务器，端口: {self.port}")
                    self.app.run(host='0.0.0.0', port=self.port, threaded=True)
                    self.running = True
                except Exception as e:
                    self.logger.error(f"服务器启动失败: {str(e)}")

            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            self.running = True

        def stop(self):
            """停止HTTP服务器"""
            if not self.running:
                return
                
            # Flask没有优雅停止方法，我们只能终止线程
            if self.server_thread and self.server_thread.is_alive():
                self.logger.info("停止远程控制服务器")
                # 实际上无法优雅停止Flask，需要手动终止
                # 在生产环境中应使用更强大的服务器如Waitress
                self.running = False
                # 发送一个终止信号
                try:
                    import requests
                    requests.get(f"http://localhost:{self.port}/shutdown", timeout=1)
                except:
                    pass

    def get_network_info(self):
        """获取网络信息"""
        try:
            # 获取本机IP地址
            ip = self.get_ip_address()
            
            # 简单判断网络连接状态（通过能否解析www.baidu.com）
            try:
                socket.gethostbyname("www.baidu.com")
                network_status = "已连接"
            except:
                network_status = "未连接"
                
            return {
                "ip_address": ip,
                "status": network_status
            }
        except Exception as e:
            logger.error(f"获取网络信息失败: {str(e)}")
            return {
                "ip_address": "未知",
                "status": "未知"
            }
    
    def event(self, event):
        """处理自定义事件"""
        if isinstance(event, PlayEvent):
            self.play_song()
        elif isinstance(event, PauseEvent):
            self.pause_song()
        elif isinstance(event, StopEvent):
            self.stop_song()
        elif isinstance(event, VolumeEvent):
            self.media_player.setVolume(event.volume)
        elif isinstance(event, NextEvent):
            self.play_next()
        elif isinstance(event, PrevEvent):
            self.play_previous()
        elif isinstance(event, PlayFileEvent):
            self.play_file_remote(event.file_path)
        return super().event(event)
    
    def get_remote_status(self):
        """获取当前播放状态"""
        status = {
            "current_song": self.current_song_info or {},
            "volume": self.media_player.volume(),
            "position": self.media_player.position(),
            "duration": self.media_player.duration(),
            "state": "playing" if self.media_player.state() == QMediaPlayer.PlayingState else "paused",
            "playlist": self.get_playlist_for_remote(),
            "network_info": self.get_network_info(),  # 添加网络信息
            "ip_address": self.get_ip_address()
        }
        return status
    
    def get_playlist_for_remote(self):
        """获取播放列表（简化版）"""
        playlist = []
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            playlist.append({
                "name": item.text(),
                "path": item.data(Qt.UserRole)
            })
        return playlist
    
    def play_file_remote(self, file_path):
        """远程播放文件"""
        if os.path.exists(file_path):
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
            
            # 添加到播放列表
            self.add_to_playlist(file_path)
            
            # 加载歌词
            self.load_lyrics_for_song(file_path)
            
            logger.info(f"播放文件: {file_path}")
            return True
        return False
    
    def get_files(self, path):
        """获取指定路径下的文件列表"""
        # 安全限制：只能访问音乐目录
        settings = load_settings()
        music_dir = settings["save_paths"]["music"]
        if not path.startswith(music_dir):
            return {"error": "访问受限"}
            
        if not os.path.exists(path):
            return {"error": "路径不存在"}
            
        files = []
        for entry in os.listdir(path):
            full_path = os.path.join(path, entry)
            if os.path.isfile(full_path) and entry.lower().endswith(('.mp3', '.wav', '.flac')):
                files.append({
                    "name": entry,
                    "path": full_path,
                    "size": os.path.getsize(full_path)
                })
        return {"path": path, "files": files}
    
    def get_ip_address(self):
        """获取本机IP地址"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"
    
    def update_network_status(self):
        """更新网络状态显示"""
        ip = self.get_ip_address()
        port = self.remote_server.port
        self.remote_button.setToolTip(f"手机访问: http://{ip}:{port}")
    
    def show_remote_options(self):
        """显示遥控选项菜单"""
        menu = QMenu(self)
        
        ip = self.get_ip_address()
        port = self.remote_server.port
        url = f"http://{ip}:{port}"
        
        # 打开浏览器
        open_browser_action = QAction("在浏览器中打开", self)
        open_browser_action.triggered.connect(lambda: QDesktopServices.openUrl(QUrl(url)))
        menu.addAction(open_browser_action)
        
        # 生成二维码
        qr_action = QAction("生成二维码", self)
        qr_action.triggered.connect(lambda: self.generate_qr_code(url))
        menu.addAction(qr_action)
        
        # 复制链接
        copy_action = QAction("复制链接", self)
        copy_action.triggered.connect(lambda: QApplication.clipboard().setText(url))
        menu.addAction(copy_action)
        
        # 服务器控制
        if self.remote_server.running:
            stop_action = QAction("停止服务器", self)
            stop_action.triggered.connect(self.remote_server.stop)
            menu.addAction(stop_action)
        else:
            start_action = QAction("启动服务器", self)
            start_action.triggered.connect(self.remote_server.start)
            menu.addAction(start_action)
        
        menu.exec_(self.remote_button.mapToGlobal(
            QPoint(0, self.remote_button.height())
        ))
    
    def generate_qr_code(self, url):
        """生成访问二维码"""
        try:
            import qrcode
            from PIL import Image, ImageQt
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # 转换为QPixmap
            qimg = ImageQt.toqimage(img)
            pixmap = QPixmap.fromImage(qimg)
            
            # 显示对话框
            dialog = QDialog(self)
            dialog.setWindowTitle("手机遥控二维码")
            layout = QVBoxLayout()
            label = QLabel()
            label.setPixmap(pixmap)
            layout.addWidget(label)
            
            # 添加文本
            url_label = QLabel(f"访问地址: {url}")
            url_label.setStyleSheet("font-weight: bold; font-size: 14px;")
            layout.addWidget(url_label)
            
            dialog.setLayout(layout)
            dialog.exec_()
            
        except ImportError:
            QMessageBox.warning(self, "错误", "需要安装qrcode和Pillow库")

class MusicRoomServer(QObject):
    started = pyqtSignal(int)  # 信号：服务器启动成功，参数为端口号
    stopped = pyqtSignal()     # 信号：服务器停止
    error_occurred = pyqtSignal(str)  # 信号：发生错误
    
    def __init__(self, port=5001, parent=None):
        super().__init__(parent)
        self.port = port
        self.server = None
        self.loop = None
        self.running = False
        self.rooms = {}
        self.user_rooms = {}
        self.connections = {}
        self.music_room_server = None 
        
    def is_running(self):
        return self.running
        
    def run(self):
        """运行服务器（在独立线程中调用）"""
        try:
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            
            # 创建服务器并显式传递事件循环
            start_server = websockets.serve(
                self.handle_connection, 
                "0.0.0.0", 
                self.port,
                loop=self.loop  # 显式传递事件循环
            )
            
            # 启动服务器并等待其准备就绪
            self.server = self.loop.run_until_complete(start_server)
            self.running = True
            self.started.emit(self.port)
            
            logger.info(f"音乐室服务器已启动，端口: {self.port}")
            
            # 运行事件循环
            self.loop.run_forever()
            
        except Exception as e:
            self.running = False
            self.error_occurred.emit(str(e))
            logger.error(f"音乐室服务器错误: {str(e)}\n{traceback.format_exc()}")
        finally:
            # 清理资源
            if self.loop and not self.loop.is_closed():
                try:
                    # 关闭所有WebSocket连接
                    if self.server:
                        self.loop.run_until_complete(self.server.close())
                        self.loop.run_until_complete(self.server.wait_closed())
                    
                    # 取消所有任务
                    tasks = asyncio.all_tasks(self.loop)
                    for task in tasks:
                        task.cancel()
                    # 等待任务完成
                    self.loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
                    
                    # 关闭事件循环
                    self.loop.close()
                except:
                    pass
                
            self.running = False
            self.stopped.emit()
            logger.info("音乐室服务器已关闭") 
    
    def stop(self):
        """停止服务器"""
        if self.running and self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
            self.running = False
    
    async def handle_connection(self, websocket, path):
        """处理客户端连接"""
        user_id = None
        room_id = None
        
        try:
            async for message in websocket:
                try:
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
                        
                except Exception as e:
                    logger.error(f"处理消息错误: {str(e)}")
                    
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
                        asyncio.run_coroutine_threadsafe(self.broadcast_room_list(), self.loop)
                        asyncio.run_coroutine_threadsafe(
                            self.notify_room_update(room_id, "closed", user_id), 
                            self.loop
                        )
                    else:
                        asyncio.run_coroutine_threadsafe(self.broadcast_room_list(), self.loop)
                        asyncio.run_coroutine_threadsafe(
                            self.notify_room_update(room_id, "user_left", user_id), 
                            self.loop
                        )
    
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

# =============== 歌词渲染函数 ===============
def draw_lyrics(
    lyrics: str,
    image_width=1000,
    font_size=30,
    line_spacing=20,
    top_color=(255, 250, 240),
    bottom_color=(235, 255, 247),
    text_color=(70, 70, 70),
) -> bytes:
    lines = lyrics.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned = re.sub(r"\[\d{2}:\d{2}(?:\.\d{2,3})?\]", "", line)
        cleaned_lines.append(cleaned if cleaned != "" else "")
    try:
        font = ImageFont.truetype(os.O_PATH, font_size)
    except IOError:
        font = ImageFont.load_default()
        logger.warning("使用默认字体渲染歌词")
    dummy_img = Image.new("RGB", (image_width, 1))
    draw = ImageDraw.Draw(dummy_img)
    line_heights = [
        draw.textbbox((0, 0), line if line.strip() else "　", font=font)[3]
        for line in cleaned_lines
    ]
    total_height = sum(line_heights) + line_spacing * (len(cleaned_lines) - 1) + 100
    img = Image.new("RGB", (image_width, total_height))
    for y in range(total_height):
        ratio = y / total_height
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        for x in range(image_width):
            img.putpixel((x, y), (r, g, b))
    draw = ImageDraw.Draw(img)
    y = 50
    for line, line_height in zip(cleaned_lines, line_heights):
        text = line if line.strip() else "　"
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((image_width - text_width) / 2, y), text, font=font, fill=text_color)
        y += line_height + line_spacing
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=90)
    img_bytes.seek(0)
    return img_bytes.getvalue()



# =============== 主程序入口 ===============
if __name__ == "__main__":
    os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    window = MusicPlayerApp()
    window.show()
    sys.exit(app.exec_())
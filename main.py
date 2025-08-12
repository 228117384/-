import time
import datetime
import sys
import os
import json
import random
import re
import traceback
import io
import logging
import requests
import subprocess
import webbrowser
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import (
    QApplication, QGridLayout, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QTextEdit, QScrollArea, QFrame,
    QFileDialog, QProgressDialog, QMessageBox, QComboBox, QAction, QMenu,
    QDialog, QGroupBox, QSpinBox, QCheckBox, QTabWidget, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPlainTextEdit, QMenuBar, QStatusBar, QColorDialog, QInputDialog,
    QProgressBar, QSlider, QDialogButtonBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QObject, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor, QIcon, QDesktopServices
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import asyncio
import aiohttp
import aiofiles
import httpx
import urllib.parse
import traceback
import socket
from bs4 import BeautifulSoup
import hashlib
from bilibili_api import video, Credential
from bilibili_api.video import VideoDownloadURLDataDetecter
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import QUrl
from PyQt5.QtWidgets import QFontDialog
from PyQt5.QtCore import QByteArray
from music_player import MusicPlayerApp

def get_settings_path():
    """获取设置文件路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    settings_path = os.path.join(base_dir, "settings.json")
    logging.info(f"设置文件路径: {settings_path}")
    return settings_path

def load_default_settings():
    """加载默认设置"""
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
    
    if not os.path.exists(settings_path):
        save_settings(load_default_settings())
        return load_default_settings()
    
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("music_app.log", encoding='utf-8'),
        UTF8StreamHandler()
    ]
)
logger = logging.getLogger("MusicApp")

FONT_PATH = "simhei.ttf"

def resource_path(relative_path):
    """获取资源的绝对路径（支持PyInstaller打包环境）"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path = os.path.join(base_path, relative_path)
    return os.path.normpath(path)

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
                    self.BILIBILI_SEARCH_API, params=params, headers=self.BILIBILI_HEADER
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
            command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
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
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px;")
        self.results_list.setIconSize(QSize(100, 100))
        self.results_list.itemDoubleClicked.connect(self.video_selected)
        layout.addWidget(self.results_list, 4)
        self.info_label = QLabel("选择视频查看详情")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd;")
        layout.addWidget(self.info_label, 1)
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
                    self.BILIBILI_SEARCH_API, params=params, headers=self.BILIBILI_HEADER
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
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px;")
        self.results_list.setIconSize(QSize(100, 100))
        self.results_list.itemDoubleClicked.connect(self.video_selected)
        layout.addWidget(self.results_list, 4)
        self.info_label = QLabel("选择视频查看详情")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("padding: 10px; background-color: #f0f0f0; border: 1px solid #ddd;")
        layout.addWidget(self.info_label, 1)
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
        playlist_layout = QHBoxLayout()
        playlist_layout.addWidget(QLabel("选择播放列表:"))
        self.playlist_combo = QComboBox()
        self.playlist_combo.addItems(self.playlist_manager.playlists.keys())
        self.playlist_combo.currentTextChanged.connect(self.update_song_list)
        playlist_layout.addWidget(self.playlist_combo)
        new_playlist_layout = QHBoxLayout()
        new_playlist_layout.addWidget(QLabel("新建播放列表:"))
        self.new_playlist_input = QLineEdit()
        self.new_playlist_button = QPushButton("创建")
        self.new_playlist_button.clicked.connect(self.create_playlist)
        new_playlist_layout.addWidget(self.new_playlist_input)
        new_playlist_layout.addWidget(self.new_playlist_button)      
        layout.addLayout(playlist_layout)
        layout.addLayout(new_playlist_layout)
        self.song_list = QListWidget()
        layout.addWidget(QLabel("播放列表歌曲:"))
        layout.addWidget(self.song_list)
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

class LyricsSync:
    def __init__(self, media_player, external_lyrics_window):
        self.media_player = media_player
        self.external_lyrics_window = external_lyrics_window
        self.lyrics_data = []
        
    def load_lyrics(self, lyrics_text):
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
        self.lyrics_data.sort(key=lambda x: x[0])

    def update_position(self):
        if not self.lyrics_data:
            return
            
        position = self.media_player.position()
        current_lyric = ""
        next_lyric = ""
        
        for i, (time_ms, text) in enumerate(self.lyrics_data):
            if time_ms <= position:
                current_lyric = text
            else:
                break
        self.external_lyrics_window.update_lyrics(current_lyric)

class SleepTimerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("睡眠定时器")
        self.setGeometry(300, 300, 300, 150)
        layout = QVBoxLayout()
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("定时关闭时间:"))
        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(1, 120)
        self.minutes_spin.setValue(30)
        time_layout.addWidget(self.minutes_spin)
        time_layout.addWidget(QLabel("分钟"))
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("启动")
        self.start_button.clicked.connect(self.start_timer)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.cancel_timer)
        self.cancel_button.setEnabled(False)
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.cancel_button)
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

class EqualizerDialog(QDialog):
    def __init__(self, media_player, parent=None):
        super().__init__(parent)
        self.setWindowTitle("均衡器设置")
        self.setGeometry(300, 300, 400, 400)
        self.media_player = media_player
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        preset_layout = QHBoxLayout()
        preset_layout.addWidget(QLabel("预设:"))
        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["默认", "流行", "摇滚", "古典", "爵士", "电子"])
        self.preset_combo.currentTextChanged.connect(self.apply_preset)
        preset_layout.addWidget(self.preset_combo)
        layout.addLayout(preset_layout)
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

    def fetch_lyrics(self, song_id):
        """获取歌词"""
        logger.info(f"获取歌词: ID={song_id}")
        url = f"https://music.163.com/api/song/lyric?id={song_id}&lv=1&kv=1&tv=-1"
        try:
            response = requests.get(url, headers=self.header, cookies=self.cookies)
            result = response.json()
            
            if "lrc" in result and "lyric" in result["lrc"]:
                logger.info("歌词获取成功")
                return result["lrc"]["lyric"]
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
    """网易云音乐专用工作线程（从文档1迁移并修改）"""
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

                        if response.status_code != 200:
                            logger.warning(f"API返回非200状态码: {response.status_code}, 尝试重试...")
                            retry_count += 1
                            time.sleep(1)  
                            continue
                            
                        if not response.text.strip():
                            logger.warning("API返回空响应, 尝试重试...")
                            retry_count += 1
                            time.sleep(1)
                            continue

                        if "verify" in response.url or "captcha" in response.url:
                            logger.error("API请求被重定向到验证页面")
                            self.error_occurred.emit("请求被拦截，可能需要解决验证码")
                            return
                
                        content_type = response.headers.get('Content-Type', '')
                        if 'application/json' not in content_type:
                            logger.warning(f"API返回非JSON内容: {content_type}, 原始内容: {response.text[:200]}")
                
                            if 'text/html' in content_type:
                                soup = BeautifulSoup(response.text, 'html.parser')
                                title = soup.title.string if soup.title else "未知错误"
                                self.error_occurred.emit(f"API返回HTML页面: {title}")
                                return
                
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            logger.error(f"无法解析JSON响应, 原始内容: {response.text[:200]}")
                            self.error_occurred.emit(f"API返回了无效的JSON数据: {response.text[:100]}...")
                            return
                        break

                    except requests.exceptions.Timeout:
                        logger.warning(f"API请求超时, 尝试重试 ({retry_count+1}/{max_retries})")
                        retry_count += 1
                        time.sleep(2)
                    except requests.exceptions.ConnectionError:
                        logger.warning(f"网络连接错误, 尝试重试 ({retry_count+1}/{max_retries})")
                        retry_count += 1
                        time.sleep(2)
            
                if retry_count >= max_retries:
                    self.error_occurred.emit("API请求失败，请检查网络连接或稍后再试")
                    return

                active_source_name = config.get("name", "")
                if active_source_name == "网易云音乐":
                    if data["code"] == 200:
                        songs = data["result"]["songs"]
                        formatted_songs = []
                        for song in songs:
                            artists = "、".join([ar["name"] for ar in song.get("ar", [])])
                            album_info = song.get("al", {})
                            album_name = album_info.get("name", "未知专辑")
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
                        logger.error(f"网易云音乐API错误: {data.get('message')}")
                        formatted_songs = []
                        video_list = []

                elif active_source_name == "酷狗音乐":
                    search_response = response.json()
                    if search_response.get("status") == 1 and search_response.get("data"):
                        items = search_response["data"].get("lists", [])
                        formatted_songs = []
                    
                        for item in items:
                            song_hash = item.get("FileHash", "")
                            if song_hash:
                                params = config.get("params", {}).copy()
                                params["hash"] = song_hash
                                full_info_url = config["url"] + "?" + urllib.parse.urlencode(params)
                                full_info_response = requests.get(full_info_url, headers=headers, timeout=30)
                                if full_info_response.status_code == 200:
                                    full_info = full_info_response.json()
                                
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
                        logger.error(f"酷狗音乐搜索失败: {search_response.get('error')}")
                        video_list = []

                elif active_source_name == "公共音乐API":
                    if data.get("code") == 200:
                        error_msg = data.get("message", "未知错误")
                        logger.error(f"公共音乐API错误: {error_msg}")
                        self.error_occurred.emit(f"公共音乐API错误: {error_msg}")
                        video_list = []
                    else:
                        video_list = data.get("data", [])

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
                        if not isinstance(song, dict):
                            continue
                            
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
                if len(video_list) > max_results:
                    video_list = video_list[:max_results]
                if self.isInterruptionRequested():
                    return
                self.search_finished.emit(formatted_songs)
                self.search_finished.emit(video_list)

            elif self.mode == "download":
                success = self.download_file(self.audio_url, self.file_path)
                if success:
                    self.download_finished.emit(self.file_path)
                else:
                    self.error_occurred.emit("歌曲下载失败")
        except Exception as e:
            error_msg = f"发生错误: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
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
            
            if hasattr(self, 'lrc_url') and self.lrc_url and hasattr(self, 'lrc_path'):
                try:
                    lrc_response = requests.get(self.lrc_url, headers=headers, timeout=10)
                    if lrc_response.status_code == 200:
                        with open(self.lrc_path, 'w', encoding='utf-8') as f:
                            f.write(lrc_response.text)
                        logger.info(f"歌词已保存到: {self.lrc_path}")
                    else:
                        logger.warning(f"歌词下载失败: HTTP {lrc_response.status_code}")
                except Exception as e:
                    logger.error(f"下载歌词失败: {str(e)}")

            lyrics = self.current_song_info.get('lrc', '')
            if lyrics:
                lrc_path = os.path.splitext(file_path)[0] + '.lrc'
                try:
                    with open(lrc_path, 'w', encoding='utf-8') as lrc_file:
                        lrc_file.write(lyrics)
                    logger.info(f"歌词已保存到: {lrc_path}")
                except Exception as e:
                    logger.error(f"保存歌词文件失败: {str(e)}")
            
            logger.info(f"歌曲下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载歌曲失败: {str(e)}")
            return False
    
    def parse_duration(self, duration_val):
        """解析不同格式的时长"""
        if isinstance(duration_val, int):
            return duration_val
    
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
    
        return 0
    
    def download_file(self, url, file_path):
        try:
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
            return 
        
    def play_downloaded_song(self, file_path):
        self.current_song_path = file_path
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.media_player.play()
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        song = self.playlist[self.current_play_index]
        self.song_info.setText(f"<b>正在播放:</b> {song.get('name', '未知')} - {song.get('artists', '未知')}")
        self.results_list.setCurrentRow(self.current_play_index)
        self.external_lyrics_window.show()
        self.lyrics_sync.load_lyrics("")
        self.external_lyrics.update_lyrics("没有歌词")

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 700, 500)
        self.settings = load_settings()
        self.parent = parent
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        self.tabs = QTabWidget()
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
        other_group = QGroupBox("其他设置")
        other_form = QFormLayout()
        self.max_results_spin = QSpinBox()
        self.max_results_spin.setRange(5, 100)
        self.auto_play_check = QCheckBox("下载后自动播放")
        other_form.addRow("最大获取数量:", self.max_results_spin)
        other_form.addRow(self.auto_play_check)
        other_group.setLayout(other_form)
        save_layout.addWidget(save_group)
        save_layout.addWidget(bg_group)
        save_layout.addWidget(other_group)
        save_layout.addStretch()
        save_tab.setLayout(save_layout)
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
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_source_names())
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("如需API密钥请在此输入")
        source_form.addRow("选择音源:", self.source_combo)
        source_form.addRow("API密钥:", self.api_key_edit)
        source_group.setLayout(source_form)
        source_layout.addWidget(source_group)
        source_tab.setLayout(source_layout)
        test_button = QPushButton("测试连接")
        test_button.clicked.connect(self.test_api_connection)
        source_form.addRow(test_button)
        dns_button = QPushButton("刷新DNS缓存")
        dns_button.clicked.connect(self.refresh_dns_cache)
        source_form.addRow(dns_button)
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
        bilibili_button_layout = QHBoxLayout()
        self.bilibili_video_button = QPushButton("搜索B站视频")
        self.bilibili_video_button.setStyleSheet("padding: 8px; background-color: rgba(219, 68, 83, 200); color: white; font-weight: bold;")
        self.bilibili_video_button.clicked.connect(self.open_bilibili_video_search)
        bilibili_button_layout.addWidget(self.bilibili_video_button)
        bilibili_layout.addLayout(bilibili_button_layout)
        bilibili_tab.setLayout(bilibili_layout)
        author_tab = QWidget()
        author_layout = QVBoxLayout()   
        author_info = QLabel("欢迎使用Railgun_lover的音乐项目！")
        author_info.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        author_layout.addWidget(author_info, alignment=Qt.AlignCenter)
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
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setLineWidth(1)
        author_layout.addWidget(separator)
        contact_info = QLabel("项目开源免费，欢迎使用和交流！")
        contact_info.setStyleSheet("font-size: 14px; color: #888888; margin-top: 15px;")
        contact_info.setAlignment(Qt.AlignCenter)
        author_layout.addWidget(contact_info)
        author_tab.setLayout(author_layout)
        self.tabs.addTab(save_tab, "保存设置")
        self.tabs.addTab(source_tab, "音源设置")
        self.tabs.addTab(bilibili_tab, "Bilibili设置")
        self.tabs.addTab(author_tab, "作者主页")
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
                self.settings["sources"]["sources_list"] = [
                    s for s in self.settings["sources"]["sources_list"]
                    if s["name"] != current_source
                ]
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
        for source in self.settings["sources"]["sources_list"]:
            if source["name"] == active_source:
                source["api_key"] = self.api_key_edit.text()
                break
        if "bilibili" not in self.settings:
            self.settings["bilibili"] = {}
        self.settings["bilibili"]["cookie"] = self.bilibili_cookie_edit.text()
        self.settings["bilibili"]["max_duration"] = self.max_duration_spin.value()
        if save_settings(self.settings):
            if self.parent:
               self.parent.refresh_source_combo()
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "保存设置失败，请检查日志")

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
        self.tabs = QTabWidget()
        lyrics_tab = QWidget()
        lyrics_layout = QVBoxLayout()
        lyrics_label = QLabel("输入歌词（支持LRC格式）：")
        lyrics_layout.addWidget(lyrics_label)
        self.lyrics_input = QTextEdit()
        self.lyrics_input.setPlaceholderText("输入歌词内容...")
        lyrics_layout.addWidget(self.lyrics_input)
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
        generate_btn = QPushButton("生成歌词图片")
        generate_btn.clicked.connect(self.generate_lyrics_image)
        lyrics_layout.addWidget(generate_btn)
        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignCenter)
        self.preview_label.setMinimumHeight(200)
        self.preview_label.setStyleSheet("background-color: #f0f0f0; border: 1px solid #ddd;")
        lyrics_layout.addWidget(self.preview_label)
        lyrics_tab.setLayout(lyrics_layout)
        convert_tab = QWidget()
        convert_layout = QVBoxLayout()
        file_layout = QHBoxLayout()
        self.file_path_edit = QLineEdit()
        self.file_path_edit.setPlaceholderText("选择音频文件...")
        browse_btn = QPushButton("浏览...")
        browse_btn.clicked.connect(self.select_audio_file)
        file_layout.addWidget(self.file_path_edit)
        file_layout.addWidget(browse_btn)
        convert_layout.addLayout(file_layout)
        format_layout = QHBoxLayout()
        format_label = QLabel("输出格式:")
        self.format_combo = QComboBox()
        self.format_combo.addItems(["MP3", "WAV", "FLAC", "M4A"])
        format_layout.addWidget(format_label)
        format_layout.addWidget(self.format_combo)
        convert_layout.addLayout(format_layout)
        convert_btn = QPushButton("开始转换")
        convert_btn.clicked.connect(self.convert_audio)
        convert_layout.addWidget(convert_btn)
        self.convert_status = QLabel("")
        self.convert_status.setAlignment(Qt.AlignCenter)
        convert_layout.addWidget(self.convert_status)
        convert_tab.setLayout(convert_layout)
        clean_tab = QWidget()
        clean_layout = QVBoxLayout()
        clean_label = QLabel("清理缓存和临时文件:")
        clean_layout.addWidget(clean_label)
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
        clean_btn = QPushButton("开始清理")
        clean_btn.clicked.connect(self.clean_files)
        clean_layout.addWidget(clean_btn)
        self.clean_status = QLabel("")
        self.clean_status.setAlignment(Qt.AlignCenter)
        clean_layout.addWidget(self.clean_status)
        clean_tab.setLayout(clean_layout)
        batch_tab = QWidget()
        batch_layout = QVBoxLayout()
        batch_label = QLabel("批量下载歌曲:")
        batch_layout.addWidget(batch_label)
        self.song_list = QTextEdit()
        self.song_list.setPlaceholderText("每行输入一首歌曲名称")
        batch_layout.addWidget(self.song_list)
        download_btn = QPushButton("开始下载")
        download_btn.clicked.connect(self.batch_download)
        batch_layout.addWidget(download_btn)
        self.download_status = QLabel("")
        self.download_status.setAlignment(Qt.AlignCenter)
        batch_layout.addWidget(self.download_status)
        batch_tab.setLayout(batch_layout)
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
            pixmap = QPixmap()
            pixmap.loadFromData(img_data)
            if not pixmap.isNull():
                pixmap = pixmap.scaled(550, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                self.preview_label.setPixmap(pixmap)
            else:
                QMessageBox.warning(self, "错误", "生成预览失败")
                return
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

            if self.cache_check.isChecked():
                for file in Path(cache_dir).glob("*.*"):
                    if file.is_file():
                        total_size += file.stat().st_size
                        file.unlink()
                        file_count += 1
    
            if self.temp_check.isChecked() and os.path.exists(temp_dir):
                for file in Path(temp_dir).rglob("*.*"):
                    if file.is_file():
                        total_size += file.stat().st_size
                        file.unlink()
                        file_count += 1
    
            if self.preview_check.isChecked():
                preview_dir = os.path.abspath(os.path.join("data", "previews"))
                if os.path.exists(preview_dir):
                    for file in Path(preview_dir).rglob("*.*"):
                        if file.is_file():
                            total_size += file.stat().st_size
                            file.unlink()
                            file_count += 1
            
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

        self.progress_dialog = QProgressDialog("批量下载歌曲...", "取消", 0, len(song_names), self)
        self.progress_dialog.setWindowTitle("批量下载")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.canceled.connect(self.cancel_batch_download)
        self.progress_dialog.show()
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
                self.msleep(1000)  
                self.success_count += 1
            except Exception:
                self.fail_count += 1
                
    def requestInterruption(self):
        """请求停止下载"""
        self._stop_requested = True


class ExternalLyricsWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
        opacity = lyrics_settings.get("opacity", 100) / 100.0
        self.setWindowOpacity(opacity)
        self.setWindowTitle("歌词 - Railgun_lover")
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        self.lyrics_label = QLabel("没有歌词")
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #FF5722;
                background-color: transparent;
                padding: 10px;
            }
        """)
        layout.addWidget(self.lyrics_label)
        
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        self.setGeometry(
            (screen_geometry.width() - 800) // 2,
            screen_geometry.height() - 150,
            800,
            100
        )
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.load_settings()
        
    def show_context_menu(self, pos):
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
        
        font_action = QAction("设置字体", self)
        font_action.triggered.connect(self.set_font)
        menu.addAction(font_action)
        color_action = QAction("设置颜色", self)
        color_action.triggered.connect(self.set_color)
        menu.addAction(color_action)
        hide_action = QAction("隐藏歌词", self)
        hide_action.triggered.connect(self.hide_lyrics)
        menu.addAction(hide_action)
        menu.addSeparator()
        close_action = QAction("关闭", self)
        close_action.triggered.connect(self.close)
        menu.addAction(close_action)
        menu.exec_(self.mapToGlobal(pos))

    def load_settings(self):
        settings = load_settings()
        lyrics_settings = settings.get("external_lyrics", {})
        
        if "geometry" in lyrics_settings:
            geometry = QByteArray.fromHex(lyrics_settings["geometry"].encode())
            self.restoreGeometry(geometry)
        
        if "font" in lyrics_settings:
            font = QFont()
            font.fromString(lyrics_settings["font"])
            self.lyrics_label.setFont(font)
        
        if "color" in lyrics_settings:
            color = lyrics_settings["color"]
            self.lyrics_label.setStyleSheet(f"""
                QLabel {{
                    font-size: {self.lyrics_label.font().pointSize()}px;
                    font-weight: bold;
                    color: {color};
                    background-color: transparent;
                    padding: 10px;
                }}
            """)
    
    def set_font(self):
        font, ok = QFontDialog.getFont(self.lyrics_label.font(), self, "选择字体")
        if ok:
            self.lyrics_label.setFont(font)
    
    def set_color(self):
        color = QColorDialog.getColor(self.lyrics_label.palette().color(QPalette.WindowText), self, "选择颜色")
        if color.isValid():
            self.lyrics_label.setStyleSheet(f"""
                QLabel {{
                    font-size: {self.lyrics_label.font().pointSize()}px;
                    font-weight: bold;
                    color: {color.name()};
                    background-color: transparent;
                    padding: 10px;
                }}
            """)
    
    def hide_lyrics(self):
        self.hide()
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def mouseDoubleClickEvent(self, event):
        self.hide_lyrics()
    
    def update_lyrics(self, text):
        self.lyrics_label.setText(text)
        if not self.isVisible():
            self.show()


class LyricsSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("歌词设置")
        self.setGeometry(300, 300, 500, 400)
        self.parent = parent
        self.settings = load_settings()
        self.lyrics_settings = self.settings.get("lyrics", {
            "show_lyrics": True,
            "show_external_lyrics": True,
            "lyrics_path": ""
        })
        self.init_ui()
        self.load_settings()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        show_group = QGroupBox("歌词显示设置")
        show_layout = QVBoxLayout()
        
        self.show_lyrics_check = QCheckBox("显示歌词")
        self.show_lyrics_check.setChecked(self.lyrics_settings.get("show_lyrics", True))
        show_layout.addWidget(self.show_lyrics_check)
        self.external_lyrics_check = QCheckBox("显示外置歌词窗口")
        self.external_lyrics_check.setChecked(self.lyrics_settings.get("show_external_lyrics", True))
        show_layout.addWidget(self.external_lyrics_check)
    
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("歌词文件路径:"))
        self.lyrics_path_edit = QLineEdit()
        self.lyrics_path_edit.setReadOnly(True)
        self.lyrics_path_edit.setPlaceholderText("未选择歌词文件")
        file_layout.addWidget(self.lyrics_path_edit)
        
        browse_button = QPushButton("浏览...")
        browse_button.clicked.connect(self.select_lyrics_file)
        file_layout.addWidget(browse_button)
        
        preview_button = QPushButton("预览歌词")
        preview_button.clicked.connect(self.preview_lyrics)
        file_layout.addWidget(preview_button)
        
        show_layout.addLayout(file_layout)
        show_group.setLayout(show_layout)
        
        auto_group = QGroupBox("歌词下载设置")
        auto_layout = QVBoxLayout()
        
        self.auto_download_check = QCheckBox("自动下载歌词（如果有）")
        self.auto_download_check.setChecked(self.lyrics_settings.get("auto_download", True))
        auto_layout.addWidget(self.auto_download_check)
        
        self.auto_save_check = QCheckBox("自动保存歌词文件")
        self.auto_save_check.setChecked(self.lyrics_settings.get("auto_save", True))
        auto_layout.addWidget(self.auto_save_check)
        auto_group.setLayout(auto_layout)
        position_group = QGroupBox("歌词窗口位置")
        position_layout = QGridLayout()
        position_layout.addWidget(QLabel("位置:"), 0, 0)
        self.position_combo = QComboBox()
        self.position_combo.addItems(["屏幕底部", "屏幕顶部", "屏幕中央", "自定义位置"])
        position_layout.addWidget(self.position_combo, 0, 1)
        position_layout.addWidget(QLabel("透明度:"), 1, 0)
        self.opacity_slider = QSlider(Qt.Horizontal)
        self.opacity_slider.setRange(30, 100)
        self.opacity_slider.setValue(100)
        position_layout.addWidget(self.opacity_slider, 1, 1)
        position_group.setLayout(position_layout)
        button_layout = QHBoxLayout()
        self.apply_button = QPushButton("应用")
        self.apply_button.clicked.connect(self.apply_settings)
        self.ok_button = QPushButton("确定")
        self.ok_button.clicked.connect(self.apply_and_close)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)
        layout.addWidget(show_group)
        layout.addWidget(auto_group)
        layout.addWidget(position_group)
        layout.addLayout(button_layout)
        self.setLayout(layout)
        
    def load_settings(self):
        self.show_lyrics_check.setChecked(self.lyrics_settings.get("show_lyrics", True))
        self.lyrics_path_edit.setText(self.lyrics_settings.get("lyrics_path", ""))
        self.auto_download_check.setChecked(self.lyrics_settings.get("auto_download", True))
        self.auto_save_check.setChecked(self.lyrics_settings.get("auto_save", True))
        
        position = self.lyrics_settings.get("position", "屏幕底部")
        index = self.position_combo.findText(position)
        if index >= 0:
            self.position_combo.setCurrentIndex(index)

        opacity = self.lyrics_settings.get("opacity", 100)
        self.opacity_slider.setValue(opacity)
    
    def select_lyrics_file(self):
        lrc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lrc")
        if not os.path.exists(lrc_dir):
            os.makedirs(lrc_dir, exist_ok=True)
            
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择歌词文件", 
            lrc_dir, 
            "歌词文件 (*.lrc);;所有文件 (*.*)"
        )
        
        if file_path:
            self.lyrics_path_edit.setText(file_path)
    
    def preview_lyrics(self):
        lyrics_path = self.lyrics_path_edit.text()
        if not lyrics_path or not os.path.exists(lyrics_path):
            QMessageBox.warning(self, "错误", "歌词文件不存在")
            return
            
        try:
            with open(lyrics_path, 'r', encoding='utf-8') as f:
                lyrics_content = f.read()
                
            preview_dialog = QDialog(self)
            preview_dialog.setWindowTitle("歌词预览")
            preview_dialog.setGeometry(300, 300, 600, 500)
            layout = QVBoxLayout()
            
            lyrics_edit = QTextEdit()
            lyrics_edit.setPlainText(lyrics_content)
            lyrics_edit.setReadOnly(True)
            lyrics_edit.setStyleSheet("font-family: 'Microsoft YaHei', sans-serif; font-size: 14px;")
            layout.addWidget(lyrics_edit)
            
            preview_dialog.setLayout(layout)
            preview_dialog.exec_()
        except Exception as e:
            logger.error(f"预览歌词失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法预览歌词:\n{str(e)}")
    
    def apply_settings(self):
        self.lyrics_settings["show_lyrics"] = self.show_lyrics_check.isChecked()
        self.lyrics_settings["show_external_lyrics"] = self.external_lyrics_check.isChecked() 
        self.lyrics_settings["lyrics_path"] = self.lyrics_path_edit.text()
        self.lyrics_settings["auto_download"] = self.auto_download_check.isChecked()
        self.lyrics_settings["auto_save"] = self.auto_save_check.isChecked()
        self.lyrics_settings["position"] = self.position_combo.currentText()
        self.lyrics_settings["opacity"] = self.opacity_slider.value()
        self.settings["lyrics"] = self.lyrics_settings
        save_settings(self.settings)
        
        
        if self.parent and hasattr(self.parent, 'external_lyrics'):
            if self.lyrics_settings["show_external_lyrics"]:
                self.parent.external_lyrics.show()
            else:
                self.parent.external_lyrics.hide()
            opacity = self.lyrics_settings["opacity"] / 100.0
            self.parent.external_lyrics.setWindowOpacity(opacity)
            position = self.lyrics_settings["position"]
            screen_geometry = QApplication.primaryScreen().availableGeometry()
            
            if position == "屏幕底部":
                self.parent.external_lyrics.move(
                    (screen_geometry.width() - self.parent.external_lyrics.width()) // 2,
                    screen_geometry.height() - 150
                )
            elif position == "屏幕顶部":
                self.parent.external_lyrics.move(
                    (screen_geometry.width() - self.parent.external_lyrics.width()) // 2,
                    50
                )
            elif position == "屏幕中央":
                self.parent.external_lyrics.move(
                    (screen_geometry.width() - self.parent.external_lyrics.width()) // 2,
                    (screen_geometry.height() - self.parent.external_lyrics.height()) // 2
                )
        
        QMessageBox.information(self, "成功", "歌词设置已应用")
    
    def apply_and_close(self):
        self.apply_settings()
        self.accept()



class MusicPlayerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.api = None
        self.current_song = None
        self.current_song_info = None
        self.search_results = []
        self.settings = load_settings()
        self.media_player = QMediaPlayer()
        self.current_song_path = None
        self.log_console = None
        self.active_threads = []
        self.tools_menu = None 
        self.resize(1280, 900)  
        self.playlist_manager = PlaylistManager()
        self.play_mode = 0
        self.current_play_index = -1
        self.playlist = []
        self.current_play_index = -1
        self.is_random_play = False
        self.repeat_mode = "none"
        self.create_necessary_dirs()  
        self.netease_worker = NetEaseWorker()  # 网易云专用worker
        self.setup_netease_connections()  # 连接网易云信号
        self.init_ui()
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)
        self.playlist_manager = PlaylistManager()
        logger.info("应用程序启动")
        self.playlist_file = "playlists.json"
        self.ensure_playlist_exists()
        self.load_playlist_on_startup()
        self.external_lyrics = ExternalLyricsWindow()
        self.lyrics_sync = LyricsSync(self.media_player, self.external_lyrics)
        self.setup_connections()
        settings = load_settings()
        lyrics_settings = settings.get("external_lyrics", {})
        lyrics_action = QAction("歌词设置", self)
        lyrics_action.triggered.connect(self.open_lyrics_settings)
        self.tools_menu.addAction(lyrics_action)
        
        
        
        if "geometry" in lyrics_settings:
            geometry = QByteArray.fromHex(lyrics_settings["geometry"].encode())
            self.external_lyrics.restoreGeometry(geometry)
        
        if "font" in lyrics_settings:
            font = QFont()
            font.fromString(lyrics_settings["font"])
            self.external_lyrics.lyrics_label.setFont(font)
        
        if "color" in lyrics_settings:
            color = lyrics_settings["color"]
            self.external_lyrics.lyrics_label.setStyleSheet(f"""
                QLabel {{
                    font-size: {self.external_lyrics.lyrics_label.font().pointSize()}px;
                    font-weight: bold;
                    color: {color};
                    background-color: transparent;
                    padding: 10px;
                }}
            """)
        
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
        
    def create_necessary_dirs(self):
        music_dir = self.settings["save_paths"]["music"]
        cache_dir = self.settings["save_paths"]["cache"]
        video_dir = self.settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos"))
        for directory in [music_dir, cache_dir, video_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"创建目录: {directory}")
                
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

    def open_lyrics_settings(self):
        """打开歌词设置对话框"""
        dialog = LyricsSettingsDialog(self)
        dialog.exec_()
        
    def toggle_lyrics_window(self):
        """打开歌词设置对话框"""
        dialog = LyricsSettingsDialog(self)
        dialog.exec_()

    def load_lyrics_for_song(self, song_path):
        """尝试加载歌曲对应的歌词文件"""
        if not hasattr(self, 'current_song_info') or self.current_song_info is None:
            self.current_song_info = {
                'path': song_path,
                'name': os.path.basename(song_path),
                'lrc': ''
            }
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
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
            lrc_path = os.path.splitext(song_path)[0] + '.lrc'
            if os.path.exists(lrc_path):
                try:
                    with open(lrc_path, 'r', encoding='utf-8') as f:
                        lyrics_text = f.read()
                    logger.info(f"从本地文件加载歌词: {lrc_path}")
                except Exception as e:
                    logger.error(f"加载歌词文件失败: {lrc_path} - {str(e)}")
        if not lyrics_text and hasattr(self, 'current_song_info'):
            lyrics_text = self.current_song_info.get('lrc', '')
            if lyrics_text:
                logger.info("从网络获取歌词内容")
                if lyrics_settings.get("auto_save", True):
                    lrc_path = os.path.splitext(song_path)[0] + '.lrc'
                    try:
                        with open(lrc_path, 'w', encoding='utf-8') as f:
                            f.write(lyrics_text)
                        logger.info(f"歌词已保存到: {lrc_path}")
                    except Exception as e:
                        logger.error(f"保存歌词文件失败: {str(e)}")
        self.lyrics_sync.load_lyrics(lyrics_text)
        if lyrics_text:
            self.external_lyrics.update_lyrics("歌词已加载")
        else:
            self.external_lyrics.update_lyrics("没有歌词")

    def load_lyrics_from_network(self, song_info=None):
        """尝试从网络加载歌词"""
        if not song_info and self.current_song_info:
            song_info = self.current_song_info
    
        if song_info and 'id' in song_info:
            try:
                api = NetEaseMusicAPI()
                lyrics = api.fetch_lyrics(song_info['id'])
                if lyrics and "歌词未找到" not in lyrics:
                    self.lyrics_sync.load_lyrics(lyrics)
                    self.external_lyrics.update_lyrics("网络歌词已加载")
                    return True
            except Exception as e:
                logger.error(f"从网络加载歌词失败: {str(e)}")
        return False

    def setup_netease_connections(self):
        """设置网易云专用信号连接"""
        self.netease_worker.search_finished.connect(self.display_netease_search_results)
        self.netease_worker.details_ready.connect(self.display_netease_details)
        self.netease_worker.error_occurred.connect(self.display_error)

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
        self.prev_button.setEnabled(False)
        self.prev_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.prev_button.clicked.connect(self.play_previous)
        control_layout.addWidget(self.prev_button)
        self.play_button = QPushButton("播放")
        self.play_button.setEnabled(False)
        self.play_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.play_button.clicked.connect(self.play_song)
        control_layout.addWidget(self.play_button)
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.pause_button.clicked.connect(self.pause_song)
        control_layout.addWidget(self.pause_button)
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.stop_button.clicked.connect(self.stop_song)
        control_layout.addWidget(self.stop_button)
        self.next_button = QPushButton("下一首")
        self.next_button.setEnabled(False)
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
        lyrics_button = QPushButton("歌词")
        lyrics_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-size: 14px;
                background-color: rgba(219, 68, 83, 200);
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(239, 88, 103, 200);
            }
        """)
        lyrics_button.setCursor(QCursor(Qt.PointingHandCursor))
        lyrics_button.clicked.connect(self.toggle_lyrics_window)
        tools_layout.addWidget(lyrics_button)
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
        control_layout.addLayout(progress_layout)  
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
        playlist_header = QWidget()
        playlist_header_layout = QHBoxLayout(playlist_header)
        playlist_label = QLabel("播放列表")
        playlist_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #FF5722;")
        playlist_header_layout.addWidget(playlist_label)
        playlist_header_layout.addStretch()
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
        self.playlist_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.playlist_widget.customContextMenuRequested.connect(self.show_playlist_menu)
        playlist_layout.addWidget(self.playlist_widget, 1)
        playlist_controls = QWidget()
        playlist_controls_layout = QHBoxLayout(playlist_controls)
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
        results_layout.addLayout(playlist_layout, 1)  
        main_layout.addLayout(results_layout, 5)
        main_layout.addLayout(results_layout, 5)
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        search_button.clicked.connect(self.start_search)

    def toggle_lyrics_window(self):
        """切换歌词窗口的显示状态"""
        if self.external_lyrics.isVisible():
            self.external_lyrics.hide()
        else:
            self.external_lyrics.show()

    def toggle_lyrics_window(self):
        """切换歌词窗口的显示状态"""
        settings = load_settings()
        lyrics_settings = settings.get("lyrics", {})
    
        if lyrics_settings.get("show_lyrics", True):
            self.external_lyrics.hide()
            lyrics_settings["show_lyrics"] = False
            self.status_bar.showMessage("歌词窗口已隐藏")
        else:
            self.external_lyrics.show()
            lyrics_settings["show_lyrics"] = True
            self.status_bar.showMessage("歌词窗口已显示")
        settings["lyrics"] = lyrics_settings
        save_settings(settings)

    def download_current_song(self):
        if self.source_combo.currentText() == "网易云音乐" and self.current_song_info:
            file_path = ...  # 文件路径选择逻辑
            self.api = NetEaseMusicAPI()
            self.api.download_song(self.current_song_info['audio_url'], file_path)
        else:
            pass
        if not self.current_song_info or 'url' not in self.current_song_info:
            self.status_bar.showMessage("没有可下载的歌曲")
            logger.warning("下载请求: 没有可下载的歌曲")
            return
        lrc_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lrc")
        if not os.path.exists(lrc_dir):
            os.makedirs(lrc_dir, exist_ok=True)
            logger.info(f"创建歌词目录: {lrc_dir}")
        song_name = self.current_song_info.get('name', '未知歌曲')
        safe_song_name = re.sub(r'[\\/*?:"<>|]', "", song_name)
        default_name = f"{safe_song_name}.mp3"
        lrc_url = self.current_song_info.get('lrc_url', '')
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
        self.download_worker = MusicWorker()
        self.download_worker.current_song_info = self.current_song_info
        self.active_threads.append(self.download_worker)
        self.download_worker.download_progress.connect(self.update_download_progress)
        self.download_worker.download_finished.connect(self.download_completed)
        self.download_worker.error_occurred.connect(self.display_error)
        self.download_worker.finished.connect(self.remove_download_worker)
        self.download_worker.lrc_path = lrc_path
        self.download_worker.lrc_url = lrc_url
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

    def update_progress(self, position):
        if self.progress_slider.isSliderDown():
            return
            
        if self.media_player.duration() > 0:
            position = max(0, min(position, self.media_player.duration()))
            self.progress_slider.setValue(int(1000 * position / self.media_player.duration()))
            self.update_time_display(position)

    def update_time_display(self, position):
        total_time = self.media_player.duration()
        self.current_time_label.setText(MusicPlayerApp.format_time(position))
        self.total_time_label.setText(MusicPlayerApp.format_time(total_time))

    def refresh_source_combo(self):
        """刷新音源选择下拉框"""
        self.source_combo.clear()
        settings = load_settings()
        source_names = [source["name"] for source in settings["sources"]["sources_list"]]
        self.source_combo.addItems(source_names)
        current_source = settings["sources"]["active_source"]
        if current_source in source_names:
            self.source_combo.setCurrentText(current_source)
        elif source_names:
            self.source_combo.setCurrentIndex(0)

    def set_volume(self, value):
        self.media_player.setVolume(value)

    def add_to_playlist(self, song_path, song_info=None):
        """添加歌曲到播放列表"""
        if not os.path.exists(song_path):
            logger.warning(f"无法添加到播放列表，文件不存在: {song_path}")
            return
            
        for i in range(self.playlist_widget.count()):
            item = self.playlist_widget.item(i)
            if item.data(Qt.UserRole) == song_path:
                logger.info(f"歌曲已在播放列表中: {song_path}")
                return
                
        if song_info is None:
            filename = os.path.basename(song_path)
            song_name = os.path.splitext(filename)[0]
            song_info = {"name": song_name, "artists": "未知艺术家"}
        else:
            song_name = f"{song_info.get('name', '未知歌曲')} - {song_info.get('artists', '未知艺术家')}"
        
        item = QListWidgetItem(song_name)
        item.setData(Qt.UserRole, song_path)
        
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
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                song_path = item.data(Qt.UserRole)
                song_name = item.text()
                playlist_data["default"].append({
                    "name": song_name,
                    "path": song_path
                })
            
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
            for i in range(self.playlist_widget.count()):
                item = self.playlist_widget.item(i)
                song_path = item.data(Qt.UserRole)
                song_name = item.text()
                playlist_data["default"].append({
                    "name": song_name,
                    "path": song_path
                })
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
            self.playlist_file = file_path
            
        except Exception as e:
            logger.error(f"加载播放列表失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"加载播放列表失败:\n{str(e)}")
    
    
    def play_playlist_item(self, item):
        """播放播放列表中的歌曲"""
        self.current_play_index = self.playlist_widget.row(item)
        song_path = item.data(Qt.UserRole)
        self.update_current_playlist()
        if not os.path.exists(song_path):
            QMessageBox.warning(self, "错误", "文件不存在，可能已被移动或删除")
            self.playlist_widget.takeItem(self.playlist_widget.row(item))
            return
            
        try:
            self.current_song_path = song_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(song_path)))
            self.media_player.play()
            self.progress_slider.setValue(0)
            self.current_time_label.setText("00:00")
            self.total_time_label.setText("00:00")
            song_name = os.path.basename(song_path)
            self.status_bar.showMessage(f"正在播放: {song_name}")
            self.song_info.setText(f"<b>正在播放:</b> {song_name}")
            self.current_song_info = {
                'path': song_path,
                'name': song_name,
                'lrc': ''  
            }
            self.check_and_load_local_lyrics(song_path)
            logger.info(f"播放播放列表歌曲: {song_path}")
        except Exception as e:
            logger.error(f"播放文件失败: {str(e)}")
            QMessageBox.critical(self, "播放错误", f"无法播放文件:\n{str(e)}")
        self.load_lyrics_for_song(song_path)

    def check_and_load_local_lyrics(self, song_path):
        """检查并加载与歌曲同目录的歌词文件"""
        try:
            base_path = os.path.splitext(song_path)[0]
            lrc_path = f"{base_path}.lrc"
        
            if os.path.exists(lrc_path):
                logger.info(f"检测到本地歌词文件: {lrc_path}")
                with open(lrc_path, 'r', encoding='utf-8') as f:
                    lyrics_text = f.read()
                    self.lyrics_sync.load_lyrics(lyrics_text)
                    self.external_lyrics.update_lyrics("本地歌词已加载")
                    logger.info(f"成功加载本地歌词文件: {lrc_path}")
                    return True
            else:
                logger.info(f"未找到本地歌词文件: {lrc_path}")
                if self.load_lyrics_from_network():
                    return True
                else:
                    self.external_lyrics.update_lyrics("没有歌词")
                    return False
                
        except Exception as e:
            logger.error(f"加载本地歌词失败: {str(e)}")
            self.external_lyrics.update_lyrics(f"歌词加载错误: {str(e)}")
            return False


    def get_next_song_index(self):
        """根据播放模式获取下一首歌曲的索引"""
        if self.playlist_widget.count() == 0:
            return -1
        if self.play_mode == 2:  
            return self.current_play_index
        elif self.play_mode == 1:  
            return random.randint(0, self.playlist_widget.count() - 1)
        else:  
            next_index = self.current_play_index + 1
            return next_index if next_index < self.playlist_widget.count() else 0
        
    def get_prev_song_index(self):
        """根据播放模式获取上一首歌曲的索引"""
        if self.playlist_widget.count() == 0:
            return -1
        
        if self.play_mode == 2:  
            return self.current_play_index
        elif self.play_mode == 1:  
            return random.randint(0, self.playlist_widget.count() - 1)
        else:  
            prev_index = self.current_play_index - 1
            return prev_index if prev_index >= 0 else self.playlist_widget.count() - 1
    
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
                'artists': "未知艺术家"  
            })

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
    
    def change_play_mode(self, index):
        """更改播放模式"""
        self.play_mode = index
        modes = ["顺序播放", "随机播放", "单曲循环"]
        self.status_bar.showMessage(f"播放模式已切换为: {modes[index]}")
        logger.info(f"播放模式切换: {modes[index]}")

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
        settings = load_settings()
        lyrics_settings = settings.get("external_lyrics", {})
        lyrics_settings["geometry"] = self.external_lyrics.saveGeometry().toHex().data().decode()
        lyrics_settings["font"] = self.external_lyrics.lyrics_label.font().toString()
        lyrics_settings["color"] = self.external_lyrics.lyrics_label.palette().color(QPalette.WindowText).name()
        settings["external_lyrics"] = lyrics_settings
        save_settings(settings)
        self.external_lyrics.close()
        self.terminate_all_threads()
        self.media_player.stop()
        if self.log_console:
            self.log_console.close()
        event.accept()

    def terminate_all_threads(self):
        threads_to_terminate = self.active_threads.copy()
        for thread in threads_to_terminate:
            if thread and thread.isRunning():
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
        log_text.setPlainText(log_content)
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(lambda: self.refresh_log_content(log_text))
        layout.addWidget(log_text)
        layout.addWidget(refresh_button, alignment=Qt.AlignRight)
        dialog.setLayout(layout)
        dialog.exec_()

    def refresh_log_content(self, log_text_widget):
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_app.log")
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
    
    def open_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            self.settings = load_settings()
            self.source_combo.clear()
            self.source_combo.addItems(get_source_names())
            self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
            self.set_background()
            self.create_necessary_dirs()
            QMessageBox.information(self, "设置", "设置已保存！")
        
    def setup_connections(self):
        self.media_player.positionChanged.connect(self.lyrics_sync.update_position)
        self.media_player.stateChanged.connect(self.handle_player_state_changed)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)

    def remove_thread(self, thread):
        """安全地从活动线程列表中移除线程"""
        try:
            if thread and thread in self.active_threads:
                self.active_threads.remove(thread)
        except ValueError:
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
        
    def display_search_results(self, songs):
        if not songs:
            self.status_bar.showMessage("未找到相关歌曲")
            logger.warning("搜索结果: 未找到相关歌曲")
            return
        logger.info(f"显示搜索结果: 共 {len(songs)} 首")
        self.status_bar.showMessage(f"找到 {len(songs)} 首歌曲")
        self.search_results = songs
        self.results_list.clear()
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
            item.setData(Qt.UserRole, song["id"])  
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
        if state == QMediaPlayer.PlayingState:
            self.status_bar.showMessage("播放中...")
        elif state == QMediaPlayer.PausedState:
            self.status_bar.showMessage("已暂停")
        elif state == QMediaPlayer.StoppedState:
            self.status_bar.showMessage("已停止")
    
    def handle_media_status_changed(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.play_next()
    
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
        self.progress_slider.setValue(0)
        self.current_time_label.setText("00:00")
        self.total_time_label.setText("00:00")
        song = self.playlist[self.current_play_index]
        self.song_info.setText(f"<b>正在播放:</b> {song.get('name', '未知')} - {song.get('artists', '未知')}")
        self.results_list.setCurrentRow(self.current_play_index)
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
    
    def play_previous(self):
        """播放上一首歌曲"""
        if not self.playlist or self.current_play_index < 0:
            return
        
        prev_index = self.get_prev_song_index()
        if 0 <= prev_index < len(self.playlist):
            item = self.playlist_widget.item(prev_index)
            self.play_playlist_item(item)
    
    def play_next(self):
        """播放下一首歌曲"""
        if not self.playlist or self.current_play_index < 0:
            return
        
        next_index = self.get_next_song_index()
        if 0 <= next_index < len(self.playlist):
            item = self.playlist_widget.item(next_index)
            self.play_playlist_item(item)

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
        font = ImageFont.truetype(FONT_PATH, font_size)
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

if __name__ == "__main__":
    os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    window = MusicPlayerApp()
    window.show()
    sys.exit(app.exec_())
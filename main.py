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
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QListWidget, QListWidgetItem, QTextEdit, QScrollArea, QFrame,
    QFileDialog, QProgressDialog, QMessageBox, QComboBox, QAction, QMenu,
    QDialog, QGroupBox, QSpinBox, QCheckBox, QTabWidget, QFormLayout,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView,
    QPlainTextEdit, QMenuBar, QStatusBar, QColorDialog, QInputDialog,
    QProgressBar, QSlider
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl, QObject, QTimer
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor, QIcon, QDesktopServices
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
import asyncio
import aiohttp
import aiofiles
import httpx
from bs4 import BeautifulSoup
import hashlib
from bilibili_api import video, Credential
from bilibili_api.video import VideoDownloadURLDataDetecter
from PyQt5.QtGui import QCursor
from PyQt5.QtCore import QUrl


# =============== Bilibili视频搜索插件整合 ===============
class VideoAPI(QObject):
    """视频API类"""
    download_progress = pyqtSignal(int)  # 下载进度信号
    
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
        # 确保临时目录存在
        os.makedirs(temp_dir, exist_ok=True)

        # 获取视频信息
        v = video.Video(video_id, credential=Credential(sessdata=""))
        # 获取视频流和音频流下载链接
        download_url_data = await v.get_download_url(page_index=0)
        detector = VideoDownloadURLDataDetecter(download_url_data)
        streams = detector.detect_best_streams()
        video_url, audio_url = streams[0].url, streams[1].url

        # 下载视频和音频并合并
        video_file = os.path.join(temp_dir, f"{video_id}-video.m4s")
        audio_file = os.path.join(temp_dir, f"{video_id}-audio.m4s")
        output_file = os.path.join(temp_dir, f"{video_id}-res.mp4")

        try:
            await asyncio.gather(
                self._download_b_file(video_url, video_file),
                self._download_b_file(audio_url, audio_file),
            )
            # 检查临时文件是否存在
            if not os.path.exists(video_file) or not os.path.exists(audio_file):
                logging.error(f"临时文件下载失败：{video_file} 或 {audio_file} 不存在")
                return None

            await self._merge_file_to_mp4(video_file, audio_file, output_file)
            # 检查输出文件是否存在
            if not os.path.exists(output_file):
                logging.error(f"合并失败，输出文件不存在：{output_file}")
                return None

            return output_file
        except Exception as e:
            logging.error(f"视频/音频下载失败: {e}")
            return None
        finally:
            # 清理临时文件
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
                        # 检查线程是否被请求终止
                        if self.thread() and self.thread().isInterruptionRequested():
                            logging.info("下载被中断")
                            return
                        
                        current_len += len(chunk)
                        await f.write(chunk)

                        percent = int(current_len / total_len * 100)
                        if percent != last_percent:
                            last_percent = percent
                            # 进度更新通过信号发送到主线程
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
        self.threads = []  # 存储所有活动线程
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
        """安全移除搜索线程"""
        if self.search_thread in self.threads:
            self.threads.remove(self.search_thread)
        self.search_thread = None
        
    def remove_download_thread(self):
        """安全移除下载线程"""
        if self.download_thread in self.threads:
            self.threads.remove(self.download_thread)
        self.download_thread = None
        
    def closeEvent(self, event):
        """确保线程安全退出"""
        self.playlist_manager.save_playlists()
        # 断开信号连接
        try:
            self.video_api.download_progress.disconnect(self.update_progress)
        except:
            pass
        
        # 终止所有活动线程
        self.terminate_all_threads()
        event.accept()
        
    def terminate_all_threads(self):
        """安全终止所有线程"""
        threads = []
        if self.search_thread:
            threads.append(self.search_thread)
        if self.download_thread:
            threads.append(self.download_thread)
        
        for thread in threads:
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):  # 等待2秒
                    thread.terminate()
                    thread.wait()
        
    async def _search_videos_async(self, keyword):
        """异步搜索视频"""
        return await self.video_api.search_video(keyword)
        
    def search_videos(self):
        """搜索视频"""
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
            
        self.results_list.clear()
        self.info_label.setText("搜索中...")
        self.download_button.setEnabled(False)
        
        # 使用线程执行异步搜索
        self.search_thread = VideoSearchThread(keyword, self.video_api)
        self.threads.append(self.search_thread)  # 添加到线程列表
        self.search_thread.results_ready.connect(self.display_results)
        self.search_thread.error_occurred.connect(self.display_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.search_thread.start()
        
    def display_results(self, videos):
        """显示搜索结果"""
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
        """显示错误信息"""
        self.info_label.setText(f"搜索失败: {error}")
        
    def video_selected(self, item):
        """视频被选中"""
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
        """下载视频"""
        if not self.selected_video:
            return
            
        video_id = self.selected_video.get("bvid", "")
        if not video_id:
            QMessageBox.warning(self, "错误", "无效的视频ID")
            return
            
        # 获取保存路径
        title = BeautifulSoup(self.selected_video["title"], "html.parser").get_text()
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]  # 限制文件名长度
        
        # 使用默认视频保存路径
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
            
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        
        # 启动下载线程
        self.download_thread = VideoDownloadThread(video_id, file_path, self.temp_dir, self.video_api)
        self.threads.append(self.download_thread)  # 添加到线程列表
        self.download_thread.download_complete.connect(self.download_finished)
        self.download_thread.error_occurred.connect(self.download_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.download_thread.start()
        
    def update_progress(self, progress):
        """更新下载进度"""
        self.progress_bar.setValue(progress)
        
    def download_finished(self, file_path):
        """下载完成"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", f"视频已下载到:\n{file_path}")
        self.accept()  # 关闭对话框
        
    def download_error(self, error):
        """下载出错"""
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
            # 在新的事件循环中运行异步搜索
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 检查中断
            if self.isInterruptionRequested():
                return
                
            results = loop.run_until_complete(self.video_api.search_video(self.keyword))
            
            # 再次检查中断
            if self.isInterruptionRequested():
                return
                
            self.results_ready.emit(results or [])
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                # 安全关闭事件循环
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        """安全停止线程"""
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
            # 在新的事件循环中运行异步下载
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 检查中断
            if self.isInterruptionRequested():
                return
                
            temp_file = loop.run_until_complete(
                self.video_api.download_video(self.video_id, self.temp_dir)
            )
            
            # 再次检查中断
            if self.isInterruptionRequested():
                return
                
            if temp_file:
                # 移动文件到目标位置
                os.replace(temp_file, self.file_path)
                self.download_complete.emit(self.file_path)
            else:
                self.error_occurred.emit("下载失败，未获取到文件")
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                # 安全关闭事件循环
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        """安全停止线程"""
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()


# =============== Bilibili音频下载插件整合 ===============
class AudioAPI(QObject):
    """B站音频API类"""
    download_progress = pyqtSignal(int)  # 下载进度信号
    
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
        # 用于存储音视频信息的字典
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
        # 首先尝试从缓存获取
        if bvid in self.audio_info_cache:
            return self.audio_info_cache[bvid]
            
        try:
            # 第一步：获取视频信息（包含cid）
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
                
                # 第二步：获取音频URL
                audio_url = f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&qn=0&fnval=16"
                response = await client.get(audio_url, headers=self.BILIBILI_HEADER)
                data = response.json()
                if data["code"] != 0:
                    return None
                    
                # 解析音频URL
                audio_url = data["data"]["dash"]["audio"][0]["baseUrl"]
                
                # 存储到缓存
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
            # 获取音频信息
            audio_info = await self.get_audio_info(bvid)
            if not audio_info:
                return False
                
            audio_url = audio_info["audio_url"]
            
            # 下载音频
            async with httpx.AsyncClient() as client:
                async with client.stream("GET", audio_url, headers=self.BILIBILI_HEADER) as response:
                    if response.status_code != 200:
                        return False
                        
                    total_size = int(response.headers.get("Content-Length", 0))
                    downloaded = 0
                    
                    async with aiofiles.open(file_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            # 检查线程是否被请求终止
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
        self.threads = []  # 存储所有活动线程
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
        """安全移除搜索线程"""
        if self.search_thread in self.threads:
            self.threads.remove(self.search_thread)
        self.search_thread = None
        
    def remove_download_thread(self):
        """安全移除下载线程"""
        if self.download_thread in self.threads:
            self.threads.remove(self.download_thread)
        self.download_thread = None

    def closeEvent(self, event):
        """确保线程安全退出"""
        # 断开信号连接
        try:
            self.audio_api.download_progress.disconnect(self.update_progress)
        except:
            pass
        
        # 终止所有活动线程
        self.terminate_all_threads()
        event.accept()
        
    def terminate_all_threads(self):
        """安全终止所有线程"""
        threads = []
        if self.search_thread:
            threads.append(self.search_thread)
        if self.download_thread:
            threads.append(self.download_thread)
        
        for thread in threads:
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):  # 等待2秒
                    thread.terminate()
                    thread.wait()
        
    async def _search_videos_async(self, keyword):
        """异步搜索视频"""
        return await self.audio_api.search_video(keyword)
        
    def search_videos(self):
        """搜索视频"""
        keyword = self.search_input.text().strip()
        if not keyword:
            QMessageBox.warning(self, "提示", "请输入搜索关键词")
            return
            
        self.results_list.clear()
        self.info_label.setText("搜索中...")
        self.download_button.setEnabled(False)
        
        # 使用线程执行异步搜索
        self.search_thread = AudioSearchThread(keyword, self.audio_api)
        self.threads.append(self.search_thread)  # 添加到线程列表
        self.search_thread.results_ready.connect(self.display_results)
        self.search_thread.error_occurred.connect(self.display_error)
        self.search_thread.finished.connect(self.remove_search_thread)
        self.search_thread.start()
        
    def display_results(self, videos):
        """显示搜索结果"""
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
        """显示错误信息"""
        self.info_label.setText(f"搜索失败: {error}")
        
    def video_selected(self, item):
        """视频被选中"""
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
        """下载音频"""
        if not self.selected_video:
            return
            
        bvid = self.selected_video.get("bvid", "")
        if not bvid:
            QMessageBox.warning(self, "错误", "无效的视频ID")
            return
            
        # 获取保存路径
        title = BeautifulSoup(self.selected_video["title"], "html.parser").get_text()
        safe_title = re.sub(r'[\\/*?:"<>|]', "", title)[:50]  # 限制文件名长度
        
        # 使用默认音频保存路径
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
            
        # 显示进度条
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.download_button.setEnabled(False)
        
        # 启动下载线程
        self.download_thread = AudioDownloadThread(bvid, file_path, self.audio_api)
        self.threads.append(self.download_thread)  # 添加到线程列表
        self.download_thread.download_complete.connect(self.download_finished)
        self.download_thread.error_occurred.connect(self.download_error)
        self.download_thread.finished.connect(self.remove_download_thread)
        self.download_thread.start()
        
    def update_progress(self, progress):
        """更新下载进度"""
        self.progress_bar.setValue(progress)
        
    def download_finished(self, file_path):
        """下载完成"""
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "完成", f"音频已下载到:\n{file_path}")
        self.accept()  # 关闭对话框
        
    def download_error(self, error):
        """下载出错"""
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
            # 在新的事件循环中运行异步搜索
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 检查中断
            if self.isInterruptionRequested():
                return
                
            results = loop.run_until_complete(self.audio_api.search_video(self.keyword))
            
            # 再次检查中断
            if self.isInterruptionRequested():
                return
                
            self.results_ready.emit(results or [])
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            if loop and not loop.is_closed():
                # 安全关闭事件循环
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        """安全停止线程"""
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
            # 在新的事件循环中运行异步下载
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # 检查中断
            if self.isInterruptionRequested():
                return
                
            success = loop.run_until_complete(
                self.audio_api.download_audio(self.bvid, self.file_path)
            )
            
            # 再次检查中断
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
                # 安全关闭事件循环
                loop.call_soon_threadsafe(loop.stop)
                loop.close()
    
    def stop(self):
        """安全停止线程"""
        self.requestInterruption()
        self.quit()
        if not self.wait(2000):
            self.terminate()
            self.wait()

# =============== 设置管理功能 ===============
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
                    "params": {"input": "{query}", "filter": "name", "type": "netease", "page": 1},
                    "method": "POST",
                    "api_key": "",
                    "headers": {}
                }
            ]
        },
        "bilibili": {
            "cookie": "",
            "max_duration": 600  # 最大下载时长（秒）
        },
        "other": {
            "max_results": 20,
            "auto_play": True,
            "playback_mode": "list",  # 播放循环模式
            "repeat_mode": "none"  # 重复模式
        },
        "background_image": "",  # 添加背景图片路径
        "custom_tools": [] # 添加这一行
    }

def load_settings():
    """加载设置"""
    settings_path = get_settings_path()
    
    # 如果设置文件不存在，创建默认设置
    if not os.path.exists(settings_path):
        save_settings(load_default_settings())
        return load_default_settings()
    
    try:
        with open(settings_path, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            
            # 兼容旧版本设置 - 添加缺少的键
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
    # 如果找不到激活的音源，返回第一个
    return settings["sources"]["sources_list"][0]

def get_source_names():
    """获取所有音源名称"""
    settings = load_settings()
    return [source["name"] for source in settings["sources"]["sources_list"]]
# =============== 设置管理功能结束 ===============

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("music_app.log", encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MusicApp")

# 设置字体文件路径
FONT_PATH = "simhei.ttf"  # 确保有这个字体文件

def resource_path(relative_path):
    """获取资源的绝对路径（支持PyInstaller打包环境）"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path = os.path.join(base_path, relative_path)
    return os.path.normpath(path)

class PlaylistManager:
    def __init__(self):
        self.playlists = {}  # {playlist_name: [song_paths]}
        self.current_playlist = None
        self.playlist_file = "playlists.json"
        
        # 加载保存的播放列表
        self.load_playlists()
        
    def load_playlists(self):
        """从文件加载播放列表"""
        if os.path.exists(self.playlist_file):
            try:
                with open(self.playlist_file, 'r', encoding='utf-8') as f:
                    self.playlists = json.load(f)
                    logger.info(f"加载播放列表: {self.playlist_file}")
            except Exception as e:
                logger.error(f"加载播放列表失败: {str(e)}")
                self.playlists = {}
    
    def save_playlists(self):
        """保存播放列表到文件"""
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
            self.save_playlists()  # 保存更改
            return True
        return False
        
    def add_to_playlist(self, playlist_name, song_path):
        if playlist_name in self.playlists:
            # 避免重复添加
            if song_path not in self.playlists[playlist_name]:
                self.playlists[playlist_name].append(song_path)
                self.save_playlists()  # 保存更改
                return True
        return False
        
    def remove_from_playlist(self, playlist_name, song_path):
        if playlist_name in self.playlists and song_path in self.playlists[playlist_name]:
            self.playlists[playlist_name].remove(song_path)
            self.save_playlists()  # 保存更改
            return True
        return False
        
    def play_playlist(self, playlist_name):
        """播放指定的播放列表"""
        if playlist_name in self.playlist_manager.playlists:
            # 设置播放列表
            self.playlist = self.playlist_manager.playlists[playlist_name]
            
            # 重置播放索引
            self.current_play_index = -1
            
            # 根据设置选择播放模式
            if self.settings["other"].get("playback_mode", "list") == "random":
                # 随机播放
                self.play_song_by_index(random.randint(0, len(self.playlist) - 1))
            else:
                # 顺序播放
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
        
        # 按钮区域 - 确保先定义 button_layout
        button_layout = QHBoxLayout()  # 关键修复：在这里定义 button_layout
        
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
        
        # 加载当前播放列表的歌曲
        if self.playlist_combo.count() > 0:
            self.update_song_list(self.playlist_combo.currentText())



    def update_song_list(self, playlist_name):
        self.song_list.clear()
        if playlist_name in self.playlist_manager.playlists:
            for song_path in self.playlist_manager.playlists[playlist_name]:
                song_name = os.path.basename(song_path)
                self.song_list.addItem(song_name)
                
    def play_playlist(self):
        """播放选中的播放列表"""
        playlist_name = self.playlist_combo.currentText()
        if playlist_name:
            # 获取父窗口引用
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
                
    def update_song_list(self, playlist_name):
        self.song_list.clear()
        if playlist_name in self.playlist_manager.playlists:
            for song_path in self.playlist_manager.playlists[playlist_name]:
                song_name = os.path.basename(song_path)
                self.song_list.addItem(song_name)
                
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
    def __init__(self, media_player, lyrics_label):
        self.media_player = media_player
        self.lyrics_label = lyrics_label
        self.lyrics_data = []  # 存储歌词数据 [(时间, 歌词)]
        
    def load_lyrics(self, lyrics_text):
        self.lyrics_data = []
        lines = lyrics_text.splitlines()
        
        # 解析歌词时间戳
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
        
    def update_position(self):
        if not self.lyrics_data:
            return
            
        position = self.media_player.position()
        
        # 查找当前歌词
        current_lyric = ""
        next_lyric = ""
        for i, (time_ms, text) in enumerate(self.lyrics_data):
            if time_ms <= position:
                current_lyric = text
                if i + 1 < len(self.lyrics_data):
                    next_lyric = self.lyrics_data[i+1][1]
            else:
                break
                
        # 高亮显示当前歌词
        if current_lyric:
            lyrics_html = f"<div style='font-size: 18px; color: #FF5722;'>{current_lyric}</div>"
            if next_lyric:
                lyrics_html += f"<div style='font-size: 16px;'>{next_lyric}</div>"
            self.lyrics_label.setText(lyrics_html)


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
        self.remaining_time = minutes * 60  # 转换为秒
        
        self.timer.start(1000)  # 每秒触发一次
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
            # 停止播放
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
    """均衡器设置对话框"""
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
        """应用预设均衡器设置"""
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
        else:  # 默认
            for slider in self.sliders.values():
                slider.setValue(0)
        
        # 更新均衡器
        self.update_equalizer()
        
    def update_equalizer(self):
        """更新均衡器设置"""
        values = {freq: slider.value() for freq, slider in self.sliders.items()}
        # 这里需要根据实际播放器API设置均衡器
        # 例如: self.media_player.setEqualizer(values)
        logger.info(f"均衡器设置更新: {values}")
        
    def save_preset(self):
        """保存当前设置为预设"""
        name, ok = QInputDialog.getText(self, "保存预设", "输入预设名称:")
        if ok and name:
            # 保存当前均衡器设置
            values = {freq: slider.value() for freq, slider in self.sliders.items()}
            
            # 保存到设置
            settings = load_settings()
            if "equalizer_presets" not in settings:
                settings["equalizer_presets"] = {}
                
            settings["equalizer_presets"][name] = values
            save_settings(settings)
            
            # 添加到预设列表
            self.preset_combo.addItem(name)
            self.preset_combo.setCurrentText(name)
            
            QMessageBox.information(self, "成功", f"预设 '{name}' 已保存")
            
    def load_preset(self):
        """加载保存的预设"""
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
            
            # 更新均衡器
            self.update_equalizer()
            self.preset_combo.setCurrentText(preset)

               

# 新增：日志控制台对话框
class LogConsoleDialog(QDialog):
    """显示日志的控制台对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("日志控制台")
        self.setGeometry(200, 200, 800, 600)
        
        # 创建布局
        layout = QVBoxLayout()
        
        # 创建文本编辑区域
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
        
        # 按钮
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
        
        # 加载日志
        self.load_logs()
    
    def load_logs(self):
        """加载日志文件内容"""
        log_file = "music_app.log"
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    content = f.read()
                    self.log_text.setPlainText(content)
                    # 滚动到底部
                    self.log_text.verticalScrollBar().setValue(
                        self.log_text.verticalScrollBar().maximum()
                    )
            except Exception as e:
                self.log_text.setPlainText(f"无法读取日志文件: {str(e)}")
        else:
            self.log_text.setPlainText("日志文件不存在")


class MusicWorker(QThread):
    """后台工作线程，用于执行网络请求和耗时操作"""
    
    search_finished = pyqtSignal(list)
    error_occurred = pyqtSignal(str)
    download_progress = pyqtSignal(int)  # 下载进度信号
    download_finished = pyqtSignal(str)  # 下载完成信号
    
    def __init__(self):
        super().__init__()
        self.mode = None
        self.keyword = None
        self.song = None
        self.audio_url = None
        self.file_path = None
        
    def search_songs(self, keyword):
        """设置搜索任务"""
        self.mode = "search"
        self.keyword = keyword
        self.start()
        
    def download_song(self, audio_url, file_path):
        """设置下载任务"""
        self.mode = "download"
        self.audio_url = audio_url
        self.file_path = file_path
        self.start()
        
    def run(self):
        """执行后台任务"""
        try:
            if self.mode == "search":
                from crawler import search_song
                settings = load_settings()
                max_results = settings["other"]["max_results"]
                
                try:
                    # 检查是否被中断
                    if self.isInterruptionRequested():
                        return
                        
                    result = search_song(self.keyword, max_results)
                except Exception as e:
                    logger.error(f"搜索歌曲失败: {str(e)}")
                    self.error_occurred.emit(f"搜索失败: {str(e)}")
                    return
                
                # 再次检查中断
                if self.isInterruptionRequested():
                    return
                
                songs = result.get("data", [])
                
                # 转换为统一格式
                formatted_songs = []
                for song in songs:
                    # 每次迭代检查中断
                    if self.isInterruptionRequested():
                        return
                    
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
                
                self.search_finished.emit(formatted_songs)
                
            elif self.mode == "download":
                # 下载歌曲
                success = self.download_file(self.audio_url, self.file_path)
                if success:
                    self.download_finished.emit(self.file_path)
                else:
                    self.error_occurred.emit("歌曲下载失败")
                    
        except Exception as e:
            error_msg = f"发生错误: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)
    
    def parse_duration(self, duration_str):
        """将字符串格式的时长转换为毫秒"""
        try:
            if ':' in duration_str:
                parts = duration_str.split(':')
                if len(parts) == 2:  # 分钟:秒
                    minutes, seconds = parts
                    return (int(minutes) * 60 + int(seconds)) * 1000
                elif len(parts) == 3:  # 小时:分钟:秒
                    hours, minutes, seconds = parts
                    return (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000
            return 0
        except:
            return 0
    
    def download_file(self, url, file_path):
        """下载文件"""
        try:
            # 设置请求头模拟浏览器
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
                    # 检查是否被中断
                    if self.isInterruptionRequested():
                        logger.info("下载被中断")
                        return False
                        
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 计算下载进度百分比
                        progress = int(100 * downloaded / total_size) if total_size > 0 else 0
                        # 发送进度信号
                        self.download_progress.emit(progress)
            
            logger.info(f"歌曲下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载歌曲失败: {str(e)}")
            return False


class SettingsDialog(QDialog):
    """设置对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setGeometry(200, 200, 700, 500)
        
        self.settings = load_settings()
        self.parent = parent  # 保存父窗口引用
        
        self.init_ui()
        self.load_settings()

    def init_ui(self):
        layout = QVBoxLayout()
        
        # 创建标签页
        self.tabs = QTabWidget()
        
        # 第一页：保存位置
        save_tab = QWidget()
        save_layout = QVBoxLayout()
        
        # 保存位置设置
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

        # 添加播放循环模式设置
        self.playback_mode_combo = QComboBox()
        self.playback_mode_combo.addItems(["顺序播放", "随机播放", "单曲循环"])
        
        # 添加重复模式设置
        self.repeat_mode_combo = QComboBox()
        self.repeat_mode_combo.addItems(["不重复", "列表循环", "单曲循环"])
        other_form.addRow("播放模式:", self.playback_mode_combo)
        other_form.addRow("重复模式:", self.repeat_mode_combo)
        
        other_form.addRow("最大获取数量:", self.max_results_spin)
        other_form.addRow(self.auto_play_check)
        other_group.setLayout(other_form)
        
        save_layout.addWidget(save_group)
        save_layout.addWidget(bg_group)
        save_layout.addWidget(other_group)
        save_layout.addStretch()
        save_tab.setLayout(save_layout)
        
        # 第二页：音源设置
        source_tab = QWidget()
        source_layout = QVBoxLayout()
        
        # 当前音源选择
        source_group = QGroupBox("当前音源")
        source_form = QFormLayout()
        
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_source_names())
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("如需API密钥请在此输入")
        
        source_form.addRow("选择音源:", self.source_combo)
        source_form.addRow("API密钥:", self.api_key_edit)
        source_group.setLayout(source_form)
        
        source_layout.addWidget(source_group)
        source_tab.setLayout(source_layout)
        
        # 第三页：Bilibili设置
        bilibili_tab = QWidget()
        bilibili_layout = QVBoxLayout()
        
        # Bilibili设置
        bilibili_group = QGroupBox("Bilibili设置")
        bilibili_form = QFormLayout()
        
        self.bilibili_cookie_edit = QLineEdit()
        self.bilibili_cookie_edit.setPlaceholderText("输入Bilibili Cookie（可选）")
        
        self.max_duration_spin = QSpinBox()
        self.max_duration_spin.setRange(60, 3600)  # 1分钟到1小时
        self.max_duration_spin.setSuffix("秒")
        
        bilibili_form.addRow("Cookie:", self.bilibili_cookie_edit)
        bilibili_form.addRow("最大下载时长:", self.max_duration_spin)
        bilibili_group.setLayout(bilibili_form)
        
        bilibili_layout.addWidget(bilibili_group)
        # 添加视频搜索按钮
        bilibili_button_layout = QHBoxLayout()
        self.bilibili_video_button = QPushButton("搜索B站视频")
        self.bilibili_video_button.setStyleSheet("""
            padding: 8px; 
            background-color: rgba(219, 68, 83, 200);
            color: white;
            font-weight: bold;
        """)
        self.bilibili_video_button.clicked.connect(self.open_bilibili_video_search)
        bilibili_button_layout.addWidget(self.bilibili_video_button)

        bilibili_layout.addLayout(bilibili_button_layout)
        bilibili_tab.setLayout(bilibili_layout)
        bilibili_tab.setLayout(bilibili_layout)
        
        # 添加标签页
        self.tabs.addTab(save_tab, "保存设置")
        self.tabs.addTab(source_tab, "音源设置")
        self.tabs.addTab(bilibili_tab, "Bilibili设置")
        
        # 按钮
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)

        # 创建标签页控件 
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)  
        self.setLayout(layout)

        #作者主页
        author_tab = QWidget()
        author_layout = QVBoxLayout()   
        author_info = QLabel("欢迎使用Railgun_lover的音乐项目！")
        author_info.setStyleSheet("font-size: 16px; font-weight: bold; margin: 10px;")
        author_layout.addWidget(author_info, alignment=Qt.AlignCenter)
        
    
        # 按钮布局
        button_layout = QHBoxLayout()
    
        # B站主页按钮
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
    
        # GitHub按钮
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
            "https://github.com/228117384/music1.0"
        )))
    
        button_layout.addWidget(bilibili_button)
        button_layout.addStretch()
        button_layout.addWidget(github_button)
    
        author_layout.addLayout(button_layout)
    
        # 添加分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setLineWidth(1)
        author_layout.addWidget(separator)
    
         # 添加联系信息
        contact_info = QLabel("项目开源免费，欢迎使用和交流！")
        contact_info.setStyleSheet("font-size: 14px; color: #888888; margin-top: 15px;")
        contact_info.setAlignment(Qt.AlignCenter)
        author_layout.addWidget(contact_info)
    
        author_tab.setLayout(author_layout)
        self.tabs.addTab(author_tab, "作者主页")
    
        # 添加到主布局
        layout.addWidget(self.tabs)
    
        # 确定和取消按钮 (已有)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("确定")
        ok_button.clicked.connect(self.accept)
        cancel_button = QPushButton("取消")
        cancel_button.clicked.connect(self.reject)
        button_layout.addStretch()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
    
        self.setLayout(layout)
    
        # 加载当前设置 (已有)
        self.load_settings()
        
        # 主布局
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
    def open_bilibili_video_search(self):
        """打开Bilibili视频搜索对话框"""
        cookie = self.bilibili_cookie_edit.text().strip()
        dialog = VideoSearchDialog(self, cookie)
        dialog.exec_()
    def create_dir_row(self, edit, btn):
        """创建目录选择行"""
        row_layout = QHBoxLayout()
        row_layout.addWidget(edit)
        row_layout.addWidget(btn)
        widget = QWidget()
        widget.setLayout(row_layout)
        return widget
        
    def select_directory(self, edit):
        """选择目录"""
        directory = QFileDialog.getExistingDirectory(self, "选择目录")
        if directory:
            edit.setText(directory)
            
    def select_image(self, edit):
        """选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择背景图片", "", "图片文件 (*.jpg *.jpeg *.png *.bmp)"
        )
        if file_path:
            edit.setText(file_path)

    def preview_background(self):
        """预览背景图片"""
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
        """加载设置"""
        # 保存位置
        self.music_dir_edit.setText(self.settings["save_paths"]["music"])
        self.cache_dir_edit.setText(self.settings["save_paths"]["cache"])
        self.video_dir_edit.setText(self.settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos")))
        
        # 背景图片
        self.bg_image_edit.setText(self.settings.get("background_image", ""))
        
        # 其他设置
        self.max_results_spin.setValue(self.settings["other"]["max_results"])
        self.auto_play_check.setChecked(self.settings["other"]["auto_play"])

         # 加载播放模式设置
        playback_mode = self.settings["other"].get("playback_mode", "list")
        if playback_mode == "list":
            self.playback_mode_combo.setCurrentIndex(0)
        elif playback_mode == "random":
            self.playback_mode_combo.setCurrentIndex(1)
        elif playback_mode == "single":
            self.playback_mode_combo.setCurrentIndex(2)
        
        # 加载重复模式设置
        repeat_mode = self.settings["other"].get("repeat_mode", "none")
        if repeat_mode == "none":
            self.repeat_mode_combo.setCurrentIndex(0)
        elif repeat_mode == "list":
            self.repeat_mode_combo.setCurrentIndex(1)
        elif repeat_mode == "single":
            self.repeat_mode_combo.setCurrentIndex(2)

        # 加载播放设置
        self.is_random_play = (self.settings["other"].get("playback_mode", "list") == "random")
        self.repeat_mode = self.settings["other"].get("repeat_mode", "none")
        
        # 音源设置
        self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
        active_source = get_active_source_config()
        self.api_key_edit.setText(active_source.get("api_key", ""))
        
        # Bilibili设置
        self.bilibili_cookie_edit.setText(self.settings["bilibili"].get("cookie", ""))
        self.max_duration_spin.setValue(self.settings["bilibili"].get("max_duration", 600))

    def save_settings(self):
        """保存设置"""
        # 保存位置
        self.settings["save_paths"]["music"] = self.music_dir_edit.text()
        self.settings["save_paths"]["cache"] = self.cache_dir_edit.text()
        self.settings["save_paths"]["videos"] = self.video_dir_edit.text()
        
        # 背景图片
        self.settings["background_image"] = self.bg_image_edit.text()
        
        # 其他设置
        self.settings["other"]["max_results"] = self.max_results_spin.value()
        self.settings["other"]["auto_play"] = self.auto_play_check.isChecked()

        # 保存播放循环模式
        playback_index = self.playback_mode_combo.currentIndex()
        if playback_index == 0:
            self.settings["other"]["playback_mode"] = "list"
        elif playback_index == 1:
            self.settings["other"]["playback_mode"] = "random"
        elif playback_index == 2:
            self.settings["other"]["playback_mode"] = "single"
        
        # 保存重复模式
        repeat_index = self.repeat_mode_combo.currentIndex()
        if repeat_index == 0:
            self.settings["other"]["repeat_mode"] = "none"
        elif repeat_index == 1:
            self.settings["other"]["repeat_mode"] = "list"
        elif repeat_index == 2:
            self.settings["other"]["repeat_mode"] = "single"
        
        # 音源设置
        active_source = self.source_combo.currentText()
        self.settings["sources"]["active_source"] = active_source
        
        # 更新API密钥
        for source in self.settings["sources"]["sources_list"]:
            if source["name"] == active_source:
                source["api_key"] = self.api_key_edit.text()
                break
        
        # 确保 bilibili 设置存在
        if "bilibili" not in self.settings:
            self.settings["bilibili"] = {}
            
        # Bilibili设置
        self.settings["bilibili"]["cookie"] = self.bilibili_cookie_edit.text()
        self.settings["bilibili"]["max_duration"] = self.max_duration_spin.value()
        
        # 保存设置并关闭对话框
        if save_settings(self.settings):
            self.accept()
        else:
            QMessageBox.warning(self, "错误", "保存设置失败，请检查日志")

class MusicPlayerApp(QMainWindow):
    """音乐搜索和播放应用程序"""
    
    def __init__(self):
        super().__init__()
        self.api = None
        self.current_song = None
        self.current_song_info = None
        self.search_results = []  # 存储搜索结果
        self.settings = load_settings()
        self.media_player = QMediaPlayer()
        self.current_song_path = None
        self.log_console = None  # 日志控制台对话框
        self.active_threads = []  # 存储所有活动线程
        self.playlist_manager = PlaylistManager()
        self.playlist = []  # 当前播放列表
        self.current_play_index = -1  # 当前播放索引
        self.is_random_play = False  # 是否随机播放
        self.repeat_mode = "none"  # 重复模式
        
        
        # 确保必要的目录存在
        self.create_necessary_dirs()
        
               
        self.init_ui()
        self.lyrics_sync = LyricsSync(self.media_player, self.lyrics_label)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)
        self.playlist_manager = PlaylistManager()
        self.setup_connections()
        logger.info("应用程序启动")
        
    def create_necessary_dirs(self):
        """创建必要的目录（音乐保存目录和缓存目录）"""
        # 获取目录路径
        music_dir = self.settings["save_paths"]["music"]
        cache_dir = self.settings["save_paths"]["cache"]
        video_dir = self.settings["save_paths"].get("videos", os.path.join(os.path.expanduser("~"), "Videos"))
        
        # 如果目录不存在，则创建
        for directory in [music_dir, cache_dir, video_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                logger.info(f"创建目录: {directory}")
    # =============== 添加打开程序目录功能 ===============
    def open_app_directory(self):
        """打开应用程序所在目录"""
        app_path = os.path.dirname(os.path.abspath(__file__))
        try:
            if sys.platform == "win32":
                # Windows系统
                os.startfile(app_path)
            elif sys.platform == "darwin":
                # macOS系统
                subprocess.Popen(["open", app_path])
            else:
                # Linux系统
                subprocess.Popen(["xdg-open", app_path])
            logger.info(f"已打开程序目录: {app_path}")
        except Exception as e:
            logger.error(f"打开程序目录失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"无法打开程序目录:\n{str(e)}")
    # =============== 实现播放文件功能 ===============
    def play_custom_file(self):
        """播放用户选择的音频文件"""
        # 获取默认音乐目录
        settings = load_settings()
        music_dir = settings["save_paths"]["music"]
        
        # 打开文件对话框
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择音频文件",
            music_dir,
            "音频文件 (*.mp3 *.wav *.flac *.m4a);;所有文件 (*.*)"
        )

        if not file_path:
            return  # 用户取消选择
        
        # 检查是否是歌词文件
        if file_path.endswith('.lrc'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lyrics = f.read()
                    self.lyrics_sync.load_lyrics(lyrics)
                return  # 只加载歌词，不播放
            except Exception as e:
                logger.error(f"加载歌词失败: {str(e)}")
                QMessageBox.warning(self, "错误", f"无法加载歌词文件:\n{str(e)}")
                return
    
        
        try:
            # 停止当前播放
            if self.media_player.state() == QMediaPlayer.PlayingState:
                self.media_player.stop()
        
            # 设置并播放新文件
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
    
            # 更新状态栏
            filename = os.path.basename(file_path)
            self.status_bar.showMessage(f"正在播放: {filename}")
    
            # 更新UI
            self.song_info.setText(f"<b>正在播放:</b> {filename}")
            self.lyrics_label.clear()
    
            # 启用控制按钮
            self.play_button.setEnabled(True)
            self.pause_button.setEnabled(True)
            self.stop_button.setEnabled(True)
    
            logger.info(f"播放文件: {file_path}")
        except Exception as e:
            logger.error(f"播放文件失败: {str(e)}")
            QMessageBox.critical(self, "播放错误", f"无法播放文件:\n{str(e)}")
   
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("音乐捕捉器 create bilibili by:Railgun_lover")
        self.setGeometry(100, 100, 1000, 800)
    
        # 创建菜单栏
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
    
        # 添加菜单
        file_menu = menu_bar.addMenu("文件")
        file_menu.setIcon(QIcon.fromTheme("document"))
        tools_menu = menu_bar.addMenu("工具")

        # 播放列表菜单项
        playlist_action = QAction("播放列表管理", self)
        playlist_action.triggered.connect(self.open_playlist_manager)
        tools_menu.addAction(playlist_action)

        # 睡眠定时器菜单项
        sleep_timer_action = QAction("睡眠定时器", self)
        sleep_timer_action.triggered.connect(self.open_sleep_timer)
        tools_menu.addAction(sleep_timer_action)

        # 添加"打开程序目录"动作
        open_dir_action = QAction(QIcon.fromTheme("folder"), "打开程序目录", self)
        open_dir_action.setShortcut("Ctrl+O")
        open_dir_action.triggered.connect(self.open_app_directory)
        file_menu.addAction(open_dir_action)

        # 添加"日志控制台"动作
        log_action = QAction(QIcon.fromTheme("text-plain"), "日志控制台", self)
        log_action.setShortcut("Ctrl+L")
        log_action.triggered.connect(self.open_log_console)
        file_menu.addAction(log_action)

        # 添加分隔线
        file_menu.addSeparator()

        # 添加退出动作
        exit_action = QAction(QIcon.fromTheme("application-exit"), "退出", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # 创建主部件和布局
        main_widget = QWidget()
        main_widget.setObjectName("centralWidget")
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
    
        # 设置背景
        self.set_background()
    
        # 顶部工具栏
        toolbar_layout = QHBoxLayout()
    
        # 左侧工具按钮区域
        tools_layout = QHBoxLayout()
    
        self.tools_button = QPushButton("小工具")
        self.tools_button.setStyleSheet("""
            padding: 8px; 
            font-size: 14px; 
            background-color: rgba(70, 130, 180, 200);
            color: white;
            font-weight: bold;
        """)
        self.tools_button.clicked.connect(self.open_tools_dialog)
        tools_layout.addWidget(self.tools_button)

        # 添加播放文件按钮
        play_file_button = QPushButton("播放文件")
        
        play_file_button.setIcon(QIcon.fromTheme("media-playback-start"))
        play_file_button.setStyleSheet("""
            QPushButton {
                padding: 8px;
                font-size: 14px;
                background-color: rgba(46, 139, 87, 200);
                color: white;
                font-weight: bold;
                min-width: 100px;  /* 设置最小宽度与其他按钮一致 */                           
            }
            QPushButton:hover {
                background-color: rgba(56, 159, 107, 200);
            }
        """)
        play_file_button.setCursor(QCursor(Qt.PointingHandCursor))
        play_file_button.clicked.connect(self.play_custom_file)
        tools_layout.addWidget(play_file_button)
    
        # 将工具布局添加到工具栏布局
        toolbar_layout.addLayout(tools_layout)
    
        # 右侧搜索区域
        search_layout = QHBoxLayout()
    
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入歌曲名称...")
        self.search_input.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        self.search_input.returnPressed.connect(self.start_search)  # 回车搜索

        # 音源选择
        self.source_combo = QComboBox()
        self.source_combo.addItems(get_source_names())
        self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
        self.source_combo.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        self.source_combo.setFixedWidth(150)
    
        search_button = QPushButton("搜索")
        search_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        search_button.clicked.connect(self.start_search)
    
        # 设置按钮
        settings_button = QPushButton("设置")
        settings_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        settings_button.clicked.connect(self.open_settings)
    
        # 切换模式按钮
        switch_button = QPushButton("切换模式")
        switch_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(46, 139, 87, 200);")
        switch_button.clicked.connect(self.switch_to_original_mode)
    
        # 日志控制台按钮
        log_button = QPushButton("日志控制台")
        log_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(70, 130, 180, 200);")
        log_button.clicked.connect(self.open_log_console)
    
        # B站音乐搜索按钮
        bilibili_audio_button = QPushButton("B站音乐")
        bilibili_audio_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(219, 68, 83, 200);")
        bilibili_audio_button.clicked.connect(self.open_bilibili_audio_search)
    
        # 将搜索相关组件添加到搜索布局
        search_layout.addWidget(self.search_input, 5)
        search_layout.addWidget(self.source_combo, 2)
        search_layout.addWidget(search_button, 1)
        search_layout.addWidget(settings_button, 1)
        search_layout.addWidget(switch_button, 1)
        search_layout.addWidget(log_button, 1)
        search_layout.addWidget(bilibili_audio_button, 1)
    
        # 将搜索布局添加到工具栏布局
        toolbar_layout.addLayout(search_layout)
    
        # 将工具栏布局添加到主布局
        main_layout.addLayout(toolbar_layout)

        # 结果区域
        results_layout = QHBoxLayout()
    
        # 左侧：搜索结果列表
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
        results_layout.addLayout(results_list_layout, 1)
    
        # 右侧：歌曲详情
        details_layout = QVBoxLayout()
    
        # 歌曲信息
        info_layout = QVBoxLayout()
        info_label = QLabel("歌曲信息")
        info_label.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        info_layout.addWidget(info_label)
    
        self.song_info = QTextEdit()
        self.song_info.setReadOnly(True)
        self.song_info.setStyleSheet("font-size: 14px; background-color: rgba(37, 37, 37, 200);")
        info_layout.addWidget(self.song_info)
    
        # 按钮区域
        button_layout = QHBoxLayout()
    
        # 下载按钮
        self.download_button = QPushButton("下载歌曲")
        self.download_button.setStyleSheet("""
            padding: 8px; 
            font-size: 14px; 
            background-color: rgba(46, 139, 87, 200);
            color: white;
            font-weight: bold;
        """)
        self.download_button.setEnabled(False)
        self.download_button.clicked.connect(self.download_current_song)
        button_layout.addWidget(self.download_button)
        info_layout.addLayout(button_layout)

        
    
        # 播放控制
        control_layout = QHBoxLayout()
        # 添加上一首按钮
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
        
        # 添加下一首按钮
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
    
        # 歌词区域
        lyrics_layout = QVBoxLayout()
        lyrics_label = QLabel("歌词")
        lyrics_label.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
        lyrics_layout.addWidget(lyrics_label)
    
        # 歌词图像显示区域
        self.lyrics_scroll = QScrollArea()
        self.lyrics_scroll.setWidgetResizable(True)
        self.lyrics_scroll.setStyleSheet("background-color: rgba(37, 37, 37, 200); border: 1px solid #555;")
        self.lyrics_label = QLabel()
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_scroll.setWidget(self.lyrics_label)
        lyrics_layout.addWidget(self.lyrics_scroll)
    
        details_layout.addLayout(lyrics_layout, 5)
        results_layout.addLayout(details_layout, 2)
        main_layout.addLayout(results_layout, 5)
    
        # 状态栏
        self.status_bar = self.statusBar()
        self.status_bar.setStyleSheet("background-color: rgba(53, 53, 53, 180);")
    
        # 连接信号
        search_button.clicked.connect(self.start_search)

        # 美化菜单栏样式
        menu_bar.setStyleSheet("""
            QMenuBar {
                background-color: rgba(53, 53, 53, 180);
                color: white;
                padding: 5px;
            }
            QMenuBar::item {
                padding: 5px 10px;
                border-radius: 4px;
            }
            QMenuBar::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
            QMenu {
                background-color: rgba(53, 53, 53, 200);
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
            QMenu::item {
                padding: 5px 30px 5px 10px;
            }
            QMenu::item:selected {
                background-color: rgba(74, 35, 90, 200);
            }
            QMenu::separator {
                height: 1px;
                background-color: #555;
                margin: 5px 0;
            }
        """)

    def open_playlist_manager(self):
        dialog = PlaylistDialog(self.playlist_manager, self)
        # 添加播放按钮
        play_button = QPushButton("播放列表")
        play_button.clicked.connect(dialog.play_playlist)
        # 将按钮添加到对话框布局中...
        dialog.exec_()
        
    def open_equalizer(self):
        dialog = EqualizerDialog(self.media_player, self)
        dialog.exec_()
        
    def open_sleep_timer(self):
        dialog = SleepTimerDialog(self)
        dialog.exec_()   
        
       
    def open_tools_dialog(self):
        """打开工具对话框"""
        dialog = ToolsDialog(self)
        dialog.exec_()

    def remove_search_worker(self):
        """安全移除搜索工作线程"""
        if self.search_worker in self.active_threads:
            self.active_threads.remove(self.search_worker)
        self.search_worker = None
        
    def remove_download_worker(self):
        """安全移除下载工作线程"""
        if self.download_worker in self.active_threads:
            self.active_threads.remove(self.download_worker)
        self.download_worker = None   

    def closeEvent(self, event):
        """确保线程安全退出"""
        # 终止所有工作线程
        self.terminate_all_threads()
        
        # 停止媒体播放器
        self.media_player.stop()
        
        # 关闭日志控制台
        if self.log_console:
            self.log_console.close()
        
        event.accept()
        
    def terminate_all_threads(self):
        """安全终止所有活动线程"""
        # 复制一份线程列表，避免在迭代时修改
        threads_to_terminate = self.active_threads.copy()
        
        for thread in threads_to_terminate:
            if thread and thread.isRunning():
                thread.requestInterruption()
                thread.quit()
                if not thread.wait(2000):  # 等待2秒
                    thread.terminate()
                    thread.wait()
                # 从活动线程列表中移除
                if thread in self.active_threads:
                    self.active_threads.remove(thread)
        
    def open_log_console(self):
        """打开日志控制台"""
        dialog = QDialog(self)
        dialog.setWindowTitle("日志控制台")
        dialog.setGeometry(100, 100, 800, 600)
    
        layout = QVBoxLayout()
    
        # 日志显示区域
        log_text = QTextEdit()
        log_text.setReadOnly(True)
        log_text.setStyleSheet("font-family: Consolas, 'Courier New', monospace; font-size: 12px;")
    
        # 尝试读取日志文件
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_app.log")
    
        try:
            # 尝试使用UTF-8编码读取
            with open(log_path, "r", encoding="utf-8") as log_file:
                log_content = log_file.read()
        except UnicodeDecodeError:
            try:
                # 如果UTF-8失败，尝试GBK编码（常见于中文Windows系统）
                with open(log_path, "r", encoding="gbk") as log_file:
                    log_content = log_file.read()
            except Exception as e:
                log_content = f"读取日志文件失败: {str(e)}"
        except Exception as e:
            log_content = f"读取日志文件失败: {str(e)}"
    
        log_text.setPlainText(log_content)
    
        # 添加刷新按钮
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(lambda: self.refresh_log_content(log_text))
    
        layout.addWidget(log_text)
        layout.addWidget(refresh_button, alignment=Qt.AlignRight)
    
        dialog.setLayout(layout)
        dialog.exec_()

    def refresh_log_content(self, log_text_widget):
        """刷新日志内容"""
        log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "music_app.log")
    
        try:
            with open(log_path, "r", encoding="utf-8") as log_file:
                log_content = log_file.read()
        except UnicodeDecodeError:
            try:
                with open(log_path, "r", encoding="gbk") as log_file:
                    log_content = log_file.read()
            except Exception as e:
                log_content = f"读取日志文件失败: {str(e)}"
        except Exception as e:
            log_content = f"读取日志文件失败: {str(e)}"
    
        log_text_widget.setPlainText(log_content)
        
    def open_bilibili_audio_search(self):
        """打开Bilibili音频搜索对话框"""
        # 安全获取cookie，处理旧版设置文件
        cookie = self.settings.get("bilibili", {}).get("cookie", "")
        
        # 创建并显示搜索对话框
        search_dialog = AudioSearchDialog(self, cookie)
        search_dialog.exec_()
        
    def open_bilibili_search(self):
        """打开Bilibili视频搜索对话框"""
        if not self.current_song_info:
            self.status_bar.showMessage("没有选中的歌曲")
            return
            
        # 安全获取cookie，处理旧版设置文件
        cookie = self.settings.get("bilibili", {}).get("cookie", "")
        
        # 创建并显示搜索对话框
        search_dialog = VideoSearchDialog(self, cookie)
        search_dialog.exec_()
        
    def set_background(self):
        """设置背景图片"""
        bg_image = self.settings.get("background_image", "")
        if bg_image and os.path.exists(bg_image):
            # 使用样式表设置背景
            self.setStyleSheet(f"""
                QMainWindow {{
                    background-image: url({bg_image});
                    background-position: center;
                    background-repeat: no-repeat;
                    background-attachment: fixed;
                }}
            """)
    
    def show_context_menu(self, pos):
        """显示上下文菜单"""
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
        
        # 下载操作
        download_action = QAction("下载歌曲", self)
        download_action.triggered.connect(lambda: self.download_selected_song(item))
        menu.addAction(download_action)
        
        # 显示歌曲信息
        info_action = QAction("查看详情", self)
        info_action.triggered.connect(lambda: self.show_song_info(item))
        menu.addAction(info_action)
        
        # 在B站搜索
        bilibili_action = QAction("在B站搜索", self)
        bilibili_action.triggered.connect(lambda: self.bilibili_search_selected(item))
        menu.addAction(bilibili_action)
        
        menu.exec_(self.results_list.mapToGlobal(pos))
        
    def bilibili_search_selected(self, item):
        """在B站搜索选中的歌曲"""
        index = self.results_list.row(item)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            self.display_song_info(self.current_song)
            self.open_bilibili_search()
    
    def download_selected_song(self, item):
        """下载选中的歌曲"""
        index = self.results_list.row(item)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            self.display_song_info(self.current_song)
            self.download_current_song()
    
    def show_song_info(self, item):
        """显示歌曲详情"""
        index = self.results_list.row(item)
        if index < len(self.search_results):
            song = self.search_results[index]
            info = f"歌曲名称: {song.get('name', '未知')}\n"
            info += f"艺术家: {song.get('artists', '未知')}\n"
            info += f"专辑: {song.get('album', '未知')}\n"
            info += f"时长: {self.format_time(song.get('duration', 0))}"
            
            QMessageBox.information(self, "歌曲详情", info)
    
    def open_settings(self):
        """打开设置对话框"""
        dialog = SettingsDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            # 重新加载设置
            self.settings = load_settings()
            # 更新音源选择
            self.source_combo.clear()
            self.source_combo.addItems(get_source_names())
            self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
            
            # 更新背景
            self.set_background()
            
            # 重新创建必要的目录
            self.create_necessary_dirs()
            
            QMessageBox.information(self, "设置", "设置已保存！")
            
    def switch_to_original_mode(self):
        """切换到原music_player.py模式"""
        try:
            # 获取当前脚本目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            original_script = os.path.join(current_dir, "music_player.py")
            
            if os.path.exists(original_script):
                # 关闭当前应用
                self.close()
                
                # 启动新进程
                subprocess.Popen([sys.executable, original_script])
            else:
                QMessageBox.critical(self, "错误", "找不到原music_player.py脚本")
        except Exception as e:
            logger.error(f"切换模式失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"切换模式失败: {str(e)}")
        
    def setup_connections(self):
        """设置信号连接"""
        # 信号连接在每次创建新线程时设置
        self.media_player.positionChanged.connect(self.lyrics_sync.update_position)
        # 连接媒体播放器状态改变信号
        self.media_player.stateChanged.connect(self.handle_player_state_changed)
        self.media_player.mediaStatusChanged.connect(self.handle_media_status_changed)

    def start_search(self):
        """开始搜索歌曲"""
        keyword = self.search_input.text().strip()
        if not keyword:
            self.status_bar.showMessage("请输入歌曲名称")
            logger.warning("搜索请求: 未输入关键词")
            return
        self.playlist = self.search_results if self.search_results else []
            
        # 更新当前音源
        self.settings["sources"]["active_source"] = self.source_combo.currentText()
        save_settings(self.settings)
            
        logger.info(f"开始搜索: {keyword}")
        self.status_bar.showMessage("搜索中...")
        self.results_list.clear()
        self.song_info.clear()
        self.lyrics_label.clear()
        self.download_button.setEnabled(False)
        
        
        # 创建新的搜索工作线程
        self.search_worker = MusicWorker()
        self.active_threads.append(self.search_worker)  # 添加到活动线程列表
        self.search_worker.search_finished.connect(self.display_search_results)
        self.search_worker.error_occurred.connect(self.display_error)
        self.search_worker.finished.connect(lambda: self.active_threads.remove(self.search_worker))  
        self.search_worker.search_songs(keyword)
        
    def display_search_results(self, songs):
        """显示搜索结果"""
        if not songs:
            self.status_bar.showMessage("未找到相关歌曲")
            logger.warning("搜索结果: 未找到相关歌曲")
            return
            
        logger.info(f"显示搜索结果: 共 {len(songs)} 首")
        self.status_bar.showMessage(f"找到 {len(songs)} 首歌曲")
        self.search_results = songs  # 保存搜索结果
        
        self.results_list.clear()  # 确保列表已清空
        
        # 确保缓存目录存在
        cache_dir = self.settings["save_paths"]["cache"]
        if not os.path.exists(cache_dir):
            os.makedirs(cache_dir, exist_ok=True)
            logger.info(f"创建缓存目录: {cache_dir}")
        
        for i, song in enumerate(songs):
            duration = self.format_time(song["duration"])
            item_text = f"{i+1}. {song['name']} - {song['artists']} ({duration})"
            
            # 使用 QListWidgetItem 创建列表项
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, i)  # 存储索引
            
            # 下载并显示专辑封面
            pic_url = song.get("pic", "")
            if pic_url:
                try:
                    # 创建安全的文件名
                    songid = song.get("id", f"song_{i}")
                    safe_songid = re.sub(r'[\\/*?:"<>|]', "", songid)
                    image_path = os.path.join(cache_dir, f"{safe_songid}.jpg")
                    
                    # 如果图片不存在，下载它
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
                    
                    # 加载图片
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
            
            self.results_list.addItem(item)  # 添加列表项到列表控件
            
    def song_selected(self, item):
        """当用户选择歌曲时触发"""
        index = item.data(Qt.UserRole)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            logger.info(f"选择歌曲: {self.current_song['name']}")
            self.status_bar.showMessage(f"正在获取歌曲详情: {self.current_song['name']}")
            self.display_song_info(self.current_song)
            
    def display_song_info(self, song):
        """显示歌曲信息"""
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
        
        # 显示歌词
        lyrics = song.get("lrc", "歌词未找到")
        lyrics_image = draw_lyrics(lyrics)
        image = QImage.fromData(lyrics_image, "JPEG")
        pixmap = QPixmap.fromImage(image)
        self.lyrics_label.setPixmap(pixmap)
        self.status_bar.showMessage("歌曲信息加载完成")
        
        # 启用播放控制按钮
        self.play_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.stop_button.setEnabled(True)

    def handle_player_state_changed(self, state):
        """处理播放器状态变化"""
        if state == QMediaPlayer.PlayingState:
            self.status_bar.showMessage("播放中...")
        elif state == QMediaPlayer.PausedState:
            self.status_bar.showMessage("已暂停")
        elif state == QMediaPlayer.StoppedState:
            self.status_bar.showMessage("已停止")
    
    def handle_media_status_changed(self, status):
        """处理媒体状态变化"""
        if status == QMediaPlayer.EndOfMedia:
            self.status_bar.showMessage("播放完成")
            self.play_next_song()
    
    def play_next_song(self):
        """播放下一首歌曲"""
        if not self.playlist:
            return
            
        if self.repeat_mode == "single":
            # 单曲循环模式，重新播放当前歌曲
            self.play_song_by_index(self.current_play_index)
            return
        
        if self.is_random_play:
            # 随机播放模式
            next_index = random.randint(0, len(self.playlist) - 1)
        else:
            # 顺序播放模式
            next_index = self.current_play_index + 1
            if next_index >= len(self.playlist):
                if self.repeat_mode == "list":
                    # 列表循环模式，从头开始
                    next_index = 0
                else:
                    # 不重复模式，停止播放
                    self.stop_song()
                    return
        
        self.play_song_by_index(next_index)
    
    def play_song_by_index(self, index):
        """播放指定索引的歌曲"""
        if index < 0 or index >= len(self.playlist):
            return
            
        self.current_play_index = index
        song = self.playlist[index]
        
        # 下载并播放歌曲
        self.current_song_info = song
        self.download_current_song_for_playback()
    
    def download_current_song_for_playback(self):
        """为播放下载当前歌曲（不弹出保存对话框）"""
        if not self.current_song_info or 'url' not in self.current_song_info:
            return
            
        # 生成保存路径
        default_name = f"{self.current_song_info['name']}.mp3".replace("/", "_").replace("\\", "_")
        file_path = os.path.join(self.settings["save_paths"]["music"], default_name)
        
        # 检查文件是否已存在
        if not os.path.exists(file_path):
            # 创建下载工作线程
            self.download_worker = MusicWorker()
            self.active_threads.append(self.download_worker)
            self.download_worker.download_finished.connect(self.handle_download_for_playback)
            self.download_worker.error_occurred.connect(self.display_error)
            self.download_worker.download_song(self.current_song_info['url'], file_path)
        else:
            # 文件已存在，直接播放
            self.play_downloaded_song(file_path)
    
    def handle_download_for_playback(self, file_path):
        """处理为播放而下载完成的歌曲"""
        self.play_downloaded_song(file_path)
    
    def play_downloaded_song(self, file_path):
        """播放已下载的歌曲"""
        self.current_song_path = file_path
        self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
        self.media_player.play()
        
        # 更新UI显示当前播放信息
        song = self.playlist[self.current_play_index]
        self.song_info.setText(f"<b>正在播放:</b> {song.get('name', '未知')} - {song.get('artists', '未知')}")
        
        # 滚动到当前播放的歌曲
        self.results_list.setCurrentRow(self.current_play_index)
        
    def display_error(self, error_msg):
        """显示错误信息"""
        logger.error(f"显示错误: {error_msg}")
        self.status_bar.showMessage("发生错误")
        self.song_info.setText(f"错误信息:\n{error_msg}")
        QMessageBox.critical(self, "错误", f"操作失败:\n{error_msg}")
        
    def download_current_song(self):
        """下载当前歌曲"""
        if not self.current_song_info or 'url' not in self.current_song_info:
            self.status_bar.showMessage("没有可下载的歌曲")
            logger.warning("下载请求: 没有可下载的歌曲")
            return
        if self.settings["other"]["auto_play"] and len(self.playlist) > 0 and self.playlist[0] == self.current_song_info:
            self.play_song_by_index(0)
            
        # 获取保存路径
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
        
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("下载歌曲...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("下载进度")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
        
        # 启动下载线程
        self.download_worker = MusicWorker()
        self.active_threads.append(self.download_worker)  # 添加到活动线程列表
        self.download_worker.download_progress.connect(self.update_download_progress)
        self.download_worker.download_finished.connect(self.download_completed)
        self.download_worker.error_occurred.connect(self.display_error)
        self.download_worker.finished.connect(self.remove_download_worker)
        self.download_worker.download_song(self.current_song_info['url'], file_path)
        
    def update_download_progress(self, progress):
        """更新下载进度"""
        self.progress_dialog.setValue(progress)
        
    def cancel_download(self):
        """取消下载"""
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
        """下载完成"""
        self.progress_dialog.close()
        self.status_bar.showMessage(f"歌曲下载完成: {file_path}")
        logger.info(f"下载完成: {file_path}")
        QMessageBox.information(self, "下载完成", f"歌曲已成功保存到:\n{file_path}")
        
        # 如果设置了自动播放，则播放歌曲
        if self.settings["other"]["auto_play"]:
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
            self.status_bar.showMessage("正在播放歌曲...")
            
    def play_song(self):
        """播放歌曲"""
        if self.current_song_path:
            self.media_player.play()
            self.status_bar.showMessage("播放中...")

    def pause_song(self):
        """暂停播放"""
        if self.media_player.state() == QMediaPlayer.PlayingState:
            self.media_player.pause()
            self.status_bar.showMessage("已暂停")

    def stop_song(self):
        """停止播放"""
        self.media_player.stop()
        self.status_bar.showMessage("已停止")
    
    def play_previous(self):
        """播放上一首歌曲"""
        if not self.playlist or self.current_play_index <= 0:
            return
            
        # 计算上一首索引
        if self.is_random_play:
            prev_index = random.randint(0, len(self.playlist) - 1)
        else:
            prev_index = self.current_play_index - 1
            if prev_index < 0:
                if self.repeat_mode == "list":
                    prev_index = len(self.playlist) - 1
                else:
                    return
        
        self.play_song_by_index(prev_index)
    
    def play_next(self):
        """播放下一首歌曲"""
        self.play_next_song()

        
    @staticmethod
    def format_time(duration_ms):
        """格式化歌曲时长"""
        duration = duration_ms // 1000
        hours = duration // 3600
        minutes = (duration % 3600) // 60
        seconds = duration % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes:02d}:{seconds:02d}"

class ToolsDialog(QDialog):
    """自定义工具对话框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("自定义工具")
        self.setGeometry(300, 300, 500, 300)
        self.init_ui()
        
    def init_ui(self):
        layout = QVBoxLayout()
        
        # 工具列表
        self.tools_list = QListWidget()
        self.tools_list.setStyleSheet("font-size: 14px;")
        layout.addWidget(QLabel("可用工具:"))
        layout.addWidget(self.tools_list)
        
        # 加载保存的工具
        self.load_tools()
        
        # 按钮区域
        button_layout = QHBoxLayout()
        
        add_button = QPushButton("添加工具")
        add_button.clicked.connect(self.add_tool)
        
        remove_button = QPushButton("移除工具")
        remove_button.clicked.connect(self.remove_tool)
        
        run_button = QPushButton("运行选中工具")
        run_button.clicked.connect(self.run_tool)
        
        button_layout.addWidget(add_button)
        button_layout.addWidget(remove_button)
        button_layout.addWidget(run_button)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def load_tools(self):
        """从设置加载工具列表"""
        self.tools_list.clear()
        settings = load_settings()
        tools = settings.get("custom_tools", [])
        
        for tool in tools:
            self.tools_list.addItem(f"{tool['name']} ({tool['path']})")
    
    def add_tool(self):
        """添加新工具"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择可执行文件", "", "可执行文件 (*.exe *.bat *.cmd);;所有文件 (*.*)"
        )
        
        if file_path:
            name, ok = QInputDialog.getText(
                self, "工具名称", "请输入工具名称:", text=os.path.basename(file_path)
            )
            
            if ok and name:
                # 更新设置
                settings = load_settings()
                tools = settings.get("custom_tools", [])
                tools.append({"name": name, "path": file_path})
                settings["custom_tools"] = tools
                save_settings(settings)
                
                # 刷新列表
                self.load_tools()
    
    def remove_tool(self):
        """移除选中的工具"""
        selected = self.tools_list.currentRow()
        if selected >= 0:
            settings = load_settings()
            tools = settings.get("custom_tools", [])
            
            if 0 <= selected < len(tools):
                del tools[selected]
                settings["custom_tools"] = tools
                save_settings(settings)
                self.load_tools()
    
    def run_tool(self):
        """运行选中的工具"""
        selected = self.tools_list.currentRow()
        if selected >= 0:
            settings = load_settings()
            tools = settings.get("custom_tools", [])
            
            if 0 <= selected < len(tools):
                tool_path = tools[selected]["path"]
                try:
                    # 根据操作系统使用不同的启动方式
                    if sys.platform == "win32":
                        os.startfile(tool_path)
                    else:
                        subprocess.Popen(tool_path)
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"启动工具失败: {str(e)}")

def draw_lyrics(
    lyrics: str,
    image_width=1000,
    font_size=30,
    line_spacing=20,
    top_color=(255, 250, 240),  # 暖白色
    bottom_color=(235, 255, 247),
    text_color=(70, 70, 70),
) -> bytes:
    """
    渲染歌词为图片，背景为竖向渐变色，返回 JPEG 字节流。
    """
    # 清除时间戳但保留空白行
    lines = lyrics.splitlines()
    cleaned_lines = []
    for line in lines:
        cleaned = re.sub(r"\[\d{2}:\d{2}(?:\.\d{2,3})?\]", "", line)
        cleaned_lines.append(cleaned if cleaned != "" else "")

    # 加载字体
    try:
        font = ImageFont.truetype(FONT_PATH, font_size)
    except IOError:
        # 如果找不到字体，使用默认字体
        font = ImageFont.load_default()
        logger.warning("使用默认字体渲染歌词")

    # 计算总高度
    dummy_img = Image.new("RGB", (image_width, 1))
    draw = ImageDraw.Draw(dummy_img)
    line_heights = [
        draw.textbbox((0, 0), line if line.strip() else "　", font=font)[3]
        for line in cleaned_lines
    ]
    total_height = sum(line_heights) + line_spacing * (len(cleaned_lines) - 1) + 100

    # 创建渐变背景图像
    img = Image.new("RGB", (image_width, total_height))
    for y in range(total_height):
        ratio = y / total_height
        r = int(top_color[0] * (1 - ratio) + bottom_color[0] * ratio)
        g = int(top_color[1] * (1 - ratio) + bottom_color[1] * ratio)
        b = int(top_color[2] * (1 - ratio) + bottom_color[2] * ratio)
        for x in range(image_width):
            img.putpixel((x, y), (r, g, b))

    draw = ImageDraw.Draw(img)

    # 绘制歌词文本（居中）
    y = 50
    for line, line_height in zip(cleaned_lines, line_heights):
        text = line if line.strip() else "　"  # 全角空格占位
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((image_width - text_width) / 2, y), text, font=font, fill=text_color)
        y += line_height + line_spacing

    # 输出到字节流
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG", quality=90)
    img_bytes.seek(0)
    return img_bytes.getvalue()


if __name__ == "__main__":
    # 设置插件环境
    os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MusicPlayerApp()
    window.show()
    sys.exit(app.exec_())
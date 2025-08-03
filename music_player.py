import sys
import random
import traceback
import json
import requests
import io
import re
import logging
import os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QLineEdit, QPushButton, QListWidget, QTextEdit, QScrollArea, QFrame,
    QFileDialog, QProgressDialog, QMessageBox
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("music_app.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MusicApp")

# 设置字体文件路径
FONT_PATH = "simhei.ttf"  # 确保有这个字体文件

class NetEaseMusicAPI:
    """音乐捕捉器create by:228117384"""
    
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

    def fetch_comments(self, song_id: int):
        """获取热评"""
        logger.info(f"获取歌曲热评: ID={song_id}")
        url = f"https://music.163.com/weapi/v1/resource/hotcomments/R_SO_4_{song_id}?csrf_token="
        data = {
            "params": self.params,
            "encSecKey": self.enc_sec_key,
        }
        try:
            response = requests.post(url, headers=self.header, cookies=self.cookies, data=data)
            result = response.json()
            logger.info(f"获取到 {len(result.get('hotComments', []))} 条热评")
            return result.get("hotComments", [])
        except Exception as e:
            logger.error(f"获取评论失败: {str(e)}")
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
            
            # 获取专辑封面
            cover_url = song["al"]["picUrl"]
            # 获取播放链接
            audio_url = f"https://music.163.com/song/media/outer/url?id={song_id}.mp3"
            
            return {
                "title": song["name"],
                "author": "、".join(artist["name"] for artist in song["ar"]),
                "cover_url": cover_url,
                "audio_url": audio_url,
            }
        except Exception as e:
            logger.error(f"获取歌曲额外信息失败: {str(e)}")
            return {}
    
    def download_song(self, audio_url: str, file_path: str) -> bool:
        """下载歌曲文件"""
        logger.info(f"开始下载歌曲: {file_path}")
        try:
            # 设置请求头模拟浏览器
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
                        # 计算下载进度百分比
                        progress = int(100 * downloaded / total_size) if total_size > 0 else 0
                        # 发送进度信号
                        self.download_progress.emit(progress)
            
            logger.info(f"歌曲下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载歌曲失败: {str(e)}")
            return False


class MusicWorker(QThread):
    """后台工作线程，用于执行网络请求和耗时操作"""
    
    search_finished = pyqtSignal(list)
    song_info_ready = pyqtSignal(dict)
    comments_ready = pyqtSignal(str)
    lyrics_ready = pyqtSignal(bytes)
    error_occurred = pyqtSignal(str)
    download_progress = pyqtSignal(int)  # 下载进度信号
    download_finished = pyqtSignal(str)  # 下载完成信号
    
    def __init__(self, api):
        super().__init__()
        self.api = api
        self.mode = None
        self.keyword = None
        self.song_id = None
        self.audio_url = None
        self.file_path = None
        
    def search_songs(self, keyword):
        """设置搜索任务"""
        self.mode = "search"
        self.keyword = keyword
        self.start()
        
    def fetch_song_details(self, song):
        """设置获取歌曲详情任务"""
        self.mode = "details"
        self.song = song
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
                songs = self.api.fetch_data(self.keyword, limit=10)
                self.search_finished.emit(songs)
                
            elif self.mode == "details":
                # 获取歌曲详情
                song_info = self.api.fetch_extra(self.song["id"])
                self.song_info_ready.emit(song_info)
                
                # 获取评论
                comments = self.api.fetch_comments(self.song["id"])
                if comments:
                    comment = random.choice(comments)["content"]
                    self.comments_ready.emit(comment)
                else:
                    self.comments_ready.emit("暂无热评")
                
                # 获取歌词
                lyrics = self.api.fetch_lyrics(self.song["id"])
                lyrics_image = draw_lyrics(lyrics)
                self.lyrics_ready.emit(lyrics_image)
                
            elif self.mode == "download":
                # 下载歌曲
                success = self.api.download_song(self.audio_url, self.file_path)
                if success:
                    self.download_finished.emit(self.file_path)
                else:
                    self.error_occurred.emit("歌曲下载失败")
                    
        except Exception as e:
            error_msg = f"发生错误: {str(e)}\n{traceback.format_exc()}"
            logger.error(error_msg)
            self.error_occurred.emit(error_msg)


class MusicPlayerApp(QMainWindow):
    """音乐搜索和播放应用程序"""
    
    def __init__(self):
        super().__init__()
        self.api = NetEaseMusicAPI()
        self.worker = MusicWorker(self.api)
        self.current_song = None
        self.current_song_info = None
        self.search_results = []  # 存储搜索结果
        self.init_ui()
        self.setup_connections()
        logger.info("应用程序启动")
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("音乐捕捉器create QQby:228117384")
        self.setGeometry(100, 100, 1000, 800)
        
        # 创建主部件和布局
        main_widget = QWidget()
        main_layout = QVBoxLayout()
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)
        
        # 创建暗色主题
        self.set_dark_theme()
        
        # 搜索区域
        search_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("输入歌曲名称...")
        self.search_input.setStyleSheet("padding: 8px; font-size: 14px;")
        self.search_input.returnPressed.connect(self.start_search)  # 回车搜索
        search_button = QPushButton("搜索")
        search_button.setStyleSheet("padding: 8px; font-size: 14px;")
        search_layout.addWidget(self.search_input)
        search_layout.addWidget(search_button)
        main_layout.addLayout(search_layout)
        
        # 结果区域
        results_layout = QHBoxLayout()
        
        # 左侧：搜索结果列表
        results_list_layout = QVBoxLayout()
        results_list_layout.addWidget(QLabel("搜索结果"))
        self.results_list = QListWidget()
        self.results_list.setStyleSheet("font-size: 14px;")
        results_list_layout.addWidget(self.results_list)
        results_layout.addLayout(results_list_layout, 1)
        
        # 右侧：歌曲详情
        details_layout = QVBoxLayout()
        
        # 歌曲信息
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel("歌曲信息"))
        
        self.song_info = QTextEdit()
        self.song_info.setReadOnly(True)
        self.song_info.setStyleSheet("font-size: 14px;")
        info_layout.addWidget(self.song_info)
        
        # 下载按钮
        self.download_button = QPushButton("下载歌曲")
        self.download_button.setStyleSheet("""
            padding: 8px; 
            font-size: 14px; 
            background-color: #2E8B57;
            color: white;
            font-weight: bold;
        """)
        self.download_button.setEnabled(False)
        info_layout.addWidget(self.download_button)
        
        details_layout.addLayout(info_layout, 2)
        
        # 热评
        details_layout.addWidget(QLabel("热门评论"))
        self.comments = QTextEdit()
        self.comments.setReadOnly(True)
        self.comments.setStyleSheet("font-size: 14px;")
        details_layout.addWidget(self.comments, 3)
        
        results_layout.addLayout(details_layout, 2)
        main_layout.addLayout(results_layout, 5)
        
        # 歌词区域
        lyrics_layout = QVBoxLayout()
        lyrics_layout.addWidget(QLabel("歌词"))
        
        # 歌词图像显示区域
        self.lyrics_scroll = QScrollArea()
        self.lyrics_scroll.setWidgetResizable(True)
        self.lyrics_label = QLabel()
        self.lyrics_label.setAlignment(Qt.AlignCenter)
        self.lyrics_scroll.setWidget(self.lyrics_label)
        lyrics_layout.addWidget(self.lyrics_scroll)
        
        main_layout.addLayout(lyrics_layout, 5)
        
        # 状态栏
        self.status_bar = self.statusBar()
        
        # 连接信号
        search_button.clicked.connect(self.start_search)
        self.results_list.itemClicked.connect(self.song_selected)
        self.download_button.clicked.connect(self.download_current_song)
        
    def set_dark_theme(self):
        """设置暗色主题"""
        dark_palette = QPalette()
        dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.WindowText, Qt.white)
        dark_palette.setColor(QPalette.Base, QColor(35, 35, 35))
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ButtonText, Qt.white)
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Highlight, QColor(142, 45, 197).lighter())
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)
        
        self.setPalette(dark_palette)
        self.setStyleSheet("""
            QMainWindow {
                background-color: #353535;
            }
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #252525;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QListWidget {
                background-color: #252525;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QLineEdit {
                background-color: #252525;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }
            QPushButton {
                background-color: #4A235A;
                color: white;
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #6C3483;
            }
            QPushButton:disabled {
                background-color: #555;
                color: #999;
            }
            QScrollArea {
                background-color: #252525;
                border: 1px solid #555;
                border-radius: 5px;
            }
            QProgressBar {
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                background-color: #353535;
            }
            QProgressBar::chunk {
                background-color: #4A235A;
                width: 10px;
            }
        """)
        
    def setup_connections(self):
        """设置信号连接"""
        self.worker.search_finished.connect(self.display_search_results)
        self.worker.song_info_ready.connect(self.display_song_info)
        self.worker.comments_ready.connect(self.display_comments)
        self.worker.lyrics_ready.connect(self.display_lyrics)
        self.worker.error_occurred.connect(self.display_error)
        self.worker.download_progress.connect(self.update_download_progress)
        self.worker.download_finished.connect(self.download_completed)
        
    def start_search(self):
        """开始搜索歌曲"""
        keyword = self.search_input.text().strip()
        if not keyword:
            self.status_bar.showMessage("请输入歌曲名称")
            logger.warning("搜索请求: 未输入关键词")
            return
            
        logger.info(f"开始搜索: {keyword}")
        self.status_bar.showMessage("搜索中...")
        self.results_list.clear()
        self.song_info.clear()
        self.comments.clear()
        self.lyrics_label.clear()
        self.download_button.setEnabled(False)
        self.worker.search_songs(keyword)
        
    def display_search_results(self, songs):
        """显示搜索结果"""
        if not songs:
            self.status_bar.showMessage("未找到相关歌曲")
            logger.warning("搜索结果: 未找到相关歌曲")
            return
            
        logger.info(f"显示搜索结果: 共 {len(songs)} 首")
        self.status_bar.showMessage(f"找到 {len(songs)} 首歌曲")
        self.search_results = songs  # 保存搜索结果
        
        for i, song in enumerate(songs):
            duration = self.format_time(song["duration"])
            item_text = f"{i+1}. {song['name']} - {song['artists']} ({duration})"
            self.results_list.addItem(item_text)
            
    def song_selected(self, item):
        """当用户选择歌曲时触发"""
        index = self.results_list.row(item)
        if index < len(self.search_results):
            self.current_song = self.search_results[index]
            logger.info(f"选择歌曲: {self.current_song['name']}")
            self.status_bar.showMessage(f"正在获取歌曲详情: {self.current_song['name']}")
            self.worker.fetch_song_details(self.current_song)
            
    def display_song_info(self, song_info):
        """显示歌曲信息"""
        if not song_info:
            self.song_info.setText("未能获取歌曲信息")
            self.download_button.setEnabled(False)
            logger.warning("歌曲信息: 获取失败")
            return
            
        self.current_song_info = song_info
        self.download_button.setEnabled(True)
        logger.info(f"显示歌曲信息: {song_info.get('title', '未知')}")
        
        info_text = (
            f"<b>歌曲名称:</b> {song_info.get('title', '未知')}<br>"
            f"<b>艺术家:</b> {song_info.get('author', '未知')}<br>"
            f"<b>播放链接:</b> <a href='{song_info.get('audio_url', '')}'>{song_info.get('audio_url', '')}</a>"
        )
        self.song_info.setHtml(info_text)
        
    def display_comments(self, comment):
        """显示热门评论"""
        logger.info("显示热门评论")
        self.comments.setText(comment)
        
    def display_lyrics(self, lyrics_image):
        """显示歌词图像"""
        logger.info("显示歌词")
        image = QImage.fromData(lyrics_image, "JPEG")
        pixmap = QPixmap.fromImage(image)
        self.lyrics_label.setPixmap(pixmap)
        self.status_bar.showMessage("歌曲信息加载完成")
        
    def display_error(self, error_msg):
        """显示错误信息"""
        logger.error(f"显示错误: {error_msg}")
        self.status_bar.showMessage("发生错误")
        self.song_info.setText(f"错误信息:\n{error_msg}")
        QMessageBox.critical(self, "错误", f"操作失败:\n{error_msg}")
        
    def download_current_song(self):
        """下载当前歌曲"""
        if not self.current_song_info or 'audio_url' not in self.current_song_info:
            self.status_bar.showMessage("没有可下载的歌曲")
            logger.warning("下载请求: 没有可下载的歌曲")
            return
            
        # 获取保存路径
        default_name = f"{self.current_song_info['title']}.mp3".replace("/", "_").replace("\\", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存歌曲", 
            os.path.join(os.path.expanduser("~"), "Music", default_name), 
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
        
        # 开始下载
        self.worker.download_song(self.current_song_info['audio_url'], file_path)
        
    def update_download_progress(self, progress):
        """更新下载进度"""
        self.progress_dialog.setValue(progress)
        
    def cancel_download(self):
        """取消下载"""
        logger.warning("下载取消: 用户取消")
        self.worker.terminate()
        self.status_bar.showMessage("下载已取消")
        
    def download_completed(self, file_path):
        """下载完成"""
        self.progress_dialog.close()
        self.status_bar.showMessage(f"歌曲下载完成: {file_path}")
        logger.info(f"下载完成: {file_path}")
        QMessageBox.information(self, "下载完成", f"歌曲已成功保存到:\n{file_path}")
        
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
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置应用字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MusicPlayerApp()
    window.show()
    sys.exit(app.exec_())
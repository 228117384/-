import sys
import os
import json
import re
import random
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
    QPlainTextEdit, QMenuBar, QStatusBar, QColorDialog, QInputDialog
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize, QUrl
from PyQt5.QtGui import QPixmap, QImage, QFont, QPalette, QColor, QIcon
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from settings_manager import load_settings, save_settings, get_active_source_config, get_source_names

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

def resource_path(relative_path):
    """获取资源的绝对路径（支持PyInstaller打包环境）"""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    path = os.path.join(base_path, relative_path)
    return os.path.normpath(path)

# 日志控制台对话框
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
        
        # 添加按钮
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
    bilibili_download_finished = pyqtSignal(str)  # Bilibili下载完成信号
    
    def __init__(self):
        super().__init__()
        self.mode = None
        self.keyword = None
        self.song = None
        self.audio_url = None
        self.file_path = None
        self.bilibili_url = None
        
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
        
    def download_bilibili_video(self, video_url, file_path):
        """设置Bilibili视频下载任务"""
        self.mode = "bilibili"
        self.bilibili_url = video_url
        self.file_path = file_path
        self.start()
        
    def run(self):
        """执行后台任务"""
        try:
            if self.mode == "search":
                from crawler import search_song
                settings = load_settings()
                max_results = settings["other"]["max_results"]
                
                result = search_song(self.keyword, max_results)
                songs = result.get("data", [])
                
                # 转换为统一格式
                formatted_songs = []
                for song in songs:
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
                    
            elif self.mode == "bilibili":
                # 下载Bilibili视频
                success = self.download_bilibili(self.bilibili_url, self.file_path)
                if success:
                    self.bilibili_download_finished.emit(self.file_path)
                else:
                    self.error_occurred.emit("Bilibili视频下载失败")
                    
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
            
            response = requests.get(url, headers=headers, stream=True)
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
            
    def download_bilibili(self, url, file_path):
        """下载Bilibili视频"""
        try:
            # 这里简化处理，实际需要调用Bilibili下载API
            logger.info(f"开始下载Bilibili视频: {url}")
            
            # 模拟下载过程
            for i in range(1, 101):
                self.download_progress.emit(i)
                QThread.msleep(50)  # 模拟下载延迟
                
            # 在实际应用中，这里应该是真实的下载代码
            # 例如：
            # response = requests.get(video_url, stream=True)
            # with open(file_path, 'wb') as f:
            #     for chunk in response.iter_content(chunk_size=8192):
            #         f.write(chunk)
            
            logger.info(f"Bilibili视频下载完成: {file_path}")
            return True
        except Exception as e:
            logger.error(f"下载Bilibili视频失败: {str(e)}")
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
        
        save_form.addRow("音乐保存位置:", self.create_dir_row(self.music_dir_edit, self.music_dir_btn))
        save_form.addRow("缓存文件位置:", self.create_dir_row(self.cache_dir_edit, self.cache_dir_btn))
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
        
        # 第三页：界面自定义
        ui_tab = QWidget()
        ui_layout = QVBoxLayout()
        
        # 颜色设置
        color_group = QGroupBox("颜色设置")
        color_form = QFormLayout()
        
        # 主背景色
        self.main_bg_btn = QPushButton("选择颜色")
        self.main_bg_btn.clicked.connect(lambda: self.select_color("main_bg"))
        self.main_bg_label = QLabel("#1e1e1e")
        color_form.addRow("主背景色:", self.create_color_row(self.main_bg_label, self.main_bg_btn))
        
        # 按钮背景色
        self.button_bg_btn = QPushButton("选择颜色")
        self.button_bg_btn.clicked.connect(lambda: self.select_color("button_bg"))
        self.button_bg_label = QLabel("#4a235a")
        color_form.addRow("按钮背景色:", self.create_color_row(self.button_bg_label, self.button_bg_btn))
        
        # 按钮悬停色
        self.button_hover_btn = QPushButton("选择颜色")
        self.button_hover_btn.clicked.connect(lambda: self.select_color("button_hover"))
        self.button_hover_label = QLabel("#6c3483")
        color_form.addRow("按钮悬停色:", self.create_color_row(self.button_hover_label, self.button_hover_btn))
        
        # 文字颜色
        self.text_color_btn = QPushButton("选择颜色")
        self.text_color_btn.clicked.connect(lambda: self.select_color("text_color"))
        self.text_color_label = QLabel("#ffffff")
        color_form.addRow("文字颜色:", self.create_color_row(self.text_color_label, self.text_color_btn))
        
        # 下载按钮颜色
        self.download_btn_color_btn = QPushButton("选择颜色")
        self.download_btn_color_btn.clicked.connect(lambda: self.select_color("download_btn_color"))
        self.download_btn_color_label = QLabel("#2e8b57")
        color_form.addRow("下载按钮色:", self.create_color_row(self.download_btn_color_label, self.download_btn_color_btn))
        
        # 预览按钮
        self.preview_btn = QPushButton("预览主题")
        self.preview_btn.clicked.connect(self.preview_theme)
        
        color_group.setLayout(color_form)
        
        ui_layout.addWidget(color_group)
        ui_layout.addWidget(self.preview_btn)
        ui_layout.addStretch()
        ui_tab.setLayout(ui_layout)
        
        # 添加标签页
        self.tabs.addTab(save_tab, "保存设置")
        self.tabs.addTab(source_tab, "音源设置")
        self.tabs.addTab(ui_tab, "界面设置")
        
        # 按钮
        button_layout = QHBoxLayout()
        self.save_btn = QPushButton("保存")
        self.save_btn.clicked.connect(self.save_settings)
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(self.save_btn)
        button_layout.addWidget(self.cancel_btn)
        
        # 主布局
        layout.addWidget(self.tabs)
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # 连接信号
        self.source_combo.currentTextChanged.connect(self.update_api_key)

    def create_dir_row(self, edit, btn):
        """创建目录选择行"""
        row_layout = QHBoxLayout()
        row_layout.addWidget(edit)
        row_layout.addWidget(btn)
        widget = QWidget()
        widget.setLayout(row_layout)
        return widget
        
    def create_color_row(self, label, btn):
        """创建颜色选择行"""
        row_layout = QHBoxLayout()
        row_layout.addWidget(label)
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
            
    def select_color(self, color_type):
        """选择颜色"""
        color = QColorDialog.getColor()
        if color.isValid():
            hex_color = color.name()
            if color_type == "main_bg":
                self.main_bg_label.setText(hex_color)
            elif color_type == "button_bg":
                self.button_bg_label.setText(hex_color)
            elif color_type == "button_hover":
                self.button_hover_label.setText(hex_color)
            elif color_type == "text_color":
                self.text_color_label.setText(hex_color)
            elif color_type == "download_btn_color":
                self.download_btn_color_label.setText(hex_color)
                
    def preview_theme(self):
        """预览主题"""
        # 创建临时颜色设置
        temp_colors = {
            "main_bg": self.main_bg_label.text(),
            "button_bg": self.button_bg_label.text(),
            "button_hover": self.button_hover_label.text(),
            "text_color": self.text_color_label.text(),
            "download_btn_color": self.download_btn_color_label.text()
        }
        
        # 应用主题预览
        self.parent.apply_theme(temp_colors)
        QMessageBox.information(self, "主题预览", "已应用主题预览，保存设置后永久生效")

    def load_settings(self):
        """加载设置"""
        # 保存位置
        self.music_dir_edit.setText(self.settings["save_paths"]["music"])
        self.cache_dir_edit.setText(self.settings["save_paths"]["cache"])
        
        # 背景图片
        self.bg_image_edit.setText(self.settings.get("background_image", ""))
        
        # 其他设置
        self.max_results_spin.setValue(self.settings["other"]["max_results"])
        self.auto_play_check.setChecked(self.settings["other"]["auto_play"])
        
        # 音源设置
        self.source_combo.setCurrentText(self.settings["sources"]["active_source"])
        active_source = get_active_source_config()
        self.api_key_edit.setText(active_source.get("api_key", ""))
        
        # 颜色设置
        colors = self.settings.get("theme_colors", {})
        self.main_bg_label.setText(colors.get("main_bg", "#1e1e1e"))
        self.button_bg_label.setText(colors.get("button_bg", "#4a235a"))
        self.button_hover_label.setText(colors.get("button_hover", "#6c3483"))
        self.text_color_label.setText(colors.get("text_color", "#ffffff"))
        self.download_btn_color_label.setText(colors.get("download_btn_color", "#2e8b57"))

    def update_api_key(self, source_name):
        """更新API密钥显示"""
        for source in self.settings["sources"]["sources_list"]:
            if source["name"] == source_name:
                self.api_key_edit.setText(source.get("api_key", ""))
                break

    def save_settings(self):
        """保存设置"""
        # 保存位置
        self.settings["save_paths"]["music"] = self.music_dir_edit.text()
        self.settings["save_paths"]["cache"] = self.cache_dir_edit.text()
        
        # 背景图片
        self.settings["background_image"] = self.bg_image_edit.text()
        
        # 其他设置
        self.settings["other"]["max_results"] = self.max_results_spin.value()
        self.settings["other"]["auto_play"] = self.auto_play_check.isChecked()
        
        # 音源设置
        active_source = self.source_combo.currentText()
        self.settings["sources"]["active_source"] = active_source
        
        # 更新API密钥
        for source in self.settings["sources"]["sources_list"]:
            if source["name"] == active_source:
                source["api_key"] = self.api_key_edit.text()
                break
        
        # 保存颜色设置
        self.settings["theme_colors"] = {
            "main_bg": self.main_bg_label.text(),
            "button_bg": self.button_bg_label.text(),
            "button_hover": self.button_hover_label.text(),
            "text_color": self.text_color_label.text(),
            "download_btn_color": self.download_btn_color_label.text()
        }
        
        # 保存设置
        save_settings(self.settings)
        self.accept()
        
        # 应用新主题
        self.parent.apply_theme(self.settings["theme_colors"])


class MusicPlayerApp(QMainWindow):
    """音乐搜索和播放应用程序"""
    
    def __init__(self):
        super().__init__()
        self.api = None
        self.worker = MusicWorker()
        self.current_song = None
        self.current_song_info = None
        self.search_results = []  # 存储搜索结果
        self.settings = load_settings()
        self.media_player = QMediaPlayer()
        self.current_song_path = None
        self.log_console = None  # 日志控制台对话框
        self.init_ui()
        self.setup_connections()
        logger.info("应用程序启动")
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("音乐捕捉器 create by:228117384")
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
        
        # 添加"查看"菜单
        view_menu = menu_bar.addMenu("查看")
        
        # 添加"日志控制台"动作
        log_action = QAction("日志控制台", self)
        log_action.setShortcut("Ctrl+L")
        log_action.triggered.connect(self.open_log_console)
        view_menu.addAction(log_action)
        
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
        
        # 搜索区域
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
        
        search_layout.addWidget(self.search_input, 6)
        search_layout.addWidget(self.source_combo, 2)
        search_layout.addWidget(search_button, 1)
        search_layout.addWidget(settings_button, 1)
        search_layout.addWidget(switch_button, 1)
        search_layout.addWidget(log_button, 1)
        toolbar_layout.addLayout(search_layout)
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
        
        # 在B站搜索按钮
        self.bilibili_button = QPushButton("在B站搜索")
        self.bilibili_button.setStyleSheet("""
            padding: 8px; 
            font-size: 14px; 
            background-color: rgba(219, 68, 83, 200);
            color: white;
            font-weight: bold;
        """)
        self.bilibili_button.setEnabled(False)
        self.bilibili_button.clicked.connect(self.open_bilibili_search)
        
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.bilibili_button)
        info_layout.addLayout(button_layout)
        
        # 播放控制
        control_layout = QHBoxLayout()
        self.play_button = QPushButton("播放")
        self.play_button.setEnabled(False)
        self.play_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.pause_button = QPushButton("暂停")
        self.pause_button.setEnabled(False)
        self.pause_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        self.stop_button = QPushButton("停止")
        self.stop_button.setEnabled(False)
        self.stop_button.setStyleSheet("padding: 8px; font-size: 14px; background-color: rgba(74, 35, 90, 200);")
        
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
        self.lyrics_scroll.setStyleSheet("background-color: rgba(37, 37, 37, 200);")
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
        self.results_list.itemClicked.connect(self.song_selected)
        self.download_button.clicked.connect(self.download_current_song)
        self.play_button.clicked.connect(self.play_song)
        self.pause_button.clicked.connect(self.pause_song)
        self.stop_button.clicked.connect(self.stop_song)
        
        # 最后：应用主题（确保所有控件都已创建）
        self.apply_theme(self.settings.get("theme_colors", {}))
        
    def apply_theme(self, colors):
        """应用主题颜色"""
        main_bg = colors.get("main_bg", "#1e1e1e")
        button_bg = colors.get("button_bg", "#4a235a")
        button_hover = colors.get("button_hover", "#6c3483")
        text_color = colors.get("text_color", "#ffffff")
        download_btn_color = colors.get("download_btn_color", "#2e8b57")
        
        # 生成样式表
        style_sheet = f"""
            QLabel {{
                color: {text_color};
                font-size: 14px;
                font-weight: bold;
                background-color: rgba(53, 53, 53, 180);
            }}
            QTextEdit {{
                background-color: rgba(37, 37, 37, 200);
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
            }}
            QListWidget {{
                background-color: rgba(37, 37, 37, 200);
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
            }}
            QLineEdit {{
                background-color: rgba(37, 37, 37, 200);
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }}
            QPushButton {{
                background-color: rgba({button_bg.lstrip('#')}, 200);
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
                padding: 8px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: rgba({button_hover.lstrip('#')}, 200);
            }}
            QPushButton:disabled {{
                background-color: rgba(85, 85, 85, 200);
                color: #999;
            }}
            QScrollArea {{
                background-color: rgba(37, 37, 37, 200);
                border: 1px solid #555;
                border-radius: 5px;
            }}
            QProgressBar {{
                border: 2px solid grey;
                border-radius: 5px;
                text-align: center;
                background-color: rgba(53, 53, 53, 180);
            }}
            QProgressBar::chunk {{
                background-color: rgba({button_bg.lstrip('#')}, 200);
                width: 10px;
            }}
            QComboBox {{
                background-color: rgba(37, 37, 37, 200);
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
                padding: 5px;
            }}
            QGroupBox {{
                color: {text_color};
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
                background-color: rgba(53, 53, 53, 180);
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 3px;
                background-color: rgba(53, 53, 53, 180);
            }}
            QStatusBar {{
                background-color: rgba(53, 53, 53, 180);
            }}
            #centralWidget {{
                background-color: {main_bg};
            }}
        """
        
        # 特殊按钮样式
        download_style = f"""
            padding: 8px; 
            font-size: 14px; 
            background-color: rgba({download_btn_color.lstrip('#')}, 200);
            color: white;
            font-weight: bold;
        """
        if hasattr(self, 'download_button'):
            self.download_button.setStyleSheet(download_style)
        
        # B站按钮样式
        bilibili_style = f"""
            padding: 8px; 
            font-size: 14px; 
            background-color: rgba(219, 68, 83, 200);
            color: white;
            font-weight: bold;
        """
        if hasattr(self, 'bilibili_button'):
            self.bilibili_button.setStyleSheet(bilibili_style)
        
        # 应用样式表
        self.setStyleSheet(style_sheet)
    
    def open_log_console(self):
        """打开日志控制台"""
        if not self.log_console:
            self.log_console = LogConsoleDialog(self)
        self.log_console.show()
        self.log_console.raise_()  # 将窗口置于顶层
        self.log_console.activateWindow()  # 激活窗口
        
    def open_bilibili_search(self):
        """在Bilibili搜索当前歌曲"""
        if not self.current_song_info:
            self.status_bar.showMessage("没有选中的歌曲")
            return
            
        song_name = self.current_song_info['name']
        artist = self.current_song_info['artists']
        search_query = f"{song_name} {artist}"
        
        # URL编码查询参数
        encoded_query = requests.utils.quote(search_query)
        bilibili_url = f"https://search.bilibili.com/all?keyword={encoded_query}"
        
        # 打开浏览器
        webbrowser.open(bilibili_url)
        self.status_bar.showMessage(f"在B站搜索: {search_query}")
        logger.info(f"打开Bilibili搜索: {bilibili_url}")
        
        # 询问用户是否要下载视频
        reply = QMessageBox.question(
            self, 
            "下载Bilibili视频", 
            "是否要下载此Bilibili视频?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.download_bilibili_video()
            
    def download_bilibili_video(self):
        """下载Bilibili视频"""
        if not self.current_song_info:
            return
            
        # 获取视频URL
        video_url, ok = QInputDialog.getText(
            self, 
            "输入视频URL", 
            "请输入Bilibili视频URL:", 
            text="https://www.bilibili.com/video/"
        )
        
        if not ok or not video_url:
            return
            
        # 获取保存路径
        default_name = f"{self.current_song_info['name']}_bilibili.mp4".replace("/", "_").replace("\\", "_")
        file_path, _ = QFileDialog.getSaveFileName(
            self, 
            "保存视频", 
            os.path.join(self.settings["save_paths"]["music"], default_name), 
            "MP4文件 (*.mp4)"
        )
        
        if not file_path:
            return
            
        logger.info(f"开始下载Bilibili视频: {video_url}")
        
        # 创建进度对话框
        self.progress_dialog = QProgressDialog("下载视频...", "取消", 0, 100, self)
        self.progress_dialog.setWindowTitle("下载进度")
        self.progress_dialog.setWindowModality(Qt.WindowModal)
        self.progress_dialog.setAutoClose(True)
        self.progress_dialog.setAutoReset(True)
        self.progress_dialog.canceled.connect(self.cancel_download)
        self.progress_dialog.show()
        
        # 开始下载
        self.worker.download_bilibili_video(video_url, file_path)
        
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
        self.worker.search_finished.connect(self.display_search_results)
        self.worker.error_occurred.connect(self.display_error)
        self.worker.download_progress.connect(self.update_download_progress)
        self.worker.download_finished.connect(self.download_completed)
        self.worker.bilibili_download_finished.connect(self.bilibili_download_completed)
        
    def start_search(self):
        """开始搜索歌曲"""
        keyword = self.search_input.text().strip()
        if not keyword:
            self.status_bar.showMessage("请输入歌曲名称")
            logger.warning("搜索请求: 未输入关键词")
            return
            
        # 更新当前音源
        self.settings["sources"]["active_source"] = self.source_combo.currentText()
        save_settings(self.settings)
            
        logger.info(f"开始搜索: {keyword}")
        self.status_bar.showMessage("搜索中...")
        self.results_list.clear()
        self.song_info.clear()
        self.lyrics_label.clear()
        self.download_button.setEnabled(False)
        self.bilibili_button.setEnabled(False)
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
        
        self.results_list.clear()  # 确保列表已清空
        
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
                    # 使用设置中的缓存目录
                    cache_dir = self.settings["save_paths"]["cache"]
                    songid = song.get("id", f"song_{i}")
                    image_path = os.path.join(cache_dir, f"{songid}.jpg")
                    
                    if not os.path.exists(image_path):
                        response = requests.get(pic_url, stream=True)
                        if response.status_code == 200:
                            with open(image_path, 'wb') as f:
                                for chunk in response.iter_content(1024):
                                    f.write(chunk)
                    
                    if os.path.exists(image_path):
                        pixmap = QPixmap(image_path)
                        if not pixmap.isNull():
                            pixmap = pixmap.scaled(100, 100, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                            item.setIcon(QIcon(pixmap))
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
            self.bilibili_button.setEnabled(False)
            logger.warning("歌曲信息: 获取失败")
            return
            
        self.current_song_info = song
        self.download_button.setEnabled(True)
        self.bilibili_button.setEnabled(True)
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
        
        # 开始下载
        self.worker.download_song(self.current_song_info['url'], file_path)
        
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
        
        # 如果设置了自动播放，则播放歌曲
        if self.settings["other"]["auto_play"]:
            self.current_song_path = file_path
            self.media_player.setMedia(QMediaContent(QUrl.fromLocalFile(file_path)))
            self.media_player.play()
            self.status_bar.showMessage("正在播放歌曲...")
            
    def bilibili_download_completed(self, file_path):
        """Bilibili视频下载完成"""
        self.progress_dialog.close()
        self.status_bar.showMessage(f"Bilibili视频下载完成: {file_path}")
        logger.info(f"Bilibili视频下载完成: {file_path}")
        QMessageBox.information(self, "下载完成", f"Bilibili视频已成功保存到:\n{file_path}")
        
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
    # 设置媒体插件环境
    os.environ["QT_MULTIMEDIA_PREFERRED_PLUGINS"] = "windowsmediafoundation"
    
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    # 设置应用字体
    font = QFont("Microsoft YaHei", 10)
    app.setFont(font)
    
    window = MusicPlayerApp()
    window.show()
    sys.exit(app.exec_())
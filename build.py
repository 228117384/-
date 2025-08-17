import os
import sys
import shutil
from pathlib import Path
import PyInstaller.__main__

# 解决QtWebEngine沙盒问题
os.environ['QTWEBENGINE_DISABLE_SANDBOX'] = '1'

# 定义项目文件结构
project_files = {
    "main.py": "E:\\python\\测试\\main.py",  # 主程序路径
    "simhei.ttf": "E:\\python\\测试\\simhei.ttf",  # 字体文件
    "music.ico": "E:\\python\\测试\\music.ico",  # 应用图标
    "data_dir": "E:\\python\\测试\\data",  # 数据目录
    "ffmpeg.exe": "E:\\python\\测试\\ffmpeg.exe",  # FFmpeg可执行文件
    "static_dir": "E:\\python\\测试\\static"  # 静态文件目录（包含remote.html）
}

# 隐藏导入列表（根据文档1添加必要依赖）
hidden_imports = [
    'PyQt5',
    'PyQt5.QtCore',
    'PyQt5.QtGui',
    'PyQt5.QtWidgets',
    'PyQt5.QtMultimedia',
    'PyQt5.QtNetwork',
    'PyQt5.QtWebEngineWidgets',
    'PyQt5.QtWebSockets',
    'aiohttp',
    'aiohttp.client',
    'aiohttp.client_exceptions',
    'aiofiles',
    'httpx',
    'requests',
    'bs4',
    'bilibili_api',
    'bilibili_api.video',
    'bilibili_api.user',
    'bilibili_api.utils',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'PIL.ImageFont',
    'charset_normalizer',
    'cchardet',
    'idna',
    'async_timeout',
    'yarl',
    'multidict',
    'certifi',
    'setuptools',
    'packaging',
    'packaging.version',
    'packaging.specifiers',
    'packaging.requirements',
    'numpy',
    'pycryptodome',
    'websockets',
    'pydub',
    'mutagen',
    'librosa',
    'librosa.feature',
    'librosa.beat',
    'sklearn',
    'sklearn.metrics',
    'sklearn.metrics.pairwise',
    'sqlalchemy',
    'qrcode',
    'waitress',
    'chardet',
    'qrcode.image.pil',
    'flask',
    'flask_cors',
    'flask_socketio',
    'eventlet',
    'engineio',
    'socketio',
    'sqlite3',
    're',
    'datetime',
    'hashlib',
    'io',
    'json',
    'logging',
    'os',
    'random',
    'socket',
    'ssl',
    'subprocess',
    'sys',
    'time',
    'traceback',
    'urllib.parse',
    'webbrowser',
    'pathlib',
    'threading',
    'uuid',
    'asyncio',
    'BeautifulSoup',
    'QWebSocket'
]

# 构建PyInstaller命令
pyinstaller_args = [
    '--onefile',                   # 打包为单个可执行文件
    '--windowed',                  # 窗口应用（不显示控制台）
    '--name=MusicPlayer',          # 生成的可执行文件名称
    '--noconfirm',                 # 覆盖输出目录而不提示
    '--clean',                     # 清理临时文件
    '--collect-all=bilibili_api',  # 收集bilibili_api所有资源
    '--add-data', f'{project_files["simhei.ttf"]};fonts',  # 包含字体文件
    '--add-data', f'{project_files["music.ico"]};.',     # 包含图标文件
    '--add-data', f'{project_files["data_dir"]};data',  # 数据目录
    # +++ 新增: 包含静态文件目录 +++
    '--add-data', f'{project_files["static_dir"]};static',  # 包含static目录（远程控制页面）
    '--add-binary', f'{project_files["ffmpeg.exe"]};.',  # FFmpeg可执行文件
    '--icon', project_files["music.ico"],  # 应用图标
    project_files["main.py"]       # 主程序入口
]

# 添加隐藏导入
for imp in hidden_imports:
    pyinstaller_args.append(f'--hidden-import={imp}')

# 添加Qt插件路径（确保媒体播放功能正常）
pyqt5_dir = Path(sys.executable).parent / 'Lib' / 'site-packages' / 'PyQt5' / 'Qt5' / 'plugins'
if pyqt5_dir.exists():
    pyinstaller_args.extend([
        '--add-data', f'{str(pyqt5_dir / "mediaservice")}{os.pathsep}mediaservice',
        '--add-data', f'{str(pyqt5_dir / "platforms")}{os.pathsep}platforms',
        '--add-data', f'{str(pyqt5_dir / "styles")}{os.pathsep}styles'
    ])

# 运行PyInstaller
print("开始构建可执行文件...")
PyInstaller.__main__.run(pyinstaller_args)

# 后处理：复制必要文件到输出目录
output_dir = Path('dist')
for file in ['settings.json', 'playlists.json']:
    if Path(file).exists():
        shutil.copy(file, output_dir / file)
        print(f"已复制{file}到输出目录")

# +++ 新增: 确保static目录被正确复制 +++
static_source = Path(project_files["static_dir"])
static_dest = output_dir / "static"
if static_source.exists():
    if static_dest.exists():
        shutil.rmtree(static_dest)
    shutil.copytree(static_source, static_dest)
    print(f"已复制static目录到输出目录: {static_dest}")

print("构建完成！可执行文件位于 dist 目录")
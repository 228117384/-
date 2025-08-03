import sys
from PyInstaller.__main__ import run

if __name__ == '__main__':
    opts = [
        '--name=MusicPlayer音乐',
        '--onefile',
        '--windowed',
        '--add-data=simhei.ttf;.',
        '--icon=music.ico',  # 可选，添加图标
        'main.py'
    ]
    run(opts)
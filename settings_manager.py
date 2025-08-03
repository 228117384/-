import os
import json

def get_settings_path():
    """获取设置文件路径"""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, "settings.json")

def load_default_settings():
    """加载默认设置"""
    return {
        "save_paths": {
            "music": "songs",
            "cache": "pics"
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
                    "url": "https://api.itxq.top/",
                    "params": {"input": "{query}", "filter": "name", "type": "netease", "page": 1},
                    "method": "POST",
                    "api_key": "",
                    "headers": {}
                }
            ]
        },
        "other": {
            "max_results": 20,
            "auto_play": True
        },
        "background_image": ""  # 添加背景图片路径
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
            return json.load(f)
    except Exception as e:
        print(f"加载设置失败: {str(e)}，使用默认设置")
        return load_default_settings()

def save_settings(settings):
    """保存设置"""
    settings_path = get_settings_path()
    try:
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        print(f"保存设置失败: {str(e)}")
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
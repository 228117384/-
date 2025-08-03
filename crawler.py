import requests
import json
import sys
import os
import urllib.parse
import logging

# 导入设置管理器
from settings_manager import get_active_source_config

# 设置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def ensure_settings_file_exists():
    """确保设置文件存在"""
    settings_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "settings.json")
    if not os.path.exists(settings_path):
        logger.warning("settings.json 文件不存在，创建默认设置")
        from settings_manager import save_settings, load_default_settings
        default_settings = load_default_settings()
        save_settings(default_settings)

def search_song(song_name, max_results=20):
    """搜索歌曲并返回结果数据"""
    # 确保设置文件存在
    ensure_settings_file_exists()
    
    # 获取当前激活的音源配置
    config = get_active_source_config()
    
    # 准备请求参数
    headers = config.get("headers", {})
    params = config.get("params", {}).copy()
    
    # 替换查询参数中的占位符
    for key, value in params.items():
        if isinstance(value, str) and "{query}" in value:
            params[key] = value.replace("{query}", song_name)
    
    # 添加API密钥
    api_key = config.get("api_key", "")
    if api_key:
        if "Authorization" in headers:
            headers["Authorization"] = f"Bearer {api_key}"
        else:
            # 如果API需要密钥但没有指定头部，添加到参数中
            params["api_key"] = api_key
    
    try:
        method = config.get("method", "GET").upper()
        url = config["url"]
        
        logger.info(f"使用音源: {config.get('name', '未知音源')}")
        logger.info(f"请求URL: {url}")
        logger.info(f"请求方法: {method}")
        logger.info(f"请求参数: {params}")
        logger.info(f"请求头: {headers}")
        
        if method == "GET":
            # 对于GET请求，将参数编码到URL中
            url = url + "?" + urllib.parse.urlencode(params)
            response = requests.get(url, headers=headers, timeout=30)
        else:
            # 对于POST请求，发送表单数据
            response = requests.post(url, data=params, headers=headers, timeout=30)
        
        response.raise_for_status()
        
        if response.status_code == 200:
            try:
                json_data = response.json()
                
                # 确保数据是字典类型
                if not isinstance(json_data, dict):
                    # 如果返回的是列表，转换为字典格式
                    if isinstance(json_data, list):
                        json_data = {"data": json_data}
                    else:
                        # 处理其他类型的数据
                        json_data = {"data": []}
                
                # 确保有"data"键
                if "data" not in json_data:
                    json_data["data"] = []
                
                # 确保data是列表
                if not isinstance(json_data["data"], list):
                    json_data["data"] = []
                
                # 限制返回结果数量
                if len(json_data["data"]) > max_results:
                    json_data["data"] = json_data["data"][:max_results]
                
                # 保存搜索结果（用于调试）
                current_dir = os.path.dirname(os.path.abspath(__file__))
                file_path = os.path.join(current_dir, 'songs_data.json')
                try:
                    with open(file_path, 'w', encoding='utf-8') as json_file:
                        json.dump(json_data, json_file, ensure_ascii=False, indent=4)
                    logger.info(f"搜索结果保存到: {file_path}")
                except Exception as e:
                    logger.error(f"保存歌曲数据失败: {str(e)}")
                
                return json_data
            except ValueError as ve:
                logger.error(f"返回的内容不是有效的 JSON 格式: {str(ve)}")
                logger.error(f"响应内容: {response.text[:200]}...")
                return {"data": []}
            except Exception as e:
                logger.error(f"解析JSON时发生错误: {str(e)}")
                return {"data": []}
        else:
            logger.error(f"请求失败，状态码: {response.status_code}")
            logger.error(f"响应内容: {response.text[:200]}...")
            return {"data": []}
    except requests.exceptions.RequestException as e:
        logger.error(f"网络请求失败: {str(e)}")
        return {"data": []}
    except Exception as e:
        logger.error(f"发生未知错误: {str(e)}")
        return {"data": []}

if __name__ == "__main__":
    if len(sys.argv) > 1:
        song_name = sys.argv[1]
    else:
        print("请输入歌曲名称作为参数！")
        sys.exit(1)
    
    # 默认搜索
    result = search_song(song_name)
    # 确保有"data"键
    songs = result.get("data", [])
    for song in songs:
        print(f"歌曲名称: {song.get('title', '未知')}")
        print(f"作者: {song.get('author', '未知')}")
        print(f"歌曲链接: {song.get('link', '未知')}")
        print(f"歌词: {song.get('lrc', '未知')}")
        print(f"下载链接: {song.get('url', '未知')}")
        print(f"封面图: {song.get('pic', '未知')}")
        print("-" * 50)
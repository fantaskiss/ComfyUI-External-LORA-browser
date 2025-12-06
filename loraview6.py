# lora_viewer.py - 最终完美版 v6：优化信息显示 + 添加文件大小

import os
import http.server
import socketserver
from urllib.parse import unquote, quote, parse_qs, urlparse
from datetime import datetime
import subprocess
import threading

# ========================
# 配置区
# ========================

FOLDER = r"N:\models\loras"  # 修改为你的实际路径
PORT = 23456

INCLUDE_ROOT = True
ROOT_NAME = "全部"

# 支持的媒体格式
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif'}
VIDEO_EXTS = {'.mp4', '.mkv'}  # 可扩展 '.avi', '.mov' 等
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS

# 缩略图配置
THUMBNAIL_DIR = ".thumbnails"  # 缩略图存放的子文件夹名
THUMBNAIL_WIDTH = 120  # 缩略图宽度
THUMBNAIL_HEIGHT = 120  # 缩略图高度

# 文本内容折叠配置
MAX_VISIBLE_LINES = 3  # 折叠状态下显示的最大行数
LINE_HEIGHT = 20  # 每行文本的近似高度(px)

# ========================
# 视频缩略图生成
# ========================

def generate_video_thumbnail(video_path, thumbnail_path):
    """使用ffmpeg生成视频缩略图"""
    try:
        # 使用ffmpeg从视频的第1秒提取一帧作为缩略图
        cmd = [
            'ffmpeg', '-i', video_path,
            '-ss', '00:00:01',  # 从第1秒开始
            '-vframes', '1',    # 只取1帧
            '-vf', f'scale={THUMBNAIL_WIDTH}:{THUMBNAIL_HEIGHT}:force_original_aspect_ratio=decrease',  # 缩放
            '-y',               # 覆盖已存在的文件
            thumbnail_path
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0 and os.path.exists(thumbnail_path):
            return True
        else:
            print(f"生成缩略图失败: {video_path}")
            return False
    except Exception as e:
        print(f"生成缩略图异常: {video_path}, 错误: {e}")
        return False

def get_video_thumbnail(video_path):
    """获取视频缩略图路径，如果不存在则生成"""
    video_dir = os.path.dirname(video_path)
    video_name = os.path.splitext(os.path.basename(video_path))[0]
    
    # 缩略图存放目录
    thumbnail_dir = os.path.join(video_dir, THUMBNAIL_DIR)
    thumbnail_path = os.path.join(thumbnail_dir, f"{video_name}.jpg")
    
    # 如果缩略图已存在，直接返回
    if os.path.exists(thumbnail_path):
        return thumbnail_path
    
    # 创建缩略图目录
    os.makedirs(thumbnail_dir, exist_ok=True)
    
    # 异步生成缩略图
    def generate_async():
        if generate_video_thumbnail(video_path, thumbnail_path):
            print(f"已生成缩略图: {thumbnail_path}")
        else:
            print(f"生成缩略图失败: {video_path}")
    
    # 在新线程中生成缩略图，避免阻塞主程序
    threading.Thread(target=generate_async, daemon=True).start()
    
    return None  # 缩略图正在生成中

# ========================
# 扫描所有子文件夹
# ========================

def scan_folders():
    folder_map = {}
    if INCLUDE_ROOT:
        folder_map[ROOT_NAME] = FOLDER
    try:
        for item in os.listdir(FOLDER):
            path = os.path.join(FOLDER, item)
            if os.path.isdir(path):
                folder_map[item] = path
    except Exception as e:
        print(f"扫描目录失败: {e}")
    return folder_map

def get_file_size_mb(file_path):
    """获取文件大小，返回MB为单位的字符串"""
    try:
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        return f"{size_mb:.1f}MB"
    except:
        return "未知大小"

def truncate_extension(ext):
    """截断扩展名，保留前2位，不足2位保持原样"""
    if len(ext) <= 3:  # 包括点号，如 '.pt' 长度为3
        return ext
    return ext[:3]  # 保留前3位（包括点号），如 '.safetensors' -> '.saf'

def group_files_in(path):
    """在指定路径中分组模型、文本、图片或视频，并记录创建时间和文件大小"""
    if not os.path.exists(path):
        return {}

    base_names = {}
    model_exts = {'.safetensors', '.ckpt', '.pt', '.bin', '.pth'}

    files = {}
    try:
        for f in os.listdir(path):
            fp = os.path.join(path, f)
            if os.path.isfile(fp):
                files[f.lower()] = f  # 原始文件名
    except Exception as e:
        print(f"读取失败 {path}: {e}")
        return {}

    for filename in files.values():
        name, ext = os.path.splitext(filename.lower())
        orig_name = filename
        full_path = os.path.join(path, orig_name)

        if ext in model_exts:
            base_names.setdefault(name, {})['model'] = orig_name
            base_names[name]['folder_path'] = path
            base_names[name]['model_ext'] = truncate_extension(ext)  # 保存截断后的扩展名
            # 获取创建时间和文件大小
            try:
                ctime = os.path.getctime(full_path)
                base_names[name]['created_timestamp'] = ctime  # 保存时间戳用于排序
                base_names[name]['created_time'] = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
                base_names[name]['file_size'] = get_file_size_mb(full_path)
            except:
                base_names[name]['created_timestamp'] = 0
                base_names[name]['created_time'] = "未知"
                base_names[name]['file_size'] = "未知"
        elif ext == '.txt':
            base_names.setdefault(name, {})['text'] = orig_name
            # 预读取文本内容并计算行数
            try:
                with open(full_path, 'r', encoding='utf-8') as tf:
                    content = tf.read().strip()
                lines = content.split('\n')
                base_names[name]['text_content'] = content
                base_names[name]['text_line_count'] = len(lines)
                # 默认展开：
                # base_names[name]['needs_collapse'] = len(lines) > MAX_VISIBLE_LINES
                base_names[name]['needs_collapse'] = True
            except Exception as e:
                base_names[name]['text_content'] = f"[读取失败] {str(e)}"
                base_names[name]['text_line_count'] = 1
                base_names[name]['needs_collapse'] = False
        elif ext in IMAGE_EXTS:
            base_names.setdefault(name, {})['image'] = orig_name
        elif ext in VIDEO_EXTS:
            base_names.setdefault(name, {})['video'] = orig_name
            # 为视频文件生成缩略图
            thumbnail_path = get_video_thumbnail(full_path)
            if thumbnail_path:
                base_names[name]['thumbnail'] = os.path.join(THUMBNAIL_DIR, f"{os.path.splitext(orig_name)[0]}.jpg")

    return base_names

# ========================
# 生成 HTML 页面
# ========================

def generate_html(current_folder_name=""):
    folder_map = scan_folders()
    if not folder_map:
        return "<h1>未找到任何子文件夹或根目录不可访问</h1>".encode('utf-8')

    current_path = folder_map.get(current_folder_name, FOLDER)
    is_root = (current_path == FOLDER and current_folder_name == ROOT_NAME) if INCLUDE_ROOT else False
    base_names = group_files_in(current_path)
    total = len(base_names)
    current_encoded = quote(current_folder_name)

    # 按创建时间排序（从新到旧）
    sorted_items = sorted(
        base_names.items(),
        key=lambda x: x[1].get('created_timestamp', 0),
        reverse=True  # 最新的在前面
    )

    # 导航链接
    nav_items = []
    for name in sorted(folder_map.keys()):
        active = 'style="font-weight:bold;color:#007acc;"' if name == current_folder_name or (is_root and name == ROOT_NAME) else ''
        encoded_name = quote(name)
        nav_items.append(f'<a href="/?dir={encoded_name}" {active}>{name}</a>')
    nav_html = " | ".join(nav_items)

    # 开始构建 HTML
    html = f"""
    <html>
    <head>
        <title>Lora Models Viewer</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <style>
            body {{ font-family: "Segoe UI", Arial, sans-serif; margin: 20px; background: #f9f9fb; }}
            h1 {{ color: #444; border-bottom: 2px solid #007acc; padding-bottom: 5px; }}
            .nav-container {{
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin: 20px 0;
                padding: 12px;
                background: #eef3f8;
                border-radius: 8px;
                flex-wrap: wrap;
                gap: 15px;
            }}
            .nav-links {{ font-size: 1.1em; }}
            .nav-links a {{ text-decoration: none; color: #555; margin: 0 10px; }}
            .nav-links a:hover {{ color: #007acc; }}
            .search-box {{
                display: flex;
                align-items: center;
            }}
            #searchInput {{
                padding: 6px 10px;
                width: 200px;
                border: 1px solid #ccc;
                border-radius: 4px;
                font-size: 0.9em;
            }}

            /* 两列网格布局 */
            .items-grid {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(500px, 1fr));
                gap: 20px;
                margin-top: 20px;
            }}
            @media (max-width: 600px) {{
                .items-grid {{
                    grid-template-columns: 1fr;
                }}
            }}

            .item {{
                border: 1px solid #ddd;
                padding: 16px;
                border-radius: 8px;
                background: white;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                display: flex;
                gap: 15px;
                height: fit-content;
            }}
            .thumb-pane {{
                width: 120px;
                height: 120px;
                flex-shrink: 0;
                border: 1px solid #eee;
                display: flex;
                align-items: center;
                justify-content: center;
                background: #f0f0f0;
                overflow: hidden;
                cursor: pointer;
                font-size: 0.8em;
                text-align: center;
                color: #555;
                position: relative;
            }}
            .thumb-pane img, .thumb-pane video {{
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }}
            .video-indicator {{
                position: absolute;
                top: 5px;
                right: 5px;
                background: rgba(0,0,0,0.7);
                color: white;
                padding: 2px 6px;
                border-radius: 3px;
                font-size: 0.7em;
            }}
            .missing {{
                color: #aaa;
                font-style: italic;
            }}
            .play-icon {{
                font-size: 36px;
                line-height: 1;
            }}
            .content-pane {{
                flex: 1;
                min-width: 0; /* 防止内容溢出 */
            }}
            .header-row {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-top: 0;
                margin-bottom: 8px;
                flex-wrap: wrap;
                gap: 8px;
            }}
            .header-row h2 {{
                margin: 0;
                color: #007acc;
                font-size: 1.2em;
                word-break: break-word;
            }}
            .model-info {{
                font-size: 0.9em;
                color: #666;
                font-weight: normal;
            }}
            .model-info .file-ext {{
                color: #007acc;
                font-weight: bold;
            }}
            .model-info .file-size {{
                color: #28a745;
                font-weight: bold;
                margin-right: 8px;
            }}
            .model-info .created-time {{
                color: #6c757d;
            }}
            .text-content {{
                white-space: pre-wrap;
                background: #f5f5f5;
                padding: 10px;
                margin: 8px 0;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: monospace;
                font-size: 16px;
                color: #333;
                position: relative;
                overflow: hidden;
                transition: max-height 0.3s ease;
            }}
            .text-content.collapsed {{
                max-height: {MAX_VISIBLE_LINES * LINE_HEIGHT}px;
            }}
            .text-content.expanded {{
                max-height: none;
            }}
            .text-fade {{
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 40px;
                background: linear-gradient(transparent, #f5f5f5);
                pointer-events: none;
                display: none;
            }}
            .text-content.collapsed .text-fade {{
                display: block;
            }}
            .toggle-text-btn {{
                background: #007acc;
                color: white;
                border: none;
                padding: 4px 10px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 0.8em;
                margin-top: 5px;
            }}
            .toggle-text-btn:hover {{
                background: #005a9e;
            }}
            footer {{ margin-top: 40px; color: #aaa; font-size: 0.9em; }}
            [data-model-name] {{ transition: opacity 0.2s; }}
            [data-model-name].hidden {{ opacity: 0.2; display: none !important; }}

            /* 模态框增强：支持图片和视频 */
            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.9);
                justify-content: center;
                align-items: center;
                flex-direction: column;
                padding: 20px;
            }}
            .modal-content {{
                max-width: 90vw;
                max-height: 85vh;
            }}
            .modal img, .modal video {{
                max-width: 100%;
                max-height: 80vh;
                object-fit: contain;
                border: 3px solid white;
                box-shadow: 0 0 20px rgba(0,0,0,0.5);
            }}
            .modal .close {{
                position: absolute;
                top: 20px;
                right: 30px;
                color: white;
                font-size: 40px;
                font-weight: bold;
                cursor: pointer;
                z-index: 1001;
            }}
            .modal .close:hover {{ color: #bbb; }}
        </style>
        <script>
            let currentModalSrc = null;

            function showModal(src, isVideo = false) {{
                const modal = document.getElementById("mediaModal");
                const container = document.getElementById("modalContent");
                
                // 清空之前内容
                container.innerHTML = '';

                if (isVideo) {{
                    const video = document.createElement('video');
                    video.src = src;
                    video.controls = true;
                    video.autoplay = true;
                    video.style.maxWidth = '100%';
                    video.style.maxHeight = '80vh';
                    container.appendChild(video);
                }} else {{
                    const img = document.createElement('img');
                    img.src = src;
                    container.appendChild(img);
                }}

                modal.style.display = "flex";
                currentModalSrc = src;
            }}

            function hideModal() {{
                document.getElementById("mediaModal").style.display = "none";
                const video = document.querySelector('#modalContent video');
                if (video) video.pause();
                currentModalSrc = null;
            }}

            window.addEventListener("keydown", (e) => {{
                if (e.key === "Escape" && currentModalSrc) {{
                    hideModal();
                }}
            }});

            window.onclick = function(event) {{
                const modal = document.getElementById("mediaModal");
                if (event.target === modal) {{
                    hideModal();
                }}
            }};

            function filterModels() {{
                const query = document.getElementById('searchInput').value.toLowerCase().trim();
                const items = document.querySelectorAll('[data-model-name]');
                items.forEach(el => {{
                    const name = el.getAttribute('data-model-name');
                    if (!query || name.includes(query)) {{
                        el.classList.remove('hidden');
                    }} else {{
                        el.classList.add('hidden');
                    }}
                }});
            }}

            function toggleText(btn, textId) {{
                const textElement = document.getElementById(textId);
                if (textElement.classList.contains('collapsed')) {{
                    textElement.classList.remove('collapsed');
                    textElement.classList.add('expanded');
                    btn.textContent = '收起说明';
                }} else {{
                    textElement.classList.remove('expanded');
                    textElement.classList.add('collapsed');
                    btn.textContent = '展开完整说明';
                }}
            }}

            window.onload = () => {{
                document.getElementById('searchInput').focus();
                document.getElementById('searchInput').addEventListener('input', filterModels);
            }};
        </script>
    </head>
    <body>
        <h1>📁 Lora Models Browser</h1>

        <!-- 导航 + 搜索 -->
        <div class="nav-container">
            <div class="nav-links">{nav_html}</div>
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 搜索模型..." autocomplete="off">
            </div>
        </div>

        <p><strong>当前目录:</strong> {current_path} &nbsp;|&nbsp; 共 <strong>{total}</strong> 个模型</p>
    """

    if not base_names:
        html += "<p class='empty'>此目录中没有找到任何 Lora 模型。</p>"
    else:
        html += '<div class="items-grid">'
        for name, files in sorted_items:
            model_file = files.get('model', '未知模型')
            model_ext = files.get('model_ext', '')
            file_size = files.get('file_size', '未知')
            image_file = files.get('image')
            video_file = files.get('video')
            thumbnail_file = files.get('thumbnail')
            text_file = files.get('text')
            text_content = files.get('text_content', '')
            needs_collapse = files.get('needs_collapse', False)
            created_time = files.get('created_time', '未知')

            # ========== 决定缩略图和点击行为 ==========
            has_image = bool(image_file)
            has_video = bool(video_file)
            has_thumbnail = bool(thumbnail_file)

            params = f"?dir={current_encoded}" if current_encoded else ""

            if has_image:
                file_url = f"/file/{quote(image_file)}{params}"
                thumb_html = f'<img src="{file_url}" alt="预览图">'
                click_handler = f"showModal('{file_url}', false)"
            elif has_thumbnail:
                # 使用视频缩略图
                file_url = f"/file/{quote(thumbnail_file)}{params}"
                thumb_html = f'<img src="{file_url}" alt="视频缩略图"><div class="video-indicator">🎥</div>'
                video_url = f"/file/{quote(video_file)}{params}"
                click_handler = f"showModal('{video_url}', true)"
            elif has_video:
                # 视频文件但还没有缩略图
                video_url = f"/file/{quote(video_file)}{params}"
                thumb_html = '<div><span class="play-icon">▶</span><br>生成缩略图中...</div>'
                click_handler = f"showModal('{video_url}', true)"
            else:
                thumb_html = '<span class="missing">📷 无预览</span>'
                click_handler = "alert('该模型没有关联的图片或视频文件。')"

            # ========== 输出模型项 ==========
            html += f"<div class='item' data-model-name='{name}'>"
            html += f"<div class='thumb-pane' onclick=\"{click_handler}\">{thumb_html}</div>"
            html += "<div class='content-pane'>"

            html += f"<div class='header-row'>"
            html += f"<h2>{name}</h2>"
            html += f"<span class='model-info'><span class='file-size'>{file_size}</span><span class='file-ext'>{model_ext.upper()}</span> | <span class='created-time'>创建: {created_time}</span></span>"
            html += "</div>"

            # 移除了重复的文件名显示行

            if text_file:
                text_id = f"text-{name.replace(' ', '-').lower()}"
                # 默认展开
                # collapse_class = "collapsed" if needs_collapse else "expanded"
                # btn_text = "展开完整说明" if needs_collapse else "收起说明"
                collapse_class = "collapsed"  # 总是折叠
                btn_text = "展开完整说明"  # 总是显示展开按钮
                
                html += f"<div id='{text_id}' class='text-content {collapse_class}'>"
                html += f"{text_content}"
                if needs_collapse:
                    html += '<div class="text-fade"></div>'
                html += "</div>"
                
                if needs_collapse:
                    html += f"<button class='toggle-text-btn' onclick=\"toggleText(this, '{text_id}')\">{btn_text}</button>"
            else:
                html += "<p><em>📝 无描述文件 (.txt)</em></p>"

            html += "</div></div>"

        html += "</div>"  # 关闭 items-grid

    # ========== 模态框：支持图片和视频 ==========
    html += """
        <div id="mediaModal" class="modal">
            <span class="close" onclick="hideModal()">&times;</span>
            <div id="modalContent" class="modal-content"></div>
        </div>

        <footer>
            Powered by Python | 支持图片与视频预览 + 视频缩略图 + 文本内容折叠 + 文件大小显示 | 使用搜索框快速定位
        </footer>
    </body>
    </html>
    """

    return html.encode('utf-8', errors='replace')

# ========================
# 自定义请求处理器（含美化日志）
# ========================

class CustomHandler(http.server.SimpleHTTPRequestHandler):
    def log_request(self, code='-', size='-'):
        """重写日志方法：将 URL 解码后输出，避免 %E5%95%86 这类编码出现在 cmd 中"""
        if hasattr(self, 'command') and hasattr(self, 'path'):
            try:
                decoded_path = unquote(self.path)
                client = self.client_address[0]
                print(f"{client} - \"{self.command} {decoded_path}\" → status={code}")
            except Exception:
                super().log_request(code, size)
        else:
            super().log_request(code, size)

    def do_GET(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query)
        path = unquote(parsed.path.strip("/"))
        dir_name = query.get("dir", [""])[0]
        folder_map = scan_folders()

        current_folder_path = folder_map.get(dir_name, FOLDER)

        if path == "":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(generate_html(dir_name))

        elif path.startswith("file/"):
            filename = path.split("/", 1)[1]
            filepath = os.path.join(current_folder_path, filename)

            # 安全检查
            if os.path.commonpath([FOLDER]) != os.path.commonpath([FOLDER, filepath]):
                self.send_error(403, "Forbidden")
                return

            if os.path.isfile(filepath):
                self.send_response(200)

                ext = os.path.splitext(filepath)[1].lower()
                if ext in IMAGE_EXTS:
                    mime = {
                        '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                        '.png': 'image/png', '.webp': 'image/webp',
                        '.bmp': 'image/bmp', '.tiff': 'image/tiff',
                        '.gif': 'image/gif'
                    }.get(ext, 'image')
                    self.send_header("Content-type", mime)
                elif ext == '.mp4':
                    self.send_header("Content-type", "video/mp4")
                elif ext == '.mkv':
                    self.send_header("Content-type", "video/x-matroska")
                else:
                    self.send_header("Content-type", "application/octet-stream")

                self.end_headers()
                with open(filepath, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_error(404, "File not found.")

        elif path == "favicon.ico":
            self.send_response(204)
            self.end_headers()

        else:
            self.send_error(404, "Not found.")

# ========================
# 启动服务器
# ========================

def run_server():
    if not os.path.isdir(FOLDER):
        print(f"错误：目录不存在！\n路径: {FOLDER}")
        return

    os.chdir(FOLDER)
    try:
        with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
            print(f"\nLora 浏览器已启动（v6：优化信息显示 + 文件大小）")
            print(f"   访问地址: http://localhost:{PORT}")
            print(f"   功能: 图片/视频预览 + 视频缩略图 + 搜索 + 文件大小 + 创建日期 + 文本折叠")
            print(f"   布局: 响应式两列 + 按创建时间排序")
            print(f"   提示: 按 Ctrl+C 停止服务")
            print(f"   注意: 首次访问视频文件时会自动生成缩略图，请确保系统已安装 ffmpeg\n")
            httpd.serve_forever()
    except Exception as e:
        print(f"启动失败: {e}")

if __name__ == "__main__":
    run_server()
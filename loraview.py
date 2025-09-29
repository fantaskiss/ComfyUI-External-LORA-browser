# lora_viewer.py - 最终完美版 v3：支持中文日志美化 + 所有增强功能

import os
import http.server
import socketserver
from urllib.parse import unquote, quote, parse_qs, urlparse
from datetime import datetime

# ========================
# 配置区
# ========================

FOLDER = r"C:\ComfyUI\models\loras"  # 修改为你的实际路径
PORT = 12321

INCLUDE_ROOT = True
ROOT_NAME = "全部"

# 支持的图片格式
IMAGE_EXTS = {'.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff', '.gif'}

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
        print(f"⚠️ 扫描目录失败: {e}")
    return folder_map

def group_files_in(path):
    """在指定路径中分组模型、文本、任意同名图片，并记录模型文件的创建时间"""
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
        print(f"⚠️ 读取失败 {path}: {e}")
        return {}

    for filename in files.values():
        name, ext = os.path.splitext(filename.lower())
        orig_name = filename
        full_path = os.path.join(path, orig_name)

        if ext in model_exts:
            base_names.setdefault(name, {})['model'] = orig_name
            base_names[name]['folder_path'] = path
            # 获取创建时间
            try:
                ctime = os.path.getctime(full_path)
                base_names[name]['created_time'] = datetime.fromtimestamp(ctime).strftime("%Y-%m-%d %H:%M")
            except:
                base_names[name]['created_time'] = "未知"
        elif ext == '.txt':
            base_names.setdefault(name, {})['text'] = orig_name
        elif ext in IMAGE_EXTS:
            base_names.setdefault(name, {})['image'] = orig_name

    return base_names

# ========================
# 生成 HTML 页面
# ========================

def generate_html(current_folder_name=""):
    folder_map = scan_folders()
    if not folder_map:
        return "<h1>❌ 未找到任何子文件夹或根目录不可访问</h1>".encode('utf-8')

    current_path = folder_map.get(current_folder_name, FOLDER)
    is_root = (current_path == FOLDER and current_folder_name == ROOT_NAME) if INCLUDE_ROOT else False
    base_names = group_files_in(current_path)
    total = len(base_names)
    current_encoded = quote(current_folder_name)

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
            .item {{
                border: 1px solid #ddd;
                padding: 16px;
                margin-bottom: 20px;
                border-radius: 8px;
                background: white;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                display: flex;
                gap: 15px;
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
            }}
            .thumb-pane img {{
                max-width: 100%;
                max-height: 100%;
                object-fit: contain;
            }}
            .missing {{
                color: #aaa;
                font-style: italic;
                font-size: 0.9em;
                text-align: center;
            }}
            .content-pane {{
                flex: 1;
            }}
            .header-row {{
                display: flex;
                justify-content: space-between;
                align-items: baseline;
                margin-top: 0;
                margin-bottom: 8px;
            }}
            .header-row h2 {{
                margin: 0;
                color: #007acc;
                font-size: 1.2em;
            }}
            .model-date {{
                font-size: 0.9em;
                color: #666;
                font-weight: normal;
                margin-left: 10px;
            }}
            .text-content {{
                white-space: pre-wrap;
                background: #f5f5f5;
                padding: 10px;
                margin: 8px 0;
                border: 1px solid #e0e0e0;
                border-radius: 4px;
                font-family: monospace;
                font-size: 16px;      /* ← 已增大 2px */
                color: #333;
            }}
            footer {{ margin-top: 40px; color: #aaa; font-size: 0.9em; }}
            [data-model-name] {{ transition: opacity 0.2s; }}
            [data-model-name].hidden {{ opacity: 0.2; display: none !important; }}

            /* 大图模态框 */
            .modal {{
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.8);
                justify-content: center;
                align-items: center;
            }}
            .modal img {{
                max-width: 90vw;
                max-height: 90vh;
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
            }}
            .modal .close:hover {{ color: #bbb; }}
        </style>
        <script>
            let currentModalImage = null;

            function showModal(src) {{
                const modal = document.getElementById("imageModal");
                const modalImg = document.getElementById("modalImage");
                modal.style.display = "flex";
                modalImg.src = src;
                currentModalImage = src;
            }}

            function hideModal() {{
                document.getElementById("imageModal").style.display = "none";
                currentModalImage = null;
            }}

            window.addEventListener("keydown", (e) => {{
                if (e.key === "Escape" && currentModalImage) {{
                    hideModal();
                }}
            }});

            window.onclick = function(event) {{
                const modal = document.getElementById("imageModal");
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
        for name, files in sorted(base_names.items()):
            model_file = files.get('model', '未知模型')
            image_file = files.get('image')
            text_file = files.get('text')
            created_time = files.get('created_time', '未知')

            # 构建图片 URL 和点击事件
            if image_file:
                params = f"?dir={current_encoded}" if current_encoded else ""
                full_image_url = f"/file/{quote(image_file)}{params}"
                thumb_html = f'<img src="{full_image_url}" alt="预览图">'
                click_handler = f"showModal('{full_image_url}')"
            else:
                thumb_html = '<span>📷 图片缺失</span>'
                click_handler = "alert('该模型没有关联的图片文件。')"

            # 输出模型项
            html += f"<div class='item' data-model-name='{name}'>"
            html += f"<div class='thumb-pane' onclick=\"{click_handler}\">{thumb_html}</div>"
            html += "<div class='content-pane'>"

            # 名称 + 创建日期（在同一行）
            html += f"<div class='header-row'>"
            html += f"<h2>{name}</h2>"
            html += f"<span class='model-date'>创建: {created_time}</span>"
            html += "</div>"

            html += f"<p><strong>📄 模型:</strong> {model_file}</p>"

            if text_file:
                try:
                    txt_path = os.path.join(files['folder_path'], text_file)
                    with open(txt_path, 'r', encoding='utf-8') as tf:
                        content = tf.read().strip()
                    if content:
                        html += f"<div class='text-content'>{content}</div>"
                    else:
                        html += "<p><em>（文本为空）</em></p>"
                except Exception as e:
                    html += f"<div class='text-content'>[读取失败] {str(e)}</div>"
            else:
                html += "<p><em>📝 无描述文件 (.txt)</em></p>"

            html += "</div></div>"  # 结束 content-pane 和 item

    # 添加大图模态框
    html += """
        <!-- 大图查看模态框 -->
        <div id="imageModal" class="modal">
            <span class="close" onclick="hideModal()">&times;</span>
            <img id="modalImage">
        </div>

        <footer>
            Powered by Python | 点击缩略图查看大图 | 使用搜索框快速定位
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
                # 出错则使用父类默认方式
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
        print(f"❌ 错误：目录不存在！\n路径: {FOLDER}")
        return

    os.chdir(FOLDER)
    try:
        with socketserver.TCPServer(("", PORT), CustomHandler) as httpd:
            print(f"\n✅ Lora 浏览器已启动（最终完美版）")
            print(f"   访问地址: http://localhost:{PORT}")
            print(f"   功能: 子文件夹导航 + 搜索 + 缩略图放大 + 文字加大 + 创建日期 + 日志美化")
            print(f"   提示: 按 Ctrl+C 停止服务\n")
            httpd.serve_forever()
    except Exception as e:
        print(f"❌ 启动失败: {e}")

if __name__ == "__main__":
    run_server()
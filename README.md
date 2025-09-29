# ComfyUI-External-LORA-browser

一个与ComfyUI便携版共用Python环境的lora收集速查器。基于Pythonweb环境。

日常收集lora时，一般是从资源站下载后，在ComfyUI中使用其他插件进行管理。其过程比较繁琐。同时对于预览图的支持，ComfyUI以及其插件经常出问题。

这里提供一个不依赖ComfyUI的收集与使用方法：下载lora=》对lora页面的说明进行摘抄保存入文本文档=》保存lora预览图=》入库完成。

这个流程比较符合我自己的日常使用习惯。和我同样习惯的小伙伴可以下载使用。

<img width="732" height="651" alt="image" src="https://github.com/user-attachments/assets/943fd7fc-3273-42a0-ac54-c8a070eb455b" />

使用方法：
一：将两个文件下载后，放入指定文件夹(注意替换前面的路径)：

目录结构如下：

d:\ComfyUI-portal\Lorabrower(可以将lorabrower改为你想要的名字。)


<img width="617" height="143" alt="image" src="https://github.com/user-attachments/assets/0b65293f-02e5-40f8-87da-fe5c551b3f2f" />

                      
二：将用文本编辑器打开loraview.py，在配置区找到：

        FOLDER = r"D:\ComfyUI-portal\ComfyUI\models\loras"  # 修改为你的实际路径
        PORT = 12321
        
把其中的引号部分改为你的loras文件夹目录。

三：在D:\CMS\ComfyUI\models\loras（你的实际路径）文件夹下建立与lora文件**同名**的*.jpg（pnp，webp等）文件以及*.txt文件，如图：

<img width="358" height="117" alt="image" src="https://github.com/user-attachments/assets/b7cb75a7-db13-42ba-9fd7-10e025a13b66" />

其中，txt文件可以储存trigger等。一般图片是预览图。

双击loraview.bat，即可在浏览器中打开访问地址（可以按ctrl直接左键点击）：

<img width="695" height="217" alt="image" src="https://github.com/user-attachments/assets/5ab2ea82-6675-43fc-93d1-3d3f87fe04a0" />

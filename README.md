# personal-agent
这是一个本地私有化大模型的尝试

主要通过调用大模型api以及本地自定义的一部分tools实现function calling功能，从而完成和用户的交互

终极目标：实现企业级数据查询分析等功能

1. 第一步，下载代码

   ```
   git clone https://github.com/wagjixiang/personal-agent.git
   ```

2. 配置个人.env环境于项目文件夹下

   ```python
   OPENAI_API_KEY = "sk-xxxx"
   GPT_MODEL = "qwen-plus"
   MODEL_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
   
   DB_HOST = "127.0.0.1"
   DB_NAME = "school"
   DB_USER = "root"
   DB_PASS = "123456"
   DB_PORT = "3306"
   ```
   
3. 运行demo

   ```python
   python demo.py
   ```

   


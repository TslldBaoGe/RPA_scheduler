#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
打包脚本：将 FastAPI 后端打包成可执行文件
"""
import subprocess
import sys
import os

def build_exe():
    """使用 PyInstaller 打包后端"""
    
    # PyInstaller 参数
    args = [
        'pyinstaller',
        '--name=CronSchedulerBackend',  # 可执行文件名称
        '--onefile',  # 打包成单个文件
        '--console',  # 使用控制台模式（显示输出）
        '--add-data=tasks.json;.',  # 包含数据文件
        '--add-data=execution_history.json;.',  # 包含数据文件
        '--add-data=frontend;frontend',  # 包含前端文件
        '--hidden-import=uvicorn.logging',
        '--hidden-import=uvicorn.loops',
        '--hidden-import=uvicorn.loops.auto',
        '--hidden-import=uvicorn.protocols',
        '--hidden-import=uvicorn.protocols.http',
        '--hidden-import=uvicorn.protocols.http.auto',
        '--hidden-import=uvicorn.protocols.websockets',
        '--hidden-import=uvicorn.protocols.websockets.auto',
        '--hidden-import=uvicorn.lifespan',
        '--hidden-import=uvicorn.lifespan.on',
        '--hidden-import=apscheduler.schedulers.background',
        '--hidden-import=apscheduler.triggers.cron',
        'main.py'
    ]
    
    print("开始打包后端...")
    subprocess.run(args, check=True)
    print("后端打包完成！")
    
    # 创建启动脚本
    create_start_script()

def create_start_script():
    """创建启动脚本"""
    script_content = '''@echo off
chcp 65001 >nul
echo 正在启动定时任务调度系统...
echo 请稍候...

REM 启动后端服务
start "" "CronSchedulerBackend.exe"

REM 等待后端启动
timeout /t 3 /nobreak >nul

REM 打开浏览器访问前端
echo 系统已启动，正在打开浏览器...
start http://localhost:8000/docs

echo 定时任务调度系统已启动！
echo 访问地址：http://localhost:8000/docs
echo 按任意键关闭此窗口...
pause >nul
'''
    
    with open('start.bat', 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print("启动脚本已创建！")

if __name__ == '__main__':
    build_exe()

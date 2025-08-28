#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
音频转录全功能GUI工具 - 基于 whisper.cpp

这个脚本提供了一个图形用户界面，整合了所有音频转录功能：
1. 单文件转录
2. 批量转录
3. 语音转文字服务（按住空格键录音并转录）
"""

import os
import sys
import glob
import time
import tempfile
import threading
import subprocess
import numpy as np
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import json
import re

# 尝试导入必要的库
try:
    import sounddevice as sd
    import pyperclip
    from pynput import keyboard
    import scipy.io.wavfile as wavfile
    VOICE_SERVICE_AVAILABLE = True
except ImportError:
    VOICE_SERVICE_AVAILABLE = False

# 尝试导入音频清理所需的库
try:
    import openai
    from pydub import AudioSegment
    AUDIO_CLEANER_AVAILABLE = True
except ImportError:
    AUDIO_CLEANER_AVAILABLE = False


class AllInOneGUI:
    """
    音频转录全功能GUI应用
    """
    def __init__(self, root):
        """
        初始化GUI应用
        
        参数:
            root: tkinter根窗口
        """
        self.root = root
        self.root.title("FlowWhisper - 音频转录全功能工具")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # 设置应用图标
        try:
            self.root.iconbitmap("whisper/whisper.ico")
        except:
            pass  # 如果图标不存在，忽略错误
        
        # 创建主框架
        self.main_frame = ttk.Frame(root, padding="15")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建标题区域
        title_frame = ttk.Frame(self.main_frame, style="TFrame")
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 创建头部容器
        header_container = ttk.Frame(title_frame, style="TFrame")
        header_container.pack(fill=tk.X, padx=10, pady=10)
        
        # 主标题
        title_label = ttk.Label(header_container, text="🎙️ FlowWhisper", style="Title.TLabel")
        title_label.pack(anchor=tk.W)
        
        # 副标题
        subtitle_label = ttk.Label(header_container, text="基于 whisper.cpp 的智能音频处理平台", style="Subtitle.TLabel")
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 分隔线
        separator = ttk.Separator(title_frame, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 创建选项卡
        self.tab_control = ttk.Notebook(self.main_frame)
        
        # 单文件转录选项卡
        self.single_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.single_tab, text="单文件转录")
        
        # 批量转录选项卡
        self.batch_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.batch_tab, text="批量转录")
        
        # 语音转文字服务选项卡
        self.voice_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.voice_tab, text="语音转文字服务")
        
        # 智能音频清理选项卡
        self.cleaner_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.cleaner_tab, text="智能音频清理")
        
        self.tab_control.pack(expand=True, fill=tk.BOTH)
        
        # 应用主题样式
        self.setup_styles()
        
        # 设置各个选项卡
        self.setup_single_tab()
        self.setup_batch_tab()
        self.setup_voice_tab()
        self.setup_audio_cleaner_tab()
        
        # 加载配置
        self.load_config()
        
        # 绑定窗口关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # 检查依赖
        self.check_dependencies()
    
    def setup_styles(self):
        """设置UI样式"""
        style = ttk.Style()
        
        # 定义颜色方案
        bg_color = "#ffffff"
        header_bg = "#f8f9fa"
        accent_color = "#007bff"
        success_color = "#28a745"
        warning_color = "#ffc107"
        danger_color = "#dc3545"
        info_color = "#17a2b8"
        dark_color = "#343a40"
        light_color = "#f8f9fa"
        text_color = "#000000"
        
        # 配置主题
        style.theme_use('clam')
        
        # 基础框架样式
        style.configure("TFrame", background=bg_color)
        style.configure("Header.TFrame", background=header_bg)
        
        # 标签样式
        style.configure("TLabel", background=bg_color, foreground=text_color, font=("Segoe UI", 9))
        style.configure("Title.TLabel", background=bg_color, foreground=dark_color, font=("Segoe UI", 16, "bold"))
        style.configure("Subtitle.TLabel", background=bg_color, foreground=dark_color, font=("Segoe UI", 10))
        style.configure("Header.TLabel", background=header_bg, foreground=dark_color, font=("Segoe UI", 11, "bold"))
        style.configure("Success.TLabel", background=bg_color, foreground=success_color, font=("Segoe UI", 9, "bold"))
        style.configure("Warning.TLabel", background=bg_color, foreground=warning_color, font=("Segoe UI", 9, "bold"))
        style.configure("Danger.TLabel", background=bg_color, foreground=danger_color, font=("Segoe UI", 9, "bold"))
        style.configure("Info.TLabel", background=bg_color, foreground=info_color, font=("Segoe UI", 9, "bold"))
        
        # 按钮样式
        style.configure("TButton", padding=6, relief="flat", background=bg_color, foreground="#000000")
        style.map("TButton", background=[('active', accent_color)], foreground=[('active', '#000000')])
        
        style.configure("Success.TButton", padding=6, relief="flat", background=success_color, foreground="#000000")
        style.map("Success.TButton", background=[('active', '#218838')], foreground=[('active', '#000000')])
        
        style.configure("Warning.TButton", padding=6, relief="flat", background=warning_color, foreground="#000000")
        style.map("Warning.TButton", background=[('active', '#e0a800')], foreground=[('active', '#000000')])
        
        style.configure("Danger.TButton", padding=6, relief="flat", background=danger_color, foreground="#000000")
        style.map("Danger.TButton", background=[('active', '#c82333')], foreground=[('active', '#000000')])
        
        style.configure("Info.TButton", padding=6, relief="flat", background=info_color, foreground="#000000")
        style.map("Info.TButton", background=[('active', '#138496')], foreground=[('active', '#000000')])
        
        # 输入框样式
        style.configure("TEntry", padding=5, relief="solid", background=bg_color, foreground=text_color)
        
        # 下拉菜单样式
        style.configure("TCombobox", padding=5, relief="solid", background=bg_color, foreground=text_color)
        style.map("TCombobox", background=[('readonly', bg_color)], foreground=[('readonly', text_color)])
        
        # 文本框样式
        style.configure("TText", background=bg_color, foreground=text_color, relief="solid", padding=5)
        
        # 滚动条样式
        style.configure("TScrollbar", background=bg_color, troughcolor=light_color)
        
        # 分隔线样式
        style.configure("TSeparator", background=light_color)
        
        # 选项卡样式
        style.configure("TNotebook", background=bg_color, foreground=text_color)
        style.configure("TNotebook.Tab", background=light_color, foreground=text_color, padding=[10, 5])
        style.map("TNotebook.Tab", background=[('selected', bg_color)], foreground=[('selected', accent_color)])
    
    def setup_single_tab(self):
        """设置单文件转录选项卡"""
        frame = ttk.Frame(self.single_tab, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建输入区域
        input_frame = ttk.LabelFrame(frame, text="输入设置", padding="15")
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 文件选择
        file_frame = ttk.Frame(input_frame)
        file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_frame, text="音频文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.single_file_var = tk.StringVar()
        ttk.Entry(file_frame, textvariable=self.single_file_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(file_frame, text="浏览", command=self.browse_single_file).pack(side=tk.LEFT, padx=(5, 0))
        
        # 模型选择
        model_frame = ttk.Frame(input_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="模型:").pack(side=tk.LEFT, padx=(0, 10))
        self.single_model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.single_model_var, width=40)
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.model_combo['values'] = self.get_available_models()
        self.model_combo.set("ggml-base.en.bin")
        
        # 语言选择
        lang_frame = ttk.Frame(input_frame)
        lang_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(lang_frame, text="语言:").pack(side=tk.LEFT, padx=(0, 10))
        self.single_lang_var = tk.StringVar()
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.single_lang_var, width=20)
        self.lang_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.lang_combo['values'] = ["auto", "en", "zh", "ja", "ko", "es", "fr", "de"]
        self.lang_combo.set("auto")
        
        # 输出格式选择
        output_frame = ttk.Frame(input_frame)
        output_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_frame, text="输出格式:").pack(side=tk.LEFT, padx=(0, 10))
        self.single_output_var = tk.StringVar()
        output_combo = ttk.Combobox(output_frame, textvariable=self.single_output_var, width=15)
        output_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        output_combo['values'] = ["txt", "srt", "vtt", "json"]
        output_combo.set("txt")
        
        # 创建按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(button_frame, text="开始转录", command=self.start_single_transcription, style="Success.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="停止", command=self.stop_transcription, style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="打开输出文件夹", command=self.open_output_folder, style="Info.TButton").pack(side=tk.LEFT)
        
        # 创建进度显示区域
        progress_frame = ttk.LabelFrame(frame, text="进度", padding="15")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        self.single_progress_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.single_progress_var).pack(anchor=tk.W)
        
        self.single_progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.single_progress_bar.pack(fill=tk.X, pady=(10, 0))
        
        # 创建输出区域
        output_frame = ttk.LabelFrame(frame, text="输出", padding="15")
        output_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        self.single_output_text = tk.Text(output_frame, height=10, wrap=tk.WORD)
        self.single_output_text.pack(fill=tk.BOTH, expand=True)
        
        output_scrollbar = ttk.Scrollbar(output_frame, orient=tk.VERTICAL, command=self.single_output_text.yview)
        output_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.single_output_text.config(yscrollcommand=output_scrollbar.set)
    
    def setup_batch_tab(self):
        """设置批量转录选项卡"""
        frame = ttk.Frame(self.batch_tab, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建输入区域
        input_frame = ttk.LabelFrame(frame, text="输入设置", padding="15")
        input_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 目录选择
        dir_frame = ttk.Frame(input_frame)
        dir_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(dir_frame, text="输入目录:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_dir_var = tk.StringVar()
        ttk.Entry(dir_frame, textvariable=self.batch_dir_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(dir_frame, text="浏览", command=self.browse_batch_dir).pack(side=tk.LEFT, padx=(5, 0))
        
        # 输出目录
        output_dir_frame = ttk.Frame(input_frame)
        output_dir_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_dir_frame, text="输出目录:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_output_dir_var = tk.StringVar()
        ttk.Entry(output_dir_frame, textvariable=self.batch_output_dir_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_dir_frame, text="浏览", command=self.browse_batch_output_dir).pack(side=tk.LEFT, padx=(5, 0))
        
        # 文件类型
        file_type_frame = ttk.Frame(input_frame)
        file_type_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(file_type_frame, text="文件类型:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_file_type_var = tk.StringVar()
        file_type_combo = ttk.Combobox(file_type_frame, textvariable=self.batch_file_type_var, width=15)
        file_type_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        file_type_combo['values'] = ["*.wav", "*.mp3", "*.ogg", "*.flac", "*.m4a", "*.*"]
        file_type_combo.set("*.*")
        
        # 模型选择
        model_frame = ttk.Frame(input_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="模型:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_model_var = tk.StringVar()
        self.batch_model_combo = ttk.Combobox(model_frame, textvariable=self.batch_model_var, width=40)
        self.batch_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.batch_model_combo['values'] = self.get_available_models()
        self.batch_model_combo.set("ggml-base.en.bin")
        
        # 语言选择
        lang_frame = ttk.Frame(input_frame)
        lang_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(lang_frame, text="语言:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_lang_var = tk.StringVar()
        self.batch_lang_combo = ttk.Combobox(lang_frame, textvariable=self.batch_lang_var, width=20)
        self.batch_lang_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.batch_lang_combo['values'] = ["auto", "en", "zh", "ja", "ko", "es", "fr", "de"]
        self.batch_lang_combo.set("auto")
        
        # 输出格式选择
        output_format_frame = ttk.Frame(input_frame)
        output_format_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_format_frame, text="输出格式:").pack(side=tk.LEFT, padx=(0, 10))
        self.batch_output_var = tk.StringVar()
        batch_output_combo = ttk.Combobox(output_format_frame, textvariable=self.batch_output_var, width=15)
        batch_output_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        batch_output_combo['values'] = ["txt", "srt", "vtt", "json"]
        batch_output_combo.set("txt")
        
        # 创建按钮区域
        button_frame = ttk.Frame(frame)
        button_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(button_frame, text="开始批量转录", command=self.start_batch_transcription, style="Success.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="停止", command=self.stop_transcription, style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(button_frame, text="扫描文件", command=self.scan_files, style="Info.TButton").pack(side=tk.LEFT)
        
        # 创建进度显示区域
        progress_frame = ttk.LabelFrame(frame, text="进度", padding="15")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        self.batch_progress_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.batch_progress_var).pack(anchor=tk.W)
        
        self.batch_progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.batch_progress_bar.pack(fill=tk.X, pady=(10, 0))
        
        # 创建文件列表区域
        file_list_frame = ttk.LabelFrame(frame, text="文件列表", padding="15")
        file_list_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        # 创建列表框和滚动条
        list_frame = ttk.Frame(file_list_frame)
        list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.file_listbox = tk.Listbox(list_frame, selectmode=tk.MULTIPLE)
        self.file_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        file_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_listbox.yview)
        file_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.file_listbox.config(yscrollcommand=file_scrollbar.set)
    
    def setup_voice_tab(self):
        """设置语音转文字服务选项卡"""
        frame = ttk.Frame(self.voice_tab, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        if not VOICE_SERVICE_AVAILABLE:
            ttk.Label(frame, text="语音转文字服务不可用，请安装以下依赖：", foreground="red").pack(pady=10)
            ttk.Label(frame, text="pip install sounddevice pyperclip pynput scipy").pack()
            return
        
        # 创建设置区域
        settings_frame = ttk.LabelFrame(frame, text="设置", padding="15")
        settings_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 模型选择
        model_frame = ttk.Frame(settings_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="模型:").pack(side=tk.LEFT, padx=(0, 10))
        self.voice_model_var = tk.StringVar()
        self.voice_model_combo = ttk.Combobox(model_frame, textvariable=self.voice_model_var, width=40)
        self.voice_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.voice_model_combo['values'] = self.get_available_models()
        self.voice_model_combo.set("ggml-base.en.bin")
        
        # 语言选择
        lang_frame = ttk.Frame(settings_frame)
        lang_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(lang_frame, text="语言:").pack(side=tk.LEFT, padx=(0, 10))
        self.voice_lang_var = tk.StringVar()
        self.voice_lang_combo = ttk.Combobox(lang_frame, textvariable=self.voice_lang_var, width=20)
        self.voice_lang_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.voice_lang_combo['values'] = ["auto", "en", "zh", "ja", "ko", "es", "fr", "de"]
        self.voice_lang_combo.set("auto")
        
        # 录音设置
        record_frame = ttk.Frame(settings_frame)
        record_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(record_frame, text="录音设备:").pack(side=tk.LEFT, padx=(0, 10))
        self.voice_device_var = tk.StringVar()
        self.voice_device_combo = ttk.Combobox(record_frame, textvariable=self.voice_device_var, width=30)
        self.voice_device_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # 初始化设备列表
        self.init_audio_devices()
        
        # 创建控制区域
        control_frame = ttk.LabelFrame(frame, text="控制", padding="15")
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.voice_service_var = tk.StringVar(value="停止")
        ttk.Label(control_frame, text="服务状态:").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Label(control_frame, textvariable=self.voice_service_var).pack(side=tk.LEFT, padx=(0, 20))
        
        ttk.Button(control_frame, text="启动服务", command=self.start_voice_service, style="Success.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="停止服务", command=self.stop_voice_service, style="Danger.TButton").pack(side=tk.LEFT)
        
        # 创建信息区域
        info_frame = ttk.LabelFrame(frame, text="使用说明", padding="15")
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        info_text = """
使用方法：
1. 点击"启动服务"按钮
2. 按住 Caps Lock 键开始录音
3. 松开 Caps Lock 键结束录音
4. 系统会自动转录并复制到剪贴板

注意事项：
- 确保麦克风正常工作
- 录音时间不宜过长（建议不超过30秒）
- 转录结果会自动复制到剪贴板
        """
        ttk.Label(info_frame, text=info_text, justify=tk.LEFT).pack(anchor=tk.W)
        
        # 创建状态显示区域
        status_frame = ttk.LabelFrame(frame, text="状态", padding="15")
        status_frame.pack(fill=tk.BOTH, expand=True)
        
        self.voice_status_var = tk.StringVar(value="服务未启动")
        ttk.Label(status_frame, textvariable=self.voice_status_var).pack(anchor=tk.W)
        
        self.voice_output_text = tk.Text(status_frame, height=8, wrap=tk.WORD)
        self.voice_output_text.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        voice_scrollbar = ttk.Scrollbar(status_frame, orient=tk.VERTICAL, command=self.voice_output_text.yview)
        voice_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.voice_output_text.config(yscrollcommand=voice_scrollbar.set)
    
    def setup_audio_cleaner_tab(self):
        """设置智能音频清理选项卡"""
        frame = ttk.Frame(self.cleaner_tab, padding="20")
        frame.pack(fill=tk.BOTH, expand=True)
        
        if not AUDIO_CLEANER_AVAILABLE:
            ttk.Label(frame, text="智能音频清理功能不可用，请安装以下依赖：", foreground="red").pack(pady=10)
            ttk.Label(frame, text="pip install openai pydub numpy scipy").pack()
            return
        
        # 工作流程指示器
        workflow_frame = ttk.Frame(frame)
        workflow_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(workflow_frame, text="工作流程:", font=("Segoe UI", 10, "bold")).pack(anchor=tk.W, pady=(0, 5))
        
        steps_frame = ttk.Frame(workflow_frame)
        steps_frame.pack(fill=tk.X)
        
        ttk.Label(steps_frame, text="📁 选择音频", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="→", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="⚙️ 配置API", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="→", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="🧹 AI清理", font=("Segoe UI", 9)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="→", font=("Segoe UI", 12)).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Label(steps_frame, text="🎬 生成字幕", font=("Segoe UI", 9)).pack(side=tk.LEFT)
        
        # AI格式配置区域
        ai_config_frame = ttk.LabelFrame(frame, text="AI格式配置", padding="15")
        ai_config_frame.pack(fill=tk.X, pady=(0, 15))
        
        # AI格式选择
        ai_format_frame = ttk.Frame(ai_config_frame)
        ai_format_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(ai_format_frame, text="AI格式:").pack(side=tk.LEFT, padx=(0, 10))
        self.ai_format_var = tk.StringVar(value="openai")
        ai_format_combo = ttk.Combobox(ai_format_frame, textvariable=self.ai_format_var, width=15)
        ai_format_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ai_format_combo['values'] = ["openai", "ollama", "gemini"]
        ai_format_combo.bind("<<ComboboxSelected>>", self.update_ai_format_ui)
        
        # 快速配置按钮
        quick_config_frame = ttk.Frame(ai_config_frame)
        quick_config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(quick_config_frame, text="🌐 OpenRouter", command=self.quick_config_openrouter, style="Info.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_config_frame, text="🦙 Ollama", command=self.quick_config_ollama, style="Info.TButton").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(quick_config_frame, text="💎 Gemini", command=self.quick_config_gemini, style="Info.TButton").pack(side=tk.LEFT)
        
        # API配置
        api_config_frame = ttk.Frame(ai_config_frame)
        api_config_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_config_frame, text="API网址:").pack(side=tk.LEFT, padx=(0, 10))
        self.api_url_var = tk.StringVar()
        self.api_url_entry = ttk.Entry(api_config_frame, textvariable=self.api_url_var, width=40)
        self.api_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(api_config_frame, text="📋 粘贴", command=self.paste_api_url).pack(side=tk.LEFT, padx=(5, 0))
        
        # API密钥
        api_key_frame = ttk.Frame(ai_config_frame)
        api_key_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(api_key_frame, text="API密钥:").pack(side=tk.LEFT, padx=(0, 10))
        self.api_key_var = tk.StringVar()
        self.api_key_entry = ttk.Entry(api_config_frame, textvariable=self.api_key_var, width=40, show="*")
        self.api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(api_key_frame, text="📋 粘贴", command=self.paste_api_key).pack(side=tk.LEFT, padx=(5, 0))
        
        # 模型选择
        model_frame = ttk.Frame(ai_config_frame)
        model_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(model_frame, text="模型:").pack(side=tk.LEFT, padx=(0, 10))
        self.cleaner_model_var = tk.StringVar()
        self.cleaner_model_combo = ttk.Combobox(model_frame, textvariable=self.cleaner_model_var, width=30)
        self.cleaner_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.cleaner_model_combo['values'] = ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo", "gpt-4o"]
        self.cleaner_model_combo.set("gpt-3.5-turbo")
        
        # 格式说明标签
        self.format_info_label = ttk.Label(ai_config_frame, text="OpenAI格式：程序会自动添加/v1后缀", font=("Segoe UI", 9), foreground="gray")
        self.format_info_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 测试连接按钮
        test_frame = ttk.Frame(ai_config_frame)
        test_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Button(test_frame, text="🧪 测试连接", command=self.test_api_connection, style="Warning.TButton").pack(side=tk.LEFT)
        
        # 文件选择区域
        file_frame = ttk.LabelFrame(frame, text="文件选择", padding="15")
        file_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 输入文件
        input_file_frame = ttk.Frame(file_frame)
        input_file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(input_file_frame, text="音频文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.cleaner_input_var = tk.StringVar()
        ttk.Entry(input_file_frame, textvariable=self.cleaner_input_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(input_file_frame, text="浏览", command=self.browse_cleaner_input).pack(side=tk.LEFT, padx=(5, 0))
        
        # 输出文件
        output_file_frame = ttk.Frame(file_frame)
        output_file_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(output_file_frame, text="输出文件:").pack(side=tk.LEFT, padx=(0, 10))
        self.cleaner_output_var = tk.StringVar()
        ttk.Entry(output_file_frame, textvariable=self.cleaner_output_var, width=50).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(output_file_frame, text="浏览", command=self.browse_cleaner_output).pack(side=tk.LEFT, padx=(5, 0))
        
        # 二次转录选项
        transcription_frame = ttk.LabelFrame(frame, text="转录选项", padding="15")
        transcription_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.enable_secondary_transcription_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(transcription_frame, text="启用二次转录（对清理后的音频再次进行语音识别）", 
                       variable=self.enable_secondary_transcription_var).pack(anchor=tk.W, pady=(0, 5))
        
        self.enable_hrt_subtitles_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(transcription_frame, text="生成HRT字幕文件（优化显示时间和内容）", 
                       variable=self.enable_hrt_subtitles_var).pack(anchor=tk.W, pady=(0, 5))
        
        # Whisper模型选择
        whisper_model_frame = ttk.Frame(transcription_frame)
        whisper_model_frame.pack(fill=tk.X, pady=(5, 0))
        
        ttk.Label(whisper_model_frame, text="Whisper模型:").pack(side=tk.LEFT, padx=(0, 10))
        self.whisper_model_var = tk.StringVar()
        self.whisper_model_combo = ttk.Combobox(whisper_model_frame, textvariable=self.whisper_model_var, width=30)
        self.whisper_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.whisper_model_combo['values'] = self.get_available_models()
        self.whisper_model_combo.set("ggml-base.en.bin")
        
        # 控制按钮区域
        control_frame = ttk.Frame(frame)
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Button(control_frame, text="🚀 开始智能清理", command=self.start_audio_cleaning, style="Success.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="⏹️ 停止", command=self.stop_audio_cleaning, style="Danger.TButton").pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(control_frame, text="📁 打开输出文件夹", command=self.open_cleaner_output_folder, style="Info.TButton").pack(side=tk.LEFT)
        
        # 进度显示区域
        progress_frame = ttk.LabelFrame(frame, text="进度", padding="15")
        progress_frame.pack(fill=tk.BOTH, expand=True)
        
        self.cleaner_progress_var = tk.StringVar(value="准备就绪")
        ttk.Label(progress_frame, textvariable=self.cleaner_progress_var).pack(anchor=tk.W)
        
        self.cleaner_progress_bar = ttk.Progressbar(progress_frame, mode='determinate')
        self.cleaner_progress_bar.pack(fill=tk.X, pady=(10, 0))
        
        # 日志显示区域
        log_frame = ttk.LabelFrame(frame, text="处理日志", padding="15")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(15, 0))
        
        self.cleaner_log_text = tk.Text(log_frame, height=10, wrap=tk.WORD)
        self.cleaner_log_text.pack(fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.cleaner_log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cleaner_log_text.config(yscrollcommand=log_scrollbar.set)
        
        # 初始化AI格式UI
        self.update_ai_format_ui()
    
    def update_ai_format_ui(self, event=None):
        """更新AI格式UI"""
        ai_format = self.ai_format_var.get()
        
        # 更新模型建议
        self.update_model_suggestions()
        
        # 更新格式说明
        if ai_format == "openai":
            self.format_info_label.config(text="OpenAI格式：程序会自动添加/v1后缀")
        elif ai_format == "ollama":
            self.format_info_label.config(text="Ollama格式：程序会自动添加/api路径，本地运行无需API密钥")
        elif ai_format == "gemini":
            self.format_info_label.config(text="Gemini格式：使用完整的API路径")
    
    def update_model_suggestions(self):
        """根据AI格式更新模型建议"""
        ai_format = self.ai_format_var.get()
        
        if ai_format == "openai":
            models = [
                "gpt-3.5-turbo", 
                "gpt-4", 
                "gpt-4-turbo", 
                "gpt-4o",
                "claude-3-haiku", 
                "claude-3-sonnet",
                "claude-3-opus"
            ]
            if not self.cleaner_model_var.get() or "llama" in self.cleaner_model_var.get():
                self.cleaner_model_var.set("gpt-3.5-turbo")
        elif ai_format == "ollama":
            models = [
                "llama3.1:8b",
                "llama3.1:70b",
                "llama3.2:3b",
                "llama3:8b",
                "llama3:70b",
                "qwen2.5:7b",
                "qwen2.5:32b",
                "mistral:7b",
                "mixtral:8x7b",
                "phi3:14b"
            ]
            if not self.cleaner_model_var.get() or "gpt" in self.cleaner_model_var.get():
                self.cleaner_model_var.set("llama3.1:8b")
        elif ai_format == "gemini":
            models = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro"
            ]
            if not self.cleaner_model_var.get() or "gpt" in self.cleaner_model_var.get():
                self.cleaner_model_var.set("gemini-1.5-flash")
        
        self.cleaner_model_combo['values'] = models
    
    def quick_config_openrouter(self):
        """快速配置OpenRouter"""
        self.ai_format_var.set("openai")
        self.api_url_var.set("https://openrouter.ai")
        self.cleaner_model_var.set("gpt-3.5-turbo")
        self.update_ai_format_ui()
        self.add_cleaner_log("已快速配置OpenRouter设置")
    
    def quick_config_ollama(self):
        """快速配置Ollama"""
        self.ai_format_var.set("ollama")
        self.api_url_var.set("http://localhost:11434")
        self.cleaner_model_var.set("llama3.1:8b")
        self.update_ai_format_ui()
        self.add_cleaner_log("已快速配置Ollama设置")
    
    def quick_config_gemini(self):
        """快速配置Gemini"""
        self.ai_format_var.set("gemini")
        self.api_url_var.set("https://generativelanguage.googleapis.com/v1beta")
        self.cleaner_model_var.set("gemini-1.5-flash")
        self.update_ai_format_ui()
        self.add_cleaner_log("已快速配置Gemini设置")
    
    def paste_api_url(self):
        """粘贴API网址"""
        try:
            import pyperclip
            url = pyperclip.paste()
            if url and isinstance(url, str):
                self.api_url_var.set(url.strip())
                self.add_cleaner_log("已粘贴API网址")
            else:
                self.add_cleaner_log("剪贴板中没有有效的URL")
        except Exception as e:
            self.add_cleaner_log(f"粘贴失败: {e}")
    
    def paste_api_key(self):
        """粘贴API密钥"""
        try:
            import pyperclip
            key = pyperclip.paste()
            if key and isinstance(key, str):
                self.api_key_var.set(key.strip())
                self.add_cleaner_log("已粘贴API密钥")
            else:
                self.add_cleaner_log("剪贴板中没有有效的API密钥")
        except Exception as e:
            self.add_cleaner_log(f"粘贴失败: {e}")
    
    def get_formatted_api_url(self):
        """根据AI格式获取格式化的API URL"""
        ai_format = self.ai_format_var.get()
        base_url = self.api_url_var.get().strip()
        
        if not base_url:
            return None
            
        if ai_format == "openai":
            # OpenAI格式：自动添加/v1后缀
            if not base_url.endswith('/v1'):
                if base_url.endswith('/'):
                    return base_url + 'v1'
                else:
                    return base_url + '/v1'
            return base_url
        elif ai_format == "ollama":
            # Ollama格式：确保有/api路径
            if not base_url.endswith('/api'):
                if base_url.endswith('/'):
                    return base_url + 'api'
                else:
                    return base_url + '/api'
            return base_url
        elif ai_format == "gemini":
            # Gemini格式：直接使用用户输入的URL
            return base_url
        
        return base_url
    
    def test_api_connection(self):
        """测试API连接"""
        self.add_cleaner_log("正在测试API连接...")
        
        # 获取配置
        api_url = self.get_formatted_api_url()
        api_key = self.api_key_var.get().strip()
        model = self.cleaner_model_var.get()
        ai_format = self.ai_format_var.get()
        
        if not api_url:
            self.add_cleaner_log("错误：API网址不能为空")
            return
        
        if not model:
            self.add_cleaner_log("错误：模型不能为空")
            return
        
        # Ollama格式不需要API密钥
        if ai_format != "ollama" and not api_key:
            self.add_cleaner_log("错误：API密钥不能为空")
            return
        
        # 在新线程中测试连接
        threading.Thread(target=self._test_api_connection_thread, args=(api_url, api_key, model, ai_format), daemon=True).start()
    
    def _test_api_connection_thread(self, api_url, api_key, model, ai_format):
        """测试API连接的线程函数"""
        try:
            if ai_format == "openai":
                # OpenAI格式测试
                client = openai.OpenAI(api_key=api_key, base_url=api_url)
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": "Hello"}],
                    max_tokens=10
                )
                self.add_cleaner_log(f"✅ OpenAI连接成功！模型: {model}")
                self.add_cleaner_log(f"响应: {response.choices[0].message.content}")
            
            elif ai_format == "ollama":
                # Ollama格式测试
                import requests
                
                # 检查Ollama服务是否可用
                response = requests.get(f"{api_url}/tags")
                if response.status_code == 200:
                    models = response.json().get('models', [])
                    available_models = [m['name'] for m in models]
                    self.add_cleaner_log(f"✅ Ollama连接成功！可用模型: {len(available_models)}个")
                    if model in available_models:
                        self.add_cleaner_log(f"✅ 模型 {model} 可用")
                    else:
                        self.add_cleaner_log(f"⚠️ 模型 {model} 不可用，可用模型: {available_models[:5]}")
                else:
                    self.add_cleaner_log(f"❌ Ollama连接失败: {response.status_code}")
            
            elif ai_format == "gemini":
                # Gemini格式测试
                import requests
                
                # 构建Gemini API请求
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key
                }
                
                data = {
                    "contents": [{"parts": [{"text": "Hello"}]}],
                    "generationConfig": {"maxOutputTokens": 10}
                }
                
                # 提取模型名称（去除可能的前缀）
                model_name = model.split('/')[-1]
                full_url = f"{api_url}/models/{model_name}:generateContent"
                
                response = requests.post(full_url, headers=headers, json=data)
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        text = result['candidates'][0]['content']['parts'][0]['text']
                        self.add_cleaner_log(f"✅ Gemini连接成功！模型: {model}")
                        self.add_cleaner_log(f"响应: {text}")
                    else:
                        self.add_cleaner_log("⚠️ Gemini响应格式异常")
                else:
                    self.add_cleaner_log(f"❌ Gemini连接失败: {response.status_code}")
                    self.add_cleaner_log(f"错误信息: {response.text}")
        
        except Exception as e:
            self.add_cleaner_log(f"❌ API连接测试失败: {e}")
    
    def add_cleaner_log(self, message):
        """添加清理日志"""
        import datetime
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] {message}\n"
        
        self.cleaner_log_text.insert(tk.END, log_entry)
        self.cleaner_log_text.see(tk.END)
        self.root.update_idletasks()
    
    def browse_cleaner_input(self):
        """浏览输入文件"""
        filename = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.ogg *.flac *.m4a"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.cleaner_input_var.set(filename)
            # 自动设置输出文件名
            base_name = os.path.splitext(filename)[0]
            self.cleaner_output_var.set(f"{base_name}_cleaned.wav")
    
    def browse_cleaner_output(self):
        """浏览输出文件"""
        filename = filedialog.asksaveasfilename(
            title="选择输出文件",
            defaultextension=".wav",
            filetypes=[
                ("WAV文件", "*.wav"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.cleaner_output_var.set(filename)
    
    def start_audio_cleaning(self):
        """开始音频清理"""
        input_file = self.cleaner_input_var.get()
        output_file = self.cleaner_output_var.get()
        
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("错误", "请选择有效的输入文件")
            return
        
        if not output_file:
            messagebox.showerror("错误", "请选择输出文件")
            return
        
        # 检查API配置
        api_url = self.get_formatted_api_url()
        api_key = self.api_key_var.get().strip()
        model = self.cleaner_model_var.get()
        ai_format = self.ai_format_var.get()
        
        if not api_url:
            messagebox.showerror("错误", "API网址不能为空")
            return
        
        if not model:
            messagebox.showerror("错误", "模型不能为空")
            return
        
        if ai_format != "ollama" and not api_key:
            messagebox.showerror("错误", "API密钥不能为空")
            return
        
        # 在新线程中处理
        threading.Thread(target=self._audio_cleaning_thread, args=(input_file, output_file, api_url, api_key, model, ai_format), daemon=True).start()
    
    def _audio_cleaning_thread(self, input_file, output_file, api_url, api_key, model, ai_format):
        """音频清理线程函数"""
        try:
            self.add_cleaner_log(f"开始处理音频文件: {input_file}")
            self.cleaner_progress_var.set("正在分析音频...")
            self.cleaner_progress_bar['value'] = 0
            
            # 加载音频文件
            audio = AudioSegment.from_file(input_file)
            duration = len(audio) / 1000  # 转换为秒
            
            self.add_cleaner_log(f"音频时长: {duration:.2f}秒")
            self.add_cleaner_log(f"音频格式: {input_file.split('.')[-1].upper()}")
            
            # 分析音频片段
            self.cleaner_progress_var.set("正在分析音频片段...")
            self.cleaner_progress_bar['value'] = 20
            
            segments = self.analyze_audio_segments(audio)
            self.add_cleaner_log(f"发现 {len(segments)} 个音频片段")
            
            # 使用AI评估片段质量
            self.cleaner_progress_var.set("正在使用AI评估片段质量...")
            self.cleaner_progress_bar['value'] = 40
            
            good_segments = self.evaluate_segments_with_ai(segments, api_url, api_key, model, ai_format)
            self.add_cleaner_log(f"保留 {len(good_segments)} 个高质量片段")
            
            # 合并高质量片段
            self.cleaner_progress_var.set("正在合并高质量片段...")
            self.cleaner_progress_bar['value'] = 70
            
            if good_segments:
                cleaned_audio = sum(good_segments)
                self.add_cleaner_log(f"清理后音频时长: {len(cleaned_audio)/1000:.2f}秒")
            else:
                cleaned_audio = AudioSegment.empty()
                self.add_cleaner_log("警告：没有找到高质量片段")
            
            # 保存清理后的音频
            self.cleaner_progress_var.set("正在保存音频文件...")
            self.cleaner_progress_bar['value'] = 90
            
            cleaned_audio.export(output_file, format="wav")
            self.add_cleaner_log(f"音频清理完成: {output_file}")
            
            # 二次转录
            if self.enable_secondary_transcription_var.get() and len(cleaned_audio) > 0:
                self.cleaner_progress_var.set("正在进行二次转录...")
                self.cleaner_progress_bar['value'] = 95
                
                self.secondary_transcription(output_file)
            
            self.cleaner_progress_var.set("处理完成")
            self.cleaner_progress_bar['value'] = 100
            
            messagebox.showinfo("成功", "音频清理完成！")
            
        except Exception as e:
            self.add_cleaner_log(f"处理失败: {e}")
            self.cleaner_progress_var.set("处理失败")
            messagebox.showerror("错误", f"音频清理失败: {e}")
    
    def analyze_audio_segments(self, audio):
        """分析音频片段"""
        # 简单的静音检测分割
        silence_threshold = -40  # dB
        min_segment_length = 1000  # ms
        
        segments = []
        start = 0
        is_silence = True
        
        for i in range(0, len(audio), 10):  # 每10ms检查一次
            chunk = audio[i:i+10]
            if chunk.dBFS < silence_threshold:
                if not is_silence:
                    # 结束一个片段
                    if i - start > min_segment_length:
                        segments.append(audio[start:i])
                    start = i
                    is_silence = True
            else:
                if is_silence:
                    # 开始一个片段
                    start = i
                    is_silence = False
        
        # 添加最后一个片段
        if not is_silence and len(audio) - start > min_segment_length:
            segments.append(audio[start:])
        
        return segments
    
    def evaluate_segments_with_ai(self, segments, api_url, api_key, model, ai_format):
        """使用AI评估片段质量"""
        good_segments = []
        
        for i, segment in enumerate(segments):
            try:
                # 将片段转换为临时文件
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                    temp_filename = temp_file.name
                    segment.export(temp_filename, format="wav")
                
                # 使用Whisper进行初步转录
                transcript = self.transcribe_segment(temp_filename)
                
                if transcript:
                    # 使用AI评估转录质量
                    evaluation = self.evaluate_transcript_quality(transcript, api_url, api_key, model, ai_format)
                    
                    if evaluation.get('is_good_quality', False):
                        good_segments.append(segment)
                        self.add_cleaner_log(f"片段 {i+1}: 保留（质量良好）")
                    else:
                        self.add_cleaner_log(f"片段 {i+1}: 跳过（{evaluation.get('reason', '质量不佳')}）")
                else:
                    self.add_cleaner_log(f"片段 {i+1}: 跳过（无法转录）")
                
                # 清理临时文件
                os.unlink(temp_filename)
                
            except Exception as e:
                self.add_cleaner_log(f"片段 {i+1}: 处理失败 - {e}")
                continue
        
        return good_segments
    
    def transcribe_segment(self, audio_file):
        """转录音频片段"""
        try:
            # 使用whisper-cli进行转录
            model_path = self.get_whisper_model_path()
            if not model_path or not os.path.exists(model_path):
                self.add_cleaner_log("错误：找不到Whisper模型")
                return None
            
            cmd = [
                "whisper-cli.exe",
                "-m", model_path,
                "-f", audio_file,
                "-otxt"
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                self.add_cleaner_log(f"Whisper转录失败: {result.stderr}")
                return None
                
        except Exception as e:
            self.add_cleaner_log(f"转录失败: {e}")
            return None
    
    def evaluate_transcript_quality(self, transcript, api_url, api_key, model, ai_format):
        """评估转录质量"""
        try:
            if ai_format == "openai":
                client = openai.OpenAI(api_key=api_key, base_url=api_url)
                
                prompt = f"""
                请评估以下音频转录文本的质量：
                
                转录内容: {transcript}
                
                请从以下方面评估：
                1. 是否包含有意义的内容（不是噪音或无意义的声音）
                2. 语言是否通顺
                3. 是否包含完整的思想或句子
                
                请以JSON格式回复，包含以下字段：
                - is_good_quality: boolean（是否保留）
                - reason: string（原因说明）
                - confidence_score: float（置信度分数0-1）
                """
                
                response = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    response_format={"type": "json_object"},
                    max_tokens=200,
                    temperature=0.3
                )
                
                result_text = response.choices[0].message.content
                return json.loads(result_text)
            
            elif ai_format == "ollama":
                # Ollama格式评估
                import requests
                
                prompt = f"""
                请评估以下音频转录文本的质量：
                
                转录内容: {transcript}
                
                请从以下方面评估：
                1. 是否包含有意义的内容（不是噪音或无意义的声音）
                2. 语言是否通顺
                3. 是否包含完整的思想或句子
                
                请以JSON格式回复，包含以下字段：
                - is_good_quality: boolean（是否保留）
                - reason: string（原因说明）
                - confidence_score: float（置信度分数0-1）
                """
                
                data = {
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
                
                response = requests.post(f"{api_url}/generate", json=data)
                if response.status_code == 200:
                    result = response.json()
                    return json.loads(result.get('response', '{}'))
                else:
                    return {"is_good_quality": False, "reason": "Ollama API调用失败", "confidence_score": 0.0}
            
            elif ai_format == "gemini":
                # Gemini格式评估
                import requests
                
                prompt = f"""
                请评估以下音频转录文本的质量：
                
                转录内容: {transcript}
                
                请从以下方面评估：
                1. 是否包含有意义的内容（不是噪音或无意义的声音）
                2. 语言是否通顺
                3. 是否包含完整的思想或句子
                
                请以JSON格式回复，包含以下字段：
                - is_good_quality: boolean（是否保留）
                - reason: string（原因说明）
                - confidence_score: float（置信度分数0-1）
                """
                
                headers = {
                    "Content-Type": "application/json",
                    "x-goog-api-key": api_key
                }
                
                model_name = model.split('/')[-1]
                full_url = f"{api_url}/models/{model_name}:generateContent"
                
                data = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {
                        "maxOutputTokens": 200,
                        "temperature": 0.3
                    }
                }
                
                response = requests.post(full_url, headers=headers, json=data)
                if response.status_code == 200:
                    result = response.json()
                    if 'candidates' in result and result['candidates']:
                        text = result['candidates'][0]['content']['parts'][0]['text']
                        # 尝试解析JSON
                        try:
                            return json.loads(text)
                        except:
                            return {"is_good_quality": True, "reason": "Gemini评估完成", "confidence_score": 0.7}
                    else:
                        return {"is_good_quality": False, "reason": "Gemini响应格式异常", "confidence_score": 0.0}
                else:
                    return {"is_good_quality": False, "reason": "Gemini API调用失败", "confidence_score": 0.0}
        
        except Exception as e:
            self.add_cleaner_log(f"AI评估失败: {e}")
            return {"is_good_quality": True, "reason": "评估失败，默认保留", "confidence_score": 0.5}
    
    def secondary_transcription(self, cleaned_audio_file):
        """二次转录"""
        try:
            self.add_cleaner_log("开始二次转录...")
            
            # 使用Whisper进行转录
            model_path = self.get_whisper_model_path()
            if not model_path or not os.path.exists(model_path):
                self.add_cleaner_log("错误：找不到Whisper模型")
                return
            
            # 生成输出文件名
            base_name = os.path.splitext(cleaned_audio_file)[0]
            
            if self.enable_hrt_subtitles_var.get():
                # 生成HRT字幕
                subtitle_file = f"{base_name}.hrt"
                self.generate_hrt_subtitles(cleaned_audio_file, model_path, subtitle_file)
            else:
                # 生成普通字幕
                subtitle_file = f"{base_name}.srt"
                cmd = [
                    "whisper-cli.exe",
                    "-m", model_path,
                    "-f", cleaned_audio_file,
                    "-osrt"
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
                
                if result.returncode == 0:
                    self.add_cleaner_log(f"字幕文件生成成功: {subtitle_file}")
                else:
                    self.add_cleaner_log(f"字幕生成失败: {result.stderr}")
            
            self.add_cleaner_log("二次转录完成")
            
        except Exception as e:
            self.add_cleaner_log(f"二次转录失败: {e}")
    
    def generate_hrt_subtitles(self, audio_file, model_path, output_file):
        """生成HRT字幕"""
        try:
            # 使用whisper-cli生成带时间戳的转录
            cmd = [
                "whisper-cli.exe",
                "-m", model_path,
                "-f", audio_file,
                "-oj"  # 输出JSON格式
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode == 0:
                # 解析JSON结果
                import json
                transcript_data = json.loads(result.stdout)
                
                # 生成HRT格式字幕
                hrt_content = self.create_hrt_subtitles(transcript_data)
                
                # 保存HRT文件
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(hrt_content)
                
                self.add_cleaner_log(f"HRT字幕生成成功: {output_file}")
            else:
                self.add_cleaner_log(f"HRT字幕生成失败: {result.stderr}")
                
        except Exception as e:
            self.add_cleaner_log(f"HRT字幕生成失败: {e}")
    
    def create_hrt_subtitles(self, transcript_data):
        """创建HRT格式字幕"""
        hrt_lines = []
        
        if 'segments' in transcript_data:
            segments = transcript_data['segments']
            
            for segment in segments:
                start_time = segment['start']
                end_time = segment['end']
                text = segment['text'].strip()
                
                # 清理文本
                text = self.clean_subtitle_text(text)
                
                if text:  # 只保留非空字幕
                    # HRT格式：时间轴 文本
                    start_str = self.format_time_hrt(start_time)
                    end_str = self.format_time_hrt(end_time)
                    
                    hrt_line = f"{start_str} --> {end_str} | {text}"
                    hrt_lines.append(hrt_line)
        
        return '\n'.join(hrt_lines)
    
    def clean_subtitle_text(self, text):
        """清理字幕文本"""
        # 移除多余的标点符号
        text = re.sub(r'[.。,，!！?？]{2,}', '', text)
        
        # 移除开头和结尾的标点
        text = text.strip(' .,!?！？。')
        
        # 移除无意义的填充词
        filler_words = ['嗯', '啊', '呃', '那个', '这个', 'uh', 'um', 'like', 'you know']
        for word in filler_words:
            text = re.sub(r'\b' + word + r'\b', '', text, flags=re.IGNORECASE)
        
        # 清理多余的空格
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def format_time_hrt(self, seconds):
        """格式化时间为HRT格式"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        milliseconds = int((seconds % 1) * 1000)
        
        return f"{hours:02d}:{minutes:02d}:{secs:02d}.{milliseconds:03d}"
    
    def get_whisper_model_path(self):
        """获取Whisper模型路径"""
        model_name = self.whisper_model_var.get()
        model_paths = [
            f"models/{model_name}",
            f"whisper/models/{model_name}",
            model_name
        ]
        
        for path in model_paths:
            if os.path.exists(path):
                return path
        
        return None
    
    def stop_audio_cleaning(self):
        """停止音频清理"""
        self.add_cleaner_log("正在停止...")
        # 这里可以添加停止逻辑
        self.cleaner_progress_var.set("已停止")
    
    def open_cleaner_output_folder(self):
        """打开输出文件夹"""
        output_file = self.cleaner_output_var.get()
        if output_file and os.path.exists(output_file):
            folder = os.path.dirname(output_file)
            os.startfile(folder)
        else:
            messagebox.showwarning("警告", "输出文件不存在")
    
    def get_available_models(self):
        """获取可用的模型列表"""
        model_dirs = ["models", "whisper/models"]
        models = []
        
        for model_dir in model_dirs:
            if os.path.exists(model_dir):
                for file in os.listdir(model_dir):
                    if file.endswith('.bin'):
                        models.append(file)
        
        # 如果没有找到模型，提供默认列表
        if not models:
            models = [
                "ggml-base.en.bin",
                "ggml-base.bin", 
                "ggml-small.en.bin",
                "ggml-small.bin",
                "ggml-medium.en.bin",
                "ggml-medium.bin",
                "ggml-large-v1.bin",
                "ggml-large-v2.bin",
                "ggml-large-v3.bin"
            ]
        
        return sorted(models)
    
    def browse_single_file(self):
        """浏览单个文件"""
        filename = filedialog.askopenfilename(
            title="选择音频文件",
            filetypes=[
                ("音频文件", "*.wav *.mp3 *.ogg *.flac *.m4a"),
                ("所有文件", "*.*")
            ]
        )
        if filename:
            self.single_file_var.set(filename)
    
    def browse_batch_dir(self):
        """浏览批量输入目录"""
        directory = filedialog.askdirectory(title="选择输入目录")
        if directory:
            self.batch_dir_var.set(directory)
            # 自动设置输出目录
            self.batch_output_dir_var.set(directory + "_output")
    
    def browse_batch_output_dir(self):
        """浏览批量输出目录"""
        directory = filedialog.askdirectory(title="选择输出目录")
        if directory:
            self.batch_output_dir_var.set(directory)
    
    def scan_files(self):
        """扫描文件"""
        input_dir = self.batch_dir_var.get()
        file_type = self.batch_file_type_var.get()
        
        if not input_dir or not os.path.exists(input_dir):
            messagebox.showerror("错误", "请选择有效的输入目录")
            return
        
        # 清空文件列表
        self.file_listbox.delete(0, tk.END)
        
        # 扫描文件
        pattern = os.path.join(input_dir, file_type)
        files = glob.glob(pattern)
        
        for file in files:
            self.file_listbox.insert(tk.END, file)
        
        self.batch_progress_var.set(f"找到 {len(files)} 个文件")
    
    def start_single_transcription(self):
        """开始单文件转录"""
        filename = self.single_file_var.get()
        if not filename or not os.path.exists(filename):
            messagebox.showerror("错误", "请选择有效的音频文件")
            return
        
        model = self.single_model_var.get()
        language = self.single_lang_var.get()
        output_format = self.single_output_var.get()
        
        # 在新线程中处理
        threading.Thread(target=self._transcribe_file, args=(filename, model, language, output_format, 'single'), daemon=True).start()
    
    def start_batch_transcription(self):
        """开始批量转录"""
        input_dir = self.batch_dir_var.get()
        output_dir = self.batch_output_dir_var.get()
        
        if not input_dir or not os.path.exists(input_dir):
            messagebox.showerror("错误", "请选择有效的输入目录")
            return
        
        if not output_dir:
            messagebox.showerror("错误", "请选择输出目录")
            return
        
        # 创建输出目录
        os.makedirs(output_dir, exist_ok=True)
        
        # 获取选中的文件
        selected_indices = self.file_listbox.curselection()
        if not selected_indices:
            messagebox.showerror("错误", "请选择要转录的文件")
            return
        
        files = [self.file_listbox.get(i) for i in selected_indices]
        
        model = self.batch_model_var.get()
        language = self.batch_lang_var.get()
        output_format = self.batch_output_var.get()
        
        # 在新线程中处理
        threading.Thread(target=self._transcribe_batch, args=(files, output_dir, model, language, output_format), daemon=True).start()
    
    def _transcribe_file(self, filename, model, language, output_format, mode):
        """转录单个文件"""
        try:
            # 更新进度
            if mode == 'single':
                self.single_progress_var.set("正在转录...")
                self.single_progress_bar['value'] = 0
            else:
                self.batch_progress_var.set("正在转录...")
                self.batch_progress_bar['value'] = 0
            
            # 构建命令
            cmd = ["whisper-cli.exe", "-m", model, "-f", filename]
            
            if language != "auto":
                cmd.extend(["-l", language])
            
            if output_format == "txt":
                cmd.append("-otxt")
            elif output_format == "srt":
                cmd.append("-osrt")
            elif output_format == "vtt":
                cmd.append("-ovtt")
            elif output_format == "json":
                cmd.append("-oj")
            
            # 执行转录
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                # 更新进度
                if mode == 'single':
                    self.single_progress_var.set("转录完成")
                    self.single_progress_bar['value'] = 100
                    self.single_output_text.delete(1.0, tk.END)
                    self.single_output_text.insert(tk.END, result.stdout)
                else:
                    self.batch_progress_var.set("转录完成")
                    self.batch_progress_bar['value'] = 100
                
                messagebox.showinfo("成功", "转录完成！")
            else:
                error_msg = f"转录失败: {result.stderr}"
                if mode == 'single':
                    self.single_progress_var.set("转录失败")
                    self.single_output_text.delete(1.0, tk.END)
                    self.single_output_text.insert(tk.END, error_msg)
                else:
                    self.batch_progress_var.set("转录失败")
                
                messagebox.showerror("错误", error_msg)
        
        except Exception as e:
            error_msg = f"转录失败: {e}"
            if mode == 'single':
                self.single_progress_var.set("转录失败")
                self.single_output_text.delete(1.0, tk.END)
                self.single_output_text.insert(tk.END, error_msg)
            else:
                self.batch_progress_var.set("转录失败")
            
            messagebox.showerror("错误", error_msg)
    
    def _transcribe_batch(self, files, output_dir, model, language, output_format):
        """批量转录"""
        try:
            total_files = len(files)
            completed_files = 0
            
            for filename in files:
                if hasattr(self, '_stop_transcription'):
                    break
                
                # 更新进度
                self.batch_progress_var.set(f"正在转录: {os.path.basename(filename)}")
                progress = (completed_files / total_files) * 100
                self.batch_progress_bar['value'] = progress
                
                # 构建输出文件名
                base_name = os.path.splitext(os.path.basename(filename))[0]
                output_file = os.path.join(output_dir, f"{base_name}.{output_format}")
                
                # 构建命令
                cmd = ["whisper-cli.exe", "-m", model, "-f", filename]
                
                if language != "auto":
                    cmd.extend(["-l", language])
                
                if output_format == "txt":
                    cmd.extend(["-o", output_file])
                elif output_format == "srt":
                    cmd.extend(["-osrt", "-of", output_file])
                elif output_format == "vtt":
                    cmd.extend(["-ovtt", "-of", output_file])
                elif output_format == "json":
                    cmd.extend(["-oj", "-of", output_file])
                
                # 执行转录
                result = subprocess.run(cmd, capture_output=True, text=True)
                
                if result.returncode != 0:
                    self.batch_progress_var.set(f"转录失败: {os.path.basename(filename)}")
                    self.batch_output_text.insert(tk.END, f"失败: {filename} - {result.stderr}\n")
                
                completed_files += 1
                progress = (completed_files / total_files) * 100
                self.batch_progress_bar['value'] = progress
            
            if hasattr(self, '_stop_transcription'):
                self.batch_progress_var.set("转录已停止")
            else:
                self.batch_progress_var.set("批量转录完成")
                self.batch_progress_bar['value'] = 100
                messagebox.showinfo("成功", "批量转录完成！")
        
        except Exception as e:
            self.batch_progress_var.set(f"批量转录失败: {e}")
            messagebox.showerror("错误", f"批量转录失败: {e}")
        
        finally:
            self._stop_transcription = False
    
    def stop_transcription(self):
        """停止转录"""
        self._stop_transcription = True
    
    def open_output_folder(self):
        """打开输出文件夹"""
        filename = self.single_file_var.get()
        if filename and os.path.exists(filename):
            folder = os.path.dirname(filename)
            os.startfile(folder)
        else:
            messagebox.showwarning("警告", "文件不存在")
    
    def init_audio_devices(self):
        """初始化音频设备列表"""
        try:
            devices = sd.query_devices()
            device_names = []
            
            for i, device in enumerate(devices):
                if device['max_input_channels'] > 0:
                    device_names.append(f"{i}: {device['name']}")
            
            if device_names:
                self.voice_device_combo['values'] = device_names
                self.voice_device_combo.set(device_names[0])
            else:
                self.voice_device_combo['values'] = ["默认设备"]
                self.voice_device_combo.set("默认设备")
        
        except Exception as e:
            self.voice_device_combo['values'] = ["默认设备"]
            self.voice_device_combo.set("默认设备")
    
    def start_voice_service(self):
        """启动语音转文字服务"""
        if not hasattr(self, 'voice_service_thread') or not self.voice_service_thread.is_alive():
            self.voice_service_thread = threading.Thread(target=self.voice_service_loop, daemon=True)
            self.voice_service_thread.start()
            self.voice_service_var.set("运行中")
            self.voice_status_var.set("服务已启动，按住 Caps Lock 键录音")
    
    def stop_voice_service(self):
        """停止语音转文字服务"""
        self.voice_service_var.set("停止")
        self.voice_status_var.set("服务已停止")
    
    def voice_service_loop(self):
        """语音转文字服务循环"""
        recording = False
        audio_data = []
        
        def on_press(key):
            nonlocal recording, audio_data
            if key == keyboard.Key.caps_lock and not recording:
                recording = True
                audio_data = []
                self.voice_status_var.set("正在录音...")
                self.voice_output_text.insert(tk.END, "\n开始录音...\n")
                self.voice_output_text.see(tk.END)
        
        def on_release(key):
            nonlocal recording, audio_data
            if key == keyboard.Key.caps_lock and recording:
                recording = False
                self.voice_status_var.set("正在转录...")
                self.voice_output_text.insert(tk.END, "录音结束，正在转录...\n")
                self.voice_output_text.see(tk.END)
                
                # 保存录音并转录
                if audio_data:
                    self.save_and_transcribe(audio_data)
        
        listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        listener.start()
        
        # 录音循环
        while self.voice_service_var.get() == "运行中":
            if recording:
                try:
                    # 录制音频
                    data = sd.rec(int(44100 * 0.1), samplerate=44100, channels=1, dtype='float32')
                    sd.wait()
                    audio_data.extend(data)
                except Exception as e:
                    self.voice_status_var.set(f"录音错误: {e}")
            
            time.sleep(0.1)
        
        listener.stop()
    
    def save_and_transcribe(self, audio_data):
        """保存并转录音频"""
        try:
            # 保存为临时文件
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
                temp_filename = temp_file.name
                wavfile.write(temp_filename, 44100, np.array(audio_data))
            
            # 转录
            model = self.voice_model_var.get()
            language = self.voice_lang_var.get()
            
            cmd = ["whisper-cli.exe", "-m", model, "-f", temp_filename]
            
            if language != "auto":
                cmd.extend(["-l", language])
            
            cmd.append("-otxt")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                transcript = result.stdout.strip()
                if transcript:
                    # 复制到剪贴板
                    pyperclip.copy(transcript)
                    
                    # 显示结果
                    self.voice_output_text.insert(tk.END, f"转录结果: {transcript}\n")
                    self.voice_output_text.insert(tk.END, "已复制到剪贴板\n")
                    self.voice_output_text.see(tk.END)
                    
                    self.voice_status_var.set("转录完成")
                else:
                    self.voice_output_text.insert(tk.END, "转录结果为空\n")
                    self.voice_output_text.see(tk.END)
                    self.voice_status_var.set("转录结果为空")
            else:
                self.voice_output_text.insert(tk.END, f"转录失败: {result.stderr}\n")
                self.voice_output_text.see(tk.END)
                self.voice_status_var.set("转录失败")
            
            # 清理临时文件
            os.unlink(temp_filename)
            
        except Exception as e:
            self.voice_output_text.insert(tk.END, f"处理失败: {e}\n")
            self.voice_output_text.see(tk.END)
            self.voice_status_var.set("处理失败")
    
    def check_dependencies(self):
        """检查依赖"""
        missing_deps = []
        
        # 检查whisper-cli
        if not os.path.exists("whisper-cli.exe"):
            missing_deps.append("whisper-cli.exe")
        
        # 检查模型
        models = self.get_available_models()
        if not models:
            missing_deps.append("whisper模型文件")
        
        if missing_deps:
            messagebox.showwarning("缺少依赖", 
                                 f"以下文件缺失：\n{', '.join(missing_deps)}\n\n请确保所有依赖文件都已正确安装。")
    
    def load_config(self):
        """加载配置"""
        config_file = "audio_cleaner_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                
                # 加载AI配置
                if 'ai_format' in config:
                    self.ai_format_var.set(config['ai_format'])
                if 'api_url' in config:
                    self.api_url_var.set(config['api_url'])
                if 'api_key' in config:
                    self.api_key_var.set(config['api_key'])
                if 'model' in config:
                    self.cleaner_model_var.set(config['model'])
                
                # 更新UI
                self.update_ai_format_ui()
                
            except Exception as e:
                print(f"加载配置失败: {e}")
    
    def save_config(self):
        """保存配置"""
        config = {
            'ai_format': self.ai_format_var.get(),
            'api_url': self.api_url_var.get(),
            'api_key': self.api_key_var.get(),
            'model': self.cleaner_model_var.get()
        }
        
        config_file = "audio_cleaner_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {e}")
    
    def on_closing(self):
        """关闭窗口时的处理"""
        # 保存配置
        self.save_config()
        
        # 停止语音服务
        if hasattr(self, 'voice_service_var'):
            self.voice_service_var.set("停止")
        
        # 关闭窗口
        self.root.destroy()


def main():
    """主函数"""
    root = tk.Tk()
    app = AllInOneGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
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

# AI文本处理相关导入
try:
    import requests
    from dataclasses import dataclass, asdict
    from enum import Enum
    from typing import Dict, List, Optional, Any
    AI_PROCESSOR_AVAILABLE = True
except ImportError:
    AI_PROCESSOR_AVAILABLE = False

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
        self.root.title("音频转录全功能工具")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # 设置应用图标
        try:
            self.root.iconbitmap("whisper/whisper.ico")
        except:
            pass  # 如果图标不存在，忽略错误
        
        # 创建主框架
        self.inner_frame = ttk.Frame(root, padding="15")
        self.inner_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建标题区域
        title_frame = ttk.Frame(self.inner_frame, style="TFrame")
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        # 创建头部容器
        header_container = ttk.Frame(title_frame, style="TFrame")
        header_container.pack(fill=tk.X, padx=10, pady=10)
        
        # 主标题
        title_label = ttk.Label(header_container, text="🎙️ 音频转录全功能工具", style="Title.TLabel")
        title_label.pack(anchor=tk.W)
        
        # 副标题
        subtitle_label = ttk.Label(header_container, text="基于 whisper.cpp 的智能音频处理平台", style="Subtitle.TLabel")
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 分隔线
        separator = ttk.Separator(title_frame, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 创建选项卡
        self.tab_control = ttk.Notebook(self.inner_frame)
        
        # 语音转文字服务选项卡 (移到第一个)
        self.voice_service_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.voice_service_tab, text="🎙️ 语音转文字服务")
        
        # 单文件转录选项卡
        self.single_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.single_tab, text="📁 单文件转录")
        
        # 批量转录选项卡
        self.batch_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.batch_tab, text="📂 批量转录")
        
        # 智能音频清理选项卡
        self.audio_cleaner_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.audio_cleaner_tab, text="🧹 智能音频清理")
        
        # 日志选项卡 (移到最后)
        self.log_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.log_tab, text="📋 操作日志")
        
        self.tab_control.pack(expand=True, fill=tk.BOTH)
        
        # 默认选中语音转文字服务选项卡
        self.tab_control.select(0)
        
        # 创建临时日志文本组件（在选项卡设置期间使用）
        self.temp_log_text = tk.Text(self.inner_frame, height=1, wrap=tk.WORD, state='disabled')
        self.temp_log_text.pack_forget()  # 隐藏临时日志组件
        
        # 状态栏
        status_frame = ttk.Frame(self.inner_frame, style="TFrame")
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_var = tk.StringVar(value="✅ 系统就绪")
        status_bar = ttk.Label(status_frame, textvariable=self.status_var, 
                              font=("Microsoft YaHei", 9), relief=tk.SUNKEN, anchor=tk.W,
                              background="#e9ecef", foreground="#495057", padding=[5, 8])
        status_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 10))
        
        # 状态指示器
        self.status_indicator = ttk.Label(status_frame, text="🟢", font=("Arial", 12))
        self.status_indicator.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 初始化变量
        self.is_recording = False
        self.recorded_frames = []
        self.sample_rate = 16000  # whisper模型推荐的采样率
        self.temp_dir = tempfile.gettempdir()
        self.voice_service_active = False
        self.keyboard_listener = None
        
        # AI文本处理相关变量
        # 语音转文字服务AI配置
        self.voice_ai_config = self.load_voice_ai_config()
        self.voice_ai_enabled = self.voice_ai_config.get("enabled", False)
        self.voice_ai_session = None
        
        # 音频清理服务AI配置
        self.audio_cleaner_ai_config = self.load_audio_cleaner_ai_config()
        self.audio_cleaner_ai_enabled = self.audio_cleaner_ai_config.get("enabled", False)
        self.audio_cleaner_ai_session = None
        
        # 设置各选项卡
        self.setup_single_tab()
        self.setup_batch_tab()
        self.setup_voice_service_tab()
        self.setup_audio_cleaner_tab()
        self.setup_log_tab()
        
        # 查找模型
        self.find_models()
        
        # 加载语音服务配置
        if VOICE_SERVICE_AVAILABLE:
            self.load_voice_service_config()
        
        # 设置样式
        self.setup_styles()
        
    def setup_styles(self):
        """
        设置界面样式
        """
        style = ttk.Style()
        
        # 设置主题色彩
        primary_color = "#4a86e8"
        secondary_color = "#f0f4f8"
        success_color = "#28a745"
        warning_color = "#ffc107"
        danger_color = "#dc3545"
        dark_color = "#343a40"
        light_color = "#ffffff"
        text_color = "#000000"  # 黑色文字
        
        # 设置选项卡样式
        style.configure("TNotebook", background=secondary_color, borderwidth=0)
        style.configure("TNotebook.Tab", padding=[12, 8], font=("Microsoft YaHei", 10, "bold"),
                        background=light_color, foreground=text_color)
        style.map("TNotebook.Tab", background=[("selected", primary_color), ("active", "#e9ecef")])
        
        # 设置按钮样式
        style.configure("TButton", font=("Microsoft YaHei", 10), padding=[8, 4], 
                        background=light_color, foreground=text_color, relief="flat", borderwidth=1)
        style.map("TButton", background=[("active", "#e9ecef"), ("pressed", "#dee2e6")])
        
        # 主要按钮样式
        style.configure("Primary.TButton", font=("Microsoft YaHei", 10, "bold"), 
                        padding=[10, 6], background=primary_color, foreground=text_color)
        style.map("Primary.TButton", background=[("active", "#3a76d8"), ("pressed", "#2a66c8")])
        
        # 成功按钮样式
        style.configure("Success.TButton", font=("Microsoft YaHei", 10), 
                        padding=[8, 4], background=success_color, foreground=text_color)
        style.map("Success.TButton", background=[("active", "#218838"), ("pressed", "#1e7e34")])
        
        # 警告按钮样式
        style.configure("Warning.TButton", font=("Microsoft YaHei", 10), 
                        padding=[8, 4], background=warning_color, foreground=dark_color)
        style.map("Warning.TButton", background=[("active", "#e0a800"), ("pressed", "#d39e00")])
        
        # 设置标签样式
        style.configure("TLabel", font=("Microsoft YaHei", 10), background=secondary_color, foreground=dark_color)
        style.configure("Header.TLabel", font=("Microsoft YaHei", 14, "bold"), background=secondary_color, foreground=primary_color)
        style.configure("Title.TLabel", font=("Microsoft YaHei", 20, "bold"), background=secondary_color, foreground=primary_color)
        style.configure("Subtitle.TLabel", font=("Microsoft YaHei", 12), background=secondary_color, foreground="#6c757d")
        
        # 设置框架样式
        style.configure("TFrame", background=secondary_color)
        style.configure("TLabelframe", background=secondary_color, borderwidth=1, relief="solid")
        style.configure("TLabelframe.Label", font=("Microsoft YaHei", 11, "bold"), 
                        background=secondary_color, foreground=primary_color)
        
        # 设置输入框样式
        style.configure("TEntry", font=("Microsoft YaHei", 10), padding=[6, 4], 
                        background=light_color, foreground=text_color, borderwidth=1)
        style.configure("TCombobox", font=("Microsoft YaHei", 10), padding=[6, 4], 
                        background=light_color, foreground=text_color, borderwidth=1)
        
        # 设置文本框样式
        style.configure("TText", font=("Microsoft YaHei", 10), background=light_color, foreground=text_color)
        
        # 设置单选按钮和复选框样式
        style.configure("TRadiobutton", font=("Microsoft YaHei", 10), background=secondary_color, foreground=dark_color)
        style.configure("TCheckbutton", font=("Microsoft YaHei", 10), background=secondary_color, foreground=dark_color)
        
        # 初始化AI处理器（在日志选项卡设置完成后）
        if AI_PROCESSOR_AVAILABLE:
            self.setup_voice_ai_processor()
            self.setup_audio_cleaner_ai_processor()
        
        # 记录初始化完成日志
        self.log("🎉 音频转录全功能工具启动完成")
        self.log("📌 当前选项卡：语音转文字服务 (已设为默认)")
        if self.voice_ai_enabled:
            self.log("🤖 语音转文字AI文本处理功能已启用")
        else:
            self.log("⏸️ 语音转文字AI文本处理功能已禁用 (可在设置中启用)")
        
    def setup_single_tab(self):
        """
        设置单文件转录选项卡
        """
        frame = ttk.Frame(self.single_tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        header = ttk.Label(frame, text="单个音频文件转录", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        # 音频文件选择
        file_frame = ttk.Frame(frame)
        file_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(file_frame, text="音频文件:").pack(side=tk.LEFT)
        
        self.single_file_var = tk.StringVar()
        file_entry = ttk.Entry(file_frame, textvariable=self.single_file_var, width=50)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(file_frame, text="浏览...", command=self.browse_file)
        browse_btn.pack(side=tk.LEFT)
        
        # 模型选择
        model_frame = ttk.Frame(frame)
        model_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(model_frame, text="模型文件:").pack(side=tk.LEFT)
        
        self.model_var = tk.StringVar()
        self.model_combo = ttk.Combobox(model_frame, textvariable=self.model_var, width=50)
        self.model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        refresh_btn = ttk.Button(model_frame, text="刷新", command=self.find_models)
        refresh_btn.pack(side=tk.LEFT)
        
        # 输出格式选择
        format_frame = ttk.LabelFrame(frame, text="输出格式")
        format_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.format_var = tk.StringVar(value="txt")
        formats = [("文本文件 (.txt)", "txt"), 
                  ("字幕文件 (.srt)", "srt"), 
                  ("网页字幕 (.vtt)", "vtt"), 
                  ("JSON文件 (.json)", "json")]
        
        for i, (text, value) in enumerate(formats):
            ttk.Radiobutton(format_frame, text=text, value=value, variable=self.format_var).pack(anchor=tk.W, padx=20, pady=2)
        
        # 语言选择
        lang_frame = ttk.Frame(frame)
        lang_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(lang_frame, text="语言:").pack(side=tk.LEFT)
        
        self.lang_var = tk.StringVar(value="自动检测")
        self.lang_combo = ttk.Combobox(lang_frame, textvariable=self.lang_var, width=20)
        self.lang_combo['values'] = ["自动检测", "英语 (en)", "中文 (zh)", "日语 (ja)", "德语 (de)", "法语 (fr)", "西班牙语 (es)"]
        self.lang_combo.current(0)
        self.lang_combo.pack(side=tk.LEFT, padx=5)
        
        # 转录按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        # 添加文件信息显示
        info_frame = ttk.Frame(frame)
        info_frame.pack(fill=tk.X, pady=5)
        
        info_label = ttk.Label(info_frame, text="💡 选择音频文件和模型后，点击开始转录", 
                             font=("Microsoft YaHei", 9), foreground="#6c757d")
        info_label.pack(anchor=tk.W)
        
        # 按钮区域
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        transcribe_btn = ttk.Button(btn_frame, text="🎵 开始转录", command=self.transcribe_single_file, style="Primary.TButton")
        transcribe_btn.pack(side=tk.RIGHT, padx=5)
        
        clear_btn = ttk.Button(btn_frame, text="🗑️ 清空", command=self.clear_single_file, style="Warning.TButton")
        clear_btn.pack(side=tk.RIGHT, padx=5)
        
    def setup_batch_tab(self):
        """
        设置批量转录选项卡
        """
        frame = ttk.Frame(self.batch_tab, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        header = ttk.Label(frame, text="批量音频文件转录", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        # 目录选择
        dir_frame = ttk.Frame(frame)
        dir_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(dir_frame, text="音频目录:").pack(side=tk.LEFT)
        
        self.batch_dir_var = tk.StringVar()
        dir_entry = ttk.Entry(dir_frame, textvariable=self.batch_dir_var, width=50)
        dir_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(dir_frame, text="浏览...", command=self.browse_directory)
        browse_btn.pack(side=tk.LEFT)
        
        # 文件扩展名选择
        ext_frame = ttk.LabelFrame(frame, text="文件类型")
        ext_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.ext_vars = {}
        extensions = [("WAV", ".wav"), ("MP3", ".mp3"), ("OGG", ".ogg"), ("FLAC", ".flac"), ("M4A", ".m4a")]
        
        ext_grid = ttk.Frame(ext_frame)
        ext_grid.pack(fill=tk.X, padx=10, pady=5)
        
        for i, (text, ext) in enumerate(extensions):
            var = tk.BooleanVar(value=True)
            self.ext_vars[ext] = var
            ttk.Checkbutton(ext_grid, text=text, variable=var).grid(row=0, column=i, padx=15)
        
        # 使用与单文件相同的模型、格式和语言选择
        ttk.Label(frame, text="使用与单文件转录相同的模型、输出格式和语言设置").pack(pady=5)
        
        # 转录按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        transcribe_btn = ttk.Button(btn_frame, text="开始批量转录", command=self.transcribe_batch, style="Primary.TButton")
        transcribe_btn.pack(side=tk.RIGHT)
        
    def setup_voice_service_tab(self):
        """
        设置语音转文字服务选项卡
        """
        # 创建主框架和滚动条
        main_canvas = tk.Canvas(self.voice_service_tab)
        scrollbar = ttk.Scrollbar(self.voice_service_tab, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = ttk.Frame(scrollable_frame, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        header = ttk.Label(frame, text="语音转文字服务", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        if not VOICE_SERVICE_AVAILABLE:
            # 显示缺少依赖的提示
            msg_frame = ttk.Frame(frame, padding=20)
            msg_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(msg_frame, text="缺少必要的依赖库，无法使用语音转文字服务", 
                      font=("Arial", 12)).pack(pady=10)
            ttk.Label(msg_frame, text="请安装以下库：", 
                      font=("Arial", 10)).pack(pady=5)
            ttk.Label(msg_frame, text="pip install pynput sounddevice numpy pyperclip scipy", 
                      font=("Courier New", 10)).pack(pady=5)
            
            install_btn = ttk.Button(msg_frame, text="安装依赖", 
                                   command=lambda: self.install_dependencies())
            install_btn.pack(pady=10)
            return
        
        # 服务控制区域
        control_frame = ttk.LabelFrame(frame, text="服务控制")
        control_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 状态指示
        status_frame = ttk.Frame(control_frame)
        status_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(status_frame, text="服务状态:").pack(side=tk.LEFT, padx=5)
        
        self.service_status_var = tk.StringVar(value="未启动")
        status_label = ttk.Label(status_frame, textvariable=self.service_status_var, 
                                font=("Arial", 10, "bold"))
        status_label.pack(side=tk.LEFT, padx=5)
        
        # 启动/停止按钮
        btn_frame = ttk.Frame(control_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_service_btn = ttk.Button(btn_frame, text="启动服务", 
                                         command=self.toggle_voice_service, 
                                         style="Primary.TButton")
        self.start_service_btn.pack(side=tk.LEFT, padx=5)
        
        # 进度条区域
        progress_frame = ttk.LabelFrame(frame, text="处理进度")
        progress_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 进度条
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_frame, variable=self.progress_var, 
                                          maximum=100, length=400, mode='determinate')
        self.progress_bar.pack(padx=10, pady=5)
        
        # 进度状态标签
        self.progress_status_var = tk.StringVar(value="就绪")
        progress_status_label = ttk.Label(progress_frame, textvariable=self.progress_status_var)
        progress_status_label.pack(padx=10, pady=2)
        
        # 转录结果显示区域
        result_frame = ttk.LabelFrame(frame, text="转录结果")
        result_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        # 转录文本显示区域
        text_frame = ttk.Frame(result_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.transcription_text = tk.Text(text_frame, wrap=tk.WORD, height=8, 
                                        font=("Arial", 11), bg="#ffffff")
        self.transcription_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        text_scrollbar = ttk.Scrollbar(text_frame, command=self.transcription_text.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.transcription_text.config(yscrollcommand=text_scrollbar.set)
        
        # 按钮区域
        button_frame = ttk.Frame(result_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        copy_btn = ttk.Button(button_frame, text="复制文本", command=self.copy_transcription)
        copy_btn.pack(side=tk.LEFT, padx=5)
        
        clear_btn = ttk.Button(button_frame, text="清空", command=self.clear_transcription)
        clear_btn.pack(side=tk.LEFT, padx=5)
        
        cleanup_btn = ttk.Button(button_frame, text="清理临时文件", command=self.cleanup_all_temp_files)
        cleanup_btn.pack(side=tk.LEFT, padx=5)
        
        # 设置区域
        settings_frame = ttk.LabelFrame(frame, text="⚙️ 设置")
        settings_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 快捷键设置
        hotkey_frame = ttk.Frame(settings_frame)
        hotkey_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(hotkey_frame, text="快捷键:").pack(side=tk.LEFT, padx=5)
        
        self.hotkey_var = tk.StringVar(value="caps_lock")
        self.hotkey_combo = ttk.Combobox(hotkey_frame, textvariable=self.hotkey_var, width=15)
        self.hotkey_combo['values'] = [
            "caps_lock", "space", "enter", "tab", "esc", 
            "shift", "ctrl", "alt",
            "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12",
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "a", "b", "c", "d", "e", "f", "g", "h", "i", "j", "k", "l", "m",
            "n", "o", "p", "q", "r", "s", "t", "u", "v", "w", "x", "y", "z",
            "num_0", "num_1", "num_2", "num_3", "num_4", "num_5", "num_6", "num_7", "num_8", "num_9",
            "num_multiply", "num_add", "num_subtract", "num_decimal", "num_divide"
        ]
        self.hotkey_combo.pack(side=tk.LEFT, padx=5)
        
        apply_hotkey_btn = ttk.Button(hotkey_frame, text="应用", command=self.apply_hotkey)
        apply_hotkey_btn.pack(side=tk.LEFT, padx=5)
        
        # 语音识别模型设置
        model_frame = ttk.Frame(settings_frame)
        model_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(model_frame, text="识别模型:").pack(side=tk.LEFT, padx=5)
        
        self.voice_model_var = tk.StringVar()
        self.voice_model_combo = ttk.Combobox(model_frame, textvariable=self.voice_model_var, width=40)
        self.voice_model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        refresh_model_btn = ttk.Button(model_frame, text="刷新", command=self.refresh_voice_models)
        refresh_model_btn.pack(side=tk.LEFT, padx=2)
        
        save_model_btn = ttk.Button(model_frame, text="保存", command=self.save_voice_model_setting)
        save_model_btn.pack(side=tk.LEFT, padx=2)
        
        # 语音识别语言设置
        lang_frame = ttk.Frame(settings_frame)
        lang_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(lang_frame, text="识别语言:").pack(side=tk.LEFT, padx=5)
        
        self.voice_lang_var = tk.StringVar(value="auto")
        self.voice_lang_combo = ttk.Combobox(lang_frame, textvariable=self.voice_lang_var, width=15)
        self.voice_lang_combo['values'] = [
            "auto", "zh", "en", "ja", "ko", "fr", "de", "es", "it", "pt", "ru", "ar", "hi", "th", "vi"
        ]
        self.voice_lang_combo.pack(side=tk.LEFT, padx=5)
        
        save_lang_btn = ttk.Button(lang_frame, text="保存语言", command=self.save_voice_language_setting)
        save_lang_btn.pack(side=tk.LEFT, padx=2)
        
        # 输出语言设置
        output_lang_frame = ttk.Frame(settings_frame)
        output_lang_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(output_lang_frame, text="输出语言:").pack(side=tk.LEFT, padx=5)
        
        self.voice_output_lang_var = tk.StringVar(value="auto")
        self.voice_output_lang_combo = ttk.Combobox(output_lang_frame, textvariable=self.voice_output_lang_var, width=15)
        self.voice_output_lang_combo['values'] = [
            "auto", "zh", "en", "ja", "ko", "fr", "de", "es", "it", "pt", "ru", "ar", "hi", "th", "vi"
        ]
        self.voice_output_lang_combo.pack(side=tk.LEFT, padx=5)
        
        save_output_lang_btn = ttk.Button(output_lang_frame, text="保存输出语言", command=self.save_voice_output_language_setting)
        save_output_lang_btn.pack(side=tk.LEFT, padx=2)
        
        # 自动输入设置
        auto_input_frame = ttk.Frame(settings_frame)
        auto_input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.auto_input_var = tk.BooleanVar(value=True)
        auto_input_check = ttk.Checkbutton(auto_input_frame, text="转录完成后自动输入", variable=self.auto_input_var, command=self.update_auto_input_setting)
        auto_input_check.pack(side=tk.LEFT, padx=5)
        
        # 输入方式设置
        input_method_frame = ttk.Frame(settings_frame)
        input_method_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_method_frame, text="输入方式:").pack(side=tk.LEFT, padx=5)
        
        self.input_method_var = tk.StringVar(value="paste")
        input_method_paste = ttk.Radiobutton(input_method_frame, text="粘贴输入", variable=self.input_method_var, value="paste", command=self.save_input_method_setting)
        input_method_paste.pack(side=tk.LEFT, padx=5)
        
        input_method_direct = ttk.Radiobutton(input_method_frame, text="直接输入", variable=self.input_method_var, value="direct", command=self.save_input_method_setting)
        input_method_direct.pack(side=tk.LEFT, padx=5)
        
        # 提示音设置
        sound_frame = ttk.Frame(settings_frame)
        sound_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.start_sound_var = tk.BooleanVar(value=True)
        start_sound_check = ttk.Checkbutton(sound_frame, text="开始录音提示音", variable=self.start_sound_var, command=self.update_sound_settings)
        start_sound_check.pack(side=tk.LEFT, padx=5)
        
        self.end_sound_var = tk.BooleanVar(value=True)
        end_sound_check = ttk.Checkbutton(sound_frame, text="结束录音提示音", variable=self.end_sound_var, command=self.update_sound_settings)
        end_sound_check.pack(side=tk.LEFT, padx=5)
        
        # AI文本处理设置
        ai_frame = ttk.Frame(settings_frame)
        ai_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.ai_enabled_var = tk.BooleanVar(value=self.voice_ai_enabled)
        ai_check = ttk.Checkbutton(ai_frame, text="启用AI文本处理", variable=self.ai_enabled_var, command=self.toggle_voice_ai_processor)
        ai_check.pack(side=tk.LEFT, padx=5)
        
        ai_settings_btn = ttk.Button(ai_frame, text="AI设置", command=self.show_voice_ai_settings_dialog)
        ai_settings_btn.pack(side=tk.LEFT, padx=5)
        
        # 提示音频率设置
        freq_frame = ttk.Frame(settings_frame)
        freq_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(freq_frame, text="开始提示音频率:").pack(side=tk.LEFT, padx=5)
        self.start_freq_var = tk.StringVar(value="1000")
        start_freq_spin = ttk.Spinbox(freq_frame, from_=200, to=3000, textvariable=self.start_freq_var, width=8)
        start_freq_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(freq_frame, text="Hz").pack(side=tk.LEFT, padx=2)
        
        ttk.Label(freq_frame, text="结束提示音频率:").pack(side=tk.LEFT, padx=(15, 5))
        self.end_freq_var = tk.StringVar(value="800")
        end_freq_spin = ttk.Spinbox(freq_frame, from_=200, to=3000, textvariable=self.end_freq_var, width=8)
        end_freq_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(freq_frame, text="Hz").pack(side=tk.LEFT, padx=2)
        
        # 提示音持续时间设置
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(duration_frame, text="提示音持续时间:").pack(side=tk.LEFT, padx=5)
        self.duration_var = tk.StringVar(value="200")
        duration_spin = ttk.Spinbox(duration_frame, from_=50, to=1000, textvariable=self.duration_var, width=8)
        duration_spin.pack(side=tk.LEFT, padx=5)
        ttk.Label(duration_frame, text="毫秒").pack(side=tk.LEFT, padx=2)
        
        test_sound_btn = ttk.Button(duration_frame, text="测试提示音", command=self.test_sound)
        test_sound_btn.pack(side=tk.LEFT, padx=10)
        
        # 初始化语音识别模型
        self.refresh_voice_models()
        
        # 使用说明
        instruction_frame = ttk.LabelFrame(frame, text="使用说明")
        instruction_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        instructions = (
            "1. 点击\"启动服务\"按钮启动语音转文字服务\n"
            "2. 第一次按下设置的快捷键开始录音\n"
            "3. 再次按下快捷键结束录音，系统会自动转录并将文本显示在上方\n"
            "4. 转录文本会自动复制到剪贴板，并可选择自动输入到当前光标位置\n"
            "5. 点击\"复制文本\"按钮复制转录结果到剪贴板\n"
            "6. 点击\"清空\"按钮清空转录文本\n"
            "7. 点击\"清理临时文件\"按钮清理临时文件\n"
            "8. 点击\"停止服务\"按钮停止服务\n\n"
            "设置选项：\n"
            "- 快捷键：可选择各种按键作为录音触发键（包括小键盘按键）\n"
            "- 识别模型：选择语音识别模型（推荐使用大模型提高准确率）\n"
            "- 识别语言：设置您说话的语言（提高识别准确率）\n"
            "- 输出语言：设置转录结果的输出语言（支持翻译功能）\n"
            "- 自动输入：转录完成后自动在当前光标位置输入结果\n"
            "- 输入方式：选择粘贴输入（Ctrl+V）或直接键盘输入\n"
            "- 提示音：可设置开始/结束录音时的提示音和频率\n"
            "- 测试提示音：点击\"测试提示音\"按钮预览声音效果\n\n"
            "自动输入说明：\n"
            "- 启用后，转录完成会自动在当前光标位置输入结果\n"
            "- 粘贴输入：使用Ctrl+V快捷键粘贴，适合大多数应用\n"
            "- 直接输入：模拟键盘逐字输入，适合不支持粘贴的场景\n\n"
            "注意：\n"
            "- 录音质量会影响转录准确度，请尽量在安静环境中使用\n"
            "- 转录过程可能需要几秒钟时间，取决于录音长度和电脑性能\n"
            "- 使用自动输入时，请确保光标位于正确的输入位置\n"
            "- 临时文件会在转录完成后自动清理，也可以手动清理"
        )
        
        instruction_text = tk.Text(instruction_frame, wrap=tk.WORD, height=10, 
                                 font=("Arial", 10), bg="#f9f9f9")
        instruction_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        instruction_text.insert(tk.END, instructions)
        instruction_text.config(state=tk.DISABLED)  # 设为只读
    
    def setup_audio_cleaner_tab(self):
        """
        设置智能音频清理选项卡
        """
        # 创建主框架和滚动条
        main_canvas = tk.Canvas(self.audio_cleaner_tab)
        scrollbar = ttk.Scrollbar(self.audio_cleaner_tab, orient="vertical", command=main_canvas.yview)
        scrollable_frame = ttk.Frame(main_canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        frame = ttk.Frame(scrollable_frame, padding="10")
        frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        header = ttk.Label(frame, text="🧠 智能音频清理工具", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        # 工作流程指示器
        workflow_frame = ttk.Frame(frame)
        workflow_frame.pack(fill=tk.X, pady=(0, 15))
        
        workflow_steps = [
            "📁 选择音频", 
            "⚙️ 配置API", 
            "🧹 AI清理", 
            "🎬 生成字幕"
        ]
        
        for i, step in enumerate(workflow_steps):
            step_frame = ttk.Frame(workflow_frame)
            step_frame.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # 步骤编号
            step_num = ttk.Label(step_frame, text=f"{i+1}", font=("Arial", 12, "bold"), 
                               foreground="#4a86e8")
            step_num.pack()
            
            # 步骤描述
            step_label = ttk.Label(step_frame, text=step, font=("Microsoft YaHei", 9))
            step_label.pack()
            
            # 连接线（除了最后一个）
            if i < len(workflow_steps) - 1:
                separator = ttk.Label(workflow_frame, text="→", font=("Arial", 14), 
                                    foreground="#6c757d")
                separator.pack(side=tk.LEFT, padx=5)
        
        if not AUDIO_CLEANER_AVAILABLE:
            # 显示缺少依赖的提示
            msg_frame = ttk.Frame(frame, padding=20)
            msg_frame.pack(fill=tk.BOTH, expand=True)
            
            ttk.Label(msg_frame, text="缺少必要的依赖库，无法使用智能音频清理功能", 
                      font=("Arial", 12)).pack(pady=10)
            ttk.Label(msg_frame, text="请安装以下库：", 
                      font=("Arial", 10)).pack(pady=5)
            ttk.Label(msg_frame, text="pip install openai pydub", 
                      font=("Courier New", 10)).pack(pady=5)
            
            install_btn = ttk.Button(msg_frame, text="安装依赖", 
                                   command=lambda: self.install_audio_cleaner_dependencies())
            install_btn.pack(pady=10)
            return
        
        # API配置区域
        api_frame = ttk.LabelFrame(frame, text="🔑 API配置 (步骤 2)")
        api_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # AI格式选择
        format_frame = ttk.Frame(api_frame)
        format_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(format_frame, text="AI格式:").pack(side=tk.LEFT, padx=(0, 10))
        self.ai_format_var = tk.StringVar(value="openai")
        ai_format_combo = ttk.Combobox(format_frame, textvariable=self.ai_format_var, width=15)
        ai_format_combo['values'] = ["openai", "ollama", "gemini"]
        ai_format_combo.pack(side=tk.LEFT, padx=5)
        ai_format_combo.bind("<<ComboboxSelected>>", self.on_ai_format_change)
        
        # 格式说明标签
        self.format_info_var = tk.StringVar()
        format_info_label = ttk.Label(format_frame, textvariable=self.format_info_var, 
                                    font=("Microsoft YaHei", 9), foreground="#6c757d")
        format_info_label.pack(side=tk.LEFT, padx=10)
        
        # API URL
        url_frame = ttk.Frame(api_frame)
        url_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(url_frame, text="API URL:").pack(side=tk.LEFT, padx=(0, 10))
        self.api_url_var = tk.StringVar(value="https://api.openai.com")
        api_url_entry = ttk.Entry(url_frame, textvariable=self.api_url_var, width=50)
        api_url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        paste_url_btn = ttk.Button(url_frame, text="📋 粘贴", command=self.paste_api_url, style="Success.TButton", width=10)
        paste_url_btn.pack(side=tk.LEFT, padx=5)
        
        # OpenAI格式提示
        self.openai_hint_var = tk.StringVar()
        openai_hint_label = ttk.Label(api_frame, textvariable=self.openai_hint_var, 
                                     font=("Microsoft YaHei", 9), foreground="#28a745")
        openai_hint_label.pack(anchor=tk.W, padx=10, pady=(0, 5))
        
        # API Key
        key_frame = ttk.Frame(api_frame)
        key_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(key_frame, text="API Key:").pack(side=tk.LEFT, padx=(0, 10))
        self.api_key_var = tk.StringVar()
        api_key_entry = ttk.Entry(key_frame, textvariable=self.api_key_var, width=50, show="*")
        api_key_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        paste_key_btn = ttk.Button(key_frame, text="📋 粘贴", command=self.paste_api_key, style="Success.TButton", width=10)
        paste_key_btn.pack(side=tk.LEFT, padx=5)
        
        # 快速配置按钮
        quick_config_frame = ttk.Frame(api_frame)
        quick_config_frame.pack(fill=tk.X, padx=10, pady=5)
        
        openrouter_btn = ttk.Button(quick_config_frame, text="🌐 OpenRouter", 
                                  command=self.quick_config_openrouter, style="Warning.TButton")
        openrouter_btn.pack(side=tk.LEFT, padx=2)
        
        ollama_btn = ttk.Button(quick_config_frame, text="🦙 Ollama", 
                               command=self.quick_config_ollama, style="Warning.TButton")
        ollama_btn.pack(side=tk.LEFT, padx=2)
        
        gemini_btn = ttk.Button(quick_config_frame, text="💎 Gemini", 
                               command=self.quick_config_gemini, style="Warning.TButton")
        gemini_btn.pack(side=tk.LEFT, padx=2)
        
        test_config_btn = ttk.Button(quick_config_frame, text="🧪 测试连接", 
                                    command=self.test_api_connection, style="Primary.TButton")
        test_config_btn.pack(side=tk.LEFT, padx=5)
        
        # 模型名称
        model_frame = ttk.Frame(api_frame)
        model_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(model_frame, text="模型名称:").pack(side=tk.LEFT, padx=(0, 10))
        self.cleaner_model_var = tk.StringVar(value="gpt-3.5-turbo")
        model_combo = ttk.Combobox(model_frame, textvariable=self.cleaner_model_var, width=20)
        
        # 根据AI格式更新模型建议
        self.update_model_suggestions()
        model_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        model_combo.bind("<<ComboboxSelected>>", lambda e: self.update_model_suggestions())
        
        # 保存设置按钮
        settings_btn_frame = ttk.Frame(api_frame)
        settings_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        save_btn = ttk.Button(settings_btn_frame, text="保存设置", command=self.save_api_settings)
        save_btn.pack(side=tk.LEFT, padx=5)
        
        load_btn = ttk.Button(settings_btn_frame, text="加载设置", command=self.load_api_settings)
        load_btn.pack(side=tk.LEFT, padx=5)
        
        ai_settings_btn = ttk.Button(settings_btn_frame, text="AI设置", command=self.show_audio_cleaner_ai_settings_dialog)
        ai_settings_btn.pack(side=tk.LEFT, padx=5)
        
        # 音频文件选择
        audio_frame = ttk.LabelFrame(frame, text="📁 音频文件 (步骤 1)")
        audio_frame.pack(fill=tk.X, pady=10, padx=5)
        
        file_select_frame = ttk.Frame(audio_frame)
        file_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(file_select_frame, text="音频文件:").pack(side=tk.LEFT)
        
        self.cleaner_audio_var = tk.StringVar()
        audio_entry = ttk.Entry(file_select_frame, textvariable=self.cleaner_audio_var, width=50)
        audio_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(file_select_frame, text="浏览...", command=self.browse_cleaner_audio)
        browse_btn.pack(side=tk.LEFT)
        
        # 输出文件设置
        output_frame = ttk.Frame(audio_frame)
        output_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(output_frame, text="输出文件:").pack(side=tk.LEFT)
        
        self.cleaner_output_var = tk.StringVar(value="cleaned_audio.mp3")
        output_entry = ttk.Entry(output_frame, textvariable=self.cleaner_output_var, width=50)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 高级设置
        advanced_frame = ttk.LabelFrame(frame, text="⚙️ 高级设置")
        advanced_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 最大片段长度
        segment_frame = ttk.Frame(advanced_frame)
        segment_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(segment_frame, text="最大片段长度:").pack(side=tk.LEFT, padx=(0, 10))
        self.max_segment_var = tk.StringVar(value="50")
        segment_entry = ttk.Entry(segment_frame, textvariable=self.max_segment_var, width=10)
        segment_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(segment_frame, text="字符").pack(side=tk.LEFT)
        
        # 间隔阈值
        gap_frame = ttk.Frame(advanced_frame)
        gap_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(gap_frame, text="间隔阈值:").pack(side=tk.LEFT, padx=(0, 10))
        self.gap_threshold_var = tk.StringVar(value="1.0")
        gap_entry = ttk.Entry(gap_frame, textvariable=self.gap_threshold_var, width=10)
        gap_entry.pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(gap_frame, text="秒").pack(side=tk.LEFT)
        
        # 系统提示词编辑
        prompt_frame = ttk.LabelFrame(frame, text="🤖 LLM系统提示词")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        prompt_text_frame = ttk.Frame(prompt_frame)
        prompt_text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.system_prompt_var = tk.StringVar(value=self.get_default_system_prompt())
        
        self.prompt_text = tk.Text(prompt_text_frame, wrap=tk.WORD, height=8, 
                                 font=("Courier New", 9), bg="#ffffff")
        self.prompt_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.prompt_text.insert(tk.END, self.system_prompt_var.get())
        
        # 添加滚动条
        prompt_scrollbar = ttk.Scrollbar(self.prompt_text, command=self.prompt_text.yview)
        prompt_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.prompt_text.config(yscrollcommand=prompt_scrollbar.set)
        
        # 提示词更新按钮
        update_prompt_btn = ttk.Button(prompt_frame, text="更新提示词", 
                                      command=lambda: self.update_system_prompt(self.prompt_text))
        update_prompt_btn.pack(pady=5)
        
        # 二次转录选项
        secondary_frame = ttk.LabelFrame(frame, text="二次转录选项")
        secondary_frame.pack(fill=tk.X, pady=10, padx=5)
        
        self.enable_secondary_var = tk.BooleanVar(value=True)
        secondary_check = ttk.Checkbutton(secondary_frame, text="启用二次转录（清理后再次语音识别）", 
                                         variable=self.enable_secondary_var)
        secondary_check.pack(anchor=tk.W, padx=10, pady=5)
        
        # HRT字幕设置
        hrt_frame = ttk.Frame(secondary_frame)
        hrt_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(hrt_frame, text="HRT字幕文件:").pack(side=tk.LEFT)
        self.hrt_output_var = tk.StringVar()
        hrt_entry = ttk.Entry(hrt_frame, textvariable=self.hrt_output_var, width=40)
        hrt_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 处理按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        # 状态指示器
        self.cleaner_status_var = tk.StringVar(value="⏳ 准备就绪")
        status_label = ttk.Label(btn_frame, textvariable=self.cleaner_status_var, 
                                font=("Microsoft YaHei", 10, "bold"), foreground="#6c757d")
        status_label.pack(side=tk.LEFT, padx=5)
        
        clean_btn = ttk.Button(btn_frame, text="🚀 开始智能清理", command=self.start_audio_cleaning, style="Primary.TButton")
        clean_btn.pack(side=tk.RIGHT, padx=5)
        
        reset_btn = ttk.Button(btn_frame, text="🔄 重置设置", command=self.reset_cleaner_settings)
        reset_btn.pack(side=tk.RIGHT, padx=5)
        
        # 自动加载设置
        self.auto_load_api_settings()
        
        # 测试OpenAI库
        self.test_openai_library()
        
        # 初始化AI格式
        self.update_ai_format_ui()
        
        # 使用说明
        instruction_frame = ttk.LabelFrame(frame, text="使用说明")
        instruction_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        instructions = (
            "🎯 使用指南：\n"
            "1. 选择AI格式（OpenAI/Ollama/Gemini）\n"
            "2. 配置API信息：输入API URL和API密钥\n"
            "3. 选择要清理的音频文件和输出路径\n"
            "4. 根据需要调整高级设置\n"
            "5. 编辑系统提示词以优化识别效果\n"
            "6. 选择是否启用二次转录和HRT字幕生成\n"
            "7. 点击\"🚀 开始智能清理\"按钮进行处理\n\n"
            "🔄 AI格式说明：\n"
            "🔹 OpenAI：标准格式，程序自动添加/v1后缀\n"
            "🔹 Ollama：本地AI模型，无需API Key\n"
            "🔹 Gemini：Google AI，需要完整API路径\n\n"
            "🔄 处理流程：\n"
            "步骤1: 使用whisper对原始音频进行语音识别\n"
            "步骤2: 优化SRT片段（分段和间隔处理）\n"
            "步骤3: LLM分析识别需要删除的低质量片段\n"
            "步骤4: 剪辑音频，保留优质片段生成新音频\n"
            "步骤5: (可选) 对清理后的音频进行二次转录\n"
            "步骤6: (可选) 生成HRT格式字幕文件\n\n"
            "🎙️ 二次转录优势：\n"
            "- 清理后的音频没有噪音和低质量内容\n"
            "- 第二次语音识别准确度更高\n"
            "- 生成的字幕质量更好\n"
            "- 避免原始音频中的干扰因素\n\n"
            "📋 HRT字幕特点：\n"
            "- 自动过滤无意义片段（嗯、啊、呃等）\n"
            "- 移除过短的字幕片段（小于1秒）\n"
            "- 优化字幕显示时间（2-5秒）\n"
            "- 清理多余标点符号\n\n"
            "💡 提示：\n"
            "- 使用快速配置按钮一键设置常用AI服务\n"
            "- OpenAI格式只需输入基础URL，程序自动处理/v1\n"
            "- Ollama确保服务运行在localhost:11434\n"
            "- 系统提示词可以自定义以获得更好的识别效果\n"
            "- 支持的音频格式：wav, mp3, m4a, flac等\n"
            "- 输出音频格式为mp3，字幕格式为srt"
        )
        
        instruction_text = tk.Text(instruction_frame, wrap=tk.WORD, height=10, 
                                 font=("Arial", 10), bg="#f9f9f9")
        instruction_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        instruction_text.insert(tk.END, instructions)
        instruction_text.config(state=tk.DISABLED)  # 设为只读
        
    def find_models(self):
        """
        查找可用的模型文件
        """
        models = []
        
        # 首先检查指定的模型路径
        specific_model_path = r"D:\Program Files\smartsub\whisper-models\ggml-large-v3.bin"
        if os.path.exists(specific_model_path):
            models.append(specific_model_path)
            self.log(f"找到指定模型: {specific_model_path}")
        
        # 然后检查本地models目录
        models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        if not os.path.exists(models_dir):
            os.makedirs(models_dir)
            self.log(f"创建模型目录: {models_dir}")
        
        # 查找本地模型文件
        for model_file in glob.glob(os.path.join(models_dir, "*.bin")):
            if model_file not in models:  # 避免重复
                models.append(model_file)
        
        if models:
            self.model_combo['values'] = models
            self.model_combo.current(0)
            self.log(f"找到 {len(models)} 个模型文件")
        else:
            self.model_combo['values'] = ["未找到模型文件"]
            self.model_combo.current(0)
            self.log("未找到模型文件，请将模型文件放在models目录中")
            messagebox.showinfo("提示", "未找到模型文件，请将模型文件放在models目录中，或者指定模型文件路径")
    
    def refresh_voice_models(self):
        """
        刷新语音识别模型列表
        """
        models = []
        
        # 首先检查指定的模型路径
        specific_model_paths = [
            r"D:\Program Files\smartsub\whisper-models\ggml-large-v3.bin",
            r"D:\Program Files\smartsub\whisper-models\ggml-medium.bin",
            r"D:\Program Files\smartsub\whisper-models\ggml-small.bin",
            r"D:\Program Files\smartsub\whisper-models\ggml-base.bin",
            r"D:\Program Files\smartsub\whisper-models\ggml-tiny.bin"
        ]
        
        for model_path in specific_model_paths:
            if os.path.exists(model_path):
                # 只显示文件名，而不是完整路径
                model_name = os.path.basename(model_path)
                models.append((model_name, model_path))
                self.log(f"找到指定模型: {model_name}")
        
        # 然后检查本地models目录
        models_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models")
        if os.path.exists(models_dir):
            # 查找本地模型文件
            for model_file in glob.glob(os.path.join(models_dir, "*.bin")):
                model_name = os.path.basename(model_file)
                model_path = model_file
                # 避免重复
                if not any(existing_name == model_name for existing_name, _ in models):
                    models.append((model_name, model_path))
                    self.log(f"找到本地模型: {model_name}")
        
        if models:
            # 显示模型名称，存储完整路径
            model_names = [name for name, _ in models]
            self.voice_model_combo['values'] = model_names
            
            # 存储模型路径映射
            self.voice_model_paths = {name: path for name, path in models}
            
            # 如果有当前选择的模型，尝试保持选择
            current_model = self.voice_model_var.get()
            if current_model in model_names:
                self.voice_model_combo.current(model_names.index(current_model))
            else:
                self.voice_model_combo.current(0)
                self.voice_model_var.set(model_names[0])
                
            self.log(f"找到 {len(models)} 个语音识别模型")
        else:
            self.voice_model_combo['values'] = ["未找到模型文件"]
            self.voice_model_combo.current(0)
            self.voice_model_var.set("")
            self.voice_model_paths = {}
            self.log("未找到语音识别模型文件")
            messagebox.showinfo("提示", "未找到语音识别模型文件，请将模型文件放在models目录中")
    
    def save_voice_model_setting(self):
        """
        保存语音识别模型设置
        """
        selected_model = self.voice_model_var.get()
        if not selected_model or selected_model == "未找到模型文件":
            messagebox.showwarning("警告", "请选择有效的语音识别模型")
            return
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新模型设置
        config["voice_model"] = selected_model
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"语音识别模型已设置为: {selected_model}")
        messagebox.showinfo("成功", f"语音识别模型已设置为: {selected_model}")
    
    def save_voice_language_setting(self):
        """
        保存语音识别语言设置
        """
        selected_lang = self.voice_lang_var.get()
        if not selected_lang:
            messagebox.showwarning("警告", "请选择有效的识别语言")
            return
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新语言设置
        config["voice_language"] = selected_lang
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"语音识别语言已设置为: {selected_lang}")
        messagebox.showinfo("成功", f"语音识别语言已设置为: {selected_lang}")
    
    def save_voice_output_language_setting(self):
        """
        保存语音识别输出语言设置
        """
        selected_output_lang = self.voice_output_lang_var.get()
        if not selected_output_lang:
            messagebox.showwarning("警告", "请选择有效的输出语言")
            return
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新输出语言设置
        config["voice_output_language"] = selected_output_lang
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"语音识别输出语言已设置为: {selected_output_lang}")
        messagebox.showinfo("成功", f"语音识别输出语言已设置为: {selected_output_lang}")
    
    def auto_input_text(self, text):
        """
        自动输入文本到当前光标位置
        
        参数:
            text: 要输入的文本
        """
        if not text or not self.auto_input_var.get():
            return
        
        # 预处理文本：将换行符和逗号替换为空格，并处理多个连续空格
        processed_text = text.replace('\n', ' ').replace('\r', ' ').replace(',', ' ')
        # 将多个连续空格替换为单个空格
        import re
        processed_text = re.sub(r'\s+', ' ', processed_text).strip()
        
        # 记录文本处理信息
        if text != processed_text:
            self.log(f"文本预处理: 原始文本='{repr(text)}' -> 处理后='{repr(processed_text)}'")
        
        input_method = self.input_method_var.get()
        
        try:
            if input_method == "paste":
                # 粘贴输入方式
                pyperclip.copy(processed_text)
                time.sleep(0.1)  # 等待复制完成
                
                # 模拟Ctrl+V粘贴
                from pynput import keyboard
                import threading
                
                def paste_text():
                    controller = keyboard.Controller()
                    with controller.pressed(keyboard.Key.ctrl):
                        controller.press(keyboard.Key.v)
                        controller.release(keyboard.Key.v)
                
                # 在新线程中执行，避免阻塞
                threading.Thread(target=paste_text, daemon=True).start()
                self.log("使用粘贴方式自动输入文本")
                
            elif input_method == "direct":
                # 直接输入方式
                from pynput import keyboard
                import threading
                
                def type_text():
                    controller = keyboard.Controller()
                    
                    # 逐个字符输入
                    for char in processed_text:
                        if char == '\n':
                            # 跳过换行符，不自动发送
                            continue
                        elif char == '\t':
                            controller.press(keyboard.Key.tab)
                            controller.release(keyboard.Key.tab)
                        elif char == ' ':
                            controller.press(keyboard.Key.space)
                            controller.release(keyboard.Key.space)
                        else:
                            # 处理特殊字符和大小写
                            try:
                                # 尝试直接输入字符
                                controller.type(char)
                            except:
                                # 如果失败，尝试使用shift组合
                                if char.isupper():
                                    with controller.pressed(keyboard.Key.shift):
                                        controller.type(char.lower())
                                else:
                                    controller.type(char)
                        
                        # 添加小延迟，避免输入过快
                        time.sleep(0.02)
                
                # 在新线程中执行，避免阻塞
                threading.Thread(target=type_text, daemon=True).start()
                self.log("使用直接输入方式自动输入文本")
                
        except Exception as e:
            self.log(f"自动输入失败: {e}")
    
    def update_auto_input_setting(self):
        """
        更新自动输入设置
        """
        auto_input_enabled = self.auto_input_var.get()
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新自动输入设置
        config["auto_input_enabled"] = auto_input_enabled
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"自动输入已{'启用' if auto_input_enabled else '禁用'}")
    
    def save_input_method_setting(self):
        """
        保存输入方式设置
        """
        input_method = self.input_method_var.get()
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新输入方式设置
        config["input_method"] = input_method
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"输入方式已设置为: {'粘贴输入' if input_method == 'paste' else '直接输入'}")
    
    def browse_file(self):
        """
        浏览并选择音频文件
        """
        filetypes = [
            ("音频文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a"),
            ("所有文件", "*.*")
        ]
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.single_file_var.set(file_path)
    
    def browse_directory(self):
        """
        浏览并选择目录
        """
        directory = filedialog.askdirectory()
        if directory:
            self.batch_dir_var.set(directory)
    
    def get_language_code(self):
        """
        获取语言代码
        
        返回:
            str: 语言代码，如果是自动检测则返回空字符串
        """
        lang = self.lang_var.get()
        if lang == "自动检测":
            return ""
        
        # 从选项中提取语言代码 (en, zh, ja, etc.)
        return lang.split("(")[1].split(")")[0] if "(" in lang else ""
    
    def log(self, message):
        """
        添加日志消息
        
        参数:
            message: 日志消息
        """
        timestamp = time.strftime("%H:%M:%S")
        
        # 检查是否有正式的日志文本组件
        if hasattr(self, 'log_text') and self.log_text.winfo_exists():
            log_widget = self.log_text
            # 更新日志统计
            if hasattr(self, 'update_log_stats'):
                self.update_log_stats()
        else:
            # 使用临时日志组件
            if not hasattr(self, 'temp_log_text'):
                return
            log_widget = self.temp_log_text
        
        # 插入日志消息
        try:
            log_widget.config(state='normal')
            log_widget.insert(tk.END, f"[{timestamp}] {message}\n")
            log_widget.see(tk.END)  # 滚动到最新消息
            log_widget.config(state='disabled')
            self.root.update_idletasks()  # 更新UI
        except:
            pass  # 忽略日志错误
    
    def paste_api_url(self):
        """
        粘贴API URL到输入框
        """
        try:
            import pyperclip
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                self.api_url_var.set(clipboard_content.strip())
                self.log("已粘贴API URL")
            else:
                self.log("剪贴板为空")
        except ImportError:
            self.log("缺少pyperclip库，无法使用粘贴功能")
        except Exception as e:
            self.log(f"粘贴API URL失败: {e}")
    
    def paste_api_key(self):
        """
        粘贴API Key到输入框
        """
        try:
            import pyperclip
            clipboard_content = pyperclip.paste()
            if clipboard_content:
                self.api_key_var.set(clipboard_content.strip())
                self.log("✅ 已粘贴API Key")
                self.update_status("✅ API Key已粘贴", "success")
            else:
                self.log("❌ 剪贴板为空")
                self.update_status("❌ 剪贴板为空", "error")
        except ImportError:
            self.log("❌ 缺少pyperclip库，无法使用粘贴功能")
            self.update_status("❌ 缺少pyperclip库", "error")
        except Exception as e:
            self.log(f"❌ 粘贴API Key失败: {e}")
            self.update_status("❌ 粘贴失败", "error")
    
    def quick_config_openrouter(self):
        """
        快速配置OpenRouter设置
        """
        self.ai_format_var.set("openai")
        self.api_url_var.set("https://openrouter.ai")
        self.cleaner_model_var.set("cognitivecomputations/dolphin-mistral-24b-venice-edition:free")
        self.update_ai_format_ui()
        self.log("✅ 已配置OpenRouter默认设置")
        self.update_status("✅ OpenRouter配置完成", "success")
        messagebox.showinfo("配置完成", "已配置OpenRouter默认设置：\n\nAI格式: OpenAI\nAPI URL: https://openrouter.ai\n模型: cognitivecomputations/dolphin-mistral-24b-venice-edition:free\n\n请粘贴您的API Key后点击测试连接")
    
    def quick_config_ollama(self):
        """
        快速配置Ollama设置
        """
        self.ai_format_var.set("ollama")
        self.api_url_var.set("http://localhost:11434")
        self.cleaner_model_var.set("llama3.1:8b")
        self.update_ai_format_ui()
        self.log("✅ 已配置Ollama默认设置")
        self.update_status("✅ Ollama配置完成", "success")
        messagebox.showinfo("配置完成", "已配置Ollama默认设置：\n\nAI格式: Ollama\nAPI URL: http://localhost:11434\n模型: llama3.1:8b\n\n请确保Ollama服务正在运行，然后点击测试连接")
    
    def quick_config_gemini(self):
        """
        快速配置Gemini设置
        """
        self.ai_format_var.set("gemini")
        self.api_url_var.set("https://generativelanguage.googleapis.com/v1beta")
        self.cleaner_model_var.set("gemini-1.5-flash")
        self.update_ai_format_ui()
        self.log("✅ 已配置Gemini默认设置")
        self.update_status("✅ Gemini配置完成", "success")
        messagebox.showinfo("配置完成", "已配置Gemini默认设置：\n\nAI格式: Gemini\nAPI URL: https://generativelanguage.googleapis.com/v1beta\n模型: gemini-1.5-flash\n\n请粘贴您的API Key后点击测试连接")
    
    def test_api_connection(self):
        """
        测试API连接
        """
        ai_format = self.ai_format_var.get()
        api_url = self.api_url_var.get()
        api_key = self.api_key_var.get()
        
        if not api_url:
            self.log("❌ 请先填写API URL")
            self.update_status("❌ 请先填写API配置", "error")
            return
        
        # Ollama格式可能不需要API Key
        if ai_format != "ollama" and not api_key:
            self.log("❌ 请先填写API Key")
            self.update_status("❌ 请先填写API配置", "error")
            return
        
        self.update_status("🔄 正在测试API连接...", "warning")
        self.log(f"🔄 开始测试{ai_format.upper()}格式API连接...")
        
        # 在新线程中测试，避免GUI冻结
        threading.Thread(target=self._test_api_connection_thread, args=(api_url, api_key, ai_format)).start()
    
    def _test_api_connection_thread(self, api_url, api_key, ai_format):
        """
        在线程中测试API连接
        """
        try:
            if not AUDIO_CLEANER_AVAILABLE:
                self.log("❌ 缺少必要的库，无法测试API连接")
                self.update_status("❌ 缺少依赖库", "error")
                return
            
            # 获取格式化的API URL
            formatted_url = self.get_formatted_api_url()
            if not formatted_url:
                self.log("❌ API URL格式化失败")
                self.update_status("❌ API URL格式错误", "error")
                return
            
            import openai
            self.log(f"使用格式化URL: {formatted_url}")
            
            if ai_format == "openai":
                # OpenAI格式调用
                client = openai.OpenAI(
                    api_key=api_key,
                    base_url=formatted_url,
                    timeout=30.0
                )
                
                # 测试简单对话
                response = client.chat.completions.create(
                    model=self.cleaner_model_var.get(),
                    messages=[{"role": "user", "content": "Hello"}],
                    temperature=0.1
                )
                
                self.log("✅ OpenAI格式API连接测试成功")
                self.log(f"📝 响应: {response.choices[0].message.content}")
                self.log(f"🤖 使用模型: {response.model}")
                self.update_status("✅ OpenAI API连接成功", "success")
                
            elif ai_format == "ollama":
                # Ollama格式调用
                client = openai.OpenAI(
                    base_url=formatted_url,
                    api_key="ollama",  # Ollama不需要真实的API Key
                    timeout=30.0
                )
                
                # 测试简单对话
                response = client.chat.completions.create(
                    model=self.cleaner_model_var.get(),
                    messages=[{"role": "user", "content": "Hello"}],
                    temperature=0.1
                )
                
                self.log("✅ Ollama格式API连接测试成功")
                self.log(f"📝 响应: {response.choices[0].message.content}")
                self.log(f"🤖 使用模型: {response.model}")
                self.update_status("✅ Ollama API连接成功", "success")
                
            elif ai_format == "gemini":
                # Gemini格式调用 - 需要特殊处理
                try:
                    # 尝试使用OpenAI兼容的方式调用Gemini
                    client = openai.OpenAI(
                        api_key=api_key,
                        base_url=formatted_url,
                        timeout=30.0
                    )
                    
                    # 测试简单对话
                    response = client.chat.completions.create(
                        model=self.cleaner_model_var.get(),
                        messages=[{"role": "user", "content": "Hello"}],
                        temperature=0.1
                    )
                    
                    self.log("✅ Gemini格式API连接测试成功")
                    self.log(f"📝 响应: {response.choices[0].message.content}")
                    self.log(f"🤖 使用模型: {response.model}")
                    self.update_status("✅ Gemini API连接成功", "success")
                    
                except Exception as gemini_error:
                    self.log(f"⚠ Gemini OpenAI兼容模式失败: {gemini_error}")
                    self.log("💡 提示: Gemini可能需要使用官方API或其他兼容方式")
                    self.update_status("⚠ Gemini连接可能需要特殊配置", "warning")
                    return
            
        except Exception as e:
            self.log(f"❌ {ai_format.upper()}格式API连接测试失败: {e}")
            self.update_status("❌ API连接失败", "error")
    
    def update_status(self, message, status_type="normal"):
        """
        更新状态栏和指示器
        
        参数:
            message: 状态消息
            status_type: 状态类型 (normal, success, warning, error)
        """
        self.status_var.set(message)
        
        # 更新状态指示器
        if status_type == "success":
            self.status_indicator.config(text="🟢")
        elif status_type == "warning":
            self.status_indicator.config(text="🟡")
        elif status_type == "error":
            self.status_indicator.config(text="🔴")
        else:
            self.status_indicator.config(text="🟢")
    
    def update_progress(self, value, status=""):
        """
        更新进度条和状态文本
        
        参数:
            value: 进度值 (0-100)
            status: 状态文本
        """
        if hasattr(self, 'progress_var'):
            self.progress_var.set(value)
        if hasattr(self, 'progress_status_var') and status:
            self.progress_status_var.set(status)
        
        # 确保界面更新
        self.root.update_idletasks()
    
    def clear_single_file(self):
        """
        清空单文件转录的输入
        """
        self.single_file_var.set("")
        self.update_status("✅ 已清空文件选择", "success")
        self.log("✅ 已清空文件选择")
    
    def get_model_path(self):
        """
        获取模型路径
        
        返回:
            str: 模型路径，如果未找到则返回None
        """
        model = self.model_var.get()
        if not model or model == "未找到模型文件":
            messagebox.showerror("错误", "请选择有效的模型文件")
            return None
            
        # 如果模型路径是完整路径，则直接使用；否则，将其视为models目录中的文件名
        if os.path.isabs(model) and os.path.exists(model):
            return model
        else:
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", model)
            if os.path.exists(model_path):
                return model_path
            else:
                messagebox.showerror("错误", f"模型文件不存在: {model_path}")
                return None
    
    def get_voice_model_path(self):
        """
        获取语音识别模型路径
        
        返回:
            str: 语音模型路径，如果未找到则返回None
        """
        selected_model = self.voice_model_var.get()
        if not selected_model or selected_model == "未找到模型文件":
            self.log("错误: 请选择有效的语音识别模型")
            return None
        
        # 从路径映射中获取完整路径
        if hasattr(self, 'voice_model_paths') and selected_model in self.voice_model_paths:
            model_path = self.voice_model_paths[selected_model]
            if os.path.exists(model_path):
                return model_path
            else:
                self.log(f"错误: 语音模型文件不存在: {model_path}")
                return None
        else:
            self.log(f"错误: 未找到语音模型路径映射: {selected_model}")
            return None
    
    def transcribe_single_file(self):
        """
        转录单个音频文件
        """
        audio_file = self.single_file_var.get()
        if not audio_file:
            messagebox.showerror("错误", "请选择音频文件")
            return
            
        if not os.path.exists(audio_file):
            messagebox.showerror("错误", f"文件不存在: {audio_file}")
            return
        
        model_path = self.get_model_path()
        if not model_path:
            return
            
        output_format = self.format_var.get()
        language = self.get_language_code()
        
        # 在新线程中运行转录，避免GUI冻结
        threading.Thread(target=self._run_transcribe_single, 
                         args=(audio_file, output_format, model_path, language)).start()
    
    def _run_transcribe_single(self, audio_file, output_format, model_path, language):
        """
        在线程中运行单文件转录
        """
        self.status_var.set(f"正在转录: {os.path.basename(audio_file)}")
        self.log(f"开始转录文件: {audio_file}")
        self.log(f"使用模型: {os.path.basename(model_path)}")
        self.log(f"输出格式: {output_format}")
        if language:
            self.log(f"语言设置: {language}")
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            self.status_var.set("转录失败")
            return
        
        command = [whisper_cli, "-m", model_path, "-f", audio_file, f"-o{output_format}"]
        
        # 如果指定了语言
        if language:
            command.extend(["-l", language])
        
        try:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
            
            # 检查错误
            stderr = process.stderr.read()
            if stderr:
                self.log(f"错误: {stderr}")
            
            if process.returncode == 0:
                output_file = f"{os.path.splitext(audio_file)[0]}.{output_format}"
                self.log(f"转录完成! 输出文件: {output_file}")
                self.status_var.set("转录完成")
            else:
                self.log(f"转录失败，返回代码: {process.returncode}")
                self.status_var.set("转录失败")
                
        except Exception as e:
            self.log(f"转录过程中出现错误: {e}")
            self.status_var.set("转录失败")
    
    def transcribe_batch(self):
        """
        批量转录目录中的音频文件
        """
        directory = self.batch_dir_var.get()
        if not directory:
            messagebox.showerror("错误", "请选择音频文件目录")
            return
            
        if not os.path.exists(directory) or not os.path.isdir(directory):
            messagebox.showerror("错误", f"目录不存在: {directory}")
            return
        
        model_path = self.get_model_path()
        if not model_path:
            return
            
        output_format = self.format_var.get()
        language = self.get_language_code()
        
        # 获取选中的文件扩展名
        extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
        if not extensions:
            messagebox.showerror("错误", "请至少选择一种文件类型")
            return
        
        # 在新线程中运行批量转录，避免GUI冻结
        threading.Thread(target=self._run_transcribe_batch, 
                         args=(directory, output_format, model_path, language, extensions)).start()
    
    def _run_transcribe_batch(self, directory, output_format, model_path, language, extensions):
        """
        在线程中运行批量转录
        """
        self.status_var.set("正在批量转录...")
        self.log(f"开始批量转录目录: {directory}")
        self.log(f"使用模型: {os.path.basename(model_path)}")
        self.log(f"输出格式: {output_format}")
        if language:
            self.log(f"语言设置: {language}")
        self.log(f"文件类型: {', '.join(extensions)}")
        
        # 查找所有匹配的音频文件
        audio_files = []
        for ext in extensions:
            audio_files.extend(glob.glob(os.path.join(directory, f"*{ext}")))
        
        if not audio_files:
            self.log(f"未找到匹配的音频文件")
            self.status_var.set("批量转录完成")
            return
        
        self.log(f"找到 {len(audio_files)} 个音频文件")
        
        # 转录每个文件
        success_count = 0
        fail_count = 0
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            self.status_var.set("转录失败")
            return
        
        for i, audio_file in enumerate(audio_files):
            self.log(f"[{i+1}/{len(audio_files)}] 转录文件: {os.path.basename(audio_file)}")
            
            command = [whisper_cli, "-m", model_path, "-f", audio_file, f"-o{output_format}"]
            
            # 如果指定了语言
            if language:
                command.extend(["-l", language])
            
            try:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
                
                # 实时读取输出
                while True:
                    output = process.stdout.readline()
                    if output == '' and process.poll() is not None:
                        break
                    if output:
                        self.log(f"  {output.strip()}")
                
                # 检查错误
                stderr = process.stderr.read()
                if stderr:
                    self.log(f"  错误: {stderr}")
                
                if process.returncode == 0:
                    output_file = f"{os.path.splitext(audio_file)[0]}.{output_format}"
                    self.log(f"  转录完成! 输出文件: {output_file}")
                    success_count += 1
                else:
                    self.log(f"  转录失败，返回代码: {process.returncode}")
                    fail_count += 1
                    
            except Exception as e:
                self.log(f"  转录过程中出现错误: {e}")
                fail_count += 1
        
        self.log(f"批量转录完成! 成功: {success_count}, 失败: {fail_count}")
        self.status_var.set("批量转录完成")
    
    def toggle_voice_service(self):
        """
        切换语音转文字服务的状态
        """
        if not VOICE_SERVICE_AVAILABLE:
            messagebox.showerror("错误", "缺少必要的依赖库，无法使用语音转文字服务")
            return
            
        if not self.voice_service_active:
            # 启动服务
            self.start_voice_service()
        else:
            # 停止服务
            self.stop_voice_service()
    
    def start_voice_service(self):
        """
        启动语音转文字服务
        """
        model_path = self.get_model_path()
        if not model_path:
            return
            
        self.voice_service_active = True
        self.service_status_var.set("已启动")
        self.start_service_btn.config(text="停止服务")
        self.log("语音转文字服务已启动")
        self.log("第一次按下Caps Lock键开始录音，再次按下Caps Lock键结束录音并转录")
        
        # 设置键盘监听器
        self.keyboard_listener = keyboard.Listener(
            on_press=self.on_press,
            on_release=self.on_release
        )
        self.keyboard_listener.start()
    
    def stop_voice_service(self):
        """
        停止语音转文字服务
        """
        self.voice_service_active = False
        self.service_status_var.set("未启动")
        self.start_service_btn.config(text="启动服务")
        self.log("语音转文字服务已停止")
        
        # 停止键盘监听器
        if self.keyboard_listener:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
        
        # 如果正在录音，停止录音
        if self.is_recording:
            self.stop_recording()
        
        # 停止服务时清理所有临时文件
        self.cleanup_all_temp_files()
    
    def play_start_sound(self):
        """
        播放开始录音提示音
        """
        try:
            if hasattr(self, 'start_sound_var') and self.start_sound_var.get():
                import winsound
                freq = int(self.start_freq_var.get())
                duration = int(self.duration_var.get())
                winsound.Beep(freq, duration)
        except Exception as e:
            self.log(f"播放开始提示音失败: {e}")
    
    def play_end_sound(self):
        """
        播放结束录音提示音
        """
        try:
            if hasattr(self, 'end_sound_var') and self.end_sound_var.get():
                import winsound
                freq = int(self.end_freq_var.get())
                duration = int(self.duration_var.get())
                winsound.Beep(freq, duration)
        except Exception as e:
            self.log(f"播放结束提示音失败: {e}")
    
    def get_hotkey_from_string(self, key_string):
        """
        将快捷键字符串转换为pynput键对象
        
        参数:
            key_string: 快捷键字符串
            
        返回:
            pynput键对象
        """
        key_mapping = {
            "caps_lock": keyboard.Key.caps_lock,
            "space": keyboard.Key.space,
            "enter": keyboard.Key.enter,
            "tab": keyboard.Key.tab,
            "esc": keyboard.Key.esc,
            "shift": keyboard.Key.shift,
            "ctrl": keyboard.Key.ctrl,
            "alt": keyboard.Key.alt,
            "f1": keyboard.Key.f1,
            "f2": keyboard.Key.f2,
            "f3": keyboard.Key.f3,
            "f4": keyboard.Key.f4,
            "f5": keyboard.Key.f5,
            "f6": keyboard.Key.f6,
            "f7": keyboard.Key.f7,
            "f8": keyboard.Key.f8,
            "f9": keyboard.Key.f9,
            "f10": keyboard.Key.f10,
            "f11": keyboard.Key.f11,
            "f12": keyboard.Key.f12,
        }
        
        # 添加数字键支持
        for i in range(10):
            key_mapping[str(i)] = keyboard.KeyCode.from_char(str(i))
        
        # 添加字母键支持
        for letter in 'abcdefghijklmnopqrstuvwxyz':
            key_mapping[letter] = keyboard.KeyCode.from_char(letter)
        
        # 小键盘按键在on_press中特殊处理，这里返回一个特殊标记
        numpad_keys = {
            "num_0": "NUMPAD_SPECIAL",
            "num_1": "NUMPAD_SPECIAL", 
            "num_2": "NUMPAD_SPECIAL",
            "num_3": "NUMPAD_SPECIAL",
            "num_4": "NUMPAD_SPECIAL",
            "num_5": "NUMPAD_SPECIAL",
            "num_6": "NUMPAD_SPECIAL",
            "num_7": "NUMPAD_SPECIAL",
            "num_8": "NUMPAD_SPECIAL",
            "num_9": "NUMPAD_SPECIAL",
            "num_multiply": "NUMPAD_SPECIAL",
            "num_add": "NUMPAD_SPECIAL",
            "num_subtract": "NUMPAD_SPECIAL",
            "num_decimal": "NUMPAD_SPECIAL",
            "num_divide": "NUMPAD_SPECIAL",
        }
        key_mapping.update(numpad_keys)
        
        return key_mapping.get(key_string.lower(), keyboard.Key.caps_lock)
    
    def get_current_hotkey(self):
        """
        获取当前配置的快捷键对象
        """
        try:
            if hasattr(self, 'hotkey_var'):
                hotkey_string = self.hotkey_var.get()
                return self.get_hotkey_from_string(hotkey_string)
            else:
                return keyboard.Key.caps_lock
        except:
            return keyboard.Key.caps_lock
    
    def on_press(self, key):
        """
        按键按下事件处理
        
        参数:
            key: 按下的键
        """
        try:
            if not self.voice_service_active:
                return
                
            hotkey_string = self.hotkey_var.get().lower()
            
            # 特殊处理小键盘按键 - 通过虚拟键码直接比较
            if hasattr(key, 'vk') and key.vk is not None:
                # 小键盘0-9的虚拟键码是96-105
                if hotkey_string.startswith('num_') and hotkey_string in ['num_0', 'num_1', 'num_2', 'num_3', 'num_4', 'num_5', 'num_6', 'num_7', 'num_8', 'num_9']:
                    # 提取数字
                    num = int(hotkey_string.split('_')[1])
                    expected_vk = 96 + num  # 小键盘0的vk是96，1是97，以此类推
                    
                    if key.vk == expected_vk:
                        self.toggle_recording()
                        return
                # 普通数字键的虚拟键码是48-57
                elif hotkey_string in ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9']:
                    num = int(hotkey_string)
                    expected_vk = 48 + num  # 普通数字键0的vk是48，1是49，以此类推
                    
                    if key.vk == expected_vk:
                        self.toggle_recording()
                        return
            
            # 获取当前配置的快捷键对象（用于非小键盘按键）
            current_hotkey = self.get_current_hotkey()
            
            # 普通按键比较（如果不是小键盘特殊标记）
            if current_hotkey != "NUMPAD_SPECIAL" and key == current_hotkey:
                self.toggle_recording()
                
        except Exception as e:
            self.log(f"按键处理错误: {e}")
    
    def toggle_recording(self):
        """切换录音状态"""
        if not self.is_recording:
            self.start_recording()
        else:
            self.stop_recording()
            self.process_audio()
    
    def on_release(self, key):
        """
        按键释放事件处理
        
        参数:
            key: 释放的键
        """
        # Caps Lock键的录音控制已经在on_press中处理，这里不需要额外处理
        pass
    
    def start_recording(self):
        """
        开始录音
        """
        self.is_recording = True
        self.recorded_frames = []  # 清空之前的录音
        self.log("开始录音...")
        self.status_var.set("正在录音...")
        
        # 播放开始录音提示音
        self.play_start_sound()
        
        # 在新线程中启动录音，避免阻塞主线程
        threading.Thread(target=self._record_audio).start()
    
    def _record_audio(self):
        """
        录制音频的内部方法
        """
        try:
            with sd.InputStream(samplerate=self.sample_rate, channels=1, callback=self._audio_callback):
                while self.is_recording:
                    time.sleep(0.1)
        except Exception as e:
            self.is_recording = False
            self.log(f"录音错误: {e}")
            self.status_var.set("录音失败")
    
    def _audio_callback(self, indata, frames, time, status):
        """
        音频数据回调函数
        
        参数:
            indata: 输入的音频数据
            frames: 帧数
            time: 时间信息
            status: 状态信息
        """
        if status:
            self.log(f"音频回调状态: {status}")
        if self.is_recording:
            self.recorded_frames.append(indata.copy())
    
    def stop_recording(self):
        """
        停止录音
        """
        self.is_recording = False
        self.log("录音结束")
        self.status_var.set("正在处理录音...")
        
        # 播放结束录音提示音
        self.play_end_sound()
    
    def process_audio(self):
        """
        处理录制的音频
        """
        if not self.recorded_frames:
            self.log("没有录制到音频数据")
            self.status_var.set("就绪")
            return
        
        try:
            # 重置进度条
            self.update_progress(0, "开始处理音频...")
            
            # 将录音数据转换为numpy数组
            self.update_progress(10, "转换音频数据...")
            audio_data = np.concatenate(self.recorded_frames, axis=0)
            
            # 保存为临时WAV文件
            self.update_progress(20, "保存音频文件...")
            temp_file = os.path.join(self.temp_dir, "temp_recording.wav")
            # 确保音频数据格式正确（16位整数）
            audio_data_int16 = np.int16(audio_data * 32767)
            wavfile.write(temp_file, self.sample_rate, audio_data_int16)
            
            self.log(f"音频已保存到临时文件: {temp_file}")
            
            # 转录音频
            self.update_progress(40, "转录音频中...")
            text = self.transcribe_audio(temp_file)
            self.update_progress(70, "转录完成")
            
            # AI后处理
            if text and self.voice_ai_enabled:
                self.update_progress(80, "语音转文字AI处理中...")
                self.log("🤖 开始语音转文字AI文本处理...")
                self.log(f"📝 原始转录文本: {text}")
                processed_text = self.process_text_with_voice_ai(text)
                if processed_text != text:
                    self.log("✅ 语音转文字AI处理完成，文本已优化")
                    self.log(f"🔤 优化后文本: {processed_text}")
                    text = processed_text
                else:
                    self.log("⚪ 语音转文字AI处理完成，文本无变化")
                    self.log(f"📄 保持原始文本: {text}")
            else:
                if text:
                    if not self.voice_ai_enabled:
                        self.log("⏸️ 语音转文字AI文本处理已禁用，直接使用原始转录文本")
                    self.log(f"📄 转录结果: {text}")
            
            # 显示转录结果
            if text:
                self.update_progress(100, "处理完成")
                # 清空之前的文本并显示新的转录结果
                self.transcription_text.delete("1.0", tk.END)
                self.transcription_text.insert(tk.END, text)
                self.log(f"转录完成: {text}")
                self.status_var.set("转录完成")
                
                # 同时复制到剪贴板
                try:
                    pyperclip.copy(text)
                    self.log("文本已自动复制到剪贴板")
                except Exception as e:
                    self.log(f"自动复制到剪贴板失败: {e}")
                
                # 自动输入文本
                self.auto_input_text(text)
            else:
                self.log("转录失败，未获得文本")
                self.status_var.set("转录失败")
            
            # 清理临时文件
            self.cleanup_temp_file(temp_file)
            
        except Exception as e:
            self.log(f"处理音频时出错: {e}")
            self.status_var.set("处理音频失败")
            # 清理临时文件
            self.cleanup_temp_file(temp_file)
    
    def transcribe_audio_segments(self, audio_file):
        """
        分段转录音频文件并实时输入
        
        参数:
            audio_file: 音频文件路径
            
        返回:
            str: 完整转录的文本，如果转录失败则返回None
        """
        model_path = self.get_voice_model_path()
        if not model_path:
            return None
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            return None
        
        # 分段处理 - 将音频分成较小的段进行处理
        import soundfile as sf
        
        try:
            # 读取音频文件
            data, sample_rate = sf.read(audio_file)
            
            # 如果是立体声，转换为单声道
            if len(data.shape) > 1:
                data = data.mean(axis=1)
            
            # 每段大约3秒的音频
            segment_length = sample_rate * 3
            segments = []
            
            # 分割音频
            for i in range(0, len(data), segment_length):
                segment = data[i:i + segment_length]
                if len(segment) > 0:
                    segments.append(segment)
            
            self.log(f"音频已分割为 {len(segments)} 个片段")
            
            # 完整转录结果
            full_transcription = ""
            
            # 逐段处理
            for i, segment in enumerate(segments):
                # 保存临时段文件
                segment_file = os.path.join(self.temp_dir, f"segment_{i}.wav")
                sf.write(segment_file, segment, sample_rate)
                
                # 转录当前段
                segment_text = self._transcribe_segment(segment_file)
                
                if segment_text:
                    # 添加到完整转录
                    full_transcription += segment_text + " "
                    
                    # 实时输入当前段
                    if self.auto_input_var.get():
                        self.auto_input_text(segment_text)
                        self.log(f"第 {i+1} 段已输入: {segment_text}")
                
                # 清理临时段文件
                self.cleanup_temp_file(segment_file)
                
                # 小延迟，避免输入过快
                time.sleep(0.1)
            
            return full_transcription.strip()
            
        except Exception as e:
            self.log(f"分段转录失败: {e}")
            # 如果分段失败，尝试整体转录
            return self.transcribe_audio_full(audio_file)
    
    def _transcribe_segment(self, audio_file):
        """
        转录单个音频片段
        
        参数:
            audio_file: 音频文件路径
            
        返回:
            str: 转录的文本，如果转录失败则返回None
        """
        model_path = self.get_voice_model_path()
        if not model_path:
            return None
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            return None
        
        # 临时输出文件
        output_file = audio_file + ".txt"
        
        command = [whisper_cli, "-m", model_path, "-f", audio_file, "-otxt"]
        
        # 添加语言参数
        voice_lang = self.voice_lang_var.get()
        if voice_lang and voice_lang != "auto":
            command.extend(["-l", voice_lang])
        
        # 添加输出语言参数（如果支持）
        voice_output_lang = self.voice_output_lang_var.get()
        if voice_output_lang and voice_output_lang != "auto":
            # whisper-cli 只支持翻译成英语
            if voice_output_lang == "en":
                command.extend(["--translate"])
                self.log(f"翻译到英语")
            elif voice_output_lang != voice_lang:
                # 如果输出语言不是英语且与识别语言不同，提示用户
                self.log(f"注意: whisper-cli 只支持翻译成英语，当前设置输出语言为 {voice_output_lang}")
                self.log(f"建议: 如果需要翻译成英语，请将输出语言设置为 'en'")
        
        try:
            # 静默运行段转录
            process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=30)
            
            # 检查输出文件
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                
                # 清理输出文件
                try:
                    os.remove(output_file)
                except:
                    pass
                
                return text if text else None
            else:
                return None
                
        except Exception as e:
            self.log(f"段转录失败: {e}")
            return None
    
    def transcribe_audio(self, audio_file):
        """
        转录音频文件（保持向后兼容）
        
        参数:
            audio_file: 音频文件路径
            
        返回:
            str: 转录的文本，如果转录失败则返回None
        """
        model_path = self.get_voice_model_path()
        if not model_path:
            return None
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            return None
        
        # 临时输出文件 (whisper-cli会在原文件名后加.txt扩展名)
        output_file = audio_file + ".txt"
        
        command = [whisper_cli, "-m", model_path, "-f", audio_file, "-otxt"]
        
        # 添加语言参数
        voice_lang = self.voice_lang_var.get()
        if voice_lang and voice_lang != "auto":
            command.extend(["-l", voice_lang])
            self.log(f"使用识别语言: {voice_lang}")
        
        # 添加输出语言参数（如果支持）
        voice_output_lang = self.voice_output_lang_var.get()
        if voice_output_lang and voice_output_lang != "auto":
            # whisper-cli 只支持翻译成英语
            if voice_output_lang == "en":
                command.extend(["--translate"])
                self.log(f"翻译到英语")
            elif voice_output_lang != voice_lang:
                # 如果输出语言不是英语且与识别语言不同，提示用户
                self.log(f"注意: whisper-cli 只支持翻译成英语，当前设置输出语言为 {voice_output_lang}")
                self.log(f"建议: 如果需要翻译成英语，请将输出语言设置为 'en'")
        
        try:
            self.log("开始转录...")
            self.log(f"执行命令: {' '.join(command)}")
            
            # 使用Popen来实时获取输出
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='replace')
            
            # 实时读取输出
            stdout_lines = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    stdout_lines.append(output.strip())
                    self.log(f"whisper输出: {output.strip()}")
            
            # 读取错误输出
            stderr = process.stderr.read()
            if stderr:
                self.log(f"whisper错误: {stderr}")
            
            self.log(f"转录进程返回代码: {process.returncode}")
            
            # 检查输出文件是否存在
            if os.path.exists(output_file):
                with open(output_file, 'r', encoding='utf-8') as f:
                    text = f.read().strip()
                self.log("转录完成")
                self.log(f"转录结果: {text}")
                return text
            else:
                self.log(f"转录后的文本文件不存在: {output_file}")
                # 检查当前目录下是否有其他输出文件
                temp_dir = os.path.dirname(audio_file)
                possible_files = [f for f in os.listdir(temp_dir) if f.startswith('temp_recording')]
                self.log(f"临时目录中的文件: {possible_files}")
                return None
                
        except subprocess.CalledProcessError as e:
            self.log(f"转录过程中出现错误: {e}")
            if e.stderr:
                self.log(f"错误信息: {e.stderr}")
            return None
        except Exception as e:
            self.log(f"转录过程中出现未知错误: {e}")
            return None
    
    def copy_transcription(self):
        """
        复制转录文本到剪贴板
        """
        try:
            text = self.transcription_text.get("1.0", tk.END).strip()
            if text:
                pyperclip.copy(text)
                self.log("转录文本已复制到剪贴板")
                self.status_var.set("文本已复制到剪贴板")
            else:
                self.log("没有可复制的文本")
                self.status_var.set("没有可复制的文本")
        except Exception as e:
            self.log(f"复制文本时出错: {e}")
            self.status_var.set("复制失败")
    
    def clear_transcription(self):
        """
        清空转录文本
        """
        self.transcription_text.delete("1.0", tk.END)
        self.log("已清空转录文本")
        self.status_var.set("文本已清空")
    
    def install_dependencies(self):
        """
        安装必要的依赖库
        """
        self.log("正在安装依赖库...")
        self.status_var.set("正在安装依赖库...")
        
        # 在新线程中运行安装，避免GUI冻结
        threading.Thread(target=self._run_install_dependencies).start()
    
    def _run_install_dependencies(self):
        """
        在线程中运行依赖库安装
        """
        try:
            command = [sys.executable, "-m", "pip", "install", "pynput", "sounddevice", "numpy", "pyperclip", "scipy"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # 实时读取输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
            
            # 检查错误
            stderr = process.stderr.read()
            if stderr:
                self.log(f"错误: {stderr}")
            
            if process.returncode == 0:
                self.log("依赖库安装完成，请重启应用")
                self.status_var.set("依赖库安装完成")
                messagebox.showinfo("提示", "依赖库安装完成，请重启应用以使用语音转文字服务")
            else:
                self.log(f"依赖库安装失败，返回代码: {process.returncode}")
                self.status_var.set("依赖库安装失败")
                
        except Exception as e:
            self.log(f"安装依赖库时出错: {e}")
            self.status_var.set("依赖库安装失败")
    
    def cleanup_temp_file(self, temp_file):
        """
        清理临时文件
        
        参数:
            temp_file: 临时文件路径
        """
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                self.log(f"临时文件已清理: {temp_file}")
                
            # 同时清理转录产生的输出文件 (whisper-cli会在原文件名后加.txt扩展名)
            output_file = temp_file + ".txt"
            if os.path.exists(output_file):
                os.remove(output_file)
                self.log(f"转录输出文件已清理: {output_file}")
                
        except Exception as e:
            self.log(f"清理临时文件时出错: {e}")
    
    def cleanup_all_temp_files(self):
        """
        清理所有临时文件
        """
        try:
            # 清理临时目录中的录音文件
            temp_files = glob.glob(os.path.join(self.temp_dir, "temp_recording.wav"))
            temp_files.extend(glob.glob(os.path.join(self.temp_dir, "temp_recording.wav.txt")))
            temp_files.extend(glob.glob(os.path.join(self.temp_dir, "temp_recording.txt")))
            
            cleaned_count = 0
            for temp_file in temp_files:
                try:
                    os.remove(temp_file)
                    self.log(f"清理临时文件: {temp_file}")
                    cleaned_count += 1
                except Exception as e:
                    self.log(f"清理文件失败: {temp_file} - {e}")
            
            if cleaned_count > 0:
                self.log(f"已清理 {cleaned_count} 个临时文件")
                self.status_var.set(f"已清理 {cleaned_count} 个临时文件")
            else:
                self.log("没有找到需要清理的临时文件")
                self.status_var.set("没有找到需要清理的临时文件")
                
        except Exception as e:
            self.log(f"清理临时文件时出错: {e}")
            self.status_var.set("清理失败")
    
    def get_default_system_prompt(self):
        """
        获取默认的系统提示词
        
        返回:
            str: 默认的系统提示词
        """
        return """你是一个音频内容质量分析师。请仔细分析以下音频转录文本片段，识别出需要删除的低质量内容。

请重点关注以下类型的问题：
1. 录了一半的句子（突然中断的句子）
2. 重复录制的内容（同一句话说了多遍）
3. 录音失败的部分（含糊不清、杂音干扰）
4. 口误后重新说的话（说错了重新说）
5. 明显的废话和无意义的填充词

请返回一个JSON数组，包含所有需要删除的片段索引号（基于片段编号，不是数组索引）。
例如：如果要删除片段3和片段7，返回 [3, 7]

只返回JSON数组，不要包含其他文字。"""
    
    def browse_cleaner_audio(self):
        """
        浏览并选择音频文件
        """
        filetypes = [
            ("音频文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a"),
            ("所有文件", "*.*")
        ]
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.cleaner_audio_var.set(file_path)
            # 自动设置输出文件名 - 确保在同一目录下
            audio_dir = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            output_path = os.path.join(audio_dir, f"{base_name}_cleaned.mp3")
            self.cleaner_output_var.set(output_path)
            
            # 自动设置HRT字幕输出路径
            hrt_path = os.path.join(audio_dir, f"{base_name}_hrt.srt")
            self.hrt_output_var.set(hrt_path)
            
            self.log(f"设置输出路径: {output_path}")
            self.log(f"设置HRT字幕路径: {hrt_path}")
    
    def update_system_prompt(self, text_widget):
        """
        更新系统提示词
        
        参数:
            text_widget: 包含新提示词的文本控件
        """
        new_prompt = text_widget.get("1.0", tk.END).strip()
        self.system_prompt_var.set(new_prompt)
        
        # 自动保存到配置文件
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cleaner_config.json")
            settings = {}
            
            # 如果配置文件存在，先读取现有设置
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
            
            # 更新系统提示词
            settings['system_prompt'] = new_prompt
            
            # 保存到配置文件
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            self.log("系统提示词已更新并保存")
            messagebox.showinfo("提示", "系统提示词已更新并保存")
        except Exception as e:
            self.log(f"保存系统提示词失败: {e}")
            messagebox.showwarning("提示", f"系统提示词已更新，但保存失败: {e}")
    
    def reset_cleaner_settings(self):
        """
        重置音频清理设置
        """
        self.api_url_var.set("https://api.openai.com/v1")
        self.api_key_var.set("")
        self.cleaner_model_var.set("gpt-3.5-turbo")
        self.max_segment_var.set("50")
        self.gap_threshold_var.set("1.0")
        self.system_prompt_var.set(self.get_default_system_prompt())
        self.log("音频清理设置已重置")
        messagebox.showinfo("提示", "设置已重置")
    
    def start_audio_cleaning(self):
        """
        开始音频清理处理
        """
        # 验证输入
        audio_file = self.cleaner_audio_var.get()
        if not audio_file:
            messagebox.showerror("错误", "请选择音频文件")
            return
            
        if not os.path.exists(audio_file):
            messagebox.showerror("错误", f"文件不存在: {audio_file}")
            return
        
        api_url = self.api_url_var.get()
        if not api_url:
            messagebox.showerror("错误", "请输入API URL")
            return
            
        api_key = self.api_key_var.get()
        if not api_key:
            messagebox.showerror("错误", "请输入API Key")
            return
        
        output_file = self.cleaner_output_var.get()
        if not output_file:
            messagebox.showerror("错误", "请设置输出文件路径")
            return
        
        # 验证数值设置
        try:
            max_segment_length = int(self.max_segment_var.get())
            gap_threshold = float(self.gap_threshold_var.get())
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数值设置")
            return
        
        # 在新线程中运行音频清理，避免GUI冻结
        threading.Thread(target=self._run_audio_cleaning, 
                         args=(audio_file, output_file, api_url, api_key, 
                              self.cleaner_model_var.get(), max_segment_length, gap_threshold)).start()
    
    def _run_audio_cleaning(self, audio_file, output_file, api_url, api_key, model_name, max_segment_length, gap_threshold):
        """
        在线程中运行音频清理
        """
        try:
            self.status_var.set("正在清理音频...")
            self.log(f"开始清理音频: {audio_file}")
            self.log(f"输出文件: {output_file}")
            self.log(f"API URL: {api_url}")
            self.log(f"模型: {model_name}")
            
            # 1. 使用whisper生成SRT文件
            self.cleaner_status_var.set("📝 步骤1: 生成字幕文件...")
            self.log("步骤1: 使用whisper生成SRT文件...")
            srt_file = self.generate_srt_from_audio(audio_file)
            
            # 2. 解析SRT文件
            self.cleaner_status_var.set("🔍 步骤2: 分析字幕片段...")
            self.log("步骤2: 解析SRT文件...")
            segments = self.parse_srt_file(srt_file)
            
            if not segments:
                self.log("错误: 未能解析到有效的SRT片段")
                self.status_var.set("清理失败")
                return
            
            # 3. 优化SRT片段
            self.cleaner_status_var.set("⚡ 步骤3: 优化字幕片段...")
            self.log("步骤3: 优化SRT片段...")
            optimized_segments = self.optimize_srt_segments(segments, max_segment_length, gap_threshold)
            
            # 4. 格式化文本供LLM分析
            self.cleaner_status_var.set("🤖 步骤4: AI智能分析...")
            self.log("步骤4: 准备LLM分析...")
            formatted_text = self.format_text_for_llm(optimized_segments)
            
            # 5. 调用LLM分析
            self.cleaner_status_var.set("🧠 步骤5: AI质量评估...")
            self.log("步骤5: 调用LLM分析...")
            self.log(f"准备发送的文本片段数量: {len(optimized_segments)}")
            self.log(f"格式化文本预览: {formatted_text[:200]}..." if len(formatted_text) > 200 else f"格式化文本: {formatted_text}")
            
            api_config = {
                'api_url': api_url,
                'api_key': api_key,
                'model_name': model_name
            }
            
            self.log("即将调用get_llm_judgment方法...")
            indices_to_delete = self.get_llm_judgment(formatted_text, api_config)
            self.log(f"LLM返回结果: {indices_to_delete}")
            self.log(f"建议删除的片段数量: {len(indices_to_delete) if indices_to_delete else 0}")
            
            # 6. 执行音频编辑
            self.cleaner_status_var.set("✂️ 步骤6: 剪辑音频文件...")
            self.log("步骤6: 处理音频文件...")
            self.execute_audio_edit(audio_file, optimized_segments, indices_to_delete, output_file)
            
            # 7. 二次转录和HRT字幕生成
            if self.enable_secondary_var.get():
                self.cleaner_status_var.set("🎙️ 步骤7: 二次转录音频...")
                self.log("步骤7: 开始二次转录（对清理后的音频再次语音识别）...")
                hrt_subtitle_file = self.generate_hrt_subtitles(output_file)
                if hrt_subtitle_file:
                    self.log(f"✓ 二次转录完成，HRT字幕生成: {hrt_subtitle_file}")
                    self.log("音频清理和二次转录全部完成!")
                    self.cleaner_status_var.set("✅ 全部完成!")
                    self.status_var.set("清理完成")
                    messagebox.showinfo("完成", f"🎉 处理完成!\n📁 清理音频: {output_file}\n🎬 HRT字幕: {hrt_subtitle_file}")
                else:
                    self.log("⚠ 二次转录失败，但音频清理已完成")
                    self.cleaner_status_var.set("⚠ 部分完成")
                    self.status_var.set("清理完成")
                    messagebox.showinfo("完成", f"✅ 音频清理完成!\n📁 输出文件: {output_file}\n⚠️ 注意: 二次转录失败")
            else:
                self.log("音频清理完成!")
                self.cleaner_status_var.set("✅ 清理完成!")
                self.status_var.set("清理完成")
                messagebox.showinfo("完成", f"✅ 音频清理完成!\n📁 输出文件: {output_file}")
            
        except Exception as e:
            self.log(f"音频清理过程中出现错误: {e}")
            self.status_var.set("清理失败")
            messagebox.showerror("错误", f"音频清理失败: {e}")
    
    def generate_srt_from_audio(self, audio_file: str) -> str:
        """使用whisper生成SRT文件"""
        self.log(f"正在使用whisper识别音频: {audio_file}")
        
        srt_file = os.path.splitext(audio_file)[0] + '.srt'
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        
        if not os.path.exists(whisper_cli):
            raise Exception(f"未找到whisper-cli.exe: {whisper_cli}")
        
        # 确保输出目录存在
        output_dir = os.path.dirname(os.path.abspath(audio_file))
        self.log(f"输出目录: {output_dir}")
        
        cmd = [whisper_cli, audio_file, '--output_srt', '--output_dir', output_dir, '--language', 'zh']
        self.log(f"执行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log(f"Whisper输出: {result.stdout}")
            if result.stderr:
                self.log(f"Whisper错误: {result.stderr}")
            
            # 检查SRT文件是否真的生成
            if os.path.exists(srt_file):
                self.log(f"✓ SRT文件生成成功: {srt_file}")
                return srt_file
            else:
                # 尝试查找可能的输出文件
                audio_dir = os.path.dirname(audio_file)
                audio_name = os.path.splitext(os.path.basename(audio_file))[0]
                possible_files = [
                    os.path.join(audio_dir, f"{audio_name}.srt"),
                    os.path.join(output_dir, f"{audio_name}.srt")
                ]
                
                for possible_file in possible_files:
                    if os.path.exists(possible_file):
                        self.log(f"✓ 找到SRT文件: {possible_file}")
                        return possible_file
                
                raise Exception(f"SRT文件未生成，期望路径: {srt_file}")
        except subprocess.CalledProcessError as e:
            self.log(f"❌ Whisper执行失败: {e}")
            self.log(f"错误输出: {e.stderr}")
            raise
    
    def parse_srt_file(self, file_path: str) -> list:
        """解析SRT文件"""
        self.log(f"正在解析SRT文件: {file_path}")
        
        segments = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            pattern = r'(\d+)\n(\d{2}:\d{2}:\d{2},\d{3}) --> (\d{2}:\d{2}:\d{2},\d{3})\n([\s\S]*?)(?=\n\n|\Z)'
            matches = re.findall(pattern, content)
            
            for match in matches:
                index = int(match[0])
                start_time = match[1]
                end_time = match[2]
                text = match[3].strip()
                
                start_ms = self.time_to_ms(start_time)
                end_ms = self.time_to_ms(end_time)
                
                segments.append({
                    'index': index,
                    'start_time_ms': start_ms,
                    'end_time_ms': end_ms,
                    'start_time': start_time,
                    'end_time': end_time,
                    'text': text,
                    'duration_ms': end_ms - start_ms
                })
            
            self.log(f"✓ 解析了 {len(segments)} 个片段")
            return segments
            
        except Exception as e:
            self.log(f"❌ SRT解析失败: {e}")
            raise
    
    def time_to_ms(self, time_str: str) -> int:
        """将SRT时间格式转换为毫秒"""
        time_str = time_str.replace(',', '.')
        h, m, s = time_str.split(':')
        return int(h) * 3600000 + int(m) * 60000 + int(float(s)) * 1000
    
    def ms_to_time(self, ms: int) -> str:
        """将毫秒转换为SRT时间格式"""
        h = ms // 3600000
        m = (ms % 3600000) // 60000
        s = (ms % 60000) // 1000
        ms = ms % 1000
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
    
    def optimize_srt_segments(self, segments: list, max_length: int = 50, gap_threshold: float = 1.0) -> list:
        """优化SRT片段"""
        self.log(f"正在优化SRT片段 (最大长度: {max_length}, 间隔阈值: {gap_threshold}秒)")
        
        optimized = []
        
        for segment in segments:
            text = segment['text']
            
            if len(text) > max_length:
                sentences = re.split(r'[。！？.!?]', text)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                if len(sentences) > 1:
                    total_duration = segment['duration_ms']
                    start_ms = segment['start_time_ms']
                    
                    for i, sentence in enumerate(sentences):
                        if sentence.strip():
                            ratio = len(sentence) / len(text)
                            seg_duration = int(total_duration * ratio)
                            
                            optimized.append({
                                'index': len(optimized) + 1,
                                'start_time_ms': start_ms,
                                'end_time_ms': start_ms + seg_duration,
                                'start_time': self.ms_to_time(start_ms),
                                'end_time': self.ms_to_time(start_ms + seg_duration),
                                'text': sentence.strip(),
                                'duration_ms': seg_duration
                            })
                            
                            start_ms += seg_duration
                    continue
            
            optimized.append(segment)
        
        final_segments = []
        for i, segment in enumerate(optimized):
            if i > 0:
                prev_segment = optimized[i-1]
                gap = segment['start_time_ms'] - prev_segment['end_time_ms']
                
                if gap > gap_threshold * 1000:
                    segment['start_time_ms'] = prev_segment['end_time_ms'] + int(gap_threshold * 1000)
                    segment['start_time'] = self.ms_to_time(segment['start_time_ms'])
                    segment['duration_ms'] = segment['end_time_ms'] - segment['start_time_ms']
            
            final_segments.append(segment)
        
        self.log(f"✓ 优化后片段数量: {len(final_segments)}")
        return final_segments
    
    def format_text_for_llm(self, segments: list) -> str:
        """将片段文本格式化为LLM可理解的格式"""
        formatted_lines = []
        
        for segment in segments:
            formatted_lines.append(f"[片段 {segment['index']}] {segment['text']}")
        
        return '\n'.join(formatted_lines)
    
    def get_llm_judgment(self, formatted_text: str, api_config: dict) -> list:
        """调用LLM分析并返回需要删除的片段索引"""
        self.log("=== 开始LLM分析 ===")
        version = getattr(openai, '__version__', '未知')
        
        # 获取AI格式和格式化URL
        ai_format = self.ai_format_var.get()
        formatted_url = self.get_formatted_api_url()
        
        self.log(f"OpenAI版本: {version}")
        self.log(f"AI格式: {ai_format.upper()}")
        self.log(f"API地址: {formatted_url}")
        self.log(f"模型名称: {api_config['model_name']}")
        self.log(f"输入文本长度: {len(formatted_text)} 字符")
        
        # 检查API配置
        if not formatted_url:
            self.log("❌ API URL格式化失败")
            return []
        
        # Ollama格式可能不需要API Key
        if ai_format != "ollama" and not api_config['api_key']:
            self.log("❌ API配置不完整 - Key为空")
            return []
        
        self.log(f"URL: '{formatted_url}'")
        self.log(f"Key: '{'已设置' if api_config['api_key'] else '未设置'}'")
        
        # 检查openai库是否正确导入
        if not hasattr(openai, 'OpenAI'):
            self.log("❌ OpenAI类不存在，可能是库版本问题")
            return []
        
        try:
            self.log("正在创建OpenAI客户端...")
            self.log(f"格式化API URL: {formatted_url}")
            self.log(f"API Key长度: {len(api_config['api_key']) if api_config['api_key'] else 0} 字符")
            
            # 根据AI格式创建客户端
            try:
                self.log(f"尝试创建{ai_format.upper()}格式客户端...")
                
                if ai_format == "openai":
                    self.log("创建OpenAI格式客户端...")
                    client = openai.OpenAI(
                        api_key=api_config['api_key'], 
                        base_url=formatted_url, 
                        timeout=120.0
                    )
                    self.log("✓ OpenAI格式客户端创建成功")
                
                elif ai_format == "ollama":
                    self.log("创建Ollama格式客户端...")
                    client = openai.OpenAI(
                        base_url=formatted_url,
                        api_key="ollama",  # Ollama不需要真实的API Key
                        timeout=120.0
                    )
                    self.log("✓ Ollama格式客户端创建成功")
                
                elif ai_format == "gemini":
                    self.log("创建Gemini格式客户端...")
                    client = openai.OpenAI(
                        api_key=api_config['api_key'],
                        base_url=formatted_url,
                        timeout=120.0
                    )
                    self.log("✓ Gemini格式客户端创建成功")
                    
            except Exception as client_error:
                self.log(f"❌ 创建{ai_format.upper()}格式客户端失败: {client_error}")
                self.log(f"错误类型: {type(client_error).__name__}")
                import traceback
                self.log(f"客户端创建错误详情: {traceback.format_exc()}")
                return []
            
            self.log(f"✓ {ai_format.upper()}格式客户端创建成功")
            
            self.log("正在发送请求到LLM...")
            system_prompt = self.system_prompt_var.get()
            self.log(f"系统提示词长度: {len(system_prompt)} 字符")
            self.log(f"系统提示词预览: {system_prompt[:100]}...")
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": formatted_text}
            ]
            
            self.log(f"消息数量: {len(messages)}")
            self.log(f"用户消息预览: {formatted_text[:100]}...")
            
            # 在发送请求前记录所有信息
            self.log("准备调用 chat.completions.create...")
            self.log(f"参数: model={api_config['model_name']}, temperature=0.1")
            self.log(f"消息列表长度: {len(messages)}")
            
            # 根据版本使用不同的调用方式
            try:
                if version.startswith('0.'):
                    # 旧版本可能使用不同的调用方式
                    self.log("使用旧版本API调用方式...")
                    response = client.chat.completions.create(
                        model=api_config['model_name'],
                        messages=messages,
                        temperature=0.1
                    )
                else:
                    # 新版本
                    self.log("使用新版本API调用方式...")
                    response = client.chat.completions.create(
                        model=api_config['model_name'],
                        messages=messages,
                        temperature=0.1,
                        timeout=120.0  # 增加超时时间到120秒
                    )
                
                self.log("✓ LLM响应成功")
                self.log(f"响应ID: {response.id}")
                self.log(f"使用模型: {response.model}")
                if hasattr(response, 'usage') and response.usage:
                    self.log(f"Token使用: {response.usage.total_tokens} (提示: {response.usage.prompt_tokens}, 完成: {response.usage.completion_tokens})")
                
            except Exception as api_error:
                self.log(f"❌ API调用失败: {api_error}")
                self.log(f"错误类型: {type(api_error).__name__}")
                if hasattr(api_error, 'response'):
                    self.log(f"响应状态: {api_error.response.status_code}")
                    self.log(f"响应内容: {api_error.response.text}")
                import traceback
                self.log(f"API调用错误详情: {traceback.format_exc()}")
                return []
            
            if not response.choices:
                self.log("❌ 响应中没有choices")
                return []
            
            result = response.choices[0].message.content.strip()
            self.log(f"LLM原始响应: {repr(result)}")
            
            if not result:
                self.log("❌ LLM返回空响应")
                return []
            
            try:
                indices_to_delete = json.loads(result)
                self.log(f"JSON解析结果: {indices_to_delete}")
                self.log(f"解析结果类型: {type(indices_to_delete)}")
                
                if isinstance(indices_to_delete, list):
                    self.log(f"✓ LLM分析完成，建议删除 {len(indices_to_delete)} 个片段: {indices_to_delete}")
                    return indices_to_delete
                else:
                    self.log(f"❌ LLM返回格式错误，期望数组，实际类型: {type(indices_to_delete)}")
                    self.log(f"返回内容: {repr(indices_to_delete)}")
                    return []
            except json.JSONDecodeError as e:
                self.log(f"❌ LLM返回的不是有效JSON: {e}")
                self.log(f"原始响应内容: {repr(result)}")
                return []
                
        except Exception as e:
            self.log(f"❌ LLM调用异常: {e}")
            self.log(f"错误类型: {type(e).__name__}")
            import traceback
            self.log(f"完整错误信息: {traceback.format_exc()}")
            if hasattr(e, 'response'):
                self.log(f"响应状态: {e.response.status_code}")
                self.log(f"响应内容: {e.response.text}")
            elif hasattr(e, 'args'):
                self.log(f"错误参数: {e.args}")
            return []
    
    def execute_audio_edit(self, original_audio_path: str, segments_data: list, indices_to_delete: list, output_path: str) -> None:
        """执行音频编辑"""
        self.log(f"正在处理音频文件: {original_audio_path}")
        self.log(f"需要删除的片段索引: {indices_to_delete}")
        
        try:
            self.log("正在加载原始音频...")
            audio = AudioSegment.from_file(original_audio_path)
            
            segments_to_keep = []
            for segment in segments_data:
                if segment['index'] not in indices_to_delete:
                    segments_to_keep.append(segment)
            
            self.log(f"✓ 保留 {len(segments_to_keep)} 个优质片段")
            
            if not segments_to_keep:
                self.log("❌ 没有可保留的片段")
                return
            
            self.log("正在拼接优质片段...")
            final_audio = None
            
            for i, segment in enumerate(segments_to_keep):
                start_ms = segment['start_time_ms']
                end_ms = segment['end_time_ms']
                
                segment_audio = audio[start_ms:end_ms]
                segment_duration = len(segment_audio)
                
                if final_audio is None:
                    final_audio = segment_audio
                else:
                    # 动态调整交叉淡入淡出时间，避免超过片段长度
                    crossfade_time = min(5, segment_duration // 2)  # 最多5毫秒，但不能超过片段长度的一半
                    if crossfade_time > 0:
                        final_audio = final_audio.append(segment_audio, crossfade=crossfade_time)
                    else:
                        # 如果片段太短，直接拼接而不使用交叉淡入淡出
                        final_audio = final_audio + segment_audio
                
                self.log(f"  处理片段 {i+1}/{len(segments_to_keep)}: [{segment['start_time']} --> {segment['end_time']}] (时长: {segment_duration}ms)")
            
            self.log(f"正在导出音频到: {output_path}")
            self.log(f"输出目录: {os.path.dirname(os.path.abspath(output_path))}")
            
            # 确保输出目录存在
            output_dir = os.path.dirname(os.path.abspath(output_path))
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                self.log(f"创建输出目录: {output_dir}")
            
            final_audio.export(output_path, format="mp3")
            
            # 验证输出文件是否真的创建
            if os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                self.log(f"✓ 输出文件创建成功: {output_path} (大小: {file_size} 字节)")
            else:
                self.log(f"❌ 输出文件创建失败: {output_path}")
            
            original_duration = len(audio) / 1000
            final_duration = len(final_audio) / 1000
            reduction = ((original_duration - final_duration) / original_duration) * 100
            
            self.log(f"✓ 音频处理完成!")
            self.log(f"  原始时长: {original_duration:.1f}秒")
            self.log(f"  最终时长: {final_duration:.1f}秒")
            self.log(f"  减少时长: {reduction:.1f}%")
            self.log(f"  输出路径: {os.path.abspath(output_path)}")
            
        except Exception as e:
            self.log(f"❌ 音频处理失败: {e}")
            raise
    
    def generate_hrt_subtitles(self, cleaned_audio_file: str) -> str:
        """对清理后的音频进行二次转录并生成HRT格式字幕"""
        try:
            self.log("开始二次转录并生成HRT字幕...")
            
            # 设置HRT字幕输出路径
            if self.hrt_output_var.get():
                hrt_file = self.hrt_output_var.get()
            else:
                # 自动生成HRT字幕文件名
                base_name = os.path.splitext(os.path.basename(cleaned_audio_file))[0]
                hrt_file = os.path.join(os.path.dirname(cleaned_audio_file), f"{base_name}_hrt.srt")
            
            self.log(f"HRT字幕输出路径: {hrt_file}")
            
            # 二次转录：使用whisper对清理后的音频再次进行语音识别
            self.log("🎙️ 开始二次转录（对清理后的音频再次语音识别）...")
            srt_file = self.generate_srt_from_audio(cleaned_audio_file)
            
            if not srt_file or not os.path.exists(srt_file):
                self.log("❌ 二次转录失败，无法生成HRT字幕")
                return None
            
            # 解析SRT文件
            self.log("解析SRT文件...")
            segments = self.parse_srt_file(srt_file)
            
            if not segments:
                self.log("❌ SRT解析失败，无法生成HRT字幕")
                return None
            
            # 优化字幕为HRT格式
            self.log("优化字幕为HRT格式...")
            hrt_segments = self.optimize_for_hrt(segments)
            
            # 生成HRT字幕文件
            self.log("生成HRT字幕文件...")
            self.create_hrt_subtitle_file(hrt_segments, hrt_file)
            
            # 验证文件是否生成成功
            if os.path.exists(hrt_file):
                file_size = os.path.getsize(hrt_file)
                self.log(f"✓ HRT字幕文件生成成功: {hrt_file} (大小: {file_size} 字节)")
                return hrt_file
            else:
                self.log(f"❌ HRT字幕文件生成失败: {hrt_file}")
                return None
                
        except Exception as e:
            self.log(f"❌ HRT字幕生成失败: {e}")
            import traceback
            self.log(f"错误详情: {traceback.format_exc()}")
            return None
    
    def optimize_for_hrt(self, segments: list) -> list:
        """优化字幕片段为HRT格式"""
        hrt_segments = []
        
        for segment in segments:
            text = segment['text'].strip()
            
            # HRT格式优化规则
            # 1. 移除过短的片段（小于1秒）
            if segment['duration_ms'] < 1000:
                continue
            
            # 2. 移除无意义的片段
            if len(text) < 2 or text in ['嗯', '啊', '哦', '呃', '这个', '那个']:
                continue
            
            # 3. 优化文本内容
            # 移除多余的标点符号
            text = re.sub(r'[，,、。.！!??]{2,}', '，', text)
            text = re.sub(r'[\.]{2,}', '…', text)
            
            # 移除开头和结尾的空白字符
            text = text.strip()
            
            # 如果文本为空，跳过
            if not text:
                continue
            
            # 4. 调整时间轴，确保合适的显示时间
            # HRT标准：每个字幕显示时间建议2-5秒
            optimal_duration = min(max(segment['duration_ms'], 2000), 5000)
            
            hrt_segment = {
                'index': len(hrt_segments) + 1,
                'start_time_ms': segment['start_time_ms'],
                'end_time_ms': segment['start_time_ms'] + optimal_duration,
                'start_time': self.ms_to_time(segment['start_time_ms']),
                'end_time': self.ms_to_time(segment['start_time_ms'] + optimal_duration),
                'text': text,
                'duration_ms': optimal_duration
            }
            
            hrt_segments.append(hrt_segment)
        
        self.log(f"✓ HRT优化完成，原始片段: {len(segments)}，优化后: {len(hrt_segments)}")
        return hrt_segments
    
    def create_hrt_subtitle_file(self, segments: list, output_file: str):
        """创建HRT格式的字幕文件"""
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                for segment in segments:
                    # 写入字幕索引
                    f.write(f"{segment['index']}\n")
                    # 写入时间轴
                    f.write(f"{segment['start_time']} --> {segment['end_time']}\n")
                    # 写入字幕文本
                    f.write(f"{segment['text']}\n\n")
            
            self.log(f"✓ HRT字幕文件写入完成: {output_file}")
            
        except Exception as e:
            self.log(f"❌ HRT字幕文件写入失败: {e}")
            raise
    
    def install_audio_cleaner_dependencies(self):
        """
        安装音频清理所需的依赖库
        """
        self.log("正在安装音频清理依赖库...")
        self.status_var.set("正在安装依赖库...")
        
        threading.Thread(target=self._run_install_audio_cleaner_dependencies).start()
    
    def _run_install_audio_cleaner_dependencies(self):
        """
        在线程中运行音频清理依赖库安装
        """
        try:
            command = [sys.executable, "-m", "pip", "install", "openai", "pydub"]
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    self.log(output.strip())
            
            stderr = process.stderr.read()
            if stderr:
                self.log(f"错误: {stderr}")
            
            if process.returncode == 0:
                self.log("音频清理依赖库安装完成，请重启应用")
                self.status_var.set("依赖库安装完成")
                messagebox.showinfo("提示", "音频清理依赖库安装完成，请重启应用以使用智能音频清理功能")
            else:
                self.log(f"依赖库安装失败，返回代码: {process.returncode}")
                self.status_var.set("依赖库安装失败")
                
        except Exception as e:
            self.log(f"安装音频清理依赖库时出错: {e}")
            self.status_var.set("依赖库安装失败")
    
    def save_api_settings(self):
        """
        保存API设置到配置文件
        """
        try:
            settings = {
                'api_url': self.api_url_var.get(),
                'api_key': self.api_key_var.get(),
                'model_name': self.cleaner_model_var.get(),
                'max_segment_length': self.max_segment_var.get(),
                'gap_threshold': self.gap_threshold_var.get(),
                'system_prompt': self.system_prompt_var.get()
            }
            
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cleaner_config.json")
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            self.log("API设置已保存")
            messagebox.showinfo("成功", "API设置已保存到配置文件")
        except Exception as e:
            self.log(f"保存API设置失败: {e}")
            messagebox.showerror("错误", f"保存设置失败: {e}")
    
    def load_api_settings(self):
        """
        从配置文件加载API设置
        """
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cleaner_config.json")
            
            if not os.path.exists(config_file):
                messagebox.showinfo("提示", "未找到配置文件，请先保存设置")
                return
            
            with open(config_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            self.api_url_var.set(settings.get('api_url', 'https://api.openai.com/v1'))
            self.api_key_var.set(settings.get('api_key', ''))
            self.cleaner_model_var.set(settings.get('model_name', 'gpt-3.5-turbo'))
            self.max_segment_var.set(settings.get('max_segment_length', '50'))
            self.gap_threshold_var.set(settings.get('gap_threshold', '1.0'))
            self.system_prompt_var.set(settings.get('system_prompt', self.get_default_system_prompt()))
            
            # 更新提示词文本框内容
            if hasattr(self, 'prompt_text'):
                self.prompt_text.delete("1.0", tk.END)
                self.prompt_text.insert(tk.END, self.system_prompt_var.get())
            
            self.log("API设置已加载")
            messagebox.showinfo("成功", "API设置已从配置文件加载")
        except Exception as e:
            self.log(f"加载API设置失败: {e}")
            messagebox.showerror("错误", f"加载设置失败: {e}")
    
    def auto_load_api_settings(self):
        """
        自动加载API设置（不显示提示框）
        """
        try:
            config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_cleaner_config.json")
            
            if os.path.exists(config_file):
                with open(config_file, 'r', encoding='utf-8') as f:
                    settings = json.load(f)
                
                self.api_url_var.set(settings.get('api_url', 'https://api.openai.com/v1'))
                self.api_key_var.set(settings.get('api_key', ''))
                self.cleaner_model_var.set(settings.get('model_name', 'gpt-3.5-turbo'))
                self.max_segment_var.set(settings.get('max_segment_length', '50'))
                self.gap_threshold_var.set(settings.get('gap_threshold', '1.0'))
                self.system_prompt_var.set(settings.get('system_prompt', self.get_default_system_prompt()))
                
                # 更新提示词文本框内容
                if hasattr(self, 'prompt_text'):
                    self.prompt_text.delete("1.0", tk.END)
                    self.prompt_text.insert(tk.END, self.system_prompt_var.get())
                
                self.log("API设置已自动加载")
            else:
                self.log("未找到配置文件，使用默认设置")
        except Exception as e:
            self.log(f"自动加载API设置失败: {e}")
            self.log("使用默认设置")
    
    def test_openai_library(self):
        """
        测试OpenAI库是否正常工作
        """
        try:
            self.log("=== 测试OpenAI库 ===")
            version = getattr(openai, '__version__', '未知')
            self.log(f"OpenAI版本: {version}")
            
            # 检查关键类和方法
            if hasattr(openai, 'OpenAI'):
                self.log("✓ OpenAI类存在")
            else:
                self.log("❌ OpenAI类不存在")
                return
            
            if hasattr(openai.OpenAI, '__init__'):
                self.log("✓ OpenAI.__init__方法存在")
            else:
                self.log("❌ OpenAI.__init__方法不存在")
                return
            
            if hasattr(openai.OpenAI, 'chat'):
                self.log("✓ OpenAI.chat属性存在")
            else:
                self.log("❌ OpenAI.chat属性不存在")
                return
            
            if hasattr(openai.OpenAI.chat, 'completions'):
                self.log("✓ OpenAI.chat.completions属性存在")
            else:
                self.log("❌ OpenAI.chat.completions属性不存在")
                return
            
            # 检查版本兼容性
            if version != '未知':
                try:
                    version_parts = version.split('.')
                    major, minor = int(version_parts[0]), int(version_parts[1])
                    if major < 1:
                        self.log(f"⚠ OpenAI版本 {version} 可能过旧，建议升级到1.0.0+")
                    elif major == 1 and minor < 2:
                        self.log(f"⚠ OpenAI版本 {version} 较旧，建议升级到1.2.0+")
                    else:
                        self.log(f"✓ OpenAI版本 {version} 看起来兼容")
                except:
                    self.log("⚠ 无法解析OpenAI版本号")
            
            # 尝试创建一个测试客户端（不发送请求）
            try:
                # 使用兼容的方式创建客户端
                if version.startswith('0.'):
                    # 旧版本OpenAI
                    self.log("使用旧版本OpenAI创建方式...")
                    test_client = openai.OpenAI(api_key="test_key")
                    if hasattr(test_client, 'base_url'):
                        test_client.base_url = "https://api.openai.com/v1"
                else:
                    # 新版本OpenAI
                    self.log("使用新版本OpenAI创建方式...")
                    test_client = openai.OpenAI(
                        base_url="https://api.openai.com/v1",
                        api_key="test_key"
                    )
                self.log("✓ OpenAI客户端创建测试成功")
            except Exception as e:
                self.log(f"⚠ OpenAI客户端创建测试失败: {e}")
                self.log("这可能是版本兼容性问题，尝试简化创建方式...")
                
                # 尝试最简单的创建方式
                try:
                    simple_client = openai.OpenAI(api_key="test_key")
                    self.log("✓ 简化方式创建OpenAI客户端成功")
                except Exception as e2:
                    self.log(f"❌ 简化方式也失败: {e2}")
            
            self.log("=== OpenAI库测试完成 ===")
            
        except Exception as e:
            self.log(f"❌ OpenAI库测试异常: {e}")
            import traceback
            self.log(f"错误信息: {traceback.format_exc()}")
    
    def on_ai_format_change(self, event=None):
        """AI格式变更处理"""
        self.update_ai_format_ui()
    
    def update_ai_format_ui(self):
        """根据选择的AI格式更新UI"""
        ai_format = self.ai_format_var.get()
        
        if ai_format == "openai":
            self.format_info_var.set("标准OpenAI兼容格式")
            self.openai_hint_var.set("💡 程序会自动添加 /v1 后缀，只需输入基础网址即可")
            # 设置默认OpenAI URL
            if not self.api_url_var.get() or "api.openai.com" in self.api_url_var.get():
                self.api_url_var.set("https://api.openai.com")
        elif ai_format == "ollama":
            self.format_info_var.set("Ollama本地AI模型格式")
            self.openai_hint_var.set("💡 Ollama默认地址: http://localhost:11434")
            # 设置默认Ollama URL
            if not self.api_url_var.get() or "api.openai.com" in self.api_url_var.get():
                self.api_url_var.set("http://localhost:11434")
        elif ai_format == "gemini":
            self.format_info_var.set("Google Gemini API格式")
            self.openai_hint_var.set("💡 Gemini API需要完整的URL，包括版本路径")
            # 设置默认Gemini URL
            if not self.api_url_var.get() or "api.openai.com" in self.api_url_var.get():
                self.api_url_var.set("https://generativelanguage.googleapis.com/v1beta")
        
        # 更新模型建议
        self.update_model_suggestions()
    
    def update_model_suggestions(self):
        """根据AI格式更新模型建议"""
        ai_format = self.ai_format_var.get()
        
        # 由于在初始化时可能无法找到控件，我们直接更新值
        # 实际的控件会在需要时更新
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
    
    def update_voice_ai_format_ui(self, ai_format, format_info_var, model_combo):
        """更新语音转文字AI格式UI"""
        if ai_format == "openai":
            format_info_var.set("标准OpenAI兼容格式")
            models = [
                "gpt-3.5-turbo", 
                "gpt-4", 
                "gpt-4-turbo", 
                "gpt-4o",
                "claude-3-haiku", 
                "claude-3-sonnet",
                "claude-3-opus"
            ]
        elif ai_format == "ollama":
            format_info_var.set("Ollama本地AI模型格式")
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
        elif ai_format == "gemini":
            format_info_var.set("Google Gemini API格式")
            models = [
                "gemini-1.5-flash",
                "gemini-1.5-pro",
                "gemini-1.0-pro"
            ]
        
        # 更新模型列表
        model_combo['values'] = models
        
        # 在实际使用中，控件会通过配置更新
        self.log(f"已更新{ai_format.upper()}格式的模型建议")
    
    def get_formatted_api_url(self):
        """根据AI格式获取格式化的API URL"""
        ai_format = self.ai_format_var.get()
        base_url = self.api_url_var.get().strip()
        
        if not base_url:
            return None
            
        if ai_format == "openai":
            # OpenAI格式：自动添加/v1后缀
            # 检查是否已经以/v1或/v1/结尾
            if not (base_url.endswith('/v1') or base_url.endswith('/v1/')):
                if base_url.endswith('/'):
                    return base_url + 'v1'
                else:
                    return base_url + '/v1'
            # 如果已经包含/v1，直接返回（移除末尾斜杠避免重复）
            return base_url.rstrip('/')
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
    
    def format_voice_ai_api_url(self, ai_format, base_url):
        """
        根据AI格式格式化语音AI的API URL
        
        参数:
            ai_format: AI格式 ("openai", "ollama", "gemini")
            base_url: 基础URL
            
        返回:
            str: 格式化后的URL
        """
        if not base_url:
            return None
            
        base_url = base_url.strip()
        
        if ai_format == "openai":
            # OpenAI格式：自动添加/v1后缀
            # 检查是否已经以/v1或/v1/结尾
            if not (base_url.endswith('/v1') or base_url.endswith('/v1/')):
                if base_url.endswith('/'):
                    return base_url + 'v1'
                else:
                    return base_url + '/v1'
            # 如果已经包含/v1，直接返回（移除末尾斜杠避免重复）
            return base_url.rstrip('/')
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
    
    def setup_log_tab(self):
        """
        设置日志选项卡
        """
        # 创建主框架
        inner_frame = ttk.Frame(self.log_tab, padding="15")
        inner_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(inner_frame, text="📋 操作日志", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 10))
        
        # 日志文本框架
        log_text_frame = ttk.Frame(inner_frame)
        log_text_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建日志文本区域
        self.log_text = tk.Text(log_text_frame, wrap=tk.WORD, 
                               font=("Microsoft YaHei", 9), bg="#f8f9fa", fg="#343a40",
                               relief="flat", borderwidth=1)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 添加滚动条
        scrollbar = ttk.Scrollbar(log_text_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)
        
        # 按钮区域
        button_frame = ttk.Frame(inner_frame)
        button_frame.pack(fill=tk.X, pady=(10, 0))
        
        clear_log_btn = ttk.Button(button_frame, text="清空日志", command=self.clear_log)
        clear_log_btn.pack(side=tk.LEFT, padx=5)
        
        save_log_btn = ttk.Button(button_frame, text="保存日志", command=self.save_log)
        save_log_btn.pack(side=tk.LEFT, padx=5)
        
        # 日志统计
        self.log_stats_var = tk.StringVar(value="日志条数: 0")
        stats_label = ttk.Label(button_frame, textvariable=self.log_stats_var)
        stats_label.pack(side=tk.RIGHT, padx=5)
    
    def clear_log(self):
        """
        清空日志
        """
        self.log_text.delete("1.0", tk.END)
        self.log("日志已清空")
        self.update_log_stats()
    
    def save_log(self):
        """
        保存日志到文件
        """
        try:
            log_content = self.log_text.get("1.0", tk.END)
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            log_file = f"voice_log_{timestamp}.txt"
            
            with open(log_file, 'w', encoding='utf-8') as f:
                f.write(log_content)
            
            self.log(f"日志已保存到: {log_file}")
            messagebox.showinfo("成功", f"日志已保存到: {log_file}")
        except Exception as e:
            self.log(f"保存日志失败: {e}")
            messagebox.showerror("错误", f"保存日志失败: {e}")
    
    def update_log_stats(self):
        """
        更新日志统计
        """
        log_content = self.log_text.get("1.0", tk.END)
        line_count = len([line for line in log_content.split('\n') if line.strip()])
        self.log_stats_var.set(f"日志条数: {line_count}")
    
    def load_voice_service_config(self):
        """
        加载语音服务配置
        """
        self.voice_config_file = "voice_service_config.json"
        default_config = {
            "hotkey": "caps_lock",
            "start_sound": True,
            "end_sound": True,
            "start_sound_freq": 1000,
            "end_sound_freq": 800,
            "sound_duration": 200,
            "voice_model": "",
            "voice_language": "auto",
            "voice_output_language": "auto",
            "auto_input_enabled": True,
            "input_method": "paste"
        }
        
        try:
            if os.path.exists(self.voice_config_file):
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置，确保所有配置项都存在
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
            else:
                config = default_config
                self.save_voice_service_config(config)
        except Exception as e:
            self.log(f"加载语音服务配置失败: {e}")
            config = default_config
        
        # 更新UI控件
        self.hotkey_var.set(config.get("hotkey", "caps_lock"))
        self.start_sound_var.set(config.get("start_sound", True))
        self.end_sound_var.set(config.get("end_sound", True))
        self.start_freq_var.set(str(config.get("start_sound_freq", 1000)))
        self.end_freq_var.set(str(config.get("end_sound_freq", 800)))
        self.duration_var.set(str(config.get("sound_duration", 200)))
        self.voice_model_var.set(config.get("voice_model", ""))
        self.voice_lang_var.set(config.get("voice_language", "auto"))
        self.voice_output_lang_var.set(config.get("voice_output_language", "auto"))
        self.auto_input_var.set(config.get("auto_input_enabled", True))
        self.input_method_var.set(config.get("input_method", "paste"))
    
    def save_voice_service_config(self, config):
        """
        保存语音服务配置
        
        参数:
            config: 配置字典
        """
        try:
            with open(self.voice_config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            self.log("语音服务配置已保存")
        except Exception as e:
            self.log(f"保存语音服务配置失败: {e}")
    
    def apply_hotkey(self):
        """
        应用新的快捷键设置
        """
        new_hotkey = self.hotkey_var.get()
        if not new_hotkey:
            messagebox.showwarning("警告", "请选择一个快捷键")
            return
        
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新快捷键
        config["hotkey"] = new_hotkey
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log(f"快捷键已设置为: {new_hotkey}")
        messagebox.showinfo("成功", f"快捷键已设置为: {new_hotkey}")
        
        # 如果服务正在运行，重启服务以应用新设置
        if self.voice_service_active:
            self.stop_voice_service()
            self.start_voice_service()
    
    def update_sound_settings(self):
        """
        更新提示音设置
        """
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 更新提示音设置
        config["start_sound"] = self.start_sound_var.get()
        config["end_sound"] = self.end_sound_var.get()
        config["start_sound_freq"] = int(self.start_freq_var.get())
        config["end_sound_freq"] = int(self.end_freq_var.get())
        config["sound_duration"] = int(self.duration_var.get())
        
        # 保存配置
        self.save_voice_service_config(config)
        
        self.log("提示音设置已更新")
    
    def test_sound(self):
        """
        测试提示音
        """
        try:
            import winsound
            
            # 测试开始提示音
            if self.start_sound_var.get():
                start_freq = int(self.start_freq_var.get())
                duration = int(self.duration_var.get())
                self.log(f"测试开始提示音: {start_freq}Hz, {duration}ms")
                winsound.Beep(start_freq, duration)
                time.sleep(0.3)  # 间隔0.3秒
            
            # 测试结束提示音
            if self.end_sound_var.get():
                end_freq = int(self.end_freq_var.get())
                duration = int(self.duration_var.get())
                self.log(f"测试结束提示音: {end_freq}Hz, {duration}ms")
                winsound.Beep(end_freq, duration)
            
            self.log("提示音测试完成")
            
        except ImportError:
            messagebox.showwarning("警告", "无法导入winsound模块，不支持提示音功能")
        except Exception as e:
            self.log(f"提示音测试失败: {e}")
            messagebox.showerror("错误", f"提示音测试失败: {e}")

    # ==================== AI文本处理功能 ====================
    
    def load_voice_ai_config(self):
        """
        加载语音转文字AI处理配置
        """
        default_config = {
            "enabled": False,
            "api_key": "",
            "api_base": "https://api.openai.com",
            "model": "gpt-3.5-turbo",
            "max_tokens": 1000,
            "temperature": 0.1,
            "auto_correct": True,
            "grammar_check": True,
            "semantic_optimization": True,
            "voice_prompt": None,
            "custom_prompt": None,
            "ai_format": "openai"
        }
        
        config_file = "voice_ai_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                return config
            except Exception as e:
                self.log(f"加载语音转文字AI配置失败: {e}")
        
        return default_config
    
    def load_audio_cleaner_ai_config(self):
        """
        加载音频清理AI处理配置
        """
        default_config = {
            "enabled": False,
            "api_key": "",
            "api_base": "https://openrouter.ai/api/v1",
            "model": "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            "max_tokens": 1000,
            "temperature": 0.1,
            "audio_cleanup_prompt": None,
            "custom_prompt": None,
            "max_segment_length": 50,
            "gap_threshold": 1.0
        }
        
        config_file = "audio_cleaner_ai_config.json"
        if os.path.exists(config_file):
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 合并默认配置
                    for key, value in default_config.items():
                        if key not in config:
                            config[key] = value
                return config
            except Exception as e:
                self.log(f"加载音频清理AI配置失败: {e}")
        
        return default_config
    
    def save_voice_ai_config(self):
        """
        保存语音转文字AI配置
        """
        config_file = "voice_ai_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.voice_ai_config, f, indent=2, ensure_ascii=False)
            self.log("语音转文字AI配置已保存")
        except Exception as e:
            self.log(f"保存语音转文字AI配置失败: {e}")
    
    def save_audio_cleaner_ai_config(self):
        """
        保存音频清理AI配置
        """
        config_file = "audio_cleaner_ai_config.json"
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.audio_cleaner_ai_config, f, indent=2, ensure_ascii=False)
            self.log("音频清理AI配置已保存")
        except Exception as e:
            self.log(f"保存音频清理AI配置失败: {e}")
    
    def setup_voice_ai_processor(self):
        """
        设置语音转文字AI处理器
        """
        if not AI_PROCESSOR_AVAILABLE:
            self.log("语音转文字AI处理功能不可用：缺少必要库")
            return
        
        try:
            self.voice_ai_session = requests.Session()
            self.update_voice_ai_session_headers()
            self.log("语音转文字AI处理器已初始化")
        except Exception as e:
            self.log(f"语音转文字AI处理器初始化失败: {e}")
    
    def setup_audio_cleaner_ai_processor(self):
        """
        设置音频清理AI处理器
        """
        if not AI_PROCESSOR_AVAILABLE:
            self.log("音频清理AI处理功能不可用：缺少必要库")
            return
        
        try:
            self.audio_cleaner_ai_session = requests.Session()
            self.update_audio_cleaner_ai_session_headers()
            self.log("音频清理AI处理器已初始化")
        except Exception as e:
            self.log(f"音频清理AI处理器初始化失败: {e}")
    
    def update_voice_ai_session_headers(self):
        """
        更新语音转文字AI会话头信息
        """
        if self.voice_ai_session and self.voice_ai_config.get("api_key"):
            self.voice_ai_session.headers.update({
                "Content-Type": "application/json",
                "x-api-key": self.voice_ai_config["api_key"],
                "anthropic-version": "2023-06-01"
            })
    
    def update_audio_cleaner_ai_session_headers(self):
        """
        更新音频清理AI会话头信息
        """
        if self.audio_cleaner_ai_session and self.audio_cleaner_ai_config.get("api_key"):
            self.audio_cleaner_ai_session.headers.update({
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.audio_cleaner_ai_config['api_key']}"
            })
    
    def process_text_with_voice_ai(self, text):
        """
        使用语音转文字AI处理文本
        
        参数:
            text: 要处理的文本
            
        返回:
            str: 处理后的文本
        """
        if not text or not text.strip():
            return text
        
        if not self.voice_ai_enabled or not AI_PROCESSOR_AVAILABLE:
            return text
        
        ai_format = self.voice_ai_config.get("ai_format", "openai")
        
        # Ollama不需要API密钥
        if ai_format != "ollama" and not self.voice_ai_config.get("api_key"):
            self.log("语音转文字AI处理失败：未设置API密钥")
            return text
        
        try:
            self.log(f"🔧 使用语音转文字模型: {self.voice_ai_config.get('model', 'gpt-3.5-turbo')}")
            self.log(f"🌡️ 温度设置: {self.voice_ai_config.get('temperature', 0.1)}")
            self.log(f"📋 AI格式: {ai_format.upper()}")
            
            # 构建提示词
            prompt = self.get_voice_ai_prompt(text)
            self.log(f"💭 发送语音转文字AI处理请求...")
            
            if ai_format == "openai":
                # OpenAI格式调用
                import openai
                
                # 格式化API URL
                api_base = self.voice_ai_config.get("api_base", "https://api.openai.com")
                formatted_url = self.format_voice_ai_api_url(ai_format, api_base)
                
                # 检查是否为OpenRouter并添加特殊头部
                if "openrouter.ai" in formatted_url:
                    client = openai.OpenAI(
                        api_key=self.voice_ai_config.get("api_key", ""),
                        base_url=formatted_url,
                        timeout=30.0,
                        default_headers={
                            "HTTP-Referer": "https://github.com/voice-assistant",
                            "X-Title": "Voice Assistant"
                        }
                    )
                else:
                    client = openai.OpenAI(
                        api_key=self.voice_ai_config.get("api_key", ""),
                        base_url=formatted_url,
                        timeout=30.0
                    )
                
                response = client.chat.completions.create(
                    model=self.voice_ai_config.get("model", "gpt-3.5-turbo"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.voice_ai_config.get("temperature", 0.1),
                    max_tokens=self.voice_ai_config.get("max_tokens", 1000)
                )
                
                processed_text = response.choices[0].message.content.strip()
                
            elif ai_format == "ollama":
                # Ollama格式调用
                import openai
                
                api_base = self.voice_ai_config.get("api_base", "http://localhost:11434")
                formatted_url = self.format_voice_ai_api_url(ai_format, api_base)
                
                client = openai.OpenAI(
                    base_url=formatted_url,
                    api_key="ollama",  # Ollama不需要真实的API Key
                    timeout=30.0
                )
                
                response = client.chat.completions.create(
                    model=self.voice_ai_config.get("model", "llama3.1:8b"),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.voice_ai_config.get("temperature", 0.1),
                    max_tokens=self.voice_ai_config.get("max_tokens", 1000)
                )
                
                processed_text = response.choices[0].message.content.strip()
                
            elif ai_format == "gemini":
                # Gemini格式调用
                import openai
                
                api_base = self.voice_ai_config.get("api_base", "https://generativelanguage.googleapis.com/v1beta")
                formatted_url = self.format_voice_ai_api_url(ai_format, api_base)
                
                try:
                    client = openai.OpenAI(
                        api_key=self.voice_ai_config.get("api_key", ""),
                        base_url=formatted_url,
                        timeout=30.0
                    )
                    
                    response = client.chat.completions.create(
                        model=self.voice_ai_config.get("model", "gemini-1.5-flash"),
                        messages=[{"role": "user", "content": prompt}],
                        temperature=self.voice_ai_config.get("temperature", 0.1),
                        max_tokens=self.voice_ai_config.get("max_tokens", 1000)
                    )
                    
                    processed_text = response.choices[0].message.content.strip()
                    
                except Exception as gemini_error:
                    self.log(f"⚠️ Gemini OpenAI兼容模式失败: {gemini_error}")
                    self.log("💡 提示：请确保API URL包含完整的版本路径")
                    return text
            
            if processed_text:
                self.log(f"🎯 {ai_format.upper()}格式AI处理成功，获得优化文本")
                return processed_text
            else:
                self.log("⚠️ AI返回的文本为空，返回原文")
                return text
                
        except Exception as e:
            self.log(f"❌ 语音转文字AI处理过程中出现错误: {str(e)}")
            return text
    
    def process_text_with_audio_cleaner_ai(self, text):
        """
        使用音频清理AI处理文本
        
        参数:
            text: 要处理的文本
            
        返回:
            str: 处理后的文本
        """
        if not text or not text.strip():
            return text
        
        if not self.audio_cleaner_ai_enabled or not AI_PROCESSOR_AVAILABLE:
            return text
        
        if not self.audio_cleaner_ai_config.get("api_key"):
            self.log("音频清理AI处理失败：未设置API密钥")
            return text
        
        try:
            self.log(f"🔧 使用音频清理模型: {self.audio_cleaner_ai_config.get('model', 'cognitivecomputations/dolphin-mistral-24b-venice-edition:free')}")
            self.log(f"🌡️ 温度设置: {self.audio_cleaner_ai_config.get('temperature', 0.1)}")
            
            # 构建提示词
            prompt = self.get_audio_cleaner_ai_prompt(text)
            self.log(f"💭 发送音频清理AI处理请求...")
            
            # 构建请求数据
            request_data = {
                "model": self.audio_cleaner_ai_config.get("model", "cognitivecomputations/dolphin-mistral-24b-venice-edition:free"),
                "max_tokens": self.audio_cleaner_ai_config.get("max_tokens", 1000),
                "temperature": self.audio_cleaner_ai_config.get("temperature", 0.1),
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            }
            
            # 发送请求
            api_url = f"{self.audio_cleaner_ai_config.get('api_base', 'https://openrouter.ai/api/v1')}/v1/chat/completions"
            self.log(f"🌐 请求音频清理API: {api_url}")
            response = self.audio_cleaner_ai_session.post(api_url, json=request_data, timeout=30)
            
            if response.status_code == 200:
                self.log(f"✅ 音频清理API请求成功 (状态码: {response.status_code})")
                result = response.json()
                processed_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                if processed_text:
                    self.log(f"🎯 音频清理AI处理成功，获得清理文本")
                    return processed_text
                else:
                    self.log("⚠️ 音频清理AI返回的文本为空，返回原文")
                    return text
            else:
                self.log(f"❌ 音频清理API请求失败，状态码: {response.status_code}")
                try:
                    error_info = response.json()
                    self.log(f"📋 错误详情: {error_info}")
                except:
                    self.log(f"📋 响应内容: {response.text[:200]}...")
                return text
                
        except Exception as e:
            self.log(f"❌ 音频清理AI处理过程中出现错误: {str(e)}")
            return text
    
    def get_voice_ai_prompt(self, text):
        """
        获取语音转文字AI处理提示词
        
        参数:
            text: 要处理的文本
            
        返回:
            str: 提示词
        """
        # 优先使用语音转文字专用提示词
        voice_prompt = self.voice_ai_config.get("voice_prompt")
        if voice_prompt:
            return voice_prompt.format(text=text)
        
        # 其次使用通用自定义提示词
        custom_prompt = self.voice_ai_config.get("custom_prompt")
        if custom_prompt:
            return custom_prompt.format(text=text)
        
        # 默认提示词
        prompt = """你是一个专业的语音转录文本优化助手。请对以下语音转录的文本进行优化：

1. 识别并修正语音识别中的错别字
2. 修正语法错误和不通顺的表达
3. 优化标点符号，使其更符合书面语规范
4. 调整口语化表达，使其更清晰易懂
5. 保持原文的核心意思和语气
6. 识别并修正同音字错误
7. 优化断句和段落结构
8. 删除模型幻觉内容（即用户未说话时转录出的无意义文本）
9. 识别并去除重复的表达

请直接返回优化后的文本，不要添加任何解释或说明。

原始语音转录文本：
{text}

优化后的文本："""
        
        return prompt.format(text=text)
    
    def get_audio_cleaner_ai_prompt(self, text):
        """
        获取音频清理AI处理提示词
        
        参数:
            text: 要处理的文本
            
        返回:
            str: 提示词
        """
        # 优先使用音频清理专用提示词
        audio_cleanup_prompt = self.audio_cleaner_ai_config.get("audio_cleanup_prompt")
        if audio_cleanup_prompt:
            return audio_cleanup_prompt.format(text=text)
        
        # 其次使用通用自定义提示词
        custom_prompt = self.audio_cleaner_ai_config.get("custom_prompt")
        if custom_prompt:
            return custom_prompt.format(text=text)
        
        # 默认提示词
        prompt = """# TASK
You are an audio cleanup AI. Analyze the transcript below and identify segments to be deleted.

# RULES
Delete the following types of content:
1.  **Self-Corrections:** A broken/mistaken sentence immediately followed by a corrected, complete version of it. The first, broken one must be deleted.
2.  **Repeated Takes:** Redundant repetitions of the same phrase. Keep only the last, best take.
3.  **Noise & Errors:** Indecipherable audio, stutters, or segments ruined by non-speech noise (coughs, clicks).
4.  **Fillers:** Excessive filler words ("uh", "um", "like", "you know"). Do not delete natural, short pauses for thought.
5.  **Incomplete Sentences:** Remove sentences that are cut off or not completed.
6.  **Unfinished Thoughts:** Delete segments where the speaker starts but doesn't complete their thought.

# OUTPUT
Return the cleaned transcript with only the complete, well-formed sentences.

Original transcript:
{text}

Cleaned transcript:"""
        
        return prompt.format(text=text)
    
    def get_default_voice_prompt(self):
        """
        获取语音转文字的默认提示词
        
        返回:
            str: 默认提示词
        """
        return """你是一个专业的语音转录文本优化助手。请对以下语音转录的文本进行优化：

1. 识别并修正语音识别中的错别字
2. 修正语法错误和不通顺的表达
3. 优化标点符号，使其更符合书面语规范
4. 调整口语化表达，使其更清晰易懂
5. 保持原文的核心意思和语气
6. 识别并修正同音字错误
7. 优化断句和段落结构

请直接返回优化后的文本，不要添加任何解释或说明。

原始语音转录文本：
{text}

优化后的文本："""
    
    def get_default_audio_cleaner_prompt(self):
        """
        获取音频清理的默认提示词
        
        返回:
            str: 默认提示词
        """
        return """# TASK
You are an audio cleanup AI. Analyze the transcript below and identify segments to be deleted.

# RULES
Delete the following types of content:
1.  **Self-Corrections:** A broken/mistaken sentence immediately followed by a corrected, complete version of it. The first, broken one must be deleted.
2.  **Repeated Takes:** Redundant repetitions of the same phrase. Keep only the last, best take.
3.  **Noise & Errors:** Indecipherable audio, stutters, or segments ruined by non-speech noise (coughs, clicks).
4.  **Fillers:** Excessive filler words ("uh", "um", "like", "you know"). Do not delete natural, short pauses for thought.
5.  **Incomplete Sentences:** Remove sentences that are cut off or not completed.
6.  **Unfinished Thoughts:** Delete segments where the speaker starts but doesn't complete their thought.

# OUTPUT
Return the cleaned transcript with only the complete, well-formed sentences.

Original transcript:
{text}

Cleaned transcript:"""
    
    def toggle_voice_ai_processor(self):
        """
        切换语音转文字AI处理器状态
        """
        self.voice_ai_enabled = not self.voice_ai_enabled
        status = "启用" if self.voice_ai_enabled else "禁用"
        self.log(f"语音转文字AI文本处理已{status}")
        
        # 更新界面状态变量
        if hasattr(self, 'ai_enabled_var'):
            self.ai_enabled_var.set(self.voice_ai_enabled)
        
        # 更新配置
        self.voice_ai_config["enabled"] = self.voice_ai_enabled
        self.save_voice_ai_config()
    
    def toggle_audio_cleaner_ai_processor(self):
        """
        切换音频清理AI处理器状态
        """
        self.audio_cleaner_ai_enabled = not self.audio_cleaner_ai_enabled
        status = "启用" if self.audio_cleaner_ai_enabled else "禁用"
        self.log(f"音频清理AI文本处理已{status}")
        
        # 更新配置
        self.audio_cleaner_ai_config["enabled"] = self.audio_cleaner_ai_enabled
        self.save_audio_cleaner_ai_config()
    
    def update_ai_config(self, **kwargs):
        """
        更新AI配置
        
        参数:
            **kwargs: 配置项
        """
        for key, value in kwargs.items():
            if key in self.ai_processor_config:
                self.ai_processor_config[key] = value
        
        self.save_ai_config()
        self.update_ai_session_headers()
        self.log("AI配置已更新")
    
    
    def show_voice_ai_settings_dialog(self):
        """
        显示语音转文字服务的AI设置对话框
        """
        if not AI_PROCESSOR_AVAILABLE:
            messagebox.showwarning("警告", "AI处理功能不可用：缺少必要库")
            return
        
        # 创建设置窗口
        settings_window = tk.Toplevel(self.root)
        settings_window.title("语音转文字AI设置")
        settings_window.geometry("500x750")
        settings_window.resizable(False, False)
        
        # 设置窗口居中
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 创建主框架和滚动条
        main_canvas = tk.Canvas(settings_window)
        scrollbar = ttk.Scrollbar(settings_window, orient="vertical", command=main_canvas.yview)
        inner_frame = ttk.Frame(main_canvas)
        
        inner_frame.bind(
            "<Configure>",
            lambda e: main_canvas.configure(scrollregion=main_canvas.bbox("all"))
        )
        
        main_canvas.create_window((0, 0), window=inner_frame, anchor="nw")
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        main_canvas.pack(side="left", fill="both", expand=True, padx=(20, 0), pady=(20, 0))
        scrollbar.pack(side="right", fill="y", padx=(0, 20), pady=(20, 0))
        
        # 标题
        title_label = ttk.Label(inner_frame, text="语音转文字AI设置", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 启用AI处理
        enabled_frame = ttk.Frame(inner_frame)
        enabled_frame.pack(fill=tk.X, pady=5)
        
        enabled_var = tk.BooleanVar(value=self.voice_ai_enabled)
        enabled_check = ttk.Checkbutton(enabled_frame, text="启用AI文本处理", variable=enabled_var,
                                       command=lambda: self.toggle_voice_ai_processor())
        enabled_check.pack(side=tk.LEFT)
        
        # API设置
        api_frame = ttk.LabelFrame(inner_frame, text="API设置", padding="10")
        api_frame.pack(fill=tk.X, pady=10)
        
        # AI格式选择
        format_frame = ttk.Frame(api_frame)
        format_frame.grid(row=0, column=0, columnspan=2, sticky=tk.W, pady=5)
        
        ttk.Label(format_frame, text="AI格式:").pack(side=tk.LEFT, padx=5)
        ai_format_var = tk.StringVar(value=self.voice_ai_config.get("ai_format", "openai"))
        ai_format_combo = ttk.Combobox(format_frame, textvariable=ai_format_var, width=15)
        ai_format_combo['values'] = ["openai", "ollama", "gemini"]
        ai_format_combo.pack(side=tk.LEFT, padx=5)
        ai_format_combo.bind("<<ComboboxSelected>>", lambda e: self.update_voice_ai_format_ui(ai_format_var.get()))
        
        # 格式说明标签
        format_info_var = tk.StringVar()
        format_info_label = ttk.Label(format_frame, textvariable=format_info_var, 
                                    font=("Microsoft YaHei", 9), foreground="#6c757d")
        format_info_label.pack(side=tk.LEFT, padx=10)
        
        # API密钥
        ttk.Label(api_frame, text="API密钥:").grid(row=1, column=0, sticky=tk.W, pady=5)
        api_key_var = tk.StringVar(value=self.voice_ai_config.get("api_key", ""))
        api_key_entry = ttk.Entry(api_frame, textvariable=api_key_var, width=50, show="*")
        api_key_entry.grid(row=1, column=1, pady=5)
        
        # API基础URL
        ttk.Label(api_frame, text="API地址:").grid(row=2, column=0, sticky=tk.W, pady=5)
        api_base_var = tk.StringVar(value=self.voice_ai_config.get("api_base", ""))
        api_base_entry = ttk.Entry(api_frame, textvariable=api_base_var, width=50)
        api_base_entry.grid(row=2, column=1, pady=5)
        
        # 模型选择
        ttk.Label(api_frame, text="模型:").grid(row=3, column=0, sticky=tk.W, pady=5)
        model_var = tk.StringVar(value=self.voice_ai_config.get("model", ""))
        model_combo = ttk.Combobox(api_frame, textvariable=model_var, width=47)
        model_combo.grid(row=3, column=1, pady=5)
        
        # 初始化UI
        self.update_voice_ai_format_ui(ai_format_var.get(), format_info_var, model_combo)
        
        # 处理设置
        processing_frame = ttk.LabelFrame(inner_frame, text="处理设置", padding="10")
        processing_frame.pack(fill=tk.X, pady=10)
        
        # 最大令牌数
        ttk.Label(processing_frame, text="最大令牌数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        max_tokens_var = tk.StringVar(value=str(self.voice_ai_config.get("max_tokens", 1000)))
        max_tokens_entry = ttk.Entry(processing_frame, textvariable=max_tokens_var, width=20)
        max_tokens_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # 温度
        ttk.Label(processing_frame, text="温度:").grid(row=1, column=0, sticky=tk.W, pady=5)
        temperature_var = tk.StringVar(value=str(self.voice_ai_config.get("temperature", 0.1)))
        temperature_entry = ttk.Entry(processing_frame, textvariable=temperature_var, width=20)
        temperature_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 处理选项
        options_frame = ttk.LabelFrame(inner_frame, text="处理选项", padding="10")
        options_frame.pack(fill=tk.X, pady=10)
        
        auto_correct_var = tk.BooleanVar(value=self.voice_ai_config.get("auto_correct", True))
        auto_correct_check = ttk.Checkbutton(options_frame, text="自动纠错", variable=auto_correct_var)
        auto_correct_check.pack(anchor=tk.W, pady=2)
        
        grammar_check_var = tk.BooleanVar(value=self.voice_ai_config.get("grammar_check", True))
        grammar_check_check = ttk.Checkbutton(options_frame, text="语法检查", variable=grammar_check_var)
        grammar_check_check.pack(anchor=tk.W, pady=2)
        
        semantic_var = tk.BooleanVar(value=self.voice_ai_config.get("semantic_optimization", True))
        semantic_check = ttk.Checkbutton(options_frame, text="语义优化", variable=semantic_var)
        semantic_check.pack(anchor=tk.W, pady=2)
        
        # 语音转文字专用提示词设置
        voice_prompt_frame = ttk.LabelFrame(inner_frame, text="语音转文字专用提示词", padding="10")
        voice_prompt_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 预设提示词选择
        preset_frame = ttk.Frame(voice_prompt_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(preset_frame, text="预设模板:").pack(side=tk.LEFT, padx=5)
        preset_var = tk.StringVar(value="standard")
        preset_combo = ttk.Combobox(preset_frame, textvariable=preset_var, width=30)
        preset_combo['values'] = [
            "standard", "formal", "casual", "academic", "business", "creative"
        ]
        preset_combo.pack(side=tk.LEFT, padx=5)
        
        # 自定义提示词
        ttk.Label(voice_prompt_frame, text="自定义提示词 (使用 {text} 作为文本占位符):").pack(anchor=tk.W, pady=(10, 5))
        
        prompt_text = tk.Text(voice_prompt_frame, height=8, width=50)
        prompt_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 加载当前提示词
        current_prompt = self.voice_ai_config.get("voice_prompt", self.get_default_voice_prompt())
        if current_prompt:
            prompt_text.insert("1.0", current_prompt)
        
        # 预设模板切换
        def on_preset_change(event=None):
            preset = preset_var.get()
            templates = {
                "standard": "请优化以下语音转录文本，修正错别字和语法错误，保持原意不变：\n\n{text}",
                "formal": "请将以下语音转录文本转换为更正式的表达方式：\n\n{text}",
                "casual": "请将以下语音转录文本调整为更自然的口语化表达：\n\n{text}",
                "academic": "请将以下语音转录文本优化为学术写作风格：\n\n{text}",
                "business": "请将以下语音转录文本优化为商务沟通风格：\n\n{text}",
                "creative": "请将以下语音转录文本优化为更有创意的表达方式：\n\n{text}"
            }
            if preset in templates:
                prompt_text.delete("1.0", tk.END)
                prompt_text.insert("1.0", templates[preset])
        
        preset_combo.bind("<<ComboboxSelected>>", on_preset_change)
        
        # 按钮框架
        button_frame = ttk.Frame(inner_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        # 保存设置
        def save_voice_ai_settings():
            try:
                # 验证输入
                if not api_key_var.get().strip():
                    messagebox.showwarning("警告", "API密钥不能为空")
                    return
                
                max_tokens = int(max_tokens_var.get())
                if max_tokens <= 0 or max_tokens > 100000:
                    messagebox.showwarning("警告", "最大令牌数必须在1-100000之间")
                    return
                
                temperature = float(temperature_var.get())
                if temperature < 0 or temperature > 2:
                    messagebox.showwarning("警告", "温度必须在0-2之间")
                    return
                
                # 保存设置
                self.voice_ai_config["api_key"] = api_key_var.get().strip()
                self.voice_ai_config["api_base"] = api_base_var.get().strip()
                self.voice_ai_config["model"] = model_var.get()
                self.voice_ai_config["max_tokens"] = max_tokens
                self.voice_ai_config["temperature"] = temperature
                self.voice_ai_config["auto_correct"] = auto_correct_var.get()
                self.voice_ai_config["grammar_check"] = grammar_check_var.get()
                self.voice_ai_config["semantic_optimization"] = semantic_var.get()
                self.voice_ai_config["ai_format"] = ai_format_var.get()
                
                # 保存语音转文字专用提示词
                custom_prompt = prompt_text.get("1.0", tk.END).strip()
                self.voice_ai_config["voice_prompt"] = custom_prompt if custom_prompt else None
                
                self.save_voice_ai_config()
                self.update_voice_ai_session_headers()
                
                # 更新启用状态
                new_enabled_state = enabled_var.get()
                if new_enabled_state != self.voice_ai_enabled:
                    self.voice_ai_enabled = new_enabled_state
                    # 更新界面状态变量
                    if hasattr(self, 'ai_enabled_var'):
                        self.ai_enabled_var.set(self.voice_ai_enabled)
                    # 更新配置
                    self.voice_ai_config["enabled"] = self.voice_ai_enabled
                    self.log(f"语音转文字AI文本处理已{'启用' if self.voice_ai_enabled else '禁用'}")
                
                messagebox.showinfo("成功", "语音转文字AI设置已保存")
                settings_window.destroy()
                
            except ValueError as e:
                messagebox.showerror("错误", f"输入格式错误：{str(e)}")
        
        save_btn = ttk.Button(button_frame, text="保存", command=save_voice_ai_settings)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="取消", command=settings_window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # 测试按钮
        def test_voice_ai():
            test_text = "这是一个测试文本，包含一些可能的错误。今天天气很好，我想去公园散步。"
            result = self.process_text_with_voice_ai(test_text)
            if result != test_text:
                messagebox.showinfo("测试成功", f"语音转文字AI处理正常。\n原文: {test_text}\n处理后: {result}")
            else:
                messagebox.showinfo("测试结果", "AI处理完成，但文本无变化或处理失败。")
        
        test_btn = ttk.Button(button_frame, text="测试", command=test_voice_ai)
        test_btn.pack(side=tk.LEFT, padx=5)

    def show_audio_cleaner_ai_settings_dialog(self):
        """
        显示音频清理服务的AI设置对话框
        """
        if not AI_PROCESSOR_AVAILABLE:
            messagebox.showwarning("警告", "AI处理功能不可用：缺少必要库")
            return
        
        # 创建设置窗口
        settings_window = tk.Toplevel(self.root)
        settings_window.title("音频清理AI设置")
        settings_window.geometry("500x750")
        settings_window.resizable(False, False)
        
        # 设置窗口居中
        settings_window.transient(self.root)
        settings_window.grab_set()
        
        # 创建主画布和滚动条
        main_canvas = tk.Canvas(settings_window)
        scrollbar = ttk.Scrollbar(settings_window, orient="vertical", command=main_canvas.yview)
        main_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 创建可滚动的主框架
        main_frame = ttk.Frame(main_canvas)
        main_canvas_frame = main_canvas.create_window((0, 0), window=main_frame, anchor="nw")
        
        # 布局画布和滚动条
        main_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 配置滚动区域
        def configure_scroll_region(event=None):
            main_canvas.configure(scrollregion=main_canvas.bbox("all"))
            # 确保窗口宽度足够
            min_width = main_frame.winfo_reqwidth() + scrollbar.winfo_reqwidth()
            settings_window.geometry(f"{max(500, min_width)}x750")
        
        main_frame.bind("<Configure>", configure_scroll_region)
        settings_window.bind("<Configure>", lambda e: main_canvas.itemconfig(main_canvas_frame, width=settings_window.winfo_width() - scrollbar.winfo_width() - 40))
        
        # 添加内部填充
        inner_frame = ttk.Frame(main_frame, padding="20")
        inner_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(inner_frame, text="音频清理AI设置", font=("Arial", 14, "bold"))
        title_label.pack(pady=(0, 20))
        
        # 启用AI处理
        enabled_frame = ttk.Frame(inner_frame)
        enabled_frame.pack(fill=tk.X, pady=5)
        
        enabled_var = tk.BooleanVar(value=self.audio_cleaner_ai_enabled)
        enabled_check = ttk.Checkbutton(enabled_frame, text="启用AI文本清理", variable=enabled_var,
                                       command=lambda: self.toggle_audio_cleaner_ai_processor())
        enabled_check.pack(side=tk.LEFT)
        
        # API设置
        api_frame = ttk.LabelFrame(inner_frame, text="API设置", padding="10")
        api_frame.pack(fill=tk.X, pady=10)
        
        # API密钥
        ttk.Label(api_frame, text="API密钥:").grid(row=0, column=0, sticky=tk.W, pady=5)
        api_key_var = tk.StringVar(value=self.audio_cleaner_ai_config.get("api_key", ""))
        api_key_entry = ttk.Entry(api_frame, textvariable=api_key_var, width=50, show="*")
        api_key_entry.grid(row=0, column=1, pady=5)
        
        # API基础URL
        ttk.Label(api_frame, text="API地址:").grid(row=1, column=0, sticky=tk.W, pady=5)
        api_base_var = tk.StringVar(value=self.audio_cleaner_ai_config.get("api_base", ""))
        api_base_entry = ttk.Entry(api_frame, textvariable=api_base_var, width=50)
        api_base_entry.grid(row=1, column=1, pady=5)
        
        # 模型选择
        ttk.Label(api_frame, text="模型:").grid(row=2, column=0, sticky=tk.W, pady=5)
        model_var = tk.StringVar(value=self.audio_cleaner_ai_config.get("model", ""))
        model_combo = ttk.Combobox(api_frame, textvariable=model_var, width=47)
        model_combo['values'] = [
            "cognitivecomputations/dolphin-mistral-24b-venice-edition:free",
            "gpt-3.5-turbo",
            "gpt-4",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]
        model_combo.grid(row=2, column=1, pady=5)
        
        # 处理设置
        processing_frame = ttk.LabelFrame(inner_frame, text="处理设置", padding="10")
        processing_frame.pack(fill=tk.X, pady=10)
        
        # 最大令牌数
        ttk.Label(processing_frame, text="最大令牌数:").grid(row=0, column=0, sticky=tk.W, pady=5)
        max_tokens_var = tk.StringVar(value=str(self.audio_cleaner_ai_config.get("max_tokens", 1000)))
        max_tokens_entry = ttk.Entry(processing_frame, textvariable=max_tokens_var, width=20)
        max_tokens_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        
        # 温度
        ttk.Label(processing_frame, text="温度:").grid(row=1, column=0, sticky=tk.W, pady=5)
        temperature_var = tk.StringVar(value=str(self.audio_cleaner_ai_config.get("temperature", 0.1)))
        temperature_entry = ttk.Entry(processing_frame, textvariable=temperature_var, width=20)
        temperature_entry.grid(row=1, column=1, sticky=tk.W, pady=5)
        
        # 音频清理专用提示词设置
        prompt_frame = ttk.LabelFrame(inner_frame, text="音频清理专用提示词", padding="10")
        prompt_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # 预设提示词选择
        preset_frame = ttk.Frame(prompt_frame)
        preset_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(preset_frame, text="预设模板:").pack(side=tk.LEFT, padx=5)
        preset_var = tk.StringVar(value="standard")
        preset_combo = ttk.Combobox(preset_frame, textvariable=preset_var, width=30)
        preset_combo['values'] = [
            "standard", "aggressive", "conservative", "academic", "casual"
        ]
        preset_combo.pack(side=tk.LEFT, padx=5)
        
        # 自定义提示词
        ttk.Label(prompt_frame, text="自定义提示词 (使用 {text} 作为文本占位符):").pack(anchor=tk.W, pady=(10, 5))
        
        prompt_text = tk.Text(prompt_frame, height=8, width=50)
        prompt_text.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # 加载当前提示词
        current_prompt = self.audio_cleaner_ai_config.get("audio_cleanup_prompt", self.get_default_audio_cleaner_prompt())
        if current_prompt:
            prompt_text.insert("1.0", current_prompt)
        
        # 预设模板切换
        def on_preset_change(event=None):
            preset = preset_var.get()
            templates = {
                "standard": "# TASK\nYou are an audio cleanup AI. Analyze the transcript below and identify segments to be deleted.\n\n# RULES\nDelete the following types of content:\n1.  **Self-Corrections:** A broken/mistaken sentence immediately followed by a corrected, complete version of it. The first, broken one must be deleted.\n2.  **Repeated Takes:** Redundant repetitions of the same phrase. Keep only the last, best take.\n3.  **Noise & Errors:** Indecipherable audio, stutters, or segments ruined by non-speech noise (coughs, clicks).\n4.  **Fillers:** Excessive filler words (\"uh\", \"um\", \"like\", \"you know\"). Do not delete natural, short pauses for thought.\n5.  **Incomplete Sentences:** Remove sentences that are cut off or not completed.\n6.  **Unfinished Thoughts:** Delete segments where the speaker starts but doesn't complete their thought.\n\n# OUTPUT\nReturn the cleaned transcript with only the complete, well-formed sentences.\n\nOriginal transcript:\n{text}\n\nCleaned transcript:",
                "aggressive": "# TASK\nYou are an aggressive audio cleanup AI. Remove all imperfect content.\n\n# RULES\nDelete: self-corrections, repetitions, noise, stutters, filler words, incomplete sentences, unfinished thoughts, hesitations, and minor grammatical errors.\n\n# OUTPUT\nReturn only the perfect, complete sentences.\n\nOriginal transcript:\n{text}\n\nCleaned transcript:",
                "conservative": "# TASK\nYou are a conservative audio cleanup AI. Only remove obvious errors.\n\n# RULES\nDelete only: indecipherable noise, severe stutters, and obvious incomplete sentences.\nKeep most content including minor filler words and hesitations.\n\n# OUTPUT\nReturn the transcript with minimal cleaning.\n\nOriginal transcript:\n{text}\n\nCleaned transcript:",
                "academic": "# TASK\nYou are an academic audio cleanup AI. Clean transcripts for formal presentations.\n\n# RULES\nDelete: informal language, filler words, self-corrections, repetitions, and incomplete thoughts.\nPreserve: technical terms, formal expressions, and complete academic sentences.\n\n# OUTPUT\nReturn a clean, formal transcript suitable for academic contexts.\n\nOriginal transcript:\n{text}\n\nCleaned transcript:",
                "casual": "# TASK\nYou are a casual audio cleanup AI. Clean transcripts while keeping natural conversation flow.\n\n# RULES\nDelete: obvious errors, repetitions, and noise.\nKeep: natural filler words, conversational tone, and minor hesitations that make speech sound authentic.\n\n# OUTPUT\nReturn a clean but natural-sounding conversation transcript.\n\nOriginal transcript:\n{text}\n\nCleaned transcript:"
            }
            if preset in templates:
                prompt_text.delete("1.0", tk.END)
                prompt_text.insert("1.0", templates[preset])
        
        preset_combo.bind("<<ComboboxSelected>>", on_preset_change)
        
        # 按钮框架
        button_frame = ttk.Frame(inner_frame)
        button_frame.pack(fill=tk.X, pady=20)
        
        # 保存设置
        def save_audio_cleaner_ai_settings():
            try:
                # 验证输入
                if not api_key_var.get().strip():
                    messagebox.showwarning("警告", "API密钥不能为空")
                    return
                
                max_tokens = int(max_tokens_var.get())
                if max_tokens <= 0 or max_tokens > 100000:
                    messagebox.showwarning("警告", "最大令牌数必须在1-100000之间")
                    return
                
                temperature = float(temperature_var.get())
                if temperature < 0 or temperature > 2:
                    messagebox.showwarning("警告", "温度必须在0-2之间")
                    return
                
                # 保存设置
                self.audio_cleaner_ai_config["api_key"] = api_key_var.get().strip()
                self.audio_cleaner_ai_config["api_base"] = api_base_var.get().strip()
                self.audio_cleaner_ai_config["model"] = model_var.get()
                self.audio_cleaner_ai_config["max_tokens"] = max_tokens
                self.audio_cleaner_ai_config["temperature"] = temperature
                
                # 保存音频清理专用提示词
                custom_prompt = prompt_text.get("1.0", tk.END).strip()
                self.audio_cleaner_ai_config["audio_cleanup_prompt"] = custom_prompt if custom_prompt else None
                
                self.save_audio_cleaner_ai_config()
                self.update_audio_cleaner_ai_session_headers()
                
                # 更新启用状态
                if enabled_var.get() != self.audio_cleaner_ai_enabled:
                    self.toggle_audio_cleaner_ai_processor()
                
                messagebox.showinfo("成功", "音频清理AI设置已保存")
                settings_window.destroy()
                
            except ValueError as e:
                messagebox.showerror("错误", f"输入格式错误：{str(e)}")
        
        save_btn = ttk.Button(button_frame, text="保存", command=save_audio_cleaner_ai_settings)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(button_frame, text="取消", command=settings_window.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
        
        # 测试按钮
        def test_audio_cleaner_ai():
            test_text = "嗯...今天我想去公园，不对，我是说想去图书馆。那里很安静适合学习。呃...我想借一些关于编程的书籍。"
            result = self.process_text_with_audio_cleaner_ai(test_text)
            if result != test_text:
                messagebox.showinfo("测试成功", f"音频清理AI处理正常。\n原文: {test_text}\n处理后: {result}")
            else:
                messagebox.showinfo("测试结果", "音频清理AI处理完成，但文本无变化或处理失败。")
        
        test_btn = ttk.Button(button_frame, text="测试", command=test_audio_cleaner_ai)
        test_btn.pack(side=tk.LEFT, padx=5)


def main():
    """
    主函数
    """
    root = tk.Tk()
    app = AllInOneGUI(root)
    
    # 程序退出时清理临时文件
    def on_closing():
        app.cleanup_all_temp_files()
        root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


if __name__ == "__main__":
    main()
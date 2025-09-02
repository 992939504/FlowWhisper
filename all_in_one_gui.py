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

# 尝试导入拖放支持
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DRAG_DROP_AVAILABLE = True
except ImportError:
    try:
        # 备用拖放库
        from tkdnd2 import DND_FILES
        DRAG_DROP_AVAILABLE = True
    except ImportError:
        DRAG_DROP_AVAILABLE = False
from pathlib import Path
import json
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
import queue
import multiprocessing as mp

# 导入全局事件日志系统
try:
    from event_logger import logger, log_function_call, LogContext
    EVENT_LOGGER_AVAILABLE = True
except ImportError:
    EVENT_LOGGER_AVAILABLE = False
    # 创建空的logger对象以避免错误
    class DummyLogger:
        def log(self, *args, **kwargs):
            pass
        def emit(self, *args, **kwargs):
            pass
    logger = DummyLogger()

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
    
    # 尝试导入视频处理库
    try:
        import cv2
        VIDEO_AVAILABLE = True
    except ImportError:
        VIDEO_AVAILABLE = False
        
except ImportError:
    AUDIO_CLEANER_AVAILABLE = False
    VIDEO_AVAILABLE = False


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
        # 记录应用启动
        logger.log("GUI", "应用初始化开始", "AllInOneGUI启动")
        
        self.root = root
        self.root.title("音频转录全功能工具")
        self.root.geometry("800x700")
        self.root.resizable(True, True)
        
        # 设置应用图标
        try:
            self.root.iconbitmap("whisper/whisper.ico")
        except:
            logger.log("WARNING", "应用图标加载失败", "whisper/whisper.ico不存在")
        
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
        title_label = ttk.Label(header_container, text="[MIC] 音频转录全功能工具", style="Title.TLabel")
        title_label.pack(anchor=tk.W)
        
        # 副标题
        subtitle_label = ttk.Label(header_container, text="基于 whisper.cpp 的智能音频处理平台", style="Subtitle.TLabel")
        subtitle_label.pack(anchor=tk.W, pady=(5, 0))
        
        # 分隔线
        separator = ttk.Separator(title_frame, orient='horizontal')
        separator.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 工具栏
        toolbar = ttk.Frame(self.inner_frame)
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        # 日志查看器按钮
        log_viewer_btn = ttk.Button(toolbar, text="[CHART] 查看详细日志", command=self.open_log_viewer)
        log_viewer_btn.pack(side=tk.LEFT, padx=5)
        
        # 诊断工具按钮
        diagnose_btn = ttk.Button(toolbar, text="[TOOL] 运行诊断", command=self.diagnose_whisper)
        diagnose_btn.pack(side=tk.LEFT, padx=5)
        
        # 创建选项卡
        self.tab_control = ttk.Notebook(self.inner_frame)
        
        # 语音转文字服务选项卡 (移到第一个)
        self.voice_service_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.voice_service_tab, text="[MIC] 语音转文字服务")
        
        # 单文件转录选项卡
        self.single_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.single_tab, text="[FILE] 单文件转录")
        
        # 批量转录选项卡
        self.batch_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.batch_tab, text="[FOLDER] 批量转录")
        
        # 智能音频清理选项卡
        self.audio_cleaner_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.audio_cleaner_tab, text="[CLEAN] 智能音频清理")
        
        # 日志选项卡 (移到最后)
        self.log_tab = ttk.Frame(self.tab_control)
        self.tab_control.add(self.log_tab, text="[LOG] 操作日志")
        
        self.tab_control.pack(expand=True, fill=tk.BOTH)
        
        # 默认选中语音转文字服务选项卡
        self.tab_control.select(0)
        
        # 创建临时日志文本组件（在选项卡设置期间使用）
        self.temp_log_text = tk.Text(self.inner_frame, height=1, wrap=tk.WORD, state='disabled')
        self.temp_log_text.pack_forget()  # 隐藏临时日志组件
        
        # 状态栏
        status_frame = ttk.Frame(self.inner_frame, style="TFrame")
        status_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.status_var = tk.StringVar(value="[OK] 系统就绪")
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
        
        # 性能优化相关变量
        self.max_workers = min(mp.cpu_count(), 4)  # 限制最大并行数
        self.thread_pool = ThreadPoolExecutor(max_workers=self.max_workers)
        self.model_cache = {}  # 模型缓存
        self.file_queue = queue.Queue()  # 文件处理队列
        self.results_cache = {}  # 结果缓存
        
        # 音频缓冲区优化
        self.max_recording_duration = 300  # 最大录音时长（秒）
        self.audio_buffer_size = int(self.sample_rate * self.max_recording_duration)  # 预分配缓冲区大小
        self.audio_buffer = np.zeros(self.audio_buffer_size, dtype=np.float32)
        self.audio_buffer_index = 0
        
        # AI文本处理相关变量
        # 语音转文字服务AI配置
        self.voice_ai_config = self.load_voice_ai_config()
        self.voice_ai_enabled = self.voice_ai_config.get("enabled", False)
        self.voice_ai_session = None
        
        # 音频清理服务AI配置
        self.audio_cleaner_ai_config = self.load_audio_cleaner_ai_config()
        self.audio_cleaner_ai_enabled = self.audio_cleaner_ai_config.get("enabled", False)
        self.audio_cleaner_ai_session = None
        
        # 音频清理相关变量初始化
        self.ai_format_var = tk.StringVar(value="openai")
        self.format_info_var = tk.StringVar()
        self.openai_hint_var = tk.StringVar()
        self.api_url_var = tk.StringVar(value="https://api.openai.com/v1")
        self.api_key_var = tk.StringVar()
        self.cleaner_model_var = tk.StringVar(value="gpt-3.5-turbo")
        self.max_segment_var = tk.StringVar(value="50")
        self.gap_threshold_var = tk.StringVar(value="1.0")
        self.system_prompt_var = tk.StringVar(value=self.get_default_system_prompt())
        
        # 转录进程管理
        self.transcribe_process = None
        self.is_transcribing = False
        
        # 设置各选项卡
        self.setup_single_tab()
        self.setup_batch_tab()
        self.setup_voice_service_tab()
        self.setup_audio_cleaner_tab()
        self.setup_log_tab()
        
        # 查找模型
        self.find_models()
        
        # 加载所有设置
        self.load_all_settings()
        
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
        
        # 设置拖放样式
        style.configure("Drag.TFrame", background="#e3f2fd", borderwidth=2, relief="solid")
        
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
        
        # 检查是否需要自动启动语音服务
        if hasattr(self, 'auto_start_var') and self.auto_start_var.get():
            self.log("🚀 启动时自动启动语音服务...")
            self.root.after(1000, self.auto_start_voice_service)  # 延迟1秒启动，确保界面完全加载
        
    def setup_single_tab(self):
        """
        设置单文件转录选项卡
        """
        # 创建主框架和滚动条
        main_canvas = tk.Canvas(self.single_tab)
        scrollbar = ttk.Scrollbar(self.single_tab, orient="vertical", command=main_canvas.yview)
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
        header = ttk.Label(frame, text="单个音频文件转录", style="Header.TLabel")
        header.pack(pady=(0, 10))
        
        # 音频文件选择
        file_frame = ttk.LabelFrame(frame, text="选择音频/视频文件")
        file_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 文件输入框
        input_frame = ttk.Frame(file_frame)
        input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_frame, text="文件路径:").pack(side=tk.LEFT)
        
        self.single_file_var = tk.StringVar()
        file_entry = ttk.Entry(input_frame, textvariable=self.single_file_var, width=50)
        file_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(input_frame, text="浏览...", command=self.browse_file)
        browse_btn.pack(side=tk.LEFT)
        
        # 拖放区域
        self.drop_frame = ttk.Frame(file_frame, style="TFrame", padding="20")
        self.drop_frame.pack(fill=tk.X, padx=10, pady=10)
        
        drop_label_frame = ttk.LabelFrame(file_frame, text="或拖放文件到此处")
        drop_label_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        self.drop_label = ttk.Label(self.drop_frame, text="[FILE] 将音频或视频文件拖放到这里\n(支持 .wav, .mp3, .mp4, .avi 等格式)", 
                                   font=("Microsoft YaHei", 10), foreground="#6c757d")
        self.drop_label.pack()
        
        # 配置拖放
        if DRAG_DROP_AVAILABLE:
            self.setup_drag_drop()
        
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
        lang_frame = ttk.LabelFrame(frame, text="语言设置")
        lang_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 输入语言
        input_lang_frame = ttk.Frame(lang_frame)
        input_lang_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_lang_frame, text="输入语言:").pack(side=tk.LEFT)
        
        self.input_lang_var = tk.StringVar(value="自动检测")
        self.input_lang_combo = ttk.Combobox(input_lang_frame, textvariable=self.input_lang_var, width=20)
        self.input_lang_combo['values'] = ["自动检测", "英语 (en)", "中文 (zh)", "日语 (ja)", "德语 (de)", "法语 (fr)", "西班牙语 (es)", "韩语 (ko)", "俄语 (ru)"]
        self.input_lang_combo.current(0)
        self.input_lang_combo.pack(side=tk.LEFT, padx=5)
        
        # 输出语言
        output_lang_frame = ttk.Frame(lang_frame)
        output_lang_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(output_lang_frame, text="输出语言:").pack(side=tk.LEFT)
        
        self.output_lang_var = tk.StringVar(value="中文")
        self.output_lang_combo = ttk.Combobox(output_lang_frame, textvariable=self.output_lang_var, width=20)
        self.output_lang_combo['values'] = ["保持原语言", "中文", "英语", "日语", "德语", "法语", "西班牙语", "韩语", "俄语"]
        self.output_lang_combo.current(0)
        self.output_lang_combo.pack(side=tk.LEFT, padx=5)
        
        # 转录按钮
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
        # 添加文件信息显示
        info_frame = ttk.LabelFrame(frame, text="文件信息")
        info_frame.pack(fill=tk.X, pady=10, padx=5)
        
        # 文件名显示
        name_frame = ttk.Frame(info_frame)
        name_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(name_frame, text="文件名:", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.file_name_var = tk.StringVar(value="未选择文件")
        ttk.Label(name_frame, textvariable=self.file_name_var, font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=5)
        
        # 文件大小显示
        size_frame = ttk.Frame(info_frame)
        size_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(size_frame, text="文件大小:", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.file_size_var = tk.StringVar(value="-")
        ttk.Label(size_frame, textvariable=self.file_size_var, font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=5)
        
        # 文件类型显示
        type_frame = ttk.Frame(info_frame)
        type_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(type_frame, text="文件类型:", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT)
        self.file_type_var = tk.StringVar(value="-")
        ttk.Label(type_frame, textvariable=self.file_type_var, font=("Microsoft YaHei", 9)).pack(side=tk.LEFT, padx=5)
        
        # 处理提示
        tip_frame = ttk.Frame(info_frame)
        tip_frame.pack(fill=tk.X, padx=10, pady=5)
        self.process_tip_var = tk.StringVar(value="[INFO] 选择音频或视频文件后，将显示文件信息")
        tip_label = ttk.Label(tip_frame, textvariable=self.process_tip_var, 
                             font=("Microsoft YaHei", 9), foreground="#6c757d")
        tip_label.pack(anchor=tk.W)
        
        # 绑定文件路径变化事件
        self.single_file_var.trace('w', self.update_file_info)
        
        # 按钮区域
        btn_frame = ttk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=10)
        
            
          
        # 添加停止按钮（初始禁用）
        self.stop_transcribe_btn = ttk.Button(btn_frame, text="⏹️ 停止转录", command=self.stop_transcription, state="disabled")
        self.stop_transcribe_btn.pack(side=tk.LEFT, padx=5)
        
        transcribe_btn = ttk.Button(btn_frame, text="🎵 开始转录", command=self.transcribe_single_file, style="Primary.TButton")
        transcribe_btn.pack(side=tk.RIGHT, padx=5)
        
        clear_btn = ttk.Button(btn_frame, text="🗑️ 清空", command=self.clear_single_file, style="Warning.TButton")
        clear_btn.pack(side=tk.RIGHT, padx=5)
        
        # 保存设置按钮
        save_settings_btn = ttk.Button(btn_frame, text="💾 保存设置", command=self.save_all_settings)
        save_settings_btn.pack(side=tk.LEFT, padx=5)
        
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
        audio_extensions = [("WAV", ".wav"), ("MP3", ".mp3"), ("OGG", ".ogg"), ("FLAC", ".flac"), ("M4A", ".m4a")]
        video_extensions = [("MP4", ".mp4"), ("AVI", ".avi"), ("MKV", ".mkv"), ("MOV", ".mov"), ("WMV", ".wmv"), ("FLV", ".flv")]
        
        # 音频文件类型
        audio_frame = ttk.Frame(ext_frame)
        audio_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(audio_frame, text="音频文件:", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        for i, (text, ext) in enumerate(audio_extensions):
            var = tk.BooleanVar(value=True)
            self.ext_vars[ext] = var
            ttk.Checkbutton(audio_frame, text=text, variable=var).pack(side=tk.LEFT, padx=5)
        
        # 视频文件类型
        video_frame = ttk.Frame(ext_frame)
        video_frame.pack(fill=tk.X, padx=10, pady=2)
        ttk.Label(video_frame, text="视频文件:", font=("Microsoft YaHei", 9, "bold")).pack(side=tk.LEFT, padx=(0, 10))
        
        for i, (text, ext) in enumerate(video_extensions):
            var = tk.BooleanVar(value=False)
            self.ext_vars[ext] = var
            ttk.Checkbutton(video_frame, text=text, variable=var).pack(side=tk.LEFT, padx=5)
        
        # ffmpeg提示
        if not self.check_ffmpeg_available():
            ttk.Label(ext_frame, text="[WARN] 处理视频文件需要安装ffmpeg", 
                      font=("Microsoft YaHei", 9), foreground="orange").pack(padx=10, pady=2)
        
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
        
        # 自动输入设置
        auto_input_frame = ttk.Frame(settings_frame)
        auto_input_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.auto_input_var = tk.BooleanVar(value=True)
        auto_input_check = ttk.Checkbutton(auto_input_frame, text="转录完成后自动输入", variable=self.auto_input_var)
        auto_input_check.pack(side=tk.LEFT, padx=5)
        
        # 输入方式设置
        input_method_frame = ttk.Frame(settings_frame)
        input_method_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(input_method_frame, text="输入方式:").pack(side=tk.LEFT, padx=5)
        
        self.input_method_var = tk.StringVar(value="paste")
        input_method_paste = ttk.Radiobutton(input_method_frame, text="粘贴输入", variable=self.input_method_var, value="paste")
        input_method_paste.pack(side=tk.LEFT, padx=5)
        
        input_method_direct = ttk.Radiobutton(input_method_frame, text="直接输入", variable=self.input_method_var, value="direct")
        input_method_direct.pack(side=tk.LEFT, padx=5)
        
        # 录音时长设置
        duration_frame = ttk.Frame(settings_frame)
        duration_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(duration_frame, text="最大录音时长:").pack(side=tk.LEFT, padx=5)
        
        # 使用不同的变量名避免冲突
        self.max_recording_duration_var = tk.IntVar(value=300)
        duration_spinbox = ttk.Spinbox(duration_frame, from_=60, to=3600, textvariable=self.max_recording_duration_var, 
                                     width=10, increment=60)
        duration_spinbox.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(duration_frame, text="秒（60-3600）").pack(side=tk.LEFT, padx=2)
        
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
        
        # 自动启动服务设置
        auto_start_frame = ttk.Frame(settings_frame)
        auto_start_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.auto_start_var = tk.BooleanVar(value=False)
        auto_start_check = ttk.Checkbutton(auto_start_frame, text="启动时自动启动服务", variable=self.auto_start_var)
        auto_start_check.pack(side=tk.LEFT, padx=5)
        
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
        
        # 统一保存按钮
        save_all_frame = ttk.Frame(settings_frame)
        save_all_frame.pack(fill=tk.X, padx=10, pady=10)
        
        save_all_btn = ttk.Button(save_all_frame, text="保存所有设置", command=self.save_all_voice_service_settings, style="Primary.TButton")
        save_all_btn.pack(side=tk.LEFT, padx=5)
        
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
            "[FILE] 选择媒体", 
            "⚙️ AI设置", 
            "[CLEAN] 智能清理", 
            "[VIDEO] 生成输出"
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
                separator = ttk.Label(workflow_frame, text="->", font=("Arial", 14), 
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
        
        # AI配置按钮
        ai_config_frame = ttk.Frame(frame)
        ai_config_frame.pack(fill=tk.X, pady=10, padx=5)
        
        ai_settings_btn = ttk.Button(ai_config_frame, text="⚙️ AI设置", 
                                    command=self.show_audio_cleaner_ai_settings_dialog, 
                                    style="Primary.TButton")
        ai_settings_btn.pack(side=tk.LEFT, padx=5)
        
        # 配置状态提示
        self.ai_config_status_var = tk.StringVar(value="[WARN] 请配置AI设置")
        config_status_label = ttk.Label(ai_config_frame, textvariable=self.ai_config_status_var,
                                      font=("Microsoft YaHei", 9), foreground="#ffc107")
        config_status_label.pack(side=tk.LEFT, padx=20)
        
        # 音频/视频文件选择
        audio_frame = ttk.LabelFrame(frame, text="[FILE] 媒体文件 (步骤 1)")
        audio_frame.pack(fill=tk.X, pady=10, padx=5)
        
        file_select_frame = ttk.Frame(audio_frame)
        file_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(file_select_frame, text="媒体文件:").pack(side=tk.LEFT)
        
        self.cleaner_audio_var = tk.StringVar()
        audio_entry = ttk.Entry(file_select_frame, textvariable=self.cleaner_audio_var, width=50)
        audio_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        browse_btn = ttk.Button(file_select_frame, text="浏览...", command=self.browse_cleaner_audio)
        browse_btn.pack(side=tk.LEFT)
        
        # 输出文件设置
        self.output_select_frame = ttk.Frame(audio_frame)
        self.output_select_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(self.output_select_frame, text="输出文件:").pack(side=tk.LEFT)
        
        self.cleaner_output_var = tk.StringVar(value="cleaned_media.mp3")
        output_entry = ttk.Entry(self.output_select_frame, textvariable=self.cleaner_output_var, width=50)
        output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 视频额外输出选项（初始隐藏）
        self.audio_output_frame = ttk.Frame(audio_frame)
        # 不立即pack，会在选择视频文件时显示
        
        ttk.Label(self.audio_output_frame, text="音频输出:").pack(side=tk.LEFT)
        
        self.cleaner_audio_output_var = tk.StringVar()
        audio_output_entry = ttk.Entry(self.audio_output_frame, textvariable=self.cleaner_audio_output_var, width=50)
        audio_output_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # 视频预览区域（初始隐藏）
        self.video_preview_frame = ttk.LabelFrame(audio_frame, text="[VIDEO] 视频预览与片段选择")
        
        # 预览控制栏
        preview_control_frame = ttk.Frame(self.video_preview_frame)
        preview_control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(preview_control_frame, text="▶️ 预览视频", 
                  command=self.preview_video).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(preview_control_frame, text="📐 选择片段", 
                  command=self.select_video_segments).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(preview_control_frame, text="[PROCESS] 重置选择", 
                  command=self.reset_segment_selection).pack(side=tk.LEFT, padx=5)
        
        # 预览信息
        self.preview_info_var = tk.StringVar(value="未选择视频文件")
        preview_info_label = ttk.Label(preview_control_frame, textvariable=self.preview_info_var,
                                     font=("Microsoft YaHei", 9), foreground="#6c757d")
        preview_info_label.pack(side=tk.LEFT, padx=20)
        
        # 片段时间范围选择
        range_frame = ttk.Frame(self.video_preview_frame)
        range_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Label(range_frame, text="开始时间:").pack(side=tk.LEFT, padx=(0, 5))
        self.start_time_var = tk.StringVar(value="00:00:00")
        start_time_entry = ttk.Entry(range_frame, textvariable=self.start_time_var, width=10)
        start_time_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Label(range_frame, text="结束时间:").pack(side=tk.LEFT, padx=(0, 5))
        self.end_time_var = tk.StringVar(value="00:00:00")
        end_time_entry = ttk.Entry(range_frame, textvariable=self.end_time_var, width=10)
        end_time_entry.pack(side=tk.LEFT, padx=(0, 10))
        
        ttk.Button(range_frame, text="应用时间范围", 
                  command=self.apply_time_range).pack(side=tk.LEFT, padx=5)
        
        # 片段列表（使用Treeview）
        columns = ("开始", "结束", "时长", "选择")
        self.segment_tree = ttk.Treeview(self.video_preview_frame, columns=columns, 
                                        show="headings", height=6)
        
        # 设置列宽和标题
        self.segment_tree.column("开始", width=100)
        self.segment_tree.column("结束", width=100)
        self.segment_tree.column("时长", width=80)
        self.segment_tree.column("选择", width=60)
        
        self.segment_tree.heading("开始", text="开始时间")
        self.segment_tree.heading("结束", text="结束时间")
        self.segment_tree.heading("时长", text="时长")
        self.segment_tree.heading("选择", text="选择")
        
        # 添加滚动条
        segment_scrollbar = ttk.Scrollbar(self.video_preview_frame, command=self.segment_tree.yview)
        self.segment_tree.configure(yscrollcommand=segment_scrollbar.set)
        
        self.segment_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=5)
        segment_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 片段操作按钮
        segment_btn_frame = ttk.Frame(self.video_preview_frame)
        segment_btn_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(segment_btn_frame, text="全选", 
                  command=lambda: self.toggle_all_segments(True)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(segment_btn_frame, text="全不选", 
                  command=lambda: self.toggle_all_segments(False)).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(segment_btn_frame, text="反选", 
                  command=self.invert_segment_selection).pack(side=tk.LEFT, padx=5)
        
        # 处理选项
        process_frame = ttk.Frame(audio_frame)
        process_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.extract_only_var = tk.BooleanVar(value=False)
        extract_check = ttk.Checkbutton(process_frame, text="仅提取音频（不处理视频）", 
                                       variable=self.extract_only_var,
                                       command=self.toggle_video_preview)
        extract_check.pack(side=tk.LEFT, padx=5)
        
        self.keep_video_var = tk.BooleanVar(value=True)
        video_check = ttk.Checkbutton(process_frame, text="保留视频轨道", 
                                     variable=self.keep_video_var)
        video_check.pack(side=tk.LEFT, padx=5)
        
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
        
        reset_btn = ttk.Button(btn_frame, text="[PROCESS] 重置设置", command=self.reset_cleaner_settings)
        reset_btn.pack(side=tk.RIGHT, padx=5)
        
        # 自动加载设置
        self.auto_load_api_settings()
        
        # 测试OpenAI库
        self.test_openai_library()
        
        # 初始化AI格式
        self.update_ai_format_ui()
        
        # 更新AI配置状态
        self.update_ai_config_status()
        
        # 使用说明
        instruction_frame = ttk.LabelFrame(frame, text="使用说明")
        instruction_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5)
        
        instructions = (
            "🎯 使用指南：\n"
            "1. 选择要处理的媒体文件（音频或视频）\n"
            "2. 点击\"⚙️ AI设置\"按钮配置AI参数\n"
            "3. 设置输出文件路径和处理选项\n"
            "4. 根据需要调整高级设置\n"
            "5. 编辑系统提示词以优化清理效果\n"
            "6. 选择是否启用二次转录和HRT字幕生成\n"
            "7. 点击\"🚀 开始智能清理\"按钮进行处理\n\n"
            "[VIDEO] 视频处理功能：\n"
            "- 支持常见视频格式：MP4, AVI, MKV, MOV, WMV, FLV\n"
            "- 可选择保留视频轨道或仅输出音频\n"
            "- 视频预览和片段选择功能\n"
            "- 直接生成视频字幕文件\n\n"
            "[PROCESS] 处理流程：\n"
            "步骤1: 使用whisper对媒体进行语音识别\n"
            "步骤2: 优化SRT片段（分段和间隔处理）\n"
            "步骤3: AI分析识别需要删除的低质量片段\n"
            "步骤4: 剪辑媒体，保留优质片段生成新文件\n"
            "步骤5: (可选) 对清理后的内容进行二次转录\n"
            "步骤6: (可选) 生成HRT格式字幕文件\n\n"
            "[MIC] 二次转录优势：\n"
            "- 清理后的内容没有噪音和低质量部分\n"
            "- 第二次语音识别准确度更高\n"
            "- 生成的字幕质量更好\n"
            "- 避免原始媒体中的干扰因素\n\n"
            "[LOG] HRT字幕特点：\n"
            "- 自动过滤无意义片段（嗯、啊、呃等）\n"
            "- 移除过短的字幕片段（小于1秒）\n"
            "- 优化字幕显示时间（2-5秒）\n"
            "- 清理多余标点符号\n\n"
            "[INFO] 提示：\n"
            "- AI设置中包含完整的API配置和提示词设置\n"
            "- 支持多种AI服务：OpenAI、Ollama、Gemini等\n"
            "- 视频文件会自动提取音频进行处理\n"
            "- 系统提示词可以自定义以获得更好的清理效果\n"
            "- 支持的音频格式：wav, mp3, m4a, flac等\n"
            "- 输出音频格式为mp3，视频格式为mp4，字幕格式为srt"
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
    
    def auto_start_voice_service(self):
        """
        自动启动语音服务
        """
        if not VOICE_SERVICE_AVAILABLE:
            self.log("[ERR] 无法自动启动语音服务：缺少必要的依赖库")
            return
        
        if not self.voice_service_active:
            self.log("🚀 自动启动语音转文字服务...")
            self.start_voice_service()
        else:
            self.log("ℹ️ 语音服务已在运行")
    
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
    
    def save_all_voice_service_settings(self):
        """
        统一保存所有语音转文字服务设置
        """
        # 读取现有配置
        config = {}
        if os.path.exists(self.voice_config_file):
            try:
                with open(self.voice_config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            except:
                pass
        
        # 验证录音时长设置
        max_duration = self.max_recording_duration_var.get()
        if max_duration < 60 or max_duration > 3600:
            messagebox.showwarning("警告", "录音时长必须在60-3600秒之间")
            return
        
        # 更新所有设置
        config["hotkey"] = self.hotkey_var.get()
        config["start_sound"] = self.start_sound_var.get()
        config["end_sound"] = self.end_sound_var.get()
        config["start_sound_freq"] = int(self.start_freq_var.get())
        config["end_sound_freq"] = int(self.end_freq_var.get())
        config["sound_duration"] = int(self.duration_var.get())
        config["voice_model"] = self.voice_model_var.get()
        config["voice_language"] = self.voice_lang_var.get()
        config["voice_output_language"] = self.voice_output_lang_var.get()
        config["auto_input_enabled"] = self.auto_input_var.get()
        config["input_method"] = self.input_method_var.get()
        config["auto_start_enabled"] = self.auto_start_var.get()
        config["max_recording_duration"] = max_duration
        
        # 保存配置
        self.save_voice_service_config(config)
        
        # 应用录音时长设置
        self.max_recording_duration = max_duration
        # 重新计算缓冲区大小
        self.audio_buffer_size = int(self.sample_rate * self.max_recording_duration)
        # 重新分配缓冲区
        self.audio_buffer = np.zeros(self.audio_buffer_size, dtype=np.float32)
        self.audio_buffer_index = 0
        
        self.log(f"[OK] 所有语音转文字服务设置已保存（录音时长：{max_duration}秒）")
        messagebox.showinfo("成功", f"所有语音转文字服务设置已保存\n录音时长已设置为：{max_duration}秒")
        
        # 如果服务正在运行，重启服务以应用新设置
        if self.voice_service_active:
            self.log("[PROCESS] 重启语音服务以应用新设置...")
            self.stop_voice_service()
            self.start_voice_service()
    
    def browse_file(self):
        """
        浏览并选择音频/视频文件
        """
        filetypes = [
            ("支持的媒体文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv"),
            ("音频文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a"),
            ("视频文件", "*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv"),
            ("所有文件", "*.*")
        ]
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.single_file_var.set(file_path)
            
            # 检查是否为视频文件
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
                self.log(f"选择了视频文件: {file_path}")
                # 如果ffmpeg可用，可以添加视频处理提示
                if self.check_ffmpeg_available():
                    self.log("[OK] 检测到ffmpeg，支持视频处理")
                else:
                    self.log("[WARN] 未检测到ffmpeg，仅提取音频")
            else:
                self.log(f"选择了音频文件: {file_path}")
    
    def setup_drag_drop(self):
        """
        设置拖放功能
        """
        try:
            # 注册拖放目标
            self.drop_frame.drop_target_register(DND_FILES)
            self.drop_frame.dnd_bind('<<Drop>>', self.on_drop)
            self.drop_frame.dnd_bind('<<DragEnter>>', self.on_drag_enter)
            self.drop_frame.dnd_bind('<<DragLeave>>', self.on_drag_leave)
            
            # 更新提示文本
            self.drop_label.config(text="[FILE] 将音频或视频文件拖放到这里\n(支持 .wav, .mp3, .mp4, .avi 等格式)\n\n[OK] 拖放功能已启用")
        except Exception as e:
            self.log(f"拖放功能初始化失败: {e}")
            self.drop_label.config(text="[ERR] 拖放功能不可用\n请使用'浏览...'按钮选择文件")
    
    def on_drag_enter(self, event):
        """
        拖拽进入时的处理
        """
        self.drop_frame.config(style="Drag.TFrame")
        self.drop_label.config(foreground="blue")
    
    def on_drag_leave(self, event):
        """
        拖拽离开时的处理
        """
        self.drop_frame.config(style="TFrame")
        self.drop_label.config(foreground="#6c757d")
    
    def on_drop(self, event):
        """
        文件拖放处理
        """
        try:
            # 获取拖放的文件路径
            file_path = event.data
            
            # Windows下可能需要去除引号
            if file_path.startswith('{') and file_path.endswith('}'):
                file_path = file_path[1:-1]
            elif file_path.startswith('"') and file_path.endswith('"'):
                file_path = file_path[1:-1]
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.root.after(0, lambda: messagebox.showerror("错误", f"文件不存在: {file_path}"))
                self.log(f"错误: 拖放的文件不存在: {file_path}")
                return
            
            # 检查文件类型
            ext = os.path.splitext(file_path)[1].lower()
            supported_extensions = ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
            
            if ext not in supported_extensions:
                self.root.after(0, lambda: messagebox.showerror("错误", f"不支持的文件格式: {ext}\n\n支持的格式: {', '.join(supported_extensions)}"))
                self.log(f"错误: 不支持的文件格式: {ext}")
                return
            
            # 设置文件路径
            self.single_file_var.set(file_path)
            
            # 记录日志
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
                self.log(f"拖入视频文件: {file_path}")
                if self.check_ffmpeg_available():
                    self.log("[OK] 检测到ffmpeg，支持视频处理")
                else:
                    self.log("[WARN] 未检测到ffmpeg，仅提取音频")
            else:
                self.log(f"拖入音频文件: {file_path}")
            
            # 恢复样式
            self.drop_frame.config(style="TFrame")
            self.drop_label.config(foreground="#6c757d")
            
            # 自动开始转录
            self.root.after(100, self.auto_transcribe)
            
        except Exception as e:
            self.log(f"处理拖放文件时出错: {e}")
            self.root.after(0, lambda err=e: messagebox.showerror("错误", f"处理文件时出错: {err}"))
    
    def auto_transcribe(self):
        """
        自动开始转录
        """
        # 检查是否已选择模型
        if not self.model_var.get():
            self.log("[WARN] 请先选择模型文件")
            return
        
        # 检查是否有文件
        audio_file = self.single_file_var.get()
        if not audio_file:
            return
        
        # 确认是否开始转录
        def confirm_transcribe():
            result = messagebox.askyesno("确认转录", f"是否开始转录文件:\n{os.path.basename(audio_file)}？")
            if result:
                self.transcribe_single_file()
        
        self.root.after(0, confirm_transcribe)
    
    def update_file_info(self, *args):
        """
        更新文件信息显示
        """
        file_path = self.single_file_var.get()
        
        if not file_path:
            self.file_name_var.set("未选择文件")
            self.file_size_var.set("-")
            self.file_type_var.set("-")
            self.process_tip_var.set("[INFO] 选择音频或视频文件后，将显示文件信息")
            return
        
        try:
            # 检查文件是否存在
            if not os.path.exists(file_path):
                self.file_name_var.set("文件不存在")
                self.file_size_var.set("-")
                self.file_type_var.set("-")
                self.process_tip_var.set("[ERR] 文件不存在，请重新选择")
                return
            
            # 获取文件信息
            file_name = os.path.basename(file_path)
            file_size = os.path.getsize(file_path)
            file_ext = os.path.splitext(file_name)[1].lower()
            
            # 更新文件名
            self.file_name_var.set(file_name)
            
            # 格式化文件大小
            if file_size < 1024:
                size_str = f"{file_size} B"
            elif file_size < 1024 * 1024:
                size_str = f"{file_size / 1024:.1f} KB"
            elif file_size < 1024 * 1024 * 1024:
                size_str = f"{file_size / (1024 * 1024):.1f} MB"
            else:
                size_str = f"{file_size / (1024 * 1024 * 1024):.1f} GB"
            
            self.file_size_var.set(size_str)
            
            # 确定文件类型
            audio_extensions = ['.wav', '.mp3', '.ogg', '.flac', '.m4a', '.aac', '.wma']
            video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
            
            if file_ext in audio_extensions:
                self.file_type_var.set("音频文件")
                self.process_tip_var.set("[OK] 音频文件 - 可以直接进行转录")
            elif file_ext in video_extensions:
                self.file_type_var.set("视频文件")
                if self.check_ffmpeg_available():
                    self.process_tip_var.set("[OK] 视频文件 - 检测到ffmpeg，将自动提取音频")
                else:
                    self.process_tip_var.set("[WARN] 视频文件 - 需要安装ffmpeg才能提取音频")
            else:
                self.file_type_var.set("未知类型")
                self.process_tip_var.set("[ERR] 不支持的文件格式")
        
        except Exception as e:
            self.log(f"更新文件信息时出错: {e}")
            self.file_name_var.set("获取信息失败")
            self.file_size_var.set("-")
            self.file_type_var.set("-")
    
    def browse_directory(self):
        """
        浏览并选择目录
        """
        directory = filedialog.askdirectory()
        if directory:
            self.batch_dir_var.set(directory)
    
    def get_language_code(self):
        """
        获取输入语言代码
        
        返回:
            str: 语言代码，如果是自动检测则返回空字符串
        """
        lang = self.input_lang_var.get()
        if lang == "自动检测":
            return ""
        
        # 从选项中提取语言代码 (en, zh, ja, etc.)
        return lang.split("(")[1].split(")")[0] if "(" in lang else ""
    
    def get_output_language(self):
        """
        获取输出语言
        
        返回:
            str: 输出语言名称
        """
        return self.output_lang_var.get()
    
    def log(self, message):
        """
        添加日志消息（线程安全版本）
        
        参数:
            message: 日志消息
        """
        # 记录到全局日志系统
        logger.log("GUI", "用户操作", message)
        
        # 检查是否在主线程中
        if threading.current_thread() is threading.main_thread():
            self._log_to_gui(message)
        else:
            # 在后台线程中，使用after方法在主线程中更新GUI
            self.root.after(0, lambda: self._log_to_gui(message))
    
    def _log_to_gui(self, message):
        """
        实际执行GUI日志更新的方法（必须在主线程中调用）
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
                self.log("[OK] 已粘贴API Key")
                self.update_status("[OK] API Key已粘贴", "success")
            else:
                self.log("[ERR] 剪贴板为空")
                self.update_status("[ERR] 剪贴板为空", "error")
        except ImportError:
            self.log("[ERR] 缺少pyperclip库，无法使用粘贴功能")
            self.update_status("[ERR] 缺少pyperclip库", "error")
        except Exception as e:
            self.log(f"[ERR] 粘贴API Key失败: {e}")
            self.update_status("[ERR] 粘贴失败", "error")
    
    def quick_config_openrouter(self):
        """
        快速配置OpenRouter设置
        """
        self.ai_format_var.set("openai")
        self.api_url_var.set("https://openrouter.ai")
        self.cleaner_model_var.set("cognitivecomputations/dolphin-mistral-24b-venice-edition:free")
        self.update_ai_format_ui()
        self.log("[OK] 已配置OpenRouter默认设置")
        self.update_status("[OK] OpenRouter配置完成", "success")
        messagebox.showinfo("配置完成", "已配置OpenRouter默认设置：\n\nAI格式: OpenAI\nAPI URL: https://openrouter.ai\n模型: cognitivecomputations/dolphin-mistral-24b-venice-edition:free\n\n请粘贴您的API Key后点击测试连接")
    
    def quick_config_ollama(self):
        """
        快速配置Ollama设置
        """
        self.ai_format_var.set("ollama")
        self.api_url_var.set("http://localhost:11434")
        self.cleaner_model_var.set("llama3.1:8b")
        self.update_ai_format_ui()
        self.log("[OK] 已配置Ollama默认设置")
        self.update_status("[OK] Ollama配置完成", "success")
        messagebox.showinfo("配置完成", "已配置Ollama默认设置：\n\nAI格式: Ollama\nAPI URL: http://localhost:11434\n模型: llama3.1:8b\n\n请确保Ollama服务正在运行，然后点击测试连接")
    
    def quick_config_gemini(self):
        """
        快速配置Gemini设置
        """
        self.ai_format_var.set("gemini")
        self.api_url_var.set("https://generativelanguage.googleapis.com/v1beta")
        self.cleaner_model_var.set("gemini-1.5-flash")
        self.update_ai_format_ui()
        self.log("[OK] 已配置Gemini默认设置")
        self.update_status("[OK] Gemini配置完成", "success")
        messagebox.showinfo("配置完成", "已配置Gemini默认设置：\n\nAI格式: Gemini\nAPI URL: https://generativelanguage.googleapis.com/v1beta\n模型: gemini-1.5-flash\n\n请粘贴您的API Key后点击测试连接")
    
    def test_api_connection(self):
        """
        测试API连接
        """
        ai_format = self.ai_format_var.get()
        api_url = self.api_url_var.get()
        api_key = self.api_key_var.get()
        
        if not api_url:
            self.log("[ERR] 请先填写API URL")
            self.update_status("[ERR] 请先填写API配置", "error")
            return
        
        # Ollama格式可能不需要API Key
        if ai_format != "ollama" and not api_key:
            self.log("[ERR] 请先填写API Key")
            self.update_status("[ERR] 请先填写API配置", "error")
            return
        
        self.update_status("[PROCESS] 正在测试API连接...", "warning")
        self.log(f"[PROCESS] 开始测试{ai_format.upper()}格式API连接...")
        
        # 在新线程中测试，避免GUI冻结
        threading.Thread(target=self._test_api_connection_thread, args=(api_url, api_key, ai_format)).start()
    
    def _test_api_connection_thread(self, api_url, api_key, ai_format):
        """
        在线程中测试API连接
        """
        try:
            if not AUDIO_CLEANER_AVAILABLE:
                self.log("[ERR] 缺少必要的库，无法测试API连接")
                self.update_status("[ERR] 缺少依赖库", "error")
                return
            
            # 获取格式化的API URL
            formatted_url = self.get_formatted_api_url()
            if not formatted_url:
                self.log("[ERR] API URL格式化失败")
                self.update_status("[ERR] API URL格式错误", "error")
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
                
                self.log("[OK] OpenAI格式API连接测试成功")
                self.log(f"📝 响应: {response.choices[0].message.content}")
                self.log(f"🤖 使用模型: {response.model}")
                self.update_status("[OK] OpenAI API连接成功", "success")
                
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
                
                self.log("[OK] Ollama格式API连接测试成功")
                self.log(f"📝 响应: {response.choices[0].message.content}")
                self.log(f"🤖 使用模型: {response.model}")
                self.update_status("[OK] Ollama API连接成功", "success")
                
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
                    
                    self.log("[OK] Gemini格式API连接测试成功")
                    self.log(f"📝 响应: {response.choices[0].message.content}")
                    self.log(f"🤖 使用模型: {response.model}")
                    self.update_status("[OK] Gemini API连接成功", "success")
                    
                except Exception as gemini_error:
                    self.log(f"⚠ Gemini OpenAI兼容模式失败: {gemini_error}")
                    self.log("[INFO] 提示: Gemini可能需要使用官方API或其他兼容方式")
                    self.update_status("⚠ Gemini连接可能需要特殊配置", "warning")
                    return
            
        except Exception as e:
            self.log(f"[ERR] {ai_format.upper()}格式API连接测试失败: {e}")
            self.update_status("[ERR] API连接失败", "error")
    
    def update_status(self, message, status_type="normal"):
        """
        更新状态栏和指示器（线程安全版本）
        
        参数:
            message: 状态消息
            status_type: 状态类型 (normal, success, warning, error)
        """
        # 检查是否在主线程中
        if threading.current_thread() is threading.main_thread():
            self._update_status_gui(message, status_type)
        else:
            # 在后台线程中，使用after方法在主线程中更新GUI
            self.root.after(0, lambda: self._update_status_gui(message, status_type))
    
    def _update_status_gui(self, message, status_type):
        """
        实际执行GUI状态更新的方法（必须在主线程中调用）
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
        更新进度条和状态文本（线程安全版本）
        
        参数:
            value: 进度值 (0-100)
            status: 状态文本
        """
        # 检查是否在主线程中
        if threading.current_thread() is threading.main_thread():
            self._update_progress_gui(value, status)
        else:
            # 在后台线程中，使用after方法在主线程中更新GUI
            self.root.after(0, lambda: self._update_progress_gui(value, status))
    
    def _update_progress_gui(self, value, status=""):
        """
        实际执行GUI进度更新的方法（必须在主线程中调用）
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
        self.update_status("[OK] 已清空文件选择", "success")
        self.log("[OK] 已清空文件选择")
    
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
    
    def test_transcription_env(self):
        """
        测试转录环境
        """
        self.log("=" * 50)
        self.log("开始测试转录环境...")
        
        # 检查whisper-cli
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        self.log(f"检查whisper-cli: {whisper_cli}")
        if os.path.exists(whisper_cli):
            self.log("[OK] whisper-cli.exe 存在")
            # 测试运行
            try:
                result = subprocess.run([whisper_cli, "--help"], capture_output=True, text=True, timeout=5)
                if result.returncode == 0:
                    self.log("[OK] whisper-cli.exe 可以正常运行")
                else:
                    self.log(f"[WARN] whisper-cli.exe 返回代码: {result.returncode}")
            except Exception as e:
                self.log(f"[ERR] whisper-cli.exe 运行失败: {e}")
        else:
            self.log("[ERR] whisper-cli.exe 不存在")
        
        # 检查模型文件
        model = self.model_var.get()
        if model:
            model_path = self.get_model_path()
            if model_path and os.path.exists(model_path):
                file_size = os.path.getsize(model_path) / (1024 * 1024)  # MB
                self.log(f"[OK] 模型文件存在: {os.path.basename(model_path)} ({file_size:.1f} MB)")
            else:
                self.log("[ERR] 模型文件不存在或路径无效")
        else:
            self.log("[WARN] 未选择模型文件")
        
        # 检查ffmpeg（用于视频处理）
        try:
            result = subprocess.run(['ffmpeg', '-version'], capture_output=True, text=True, timeout=2)
            if result.returncode == 0:
                self.log("[OK] ffmpeg 已安装")
            else:
                self.log("[ERR] ffmpeg 未正确安装")
        except:
            self.log("[WARN] ffmpeg 未安装（处理视频文件需要）")
        
        # 检查当前选择的文件
        audio_file = self.single_file_var.get()
        if audio_file:
            if os.path.exists(audio_file):
                file_size = os.path.getsize(audio_file) / (1024 * 1024)  # MB
                ext = os.path.splitext(audio_file)[1].lower()
                self.log(f"[OK] 输入文件存在: {os.path.basename(audio_file)} ({file_size:.1f} MB, {ext})")
            else:
                self.log("[ERR] 输入文件不存在")
        else:
            self.log("[WARN] 未选择输入文件")
        
        self.log("环境测试完成")
        self.log("=" * 50)
    
        
    def open_log_viewer(self):
        """打开日志查看器"""
        try:
            from log_manager import LogViewerWindow
            # 创建日志查看器窗口
            log_viewer = LogViewerWindow(self.root)
            logger.log("GUI", "打开日志查看器", "用户点击了查看详细日志按钮")
        except ImportError:
            messagebox.showerror("错误", "日志管理模块未找到")
        except Exception as e:
            logger.log("ERROR", "打开日志查看器失败", str(e))
            messagebox.showerror("错误", f"打开日志查看器失败: {e}")
    
    def save_all_settings(self):
        """保存所有设置到配置文件"""
        settings = {
            "single_file": {
                "model": self.model_var.get(),
                "format": self.format_var.get(),
                "input_language": self.input_lang_var.get(),
                "output_language": self.output_lang_var.get()
            },
            "batch": {
                "directory": self.batch_dir_var.get(),
                "extensions": {ext: var.get() for ext, var in self.ext_vars.items()}
            },
            "voice_service": {
                "hotkey": self.voice_hotkey_var.get(),
                "max_duration": self.max_duration_var.get(),
                "language": self.voice_lang_var.get(),
                "output_language": self.voice_output_lang_var.get(),
                "auto_input": self.auto_input_var.get(),
                "ai_enabled": self.voice_ai_enabled,
                "ai_config": self.voice_ai_config
            },
            "audio_cleaner": {
                "enabled": self.audio_cleaner_ai_enabled,
                "config": self.audio_cleaner_ai_config
            }
        }
        
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_settings.json")
        try:
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            
            self.log("所有设置已保存")
            messagebox.showinfo("成功", "所有设置已保存到配置文件")
        except Exception as e:
            self.log(f"保存设置失败: {e}")
            messagebox.showerror("错误", f"保存设置失败: {e}")
    
    def load_all_settings(self):
        """从配置文件加载所有设置"""
        config_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "all_settings.json")
        
        if not os.path.exists(config_file):
            self.log("未找到配置文件，使用默认设置")
            return
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                settings = json.load(f)
            
            # 加载单文件设置
            if "single_file" in settings:
                sf = settings["single_file"]
                if "model" in sf:
                    self.model_var.set(sf["model"])
                if "format" in sf:
                    self.format_var.set(sf["format"])
                if "input_language" in sf:
                    self.input_lang_var.set(sf["input_language"])
                if "output_language" in sf:
                    self.output_lang_var.set(sf["output_language"])
            
            # 加载批量设置
            if "batch" in settings:
                batch = settings["batch"]
                if "directory" in batch:
                    self.batch_dir_var.set(batch["directory"])
                if "extensions" in batch:
                    for ext, value in batch["extensions"].items():
                        if ext in self.ext_vars:
                            self.ext_vars[ext].set(value)
            
            # 加载语音服务设置
            if "voice_service" in settings:
                vs = settings["voice_service"]
                if "hotkey" in vs:
                    self.voice_hotkey_var.set(vs["hotkey"])
                if "max_duration" in vs:
                    self.max_duration_var.set(vs["max_duration"])
                if "language" in vs:
                    self.voice_lang_var.set(vs["language"])
                if "output_language" in vs:
                    self.voice_output_lang_var.set(vs["output_language"])
                if "auto_input" in vs:
                    self.auto_input_var.set(vs["auto_input"])
                if "ai_enabled" in vs:
                    self.voice_ai_enabled = vs["ai_enabled"]
                if "ai_config" in vs:
                    self.voice_ai_config = vs["ai_config"]
            
            self.log("所有设置已加载")
        except Exception as e:
            self.log(f"加载设置失败: {e}")
    
    def diagnose_whisper(self):
        """运行whisper诊断"""
        self.log("=" * 50)
        self.log("开始Whisper CLI诊断...")
        
        # 在新线程中运行诊断，避免GUI冻结
        threading.Thread(target=self._run_diagnose, daemon=True).start()
    
    def _run_diagnose(self):
        """实际运行诊断"""
        try:
            # 运行诊断脚本
            diagnose_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnose_whisper.py")
            
            if not os.path.exists(diagnose_script):
                self.log("[ERR] 诊断脚本不存在")
                return
            
            self.log("正在运行诊断脚本...")
            result = subprocess.run([sys.executable, diagnose_script], 
                                   capture_output=True, text=True, 
                                   encoding='utf-8', errors='replace',
                                   timeout=180)  # 3分钟超时
            
            # 输出诊断结果
            self.log("=== 诊断结果 ===")
            if result.stdout:
                for line in result.stdout.split('\n'):
                    if line.strip():
                        self.log(line)
            
            if result.stderr:
                self.log("=== 错误信息 ===")
                for line in result.stderr.split('\n'):
                    if line.strip():
                        self.log(f"[ERROR] {line}")
            
            self.log(f"诊断完成，返回代码: {result.returncode}")
            
        except Exception as e:
            self.log(f"运行诊断时出错: {e}")
    
    def transcribe_single_file(self):
        """
        转录单个音频文件
        """
        logger.log("TRANSCRIBE", "开始单文件转录", f"用户触发了单文件转录操作")
        
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
        self.is_transcribing = True
        self.stop_transcribe_btn.config(state="normal")
        threading.Thread(target=self._run_transcribe_single, 
                         args=(audio_file, output_format, model_path, language), 
                         daemon=True).start()
    
    def _run_transcribe_single(self, audio_file, output_format, model_path, language):
        """
        在线程中运行单文件转录
        """
        self.status_var.set(f"正在转录: {os.path.basename(audio_file)}")
        self.log("=" * 50)
        self.log("开始单文件转录任务")
        self.log(f"输入文件: {audio_file}")
        self.log(f"使用模型: {model_path}")
        self.log(f"输出格式: {output_format}")
        if language:
            self.log(f"语言设置: {language}")
        
        # 检查文件是否存在
        if not os.path.exists(audio_file):
            self.log(f"错误: 输入文件不存在: {audio_file}")
            self.status_var.set("转录失败 - 文件不存在")
            return
        
        # 检查模型是否存在
        if not os.path.exists(model_path):
            self.log(f"错误: 模型文件不存在: {model_path}")
            self.status_var.set("转录失败 - 模型不存在")
            return
        
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        self.log(f"Whisper CLI路径: {whisper_cli}")
        
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            self.status_var.set("转录失败 - 未找到whisper-cli.exe")
            return
        
        self.log("[OK] 所有文件检查通过，开始执行转录命令")
        
        # 检查是否为视频文件
        file_ext = os.path.splitext(audio_file)[1].lower()
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']
        
        # 确定实际要处理的音频文件
        audio_to_process = audio_file
        temp_audio = None
        
        if file_ext in video_extensions:
            logger.log("VIDEO", "检测到视频文件", f"文件: {audio_file}")
            self.log("检测到视频文件，准备提取音频...")
            
            # 检查ffmpeg是否可用
            if not self.check_ffmpeg_available():
                logger.log("ERROR", "FFmpeg不可用", "处理视频文件需要安装ffmpeg")
                self.log("[ERR] 处理视频文件需要安装ffmpeg")
                self.status_var.set("转录失败 - 需要ffmpeg")
                return
            
            # 创建临时音频文件
            temp_dir = tempfile.gettempdir()
            temp_audio = os.path.join(temp_dir, f"temp_audio_{os.path.basename(audio_file)}.wav")
            
            try:
                logger.log("VIDEO", "开始音频提取", f"输出文件: {temp_audio}")
                self.log(f"正在提取音频到: {temp_audio}")
                
                # 使用ffmpeg提取音频
                extract_command = [
                    'ffmpeg', '-i', audio_file,
                    '-vn',  # 不包含视频
                    '-acodec', 'pcm_s16le',  # 16-bit PCM
                    '-ar', '16000',  # 采样率 16kHz
                    '-ac', '1',  # 单声道
                    '-y',  # 覆盖输出文件
                    temp_audio
                ]
                
                # 运行ffmpeg
                extract_process = subprocess.run(
                    extract_command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace'
                )
                
                if extract_process.returncode == 0:
                    self.log("[OK] 音频提取成功")
                    audio_to_process = temp_audio
                    self._temp_audio_file = temp_audio  # 保存引用以便清理
                else:
                    self.log(f"[ERR] 音频提取失败: {extract_process.stderr}")
                    self.status_var.set("转录失败 - 音频提取失败")
                    return
                    
            except Exception as e:
                self.log(f"[ERR] 音频提取过程出错: {e}")
                self.status_var.set("转录失败 - 音频提取出错")
                return
        
        # 确定输出目录（使用输入文件所在目录）
        output_dir = os.path.dirname(os.path.abspath(audio_file))
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(output_dir, os.path.splitext(os.path.basename(audio_file))[0])
        
        command = [
            whisper_cli,
            "-m", model_path,
            "-f", audio_to_process,
            f"-o{output_format}",
            "-of", output_file_without_ext
        ]
        
        # 如果指定了语言
        if language:
            command.extend(["-l", language])
        
        # 记录命令执行
        logger.log("WHISPER", "执行转录命令", f"模型: {os.path.basename(model_path)}, 文件: {os.path.basename(audio_to_process)}")
        self.log(f"执行命令: {' '.join(command)}")
        self.log(f"输出目录: {output_dir}")
        self.log(f"原始文件: {audio_file}")
        self.log(f"处理文件: {audio_to_process}")
        self.log(f"输出格式: {output_format}")
        
        try:
            self.log("正在启动whisper-cli进程...")
            self.log(f"工作目录: {os.getcwd()}")
            
            # 启动进程
            self.transcribe_process = subprocess.Popen(command, 
                                     stdout=subprocess.PIPE, 
                                     stderr=subprocess.STDOUT,  # 合并stderr到stdout
                                     text=True, 
                                     encoding='utf-8', 
                                     errors='replace',
                                     bufsize=1,  # 行缓冲
                                     universal_newlines=True)
            process = self.transcribe_process
            
            # 实时读取输出
            self.log("开始读取whisper-cli输出...")
            output_lines = []
            last_output_time = time.time()
            timeout_seconds = 300  # 5分钟超时
            
            while True:
                # 检查超时
                if time.time() - last_output_time > timeout_seconds:
                    self.log(f"[WARN] 超过 {timeout_seconds} 秒没有输出，可能已卡住")
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except:
                        process.kill()
                    break
                
                # 读取一行输出
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    last_output_time = time.time()
                    line = output.strip()
                    output_lines.append(line)
                    self.log(f"[Whisper] {line}")
                    
                    # 检查是否正在处理
                    if any(keyword in line.lower() for keyword in ['whispering', 'processing', 'transcribing', 'loading']):
                        self.log(f"[PROCESS] 检测到处理中，重置超时计时器")
            
            # 等待进程结束
            process.wait()
            self.log(f"进程结束，返回代码: {process.returncode}")
            
            if not output_lines:
                self.log("[WARN] 没有收到任何输出，可能是whisper-cli无法正常启动")
                # 检查临时文件是否存在
                if temp_audio and os.path.exists(temp_audio):
                    file_size = os.path.getsize(temp_audio)
                    self.log(f"临时音频文件信息: {temp_audio} ({file_size} 字节)")
                    
                    # 尝试直接运行whisper-cli --help测试
                    try:
                        test_cmd = [whisper_cli, '--help']
                        test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
                        self.log(f"whisper-cli --help 返回代码: {test_result.returncode}")
                        if test_result.returncode != 0:
                            self.log(f"whisper-cli 错误: {test_result.stderr}")
                    except Exception as e:
                        self.log(f"测试whisper-cli失败: {e}")
            
            if process.returncode == 0:
                # 使用原始文件名构建输出文件路径（而不是临时音频文件）
                output_file = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(audio_file))[0]}.{output_format}")
                
                # 记录调试信息
                logger.log("WHISPER", "检查输出文件", f"预期路径: {output_file}")
                self.log(f"检查输出文件: {output_file}")
                
                # 列出输出目录中的所有文件
                self.log("输出目录内容:")
                try:
                    for f in os.listdir(output_dir):
                        file_path = os.path.join(output_dir, f)
                        if os.path.isfile(file_path):
                            file_size = os.path.getsize(file_path)
                            self.log(f"  - {f} ({file_size} 字节)")
                            # 查找可能的输出文件
                            if os.path.splitext(audio_file)[0] in f:
                                logger.log("WHISPER", "找到可能的输出文件", f"文件: {f}, 大小: {file_size}")
                except Exception as e:
                    self.log(f"列出目录失败: {e}")
                
                # 检查输出文件是否真的存在
                if os.path.exists(output_file):
                    file_size = os.path.getsize(output_file)
                    logger.log("WHISPER", "转录成功", f"输出文件: {output_file}, 大小: {file_size} 字节")
                    self.log(f"[OK] 转录完成! 输出文件: {output_file}")
                    self.log(f"文件大小: {file_size} 字节")
                    self.status_var.set("转录完成")
                    
                    # 可选：自动打开输出文件所在目录
                    if hasattr(self, 'auto_open_dir_var') and self.auto_open_dir_var.get():
                        try:
                            subprocess.run(['explorer', '/select,', output_file], shell=True)
                        except:
                            pass
                else:
                    self.log(f"[WARN] 转录命令返回成功，但未找到输出文件: {output_file}")
                    self.status_var.set("转录完成 - 但未找到输出文件")
            else:
                self.log(f"[ERR] 转录失败，返回代码: {process.returncode}")
                if not output_lines:
                    self.log("提示: 没有任何输出，可能是whisper-cli无法正常执行")
                self.status_var.set("转录失败")
                
        except Exception as e:
            self.log(f"转录过程中出现错误: {e}")
            self.status_var.set("转录失败")
        
        finally:
            # 重置转录状态
            self.is_transcribing = False
            self.transcribe_process = None
            self.stop_transcribe_btn.config(state="disabled")
            
            # 清理临时音频文件
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                    self.log(f"已清理临时文件: {temp_audio}")
                except Exception as e:
                    self.log(f"清理临时文件失败: {e}")
    
    def stop_transcription(self):
        """停止当前转录任务"""
        if self.transcribe_process and self.is_transcribing:
            self.log("⏹️ 正在停止转录任务...")
            
            try:
                # 尝试优雅终止
                self.transcribe_process.terminate()
                
                # 等待5秒
                try:
                    self.transcribe_process.wait(timeout=5)
                    self.log("[OK] 转录任务已停止")
                except subprocess.TimeoutExpired:
                    # 如果没有响应，强制杀死
                    self.log("[WARN] 强制停止转录任务...")
                    self.transcribe_process.kill()
                    self.transcribe_process.wait()
                    self.log("[OK] 转录任务已强制停止")
                    
            except Exception as e:
                self.log(f"[ERR] 停止转录任务时出错: {e}")
            
            finally:
                self.is_transcribing = False
                self.transcribe_process = None
                self.stop_transcribe_btn.config(state="disabled")
                self.status_var.set("转录已停止")
                
                # 清理临时文件
                if hasattr(self, '_temp_audio_file') and self._temp_audio_file:
                    if os.path.exists(self._temp_audio_file):
                        try:
                            os.remove(self._temp_audio_file)
                            self.log(f"已清理临时文件: {self._temp_audio_file}")
                        except:
                            pass
        else:
            self.log("没有正在运行的转录任务")
    
    def transcribe_batch(self):
        """
        批量转录目录中的音频/视频文件
        """
        directory = self.batch_dir_var.get()
        if not directory:
            messagebox.showerror("错误", "请选择媒体文件目录")
            return
            
        if not os.path.exists(directory) or not os.path.isdir(directory):
            messagebox.showerror("错误", f"目录不存在: {directory}")
            return
        
        # 检查是否选择了视频文件但没有ffmpeg
        extensions = [ext for ext, var in self.ext_vars.items() if var.get()]
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
        has_video = any(ext in video_extensions for ext in extensions)
        
        if has_video and not self.check_ffmpeg_available():
            messagebox.showerror("错误", "处理视频文件需要安装ffmpeg\n\n请安装ffmpeg后重试")
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
        在线程中运行批量转录（优化版本 - 支持并行处理）
        """
        self.status_var.set("正在批量转录...")
        self.log(f"开始批量转录目录: {directory}")
        self.log(f"使用模型: {os.path.basename(model_path)}")
        self.log(f"输出格式: {output_format}")
        if language:
            self.log(f"语言设置: {language}")
        self.log(f"文件类型: {', '.join(extensions)}")
        self.log(f"并行工作线程数: {self.max_workers}")
        
        # 查找所有匹配的媒体文件（使用更高效的方法）
        media_files = []
        pattern = os.path.join(directory, "*")
        video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
        
        for ext in extensions:
            files = glob.glob(pattern + ext.lower()) + glob.glob(pattern + ext.upper())
            for file in files:
                media_files.append({
                    'path': file,
                    'is_video': ext in video_extensions
                })
        
        if not media_files:
            self.log(f"未找到匹配的媒体文件")
            self.status_var.set("批量转录完成")
            return
        
        # 统计文件类型
        video_count = sum(1 for f in media_files if f['is_video'])
        audio_count = len(media_files) - video_count
        self.log(f"找到 {len(media_files)} 个媒体文件（音频: {audio_count}, 视频: {video_count}）")
        
        # 缓存whisper-cli路径
        whisper_cli = os.path.join(os.path.dirname(os.path.abspath(__file__)), "whisper", "whisper-cli.exe")
        if not os.path.exists(whisper_cli):
            self.log(f"错误: 未找到whisper-cli.exe，请确保它位于 {os.path.dirname(whisper_cli)} 目录中")
            self.status_var.set("转录失败")
            return
        
        # 使用线程池并行处理
        success_count = 0
        fail_count = 0
        processed_count = 0
        
        # 准备任务
        tasks = []
        for media_info in media_files:
            tasks.append((media_info, output_format, model_path, language, whisper_cli))
        
        # 并行执行
        futures = []
        for task in tasks:
            future = self.thread_pool.submit(self._transcribe_media_file_optimized, *task)
            futures.append(future)
        
        # 收集结果
        for i, future in enumerate(as_completed(futures)):
            processed_count += 1
            self.status_var.set(f"批量转录进度: {processed_count}/{len(media_files)}")
            
            result = future.result()
            if result['success']:
                success_count += 1
                file_type = "视频" if result['is_video'] else "音频"
                self.log(f"[{processed_count}/{len(media_files)}] [OK] {result['filename']} ({file_type})")
                if result['output']:
                    self.log(f"  输出文件: {result['output']}")
            else:
                fail_count += 1
                file_type = "视频" if result['is_video'] else "音频"
                self.log(f"[{processed_count}/{len(media_files)}] [ERR] {result['filename']} ({file_type})")
                if result['error']:
                    self.log(f"  错误: {result['error']}")
        
        self.log(f"批量转录完成! 成功: {success_count}, 失败: {fail_count}")
        self.status_var.set("批量转录完成")
    
    def _transcribe_media_file_optimized(self, media_info, output_format, model_path, language, whisper_cli):
        """
        优化的媒体文件转录函数（支持音频和视频文件，用于并行处理）
        """
        media_file = media_info['path']
        is_video = media_info['is_video']
        
        result = {
            'filename': os.path.basename(media_file),
            'is_video': is_video,
            'success': False,
            'output': None,
            'error': None
        }
        
        # 如果是视频文件，先提取音频
        audio_to_process = media_file
        temp_audio = None
        
        if is_video:
            try:
                # 创建临时音频文件
                temp_dir = tempfile.gettempdir()
                temp_audio = os.path.join(temp_dir, f"temp_audio_{os.path.basename(media_file)}.wav")
                
                # 使用ffmpeg提取音频
                self.log(f"正在从视频提取音频: {result['filename']}")
                command = [
                    'ffmpeg', '-i', media_file,
                    '-vn', '-acodec', 'pcm_s16le',
                    '-ar', '16000', '-ac', '1',
                    '-y', temp_audio
                ]
                
                extract_process = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    timeout=600  # 10分钟超时
                )
                
                if extract_process.returncode == 0:
                    audio_to_process = temp_audio
                else:
                    result['error'] = f"音频提取失败: {extract_process.stderr.strip()}"
                    return result
                    
            except subprocess.TimeoutExpired:
                result['error'] = "音频提取超时（10分钟）"
                return result
            except Exception as e:
                result['error'] = f"音频提取失败: {str(e)}"
                return result
        
        # 转录音频
        # 确定输出目录（使用输入文件所在目录）
        output_dir = os.path.dirname(os.path.abspath(media_file))
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(output_dir, os.path.splitext(os.path.basename(audio_file))[0])
        
        command = [
            whisper_cli,
            "-m", model_path,
            "-f", audio_to_process,
            f"-o{output_format}",
            "-of", output_file_without_ext
        ]
        
        if language:
            command.extend(["-l", language])
        
        try:
            # 使用subprocess.run而不是Popen，更高效
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5分钟超时
            )
            
            if process.returncode == 0:
                result['success'] = True
                result['output'] = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(media_file))[0]}.{output_format}")
            else:
                result['error'] = f"返回代码: {process.returncode}"
                if process.stderr:
                    result['error'] += f", 错误信息: {process.stderr.strip()}"
                    
        except subprocess.TimeoutExpired:
            result['error'] = "转录超时（5分钟）"
        except Exception as e:
            result['error'] = str(e)
        finally:
            # 清理临时文件
            if temp_audio and os.path.exists(temp_audio):
                try:
                    os.remove(temp_audio)
                except:
                    pass
        
        return result
    
    def _transcribe_single_file_optimized(self, audio_file, output_format, model_path, language, whisper_cli):
        """
        优化的单文件转录函数（用于并行处理）
        """
        result = {
            'filename': os.path.basename(audio_file),
            'success': False,
            'output': None,
            'error': None
        }
        
        # 确定输出目录（使用输入文件所在目录）
        output_dir = os.path.dirname(os.path.abspath(audio_file))
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(output_dir, os.path.splitext(os.path.basename(audio_file))[0])
        
        command = [
            whisper_cli,
            "-m", model_path,
            "-f", audio_file,
            f"-o{output_format}",
            "-of", output_file_without_ext
        ]
        
        if language:
            command.extend(["-l", language])
        
        try:
            # 使用subprocess.run而不是Popen，更高效
            process = subprocess.run(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=300  # 5分钟超时
            )
            
            if process.returncode == 0:
                result['success'] = True
                result['output'] = os.path.join(output_dir, f"{os.path.splitext(os.path.basename(audio_file))[0]}.{output_format}")
            else:
                result['error'] = f"返回代码: {process.returncode}"
                if process.stderr:
                    result['error'] += f", 错误信息: {process.stderr.strip()}"
                    
        except subprocess.TimeoutExpired:
            result['error'] = "处理超时（5分钟）"
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
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
        model_path = self.get_voice_model_path()
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
        开始录音（优化版本 - 使用预分配缓冲区）
        """
        self.is_recording = True
        self.recorded_frames = []  # 清空之前的录音
        self.audio_buffer_index = 0  # 重置缓冲区索引
        self.log("开始录音...")
        self.status_var.set("正在录音...")
        
        # 播放开始录音提示音
        self.play_start_sound()
        
        # 在新线程中启动录音，避免阻塞主线程
        threading.Thread(target=self._record_audio_optimized).start()
    
    def _record_audio_optimized(self):
        """
        录制音频的内部方法（优化版本）
        """
        try:
            # 使用更大的块大小以减少回调频率
            with sd.InputStream(
                samplerate=self.sample_rate, 
                channels=1, 
                callback=self._audio_callback_optimized,
                blocksize=4096  # 增加块大小
            ):
                while self.is_recording:
                    time.sleep(0.05)  # 减少睡眠时间，提高响应性
        except Exception as e:
            self.is_recording = False
            self.log(f"录音错误: {e}")
            self.status_var.set("录音失败")
    
    def _audio_callback_optimized(self, indata, frames, time, status):
        """
        优化的音频数据回调函数
        
        参数:
            indata: 输入的音频数据
            frames: 帧数
            time: 时间信息
            status: 状态信息
        """
        if status:
            self.log(f"音频回调状态: {status}")
        
        if self.is_recording:
            # 直接写入预分配的缓冲区
            end_index = self.audio_buffer_index + frames
            if end_index <= self.audio_buffer_size:
                self.audio_buffer[self.audio_buffer_index:end_index] = indata.flatten()
                self.audio_buffer_index = end_index
            else:
                # 缓冲区已满，停止录音
                self.is_recording = False
                self.log("录音达到最大时长限制")
                self.stop_recording()
    
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
        处理录制的音频（优化版本）
        """
        # 检查是否有录音数据
        if self.audio_buffer_index == 0:
            self.log("没有录制到音频数据")
            self.status_var.set("就绪")
            return
        
        try:
            # 重置进度条
            self.update_progress(0, "开始处理音频...")
            
            # 从缓冲区提取音频数据（避免内存拷贝）
            self.update_progress(10, "提取音频数据...")
            audio_data = self.audio_buffer[:self.audio_buffer_index].copy()
            
            # 保存为临时WAV文件（使用更高效的写入方式）
            self.update_progress(20, "保存音频文件...")
            temp_file = os.path.join(self.temp_dir, "temp_recording.wav")
            
            # 直接使用numpy的内存视图，避免额外的内存分配
            audio_data_int16 = np.empty(self.audio_buffer_index, dtype=np.int16)
            np.multiply(audio_data, 32767, out=audio_data_int16, casting='unsafe')
            
            # 使用更高效的文件写入
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
                    self.log("[OK] 语音转文字AI处理完成，文本已优化")
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
            str: 完整转录的文本.如果转录失败则返回None
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
            return self.transcribe_audio(audio_file)
    
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
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(os.path.dirname(os.path.abspath(audio_file)), os.path.splitext(os.path.basename(audio_file))[0])
        
        command = [whisper_cli, "-m", model_path, "-f", audio_file, "-otxt", "-of", output_file_without_ext]
        
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
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(os.path.dirname(os.path.abspath(audio_file)), os.path.splitext(os.path.basename(audio_file))[0])
        
        # 临时输出文件 (whisper-cli会在-of参数后加.txt扩展名)
        output_file = output_file_without_ext + ".txt"
        
        command = [whisper_cli, "-m", model_path, "-f", audio_file, "-otxt", "-of", output_file_without_ext]
        
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
    
    def cleanup_resources(self):
        """
        清理所有资源（线程池、缓存等）
        """
        try:
            # 关闭线程池
            if hasattr(self, 'thread_pool'):
                self.thread_pool.shutdown(wait=True)
                self.log("已关闭线程池")
            
            # 清理缓存
            if hasattr(self, 'model_cache'):
                self.model_cache.clear()
            
            if hasattr(self, 'results_cache'):
                self.results_cache.clear()
            
            # 清理临时文件
            self.cleanup_all_temp_files()
            
            self.log("资源清理完成")
        except Exception as e:
            self.log(f"资源清理失败: {e}")
    
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
        浏览并选择音频/视频文件
        """
        filetypes = [
            ("支持的媒体文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a;*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv"),
            ("音频文件", "*.wav;*.mp3;*.ogg;*.flac;*.m4a"),
            ("视频文件", "*.mp4;*.avi;*.mkv;*.mov;*.wmv;*.flv"),
            ("所有文件", "*.*")
        ]
        file_path = filedialog.askopenfilename(filetypes=filetypes)
        if file_path:
            self.cleaner_audio_var.set(file_path)
            # 自动设置输出文件名 - 确保在同一目录下
            audio_dir = os.path.dirname(file_path)
            base_name = os.path.splitext(os.path.basename(file_path))[0]
            
            # 根据输入文件类型设置默认输出格式
            ext = os.path.splitext(file_path)[1].lower()
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
                # 视频文件，输出 cleaned 视频
                output_path = os.path.join(audio_dir, f"{base_name}_cleaned.mp4")
                # 同时输出音频
                audio_output_path = os.path.join(audio_dir, f"{base_name}_cleaned.mp3")
                self.cleaner_output_var.set(output_path)
                # 显示音频输出选项
                if hasattr(self, 'audio_output_frame'):
                    self.audio_output_frame.pack(fill=tk.X, padx=10, pady=5, after=self.output_select_frame)
                    self.cleaner_audio_output_var.set(audio_output_path)
            else:
                # 音频文件
                output_path = os.path.join(audio_dir, f"{base_name}_cleaned.mp3")
                self.cleaner_output_var.set(output_path)
                # 隐藏音频输出选项
                if hasattr(self, 'audio_output_frame'):
                    self.audio_output_frame.pack_forget()
            
            # 自动设置HRT字幕输出路径
            hrt_path = os.path.join(audio_dir, f"{base_name}_hrt.srt")
            self.hrt_output_var.set(hrt_path)
            
            self.log(f"选择文件: {file_path}")
            self.log(f"设置输出路径: {output_path}")
            self.log(f"设置HRT字幕路径: {hrt_path}")
            
            # 如果是视频文件，显示视频预览区域
            if ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']:
                self.toggle_video_preview()
    
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
        开始音频/视频清理处理
        """
        # 验证输入
        media_file = self.cleaner_audio_var.get()
        if not media_file:
            messagebox.showerror("错误", "请选择媒体文件")
            return
            
        if not os.path.exists(media_file):
            messagebox.showerror("错误", f"文件不存在: {media_file}")
            return
        
        # 检查文件类型
        ext = os.path.splitext(media_file)[1].lower()
        is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
        
        if is_video and not VIDEO_AVAILABLE:
            messagebox.showerror("错误", "视频处理需要安装OpenCV库\n\n请运行: pip install opencv-python")
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
                         args=(media_file, output_file, api_url, api_key, 
                              self.cleaner_model_var.get(), max_segment_length, gap_threshold)).start()
    
    def _run_audio_cleaning(self, media_file, output_file, api_url, api_key, model_name, max_segment_length, gap_threshold):
        """
        在线程中运行音频/视频清理
        """
        try:
            # 检查文件类型
            ext = os.path.splitext(media_file)[1].lower()
            is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
            
            if is_video:
                self.status_var.set("正在处理视频...")
                self.log(f"开始处理视频: {media_file}")
            else:
                self.status_var.set("正在清理音频...")
                self.log(f"开始清理音频: {media_file}")
            
            self.log(f"输出文件: {output_file}")
            self.log(f"API URL: {api_url}")
            self.log(f"模型: {model_name}")
            
            # 如果是视频文件且选择了仅提取音频
            if is_video and self.extract_only_var.get():
                self.cleaner_status_var.set("[VIDEO] 提取视频音频...")
                self.log("提取视频音频...")
                temp_audio = os.path.join(self.temp_dir, "extracted_audio.mp3")
                if not self.extract_audio_from_video(media_file, temp_audio):
                    raise Exception("音频提取失败")
                # 使用提取的音频继续处理
                audio_to_process = temp_audio
            else:
                audio_to_process = media_file
            
            # 1. 使用whisper生成SRT文件
            self.cleaner_status_var.set("📝 步骤1: 生成字幕文件...")
            self.log("步骤1: 使用whisper生成SRT文件...")
            srt_file = self.generate_srt_from_audio(audio_to_process)
            
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
            self.execute_audio_edit(audio_to_process, optimized_segments, indices_to_delete, output_file)
            
            # 如果是视频文件且需要保留视频轨道
            final_output_file = output_file
            if is_video and self.keep_video_var.get() and not self.extract_only_var.get():
                self.cleaner_status_var.set("[VIDEO] 步骤6.5: 合并视频轨道...")
                self.log("步骤6.5: 合并视频和清理后的音频...")
                
                # 生成临时视频文件名
                temp_video_output = os.path.splitext(output_file)[0] + "_temp.mp4"
                
                if self.process_video_with_cleaned_audio(media_file, output_file, temp_video_output):
                    # 替换最终输出文件
                    final_output_file = temp_video_output
                    
                    # 如果需要同时输出音频文件
                    if hasattr(self, 'cleaner_audio_output_var') and self.cleaner_audio_output_var.get():
                        import shutil
                        shutil.copy2(output_file, self.cleaner_audio_output_var.get())
                        self.log(f"[OK] 音频文件已保存: {self.cleaner_audio_output_var.get()}")
                else:
                    self.log("[WARN] 视频合并失败，仅输出清理后的音频")
            
            # 7. 二次转录和HRT字幕生成
            if self.enable_secondary_var.get():
                self.cleaner_status_var.set("[MIC] 步骤7: 二次转录音频...")
                self.log("步骤7: 开始二次转录（对清理后的音频再次语音识别）...")
                hrt_subtitle_file = self.generate_hrt_subtitles(output_file)
                if hrt_subtitle_file:
                    self.log(f"[OK] 二次转录完成，HRT字幕生成: {hrt_subtitle_file}")
                    self.log("音频清理和二次转录全部完成!")
                    self.cleaner_status_var.set("[OK] 全部完成!")
                    self.status_var.set("清理完成")
                    
                    # 构建完成消息
                    msg = f"🎉 处理完成!\n[FILE] 输出文件: {final_output_file}"
                    if hrt_subtitle_file:
                        msg += f"\n[VIDEO] HRT字幕: {hrt_subtitle_file}"
                    if is_video and self.keep_video_var.get():
                        msg += f"\n🎥 视频格式: MP4 (保留原视频)"
                    
                    messagebox.showinfo("完成", msg)
                else:
                    self.log("⚠ 二次转录失败，但音频清理已完成")
                    self.cleaner_status_var.set("⚠ 部分完成")
                    self.status_var.set("清理完成")
                    messagebox.showinfo("完成", f"[OK] 处理完成!\n[FILE] 输出文件: {final_output_file}\n[WARN] 注意: 二次转录失败")
            else:
                self.log("处理完成!")
                self.cleaner_status_var.set("[OK] 清理完成!")
                self.status_var.set("清理完成")
                
                # 构建完成消息
                msg = f"[OK] 处理完成!\n[FILE] 输出文件: {final_output_file}"
                if is_video and self.keep_video_var.get():
                    msg += f"\n🎥 视频格式: MP4 (保留原视频)"
                elif is_video:
                    msg += f"\n🎵 仅音频: MP3"
                
                messagebox.showinfo("完成", msg)
            
        except Exception as e:
            self.log(f"音频清理过程中出现错误: {e}")
            self.status_var.set("清理失败")
            messagebox.showerror("错误", f"音频清理失败: {e}")
    
    def extract_audio_from_video(self, video_file, output_audio_file):
        """
        从视频文件中提取音频
        
        参数:
            video_file: 视频文件路径
            output_audio_file: 输出音频文件路径
            
        返回:
            bool: 是否成功
        """
        try:
            self.log(f"正在从视频提取音频: {video_file}")
            
            # 使用ffmpeg提取音频（更高效）
            if self.check_ffmpeg_available():
                cmd = [
                    'ffmpeg', '-i', video_file,
                    '-vn',  # 不包含视频
                    '-acodec', 'libmp3lame',  # 使用MP3编码
                    '-ab', '192k',  # 音频比特率
                    '-y',  # 覆盖输出文件
                    output_audio_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0 and os.path.exists(output_audio_file):
                    self.log(f"[OK] 音频提取成功: {output_audio_file}")
                    return True
                else:
                    self.log(f"[ERR] 音频提取失败: {result.stderr}")
                    return False
            else:
                self.log("[WARN] 未找到ffmpeg，无法提取音频")
                return False
                
        except Exception as e:
            self.log(f"[ERR] 提取音频时出错: {str(e)}")
            return False
    
    def check_ffmpeg_available(self):
        """
        检查ffmpeg是否可用
        
        返回:
            bool: ffmpeg是否可用
        """
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            return True
        except:
            return False
    
    def process_video_with_cleaned_audio(self, video_file, cleaned_audio_file, output_video_file):
        """
        使用清理后的音频处理视频文件
        
        参数:
            video_file: 原始视频文件路径
            cleaned_audio_file: 清理后的音频文件路径
            output_video_file: 输出视频文件路径
            
        返回:
            bool: 是否成功
        """
        try:
            self.log(f"正在处理视频: {video_file}")
            
            if not self.check_ffmpeg_available():
                self.log("[ERR] 未找到ffmpeg，无法处理视频")
                return False
            
            # 使用ffmpeg合并视频和清理后的音频
            cmd = [
                'ffmpeg', '-i', video_file,  # 输入视频
                '-i', cleaned_audio_file,  # 输入清理后的音频
                '-c:v', 'copy',  # 直接复制视频流，不重新编码
                '-c:a', 'aac',  # 音频使用AAC编码
                '-map', '0:v:0',  # 使用第一个文件的视频流
                '-map', '1:a:0',  # 使用第二个文件的音频流
                '-shortest',  # 以较短的流为准
                '-y',  # 覆盖输出文件
                output_video_file
            ]
            
            self.log(f"执行命令: {' '.join(cmd)}")
            
            # 由于视频处理可能耗时较长，使用实时输出
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                                     text=True, universal_newlines=True)
            
            # 实时显示输出
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    # 只显示进度相关的行
                    if 'time=' in output or 'frame=' in output:
                        self.log(f"视频处理: {output.strip()}")
            
            if process.returncode == 0 and os.path.exists(output_video_file):
                file_size = os.path.getsize(output_video_file)
                self.log(f"[OK] 视频处理成功: {output_video_file} (大小: {file_size} bytes)")
                return True
            else:
                self.log(f"[ERR] 视频处理失败")
                return False
                
        except Exception as e:
            self.log(f"[ERR] 处理视频时出错: {str(e)}")
            return False
    
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
        
        # 构建输出文件路径（不带扩展名）
        output_file_without_ext = os.path.join(output_dir, os.path.splitext(os.path.basename(audio_file))[0])
        
        cmd = [whisper_cli, audio_file, '--output_srt', '-of', output_file_without_ext, '--language', 'zh']
        self.log(f"执行命令: {' '.join(cmd)}")
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            self.log(f"Whisper输出: {result.stdout}")
            if result.stderr:
                self.log(f"Whisper错误: {result.stderr}")
            
            # 检查SRT文件是否真的生成
            if os.path.exists(srt_file):
                self.log(f"[OK] SRT文件生成成功: {srt_file}")
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
                        self.log(f"[OK] 找到SRT文件: {possible_file}")
                        return possible_file
                
                raise Exception(f"SRT文件未生成，期望路径: {srt_file}")
        except subprocess.CalledProcessError as e:
            self.log(f"[ERR] Whisper执行失败: {e}")
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
            
            self.log(f"[OK] 解析了 {len(segments)} 个片段")
            return segments
            
        except Exception as e:
            self.log(f"[ERR] SRT解析失败: {e}")
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
        
        self.log(f"[OK] 优化后片段数量: {len(final_segments)}")
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
            self.log("[ERR] API URL格式化失败")
            return []
        
        # Ollama格式可能不需要API Key
        if ai_format != "ollama" and not api_config['api_key']:
            self.log("[ERR] API配置不完整 - Key为空")
            return []
        
        self.log(f"URL: '{formatted_url}'")
        self.log(f"Key: '{'已设置' if api_config['api_key'] else '未设置'}'")
        
        # 检查openai库是否正确导入
        if not hasattr(openai, 'OpenAI'):
            self.log("[ERR] OpenAI类不存在，可能是库版本问题")
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
                    self.log("[OK] OpenAI格式客户端创建成功")
                
                elif ai_format == "ollama":
                    self.log("创建Ollama格式客户端...")
                    client = openai.OpenAI(
                        base_url=formatted_url,
                        api_key="ollama",  # Ollama不需要真实的API Key
                        timeout=120.0
                    )
                    self.log("[OK] Ollama格式客户端创建成功")
                
                elif ai_format == "gemini":
                    self.log("创建Gemini格式客户端...")
                    client = openai.OpenAI(
                        api_key=api_config['api_key'],
                        base_url=formatted_url,
                        timeout=120.0
                    )
                    self.log("[OK] Gemini格式客户端创建成功")
                    
            except Exception as client_error:
                self.log(f"[ERR] 创建{ai_format.upper()}格式客户端失败: {client_error}")
                self.log(f"错误类型: {type(client_error).__name__}")
                import traceback
                self.log(f"客户端创建错误详情: {traceback.format_exc()}")
                return []
            
            self.log(f"[OK] {ai_format.upper()}格式客户端创建成功")
            
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
                
                self.log("[OK] LLM响应成功")
                self.log(f"响应ID: {response.id}")
                self.log(f"使用模型: {response.model}")
                if hasattr(response, 'usage') and response.usage:
                    self.log(f"Token使用: {response.usage.total_tokens} (提示: {response.usage.prompt_tokens}, 完成: {response.usage.completion_tokens})")
                
            except Exception as api_error:
                self.log(f"[ERR] API调用失败: {api_error}")
                self.log(f"错误类型: {type(api_error).__name__}")
                if hasattr(api_error, 'response'):
                    self.log(f"响应状态: {api_error.response.status_code}")
                    self.log(f"响应内容: {api_error.response.text}")
                import traceback
                self.log(f"API调用错误详情: {traceback.format_exc()}")
                return []
            
            if not response.choices:
                self.log("[ERR] 响应中没有choices")
                return []
            
            result = response.choices[0].message.content.strip()
            self.log(f"LLM原始响应: {repr(result)}")
            
            if not result:
                self.log("[ERR] LLM返回空响应")
                return []
            
            try:
                indices_to_delete = json.loads(result)
                self.log(f"JSON解析结果: {indices_to_delete}")
                self.log(f"解析结果类型: {type(indices_to_delete)}")
                
                if isinstance(indices_to_delete, list):
                    self.log(f"[OK] LLM分析完成，建议删除 {len(indices_to_delete)} 个片段: {indices_to_delete}")
                    return indices_to_delete
                else:
                    self.log(f"[ERR] LLM返回格式错误，期望数组，实际类型: {type(indices_to_delete)}")
                    self.log(f"返回内容: {repr(indices_to_delete)}")
                    return []
            except json.JSONDecodeError as e:
                self.log(f"[ERR] LLM返回的不是有效JSON: {e}")
                self.log(f"原始响应内容: {repr(result)}")
                return []
                
        except Exception as e:
            self.log(f"[ERR] LLM调用异常: {e}")
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
            
            self.log(f"[OK] 保留 {len(segments_to_keep)} 个优质片段")
            
            if not segments_to_keep:
                self.log("[ERR] 没有可保留的片段")
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
                self.log(f"[OK] 输出文件创建成功: {output_path} (大小: {file_size} 字节)")
            else:
                self.log(f"[ERR] 输出文件创建失败: {output_path}")
            
            original_duration = len(audio) / 1000
            final_duration = len(final_audio) / 1000
            reduction = ((original_duration - final_duration) / original_duration) * 100
            
            self.log(f"[OK] 音频处理完成!")
            self.log(f"  原始时长: {original_duration:.1f}秒")
            self.log(f"  最终时长: {final_duration:.1f}秒")
            self.log(f"  减少时长: {reduction:.1f}%")
            self.log(f"  输出路径: {os.path.abspath(output_path)}")
            
        except Exception as e:
            self.log(f"[ERR] 音频处理失败: {e}")
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
            self.log("[MIC] 开始二次转录（对清理后的音频再次语音识别）...")
            srt_file = self.generate_srt_from_audio(cleaned_audio_file)
            
            if not srt_file or not os.path.exists(srt_file):
                self.log("[ERR] 二次转录失败，无法生成HRT字幕")
                return None
            
            # 解析SRT文件
            self.log("解析SRT文件...")
            segments = self.parse_srt_file(srt_file)
            
            if not segments:
                self.log("[ERR] SRT解析失败，无法生成HRT字幕")
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
                self.log(f"[OK] HRT字幕文件生成成功: {hrt_file} (大小: {file_size} 字节)")
                return hrt_file
            else:
                self.log(f"[ERR] HRT字幕文件生成失败: {hrt_file}")
                return None
                
        except Exception as e:
            self.log(f"[ERR] HRT字幕生成失败: {e}")
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
            text = re.sub(r'[\.]{2,}', '...', text)
            
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
        
        self.log(f"[OK] HRT优化完成，原始片段: {len(segments)}，优化后: {len(hrt_segments)}")
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
            
            self.log(f"[OK] HRT字幕文件写入完成: {output_file}")
            
        except Exception as e:
            self.log(f"[ERR] HRT字幕文件写入失败: {e}")
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
                self.log("[OK] OpenAI类存在")
            else:
                self.log("[ERR] OpenAI类不存在")
                return
            
            if hasattr(openai.OpenAI, '__init__'):
                self.log("[OK] OpenAI.__init__方法存在")
            else:
                self.log("[ERR] OpenAI.__init__方法不存在")
                return
            
            if hasattr(openai.OpenAI, 'chat'):
                self.log("[OK] OpenAI.chat属性存在")
            else:
                self.log("[ERR] OpenAI.chat属性不存在")
                return
            
            if hasattr(openai.OpenAI.chat, 'completions'):
                self.log("[OK] OpenAI.chat.completions属性存在")
            else:
                self.log("[ERR] OpenAI.chat.completions属性不存在")
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
                        self.log(f"[OK] OpenAI版本 {version} 看起来兼容")
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
                self.log("[OK] OpenAI客户端创建测试成功")
            except Exception as e:
                self.log(f"⚠ OpenAI客户端创建测试失败: {e}")
                self.log("这可能是版本兼容性问题，尝试简化创建方式...")
                
                # 尝试最简单的创建方式
                try:
                    simple_client = openai.OpenAI(api_key="test_key")
                    self.log("[OK] 简化方式创建OpenAI客户端成功")
                except Exception as e2:
                    self.log(f"[ERR] 简化方式也失败: {e2}")
            
            self.log("=== OpenAI库测试完成 ===")
            
        except Exception as e:
            self.log(f"[ERR] OpenAI库测试异常: {e}")
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
            self.openai_hint_var.set("[INFO] 程序会自动添加 /v1 后缀，只需输入基础网址即可")
            # 设置默认OpenAI URL
            if not self.api_url_var.get() or "api.openai.com" in self.api_url_var.get():
                self.api_url_var.set("https://api.openai.com")
        elif ai_format == "ollama":
            self.format_info_var.set("Ollama本地AI模型格式")
            self.openai_hint_var.set("[INFO] Ollama默认地址: http://localhost:11434")
            # 设置默认Ollama URL
            if not self.api_url_var.get() or "api.openai.com" in self.api_url_var.get():
                self.api_url_var.set("http://localhost:11434")
        elif ai_format == "gemini":
            self.format_info_var.set("Google Gemini API格式")
            self.openai_hint_var.set("[INFO] Gemini API需要完整的URL，包括版本路径")
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
        title_label = ttk.Label(inner_frame, text="[LOG] 操作日志", font=("Arial", 14, "bold"))
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
            "input_method": "paste",
            "auto_start_enabled": False,
            "max_recording_duration": 300
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
        self.auto_start_var.set(config.get("auto_start_enabled", False))
        
        # 加载并应用录音时长设置
        max_duration = config.get("max_recording_duration", 300)
        self.max_recording_duration_var.set(max_duration)
        self.max_recording_duration = max_duration
        # 重新计算缓冲区大小
        self.audio_buffer_size = int(self.sample_rate * self.max_recording_duration)
        # 重新分配缓冲区
        self.audio_buffer = np.zeros(self.audio_buffer_size, dtype=np.float32)
        self.audio_buffer_index = 0
    
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
        
        self.log(f"快捷键已临时设置为: {new_hotkey}")
        messagebox.showinfo("提示", f"快捷键已设置为: {new_hotkey}\n\n请点击'保存所有设置'按钮以保存此设置")
        
        # 如果服务正在运行，重启服务以应用新设置
        if self.voice_service_active:
            self.stop_voice_service()
            self.start_voice_service()
    
    def update_sound_settings(self):
        """
        更新提示音设置
        """
        self.log("提示音设置已临时更新，请点击'保存所有设置'按钮以保存")
    
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
            self.log(f"[TOOL] 使用语音转文字模型: {self.voice_ai_config.get('model', 'gpt-3.5-turbo')}")
            self.log(f"🌡️ 温度设置: {self.voice_ai_config.get('temperature', 0.1)}")
            self.log(f"[LOG] AI格式: {ai_format.upper()}")
            
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
                    self.log(f"[WARN] Gemini OpenAI兼容模式失败: {gemini_error}")
                    self.log("[INFO] 提示：请确保API URL包含完整的版本路径")
                    return text
            
            if processed_text:
                self.log(f"🎯 {ai_format.upper()}格式AI处理成功，获得优化文本")
                return processed_text
            else:
                self.log("[WARN] AI返回的文本为空，返回原文")
                return text
                
        except Exception as e:
            self.log(f"[ERR] 语音转文字AI处理过程中出现错误: {str(e)}")
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
            self.log(f"[TOOL] 使用音频清理模型: {self.audio_cleaner_ai_config.get('model', 'cognitivecomputations/dolphin-mistral-24b-venice-edition:free')}")
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
                self.log(f"[OK] 音频清理API请求成功 (状态码: {response.status_code})")
                result = response.json()
                processed_text = result.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                
                if processed_text:
                    self.log(f"🎯 音频清理AI处理成功，获得清理文本")
                    return processed_text
                else:
                    self.log("[WARN] 音频清理AI返回的文本为空，返回原文")
                    return text
            else:
                self.log(f"[ERR] 音频清理API请求失败，状态码: {response.status_code}")
                try:
                    error_info = response.json()
                    self.log(f"[LOG] 错误详情: {error_info}")
                except:
                    self.log(f"[LOG] 响应内容: {response.text[:200]}...")
                return text
                
        except Exception as e:
            self.log(f"[ERR] 音频清理AI处理过程中出现错误: {str(e)}")
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
        ai_format_combo.bind("<<ComboboxSelected>>", lambda e: self.update_voice_ai_format_ui(ai_format_var.get(), format_info_var, model_combo))
        
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
                # 更新AI配置状态显示
                self.update_ai_config_status()
                
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

    

# ==================== 视频预览和片段选择功能 ====================
    
    def update_ai_config_status(self):
        """更新AI配置状态显示"""
        if hasattr(self, 'audio_cleaner_ai_enabled') and self.audio_cleaner_ai_enabled:
            if hasattr(self, 'audio_cleaner_ai_config') and self.audio_cleaner_ai_config.get('api_key'):
                self.ai_config_status_var.set("[OK] AI已配置")
                # 尝试更改文字颜色为绿色
                try:
                    for widget in self.ai_config_frame.winfo_children():
                        if isinstance(widget, ttk.Label) and widget.cget('textvariable') == str(self.ai_config_status_var):
                            widget.configure(foreground='#28a745')
                            break
                except:
                    pass
            else:
                self.ai_config_status_var.set("[WARN] AI已启用但未配置API")
        else:
            self.ai_config_status_var.set("[ERR] AI未启用")
    
    def toggle_video_preview(self):
        """切换视频预览区域的显示/隐藏"""
        media_file = self.cleaner_audio_var.get()
        if not media_file:
            return
            
        ext = os.path.splitext(media_file)[1].lower()
        is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
        
        if is_video and not self.extract_only_var.get():
            self.video_preview_frame.pack(fill=tk.BOTH, expand=True, pady=10, padx=5, after=self.audio_output_frame)
            self.preview_info_var.set(f"视频文件: {os.path.basename(media_file)}")
        else:
            self.video_preview_frame.pack_forget()
    
    def preview_video(self):
        """预览选中的视频文件"""
        media_file = self.cleaner_audio_var.get()
        if not media_file:
            messagebox.showwarning("警告", "请先选择视频文件")
            return
            
        ext = os.path.splitext(media_file)[1].lower()
        is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
        
        if not is_video:
            messagebox.showwarning("警告", "请选择视频文件")
            return
            
        try:
            # 使用系统默认播放器打开视频
            if os.name == 'nt':  # Windows
                os.startfile(media_file)
            elif os.name == 'posix':  # macOS/Linux
                if sys.platform == 'darwin':  # macOS
                    subprocess.run(['open', media_file])
                else:  # Linux
                    subprocess.run(['xdg-open', media_file])
            
            self.log(f"正在预览视频: {media_file}")
        except Exception as e:
            self.log(f"预览视频失败: {e}")
            messagebox.showerror("错误", f"无法预览视频: {e}")
    
    def select_video_segments(self):
        """分析视频并生成片段列表"""
        media_file = self.cleaner_audio_var.get()
        if not media_file:
            messagebox.showwarning("警告", "请先选择视频文件")
            return
            
        # 清空现有片段
        for item in self.segment_tree.get_children():
            self.segment_tree.delete(item)
        
        try:
            # 使用whisper生成字幕片段
            self.cleaner_status_var.set("🔍 正在分析视频片段...")
            self.log("正在分析视频并生成片段...")
            
            # 如果是视频文件，先提取音频
            ext = os.path.splitext(media_file)[1].lower()
            is_video = ext in ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv']
            
            audio_to_process = media_file
            if is_video:
                temp_audio = os.path.join(self.temp_dir, "temp_segment_analysis.wav")
                if self.extract_audio_from_video(media_file, temp_audio):
                    audio_to_process = temp_audio
                else:
                    raise Exception("音频提取失败")
            
            # 生成SRT文件
            srt_file = self.generate_srt_from_audio(audio_to_process)
            
            # 解析SRT文件
            segments = self.parse_srt_file(srt_file)
            
            # 添加到树形视图
            for segment in segments:
                duration = self.ms_to_time(segment['duration_ms'])
                self.segment_tree.insert('', 'end', values=(
                    segment['start_time'],
                    segment['end_time'],
                    duration,
                    '[OK]'
                ), tags=(segment['index'],))
            
            # 设置标签样式
            self.segment_tree.tag_configure('selected', background='#e3f2fd')
            
            # 更新视频总时长
            if segments:
                total_duration = self.ms_to_time(segments[-1]['end_time_ms'])
                self.end_time_var.set(total_duration)
                self.preview_info_var.set(f"视频文件: {os.path.basename(media_file)} | 总时长: {total_duration} | 片段数: {len(segments)}")
            
            self.log(f"[OK] 成功分析 {len(segments)} 个片段")
            self.cleaner_status_var.set("[OK] 片段分析完成")
            
        except Exception as e:
            self.log(f"[ERR] 分析视频片段失败: {e}")
            messagebox.showerror("错误", f"分析视频片段失败: {e}")
            self.cleaner_status_var.set("[ERR] 分析失败")
    
    def reset_segment_selection(self):
        """重置片段选择"""
        # 清空片段列表
        for item in self.segment_tree.get_children():
            self.segment_tree.delete(item)
        
        # 重置时间范围
        self.start_time_var.set("00:00:00")
        self.end_time_var.set("00:00:00")
        
        # 重置预览信息
        media_file = self.cleaner_audio_var.get()
        if media_file:
            self.preview_info_var.set(f"视频文件: {os.path.basename(media_file)}")
        else:
            self.preview_info_var.set("未选择视频文件")
        
        self.log("已重置片段选择")
    
    def apply_time_range(self):
        """应用时间范围选择，自动选择范围内的片段"""
        start_time = self.time_to_ms(self.start_time_var.get())
        end_time = self.time_to_ms(self.end_time_var.get())
        
        if start_time >= end_time:
            messagebox.showwarning("警告", "开始时间必须小于结束时间")
            return
        
        selected_count = 0
        for item in self.segment_tree.get_children():
            values = self.segment_tree.item(item)['values']
            segment_start = self.time_to_ms(values[0])
            segment_end = self.time_to_ms(values[1])
            
            # 检查片段是否在选择范围内
            if segment_end > start_time and segment_start < end_time:
                self.segment_tree.set(item, "选择", "[OK]")
                selected_count += 1
            else:
                self.segment_tree.set(item, "选择", "[ERR]")
        
        self.log(f"已根据时间范围选择 {selected_count} 个片段")
    
    def toggle_all_segments(self, select=True):
        """全选或全不选片段"""
        symbol = "[OK]" if select else "[ERR]"
        for item in self.segment_tree.get_children():
            self.segment_tree.set(item, "选择", symbol)
        
        action = "全选" if select else "全不选"
        self.log(f"已{action}所有片段")
    
    def invert_segment_selection(self):
        """反选片段"""
        for item in self.segment_tree.get_children():
            current = self.segment_tree.item(item)['values'][3]
            new_symbol = "[ERR]" if current == "[OK]" else "[OK]"
            self.segment_tree.set(item, "选择", new_symbol)
        
        self.log("已反选所有片段")
    
    def get_selected_segments(self):
        """获取选中的片段时间范围"""
        selected_ranges = []
        
        for item in self.segment_tree.get_children():
            values = self.segment_tree.item(item)['values']
            if values[3] == "[OK]":  # 如果选中
                start_time = self.time_to_ms(values[0])
                end_time = self.time_to_ms(values[1])
                selected_ranges.append((start_time, end_time))
        
        return selected_ranges
    
    def ms_to_time(self, ms):
        """将毫秒转换为时间字符串 (HH:MM:SS)"""
        seconds = ms // 1000
        minutes = seconds // 60
        hours = minutes // 60
        
        return f"{hours:02d}:{minutes % 60:02d}:{seconds % 60:02d}"


def main():
    """
    主函数（优化版本）
    """
    # 设置进程优先级（Windows）
    try:
        import psutil
        process = psutil.Process()
        # 设置为高优先级
        process.nice(psutil.HIGH_PRIORITY_CLASS)
    except:
        pass
    
    # 创建支持拖放的根窗口
    if DRAG_DROP_AVAILABLE:
        try:
            root = TkinterDnD.Tk()
        except:
            root = tk.Tk()
    else:
        root = tk.Tk()
    
    app = AllInOneGUI(root)
    
    # 程序退出时清理所有资源
    def on_closing():
        try:
            logger.log("SYSTEM", "应用关闭", "用户关闭应用程序")
            app.cleanup_resources()
            # 关闭全局日志系统
            if EVENT_LOGGER_AVAILABLE:
                logger.close()
        except Exception as e:
            print(f"清理资源时出错: {e}")
        finally:
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    
    # 优化Tkinter性能
    try:
        # 启用优化模式
        root.tk.call('tk', 'scaling', 1.0)
        # 减少重绘频率
        root.after(100, lambda: None)
    except:
        pass
    
    root.mainloop()


if __name__ == "__main__":
    main()
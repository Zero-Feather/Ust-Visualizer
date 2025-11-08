import os
import pygame
import math
from pygame.locals import *
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import threading
from PIL import Image
import json
import re

class USTParser:
    def __init__(self):
        self.notes = []
        self.tempo = 120.0
        self.project_name = ""
        self.total_duration = 0  # 总时长（秒）
        
    def parse_file(self, filename):
        """解析UST文件"""
        try:
            # 尝试多种编码格式
            encodings = ['utf-8', 'shift_jis', 'gbk', 'big5', 'cp932']
            content = None
            
            for encoding in encodings:
                try:
                    with open(filename, 'r', encoding=encoding) as file:
                        content = file.read()
                    print(f"成功以 {encoding} 编码读取UST文件")
                    break
                except UnicodeDecodeError:
                    continue
            
            if content is None:
                # 如果所有编码都失败，使用二进制读取并忽略错误
                with open(filename, 'rb') as file:
                    content = file.read().decode('utf-8', errors='ignore')
                print("使用忽略错误的方式读取UST文件")
            
            # 解析基本信息
            self._parse_metadata(content)
            
            # 解析音符数据
            self._parse_notes(content)
            
            # 计算总时长
            self._calculate_total_duration()
            
            # 调试信息：打印前几个音符的时间信息
            print(f"解析完成，共 {len(self.notes)} 个音符")
            for i, note in enumerate(self.notes[:5]):
                print(f"音符 {i}: 开始={note['start_time']:.2f}s, 结束={note['end_time']:.2f}s, "
                      f"歌词='{note['lyric']}', 音高={note['note_num']}")
            
            return True
            
        except Exception as e:
            print(f"UST解析错误: {e}")
            return False
    
    def _parse_metadata(self, content):
        """解析元数据"""
        # 解析速度
        tempo_match = re.search(r'Tempo=([\d.]+)', content)
        if tempo_match:
            self.tempo = float(tempo_match.group(1))
            print(f"解析到速度: {self.tempo} BPM")
        
        # 解析项目名称
        project_match = re.search(r'ProjectName=([^\r\n]+)', content)
        if project_match:
            self.project_name = project_match.group(1)
            print(f"项目名称: {self.project_name}")
    
    def _safe_float_convert(self, value_str, default=0.0):
        """安全地将字符串转换为浮点数"""
        if value_str is None or value_str.strip().lower() in ['null', '']:
            return default
        try:
            return float(value_str)
        except ValueError:
            return default
    
    def _safe_int_convert(self, value_str, default=0):
        """安全地将字符串转换为整数"""
        if value_str is None or value_str.strip().lower() in ['null', '']:
            return default
        try:
            return int(value_str)
        except ValueError:
            return default
    
    def _parse_notes(self, content):
        """解析音符数据"""
        self.notes = []
        
        # 使用正则表达式找到所有音符块
        note_blocks = re.findall(r'\[#(\d+)\](.*?)(?=\[#\d+\]|$)', content, re.DOTALL)
        
        print(f"找到 {len(note_blocks)} 个音符块")
        
        current_time = 0  # 当前时间（秒）
        
        for note_num, note_content in note_blocks:
            # 跳过设置块（[#SETTING]）和其他非音符块
            if note_num == 'SETTING' or note_num == 'TRACKEND' or note_num == 'PREV' or note_num == 'NEXT':
                continue
                
            try:
                note_number = int(note_num)
            except ValueError:
                # 如果不是数字，跳过这个块
                continue
            
            note_data = {
                'number': note_number,
                'length': 480,  # 默认值（ticks）
                'lyric': 'R',   # 默认休止符
                'note_num': 60,  # 默认C5
                'pbs': [0, 0],  # PBS格式: PBS=X;Y 或 PBS=X
                'pbw': [],      # PBW点之间的宽度
                'pby': [],      # PBY点的音高偏移
                'pbm': [],      # 曲线类型
                'pitch_bend': [], # PitchBend数据
                'start_time': 0,  # 开始时间（秒）
                'end_time': 0,    # 结束时间（秒）
                'duration': 0     # 持续时间（秒）
            }
            
            # 解析长度
            length_match = re.search(r'Length=(\d+)', note_content)
            if length_match:
                note_data['length'] = self._safe_int_convert(length_match.group(1), 480)
            
            # 解析歌词
            lyric_match = re.search(r'Lyric=([^\r\n]+)', note_content)
            if lyric_match:
                note_data['lyric'] = lyric_match.group(1).strip()
            
            # 解析音高
            note_num_match = re.search(r'NoteNum=(\d+)', note_content)
            if note_num_match:
                note_data['note_num'] = self._safe_int_convert(note_num_match.group(1), 60)
            
            # 解析PBS (Pitch Bend Start)
            pbs_match = re.search(r'PBS=([^\r\n]+)', note_content)
            if pbs_match:
                pbs_str = pbs_match.group(1)
                if pbs_str.strip().lower() != 'null' and pbs_str.strip():
                    try:
                        if ';' in pbs_str:
                            pbs_parts = pbs_str.split(';')
                            note_data['pbs'] = [
                                self._safe_float_convert(pbs_parts[0], 0),
                                self._safe_float_convert(pbs_parts[1], 0)
                            ]
                        else:
                            note_data['pbs'] = [self._safe_float_convert(pbs_str, 0), 0]
                    except Exception as e:
                        print(f"警告: 音符 #{note_num} 的PBS值 '{pbs_str}' 解析失败: {e}")
                        note_data['pbs'] = [0, 0]
            
            # 解析PBW (Pitch Bend Width)
            pbw_match = re.search(r'PBW=([^\r\n]+)', note_content)
            if pbw_match:
                pbw_str = pbw_match.group(1)
                if pbw_str.strip().lower() != 'null' and pbw_str.strip():
                    try:
                        note_data['pbw'] = [self._safe_float_convert(x) for x in pbw_str.split(',') if x.strip()]
                    except Exception as e:
                        print(f"警告: 音符 #{note_num} 的PBW值解析失败: {e}")
                        note_data['pbw'] = []
            
            # 解析PBY (Pitch Bend Y)
            pby_match = re.search(r'PBY=([^\r\n]+)', note_content)
            if pby_match:
                pby_str = pby_match.group(1)
                if pby_str.strip().lower() != 'null' and pby_str.strip():
                    try:
                        note_data['pby'] = [self._safe_float_convert(x) for x in pby_str.split(',') if x.strip()]
                    except Exception as e:
                        print(f"警告: 音符 #{note_num} 的PBY值解析失败: {e}")
                        note_data['pby'] = []
            
            # 解析PBM (Pitch Bend Mode)
            pbm_match = re.search(r'PBM=([^\r\n]+)', note_content)
            if pbm_match:
                pbm_str = pbm_match.group(1)
                if pbm_str.strip().lower() != 'null' and pbm_str.strip():
                    note_data['pbm'] = [x.strip() for x in pbm_str.split(',')]
            
            # 解析PitchBend
            pitch_bend_match = re.search(r'PitchBend=([^\r\n]+)', note_content)
            if pitch_bend_match:
                pitch_bend_str = pitch_bend_match.group(1)
                if pitch_bend_str.strip().lower() != 'null' and pitch_bend_str.strip():
                    try:
                        note_data['pitch_bend'] = [self._safe_int_convert(x) for x in pitch_bend_str.split(',') if x.strip()]
                    except Exception as e:
                        print(f"警告: 音符 #{note_num} 的PitchBend值解析失败: {e}")
                        note_data['pitch_bend'] = []
            
            # 计算时间信息（将ticks转换为秒）
            # UST中通常使用480 ticks per quarter note
            # 正确的计算方式：duration_seconds = (length_in_ticks / 480) * (60 / tempo)
            quarter_note_duration = 60.0 / self.tempo  # 一个四分音符的秒数
            note_duration_seconds = (note_data['length'] / 480.0) * quarter_note_duration
            
            note_data['start_time'] = current_time
            note_data['end_time'] = current_time + note_duration_seconds
            note_data['duration'] = note_duration_seconds
            
            current_time += note_duration_seconds
            
            # 只添加有意义的音符（非休止符或有音高的音符）
            if note_data['lyric'].upper() != 'R' or note_data['note_num'] > 0:
                self.notes.append(note_data)
            else:
                print(f"跳过休止符: 音符 #{note_num}")
    
    def _calculate_total_duration(self):
        """计算总时长"""
        if not self.notes:
            self.total_duration = 0
            return
        
        # 最后一个音符的结束时间
        self.total_duration = max(note['end_time'] for note in self.notes)
        print(f"总时长: {self.total_duration:.2f} 秒")
    
    def calculate_pitch_curve(self, note_data, resolution=100):
        """计算音符的音高曲线"""
        # 如果没有PitchBend数据，尝试使用PBW和PBY生成曲线
        if not note_data['pitch_bend'] and note_data['pbw'] and note_data['pby']:
            return self._calculate_pitch_curve_from_pb(note_data, resolution)
        
        # 如果没有PitchBend数据，返回平坦曲线
        if not note_data['pitch_bend']:
            base_pitch = note_data['note_num']
            return [(i/resolution, base_pitch) for i in range(resolution + 1)]
        
        # 使用PitchBend数据生成曲线
        pitch_points = []
        pitch_bend_data = note_data['pitch_bend']
        
        # 计算每个点的音高
        for i in range(len(pitch_bend_data)):
            progress = i / (len(pitch_bend_data) - 1) if len(pitch_bend_data) > 1 else 0
            # PitchBend值转换为半音偏移（需要根据实际转换比例调整）
            pitch_offset = pitch_bend_data[i] / 100.0  # 简化转换
            actual_pitch = note_data['note_num'] + pitch_offset
            pitch_points.append((progress, actual_pitch))
        
        return pitch_points
    
    def _calculate_pitch_curve_from_pb(self, note_data, resolution):
        """使用PBW和PBY数据计算音高曲线"""
        base_pitch = note_data['note_num']
        pbs_x, pbs_y = note_data['pbs']
        pbw = note_data['pbw']
        pby = note_data['pby']
        
        # 如果没有PBW数据，返回平坦曲线
        if not pbw:
            return [(i/resolution, base_pitch) for i in range(resolution + 1)]
        
        # 计算总宽度
        total_width = sum(pbw)
        
        # 生成曲线点
        pitch_points = []
        current_pos = 0
        
        # 添加起点
        pitch_points.append((0, base_pitch + pbs_y))
        
        # 处理每个PBW段
        for i in range(len(pbw)):
            segment_width = pbw[i]
            segment_pitch = base_pitch + (pby[i] if i < len(pby) else 0)
            
            # 计算段的起点和终点
            start_pos = current_pos / total_width
            end_pos = (current_pos + segment_width) / total_width
            
            # 添加段终点
            pitch_points.append((end_pos, segment_pitch))
            
            current_pos += segment_width
        
        # 如果点太少，进行插值
        if len(pitch_points) < 2:
            return [(i/resolution, base_pitch) for i in range(resolution + 1)]
        
        # 对曲线进行插值以获得更平滑的结果
        interpolated_points = []
        for i in range(resolution + 1):
            progress = i / resolution
            
            # 找到当前进度所在的段
            for j in range(len(pitch_points) - 1):
                if pitch_points[j][0] <= progress <= pitch_points[j+1][0]:
                    # 线性插值
                    seg_progress = (progress - pitch_points[j][0]) / (pitch_points[j+1][0] - pitch_points[j][0])
                    pitch_value = pitch_points[j][1] + seg_progress * (pitch_points[j+1][1] - pitch_points[j][1])
                    interpolated_points.append((progress, pitch_value))
                    break
            else:
                # 如果找不到段，使用最后一个点的值
                interpolated_points.append((progress, pitch_points[-1][1]))
        
        return interpolated_points

class NoteRenderer:
    def __init__(self):
        # 音高到Y坐标的映射 (C0-C8)
        self.pitch_to_y = {}
        self._create_pitch_mapping()
    
    def _create_pitch_mapping(self):
        """创建音高到Y坐标的映射"""
        pitches = []
        for octave in range(0, 9):  # C0到C8
            for step in ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']:
                pitches.append(f"{step}{octave}")
        
        # 反转列表，使C8在顶部，C0在底部
        pitches.reverse()
        self.pitch_to_y = {pitch: i for i, pitch in enumerate(pitches)}
    
    def get_note_y_position(self, note_num, total_height, vertical_offset=0):
        """根据半音值获取Y坐标位置"""
        # 将半音值映射到屏幕位置 (C1=24, C2=36, 等等)
        # C8 = 108, C0 = 0
        max_pitch = 108  # C8
        min_pitch = 0    # C0
        
        # 归一化到0-1范围
        normalized = (note_num - min_pitch) / (max_pitch - min_pitch)
        # 反转Y轴（屏幕坐标：0在顶部）
        base_y = total_height * (1 - normalized)
        
        # 应用纵向偏移（按像素计算）
        return base_y + vertical_offset

class SequenceGenerator:
    def __init__(self):
        self.ust_parser = USTParser()
        self.renderer = NoteRenderer()
        
    def generate_frames(self, ust_file, output_folder, config):
        """生成序列帧"""
        if not self.ust_parser.parse_file(ust_file):
            return False
        
        # 创建输出文件夹
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)
        
        # 初始化Pygame
        pygame.init()
        
        # 设置屏幕模式，支持透明背景
        if config['transparent_background']:
            screen = pygame.Surface((config['width'], config['height']), pygame.SRCALPHA)
        else:
            screen = pygame.Surface((config['width'], config['height']))
        
        # 加载字体
        font = None
        if config['font_path'] and os.path.exists(config['font_path']):
            try:
                font = pygame.font.Font(config['font_path'], config['font_size'])
                print(f"成功加载字体: {config['font_path']}")
            except Exception as e:
                print(f"加载字体失败: {e}")
                font = pygame.font.SysFont(config['fallback_font'], config['font_size'])
        else:
            font = pygame.font.SysFont(config['fallback_font'], config['font_size'])
            print(f"使用备用字体: {config['fallback_font']}")
        
        # 计算总时长
        if not self.ust_parser.notes:
            print("没有找到音符")
            return False
            
        total_duration = self.ust_parser.total_duration
        
        # 计算滚动速度
        pixels_per_second = config['scroll_speed']
        judgment_line_x = config['width'] * config['judgment_line_position']
        
        # 第一个音符从屏幕右侧外进入需要的时间
        # 修改：音符从屏幕最右侧进入，而不是判定线右侧
        lead_in_time = config['width'] / pixels_per_second
        
        # 最后一个音符完全离开屏幕需要的时间
        lead_out_time = config['width'] / pixels_per_second
        
        # 调整总时长
        total_duration += lead_in_time + lead_out_time
        
        # 计算总帧数
        total_frames = int(total_duration * config['fps'])
        
        # 计算淡入淡出时间（秒）
        fade_duration = config['fade_duration']
        
        print(f"开始生成序列帧，共 {total_frames} 帧")
        print(f"总时长: {total_duration:.2f} 秒, 滚动速度: {pixels_per_second} 像素/秒")
        
        for frame_num in range(total_frames):
            current_time = frame_num / config['fps']
            
            # 清空屏幕
            if config['transparent_background']:
                screen.fill((0, 0, 0, 0))  # 透明背景
            else:
                screen.fill(config['background_color'])
            
            # 绘制判定线
            pygame.draw.line(screen, config['judgment_line_color'], 
                           (judgment_line_x, 0), 
                           (judgment_line_x, config['height']), 2)
            
            # 绘制音符
            visible_notes_count = 0
            for note in self.ust_parser.notes:
                if self._draw_note(screen, note, current_time, config, 
                                 pixels_per_second, judgment_line_x, font, total_duration, lead_in_time):
                    visible_notes_count += 1
            
            # 绘制音高曲线（在音符上层）
            if config.get('show_pitch_curve', False):
                self._draw_pitch_curves(screen, self.ust_parser.notes, current_time, 
                                      config, pixels_per_second, judgment_line_x, total_duration, lead_in_time)
            
            # 保存帧
            frame_path = os.path.join(output_folder, f"frame_{frame_num:06d}.png")
            pygame.image.save(screen, frame_path)
            
            if frame_num % 30 == 0:  # 每30帧打印进度
                print(f"生成进度: {frame_num}/{total_frames}, 当前可见音符: {visible_notes_count}")
        
        pygame.quit()
        return True
    
    def _draw_note(self, screen, note, current_time, config, pixels_per_second, judgment_line_x, font, total_duration, lead_in_time):
        """绘制单个音符，返回是否成功绘制"""
        # 修改：音符从屏幕最右侧进入
        # 计算音符位置 - 确保第一个音符从屏幕最右侧外进入
        note_start_x = config['width'] + (note['start_time'] - current_time + lead_in_time) * pixels_per_second
        note_end_x = config['width'] + (note['end_time'] - current_time + lead_in_time) * pixels_per_second
        
        # 如果音符完全在屏幕外，不绘制
        if note_end_x < 0 or note_start_x > config['width']:
            return False
        
        # 跳过无效的音符（休止符或音高为0）
        if note['lyric'].upper() == 'R' or note['note_num'] <= 0:
            return False
         
        # 计算音符位置和大小（应用纵向偏移）
        note_y = self.renderer.get_note_y_position(note['note_num'], config['height'], config['vertical_offset'])
        note_width = max(10, note_end_x - note_start_x)
        note_height = config['note_height']  # 使用可配置的音符高度
        
        # 如果音符宽度太小，可能是计算错误，跳过
        if note_width < 5:
            return False
        
        # 判断是否在判定线上
        is_active = note_start_x <= judgment_line_x <= note_end_x
        
        # 计算淡入淡出透明度
        fade_alpha = 255
        fade_duration = config['fade_duration']
        
        # 开头淡入 - 只在序列开始时应用
        if current_time < fade_duration:
            fade_alpha = int(255 * (current_time / fade_duration))
        
        # 结尾淡出 - 只在序列结束时应用
        if current_time > total_duration - fade_duration:
            fade_alpha = int(255 * ((total_duration - current_time) / fade_duration))
        
        # 选择颜色
        note_color = config['active_note_color'] if is_active else config['note_color']
        
        # 应用淡入淡出效果
        if fade_alpha < 255:
            note_color = (*note_color[:3], fade_alpha)
        
        # 绘制音符阴影
        if config['note_shadow']:
            shadow_color = (0, 0, 0, 100) if config['transparent_background'] else (30, 30, 30)
            shadow_rect = (note_start_x + 3, note_y - note_height/2 + 3, 
                          note_width, note_height)
            if config['note_corner_radius'] > 0:
                self._draw_rounded_rect(screen, shadow_color, shadow_rect, config['note_corner_radius'])
            else:
                pygame.draw.rect(screen, shadow_color, shadow_rect)
        
        # 绘制音符主体
        note_rect = (note_start_x, note_y - note_height/2, note_width, note_height)
        if config['note_corner_radius'] > 0:
            self._draw_rounded_rect(screen, note_color, note_rect, config['note_corner_radius'])
        else:
            pygame.draw.rect(screen, note_color, note_rect)
        
        # 绘制歌词（如果不是休止符）
        if note['lyric'] and note['lyric'].upper() != 'R':
            try:
                # 使用传入的字体渲染文本
                lyric_color = config['lyric_color']
                if fade_alpha < 255:
                    lyric_color = (*lyric_color[:3], fade_alpha)
                
                text_surface = font.render(note['lyric'], True, lyric_color)
                
                # 计算歌词位置（音符头部上方）
                lyric_x = note_start_x + min(20, note_width / 2)  # 在音符开头位置
                lyric_y = note_y - note_height/2 - config['lyric_offset']
                
                text_rect = text_surface.get_rect(midbottom=(lyric_x, lyric_y))
                screen.blit(text_surface, text_rect)
            except Exception as e:
                print(f"渲染歌词失败: {e}")
        
        return True
    
    def _draw_pitch_curves(self, screen, ust_notes, current_time, config, 
                          pixels_per_second, judgment_line_x, total_duration, lead_in_time):
        """绘制音高曲线"""
        if not ust_notes:
            return
        
        curve_color = config.get('pitch_curve_color', (255, 255, 0))
        curve_width = config.get('pitch_curve_width', 3)
        show_shadow = config.get('pitch_curve_shadow', True)
        show_dots = config.get('pitch_curve_dots', True)
        dot_size = config.get('pitch_curve_dot_size', 5)
        curve_smoothness = config.get('pitch_curve_smoothness', 50)  # 平滑度参数
        
        # 计算淡入淡出透明度
        fade_alpha = 255
        fade_duration = config['fade_duration']
        
        if current_time < fade_duration:
            fade_alpha = int(255 * (current_time / fade_duration))
        elif current_time > total_duration - fade_duration:
            fade_alpha = int(255 * ((total_duration - current_time) / fade_duration))
        
        if fade_alpha < 255:
            curve_color = (*curve_color[:3], fade_alpha)
        
        # 绘制每个音符的音高曲线
        for i, note in enumerate(ust_notes):
            # 跳过无效的音符
            if note['lyric'].upper() == 'R' or note['note_num'] <= 0:
                continue
                
            # 计算音符在屏幕上的位置
            # 修改：音符从屏幕最右侧进入
            note_start_x = config['width'] + (note['start_time'] - current_time + lead_in_time) * pixels_per_second
            note_end_x = config['width'] + (note['end_time'] - current_time + lead_in_time) * pixels_per_second
            
            # 如果音符完全在屏幕外，跳过
            if note_end_x < 0 or note_start_x > config['width']:
                continue
            
            # 计算音高曲线（使用平滑度参数）
            pitch_points = self.ust_parser.calculate_pitch_curve(note, resolution=curve_smoothness)
            
            if len(pitch_points) < 2:
                continue
            
            # 将音高点转换为屏幕坐标（应用纵向偏移）
            screen_points = []
            for progress, pitch_value in pitch_points:
                x = note_start_x + progress * (note_end_x - note_start_x)
                y = self.renderer.get_note_y_position(pitch_value, config['height'], config['vertical_offset'])
                screen_points.append((x, y))
            
            # 绘制曲线阴影
            if show_shadow and curve_width > 1:
                shadow_points = [(x + 2, y + 2) for x, y in screen_points]
                shadow_color = (0, 0, 0, 100) if config['transparent_background'] else (30, 30, 30)
                if len(shadow_points) > 1:
                    pygame.draw.lines(screen, shadow_color, False, shadow_points, curve_width)
            
            # 绘制音高曲线
            if len(screen_points) > 1:
                pygame.draw.lines(screen, curve_color, False, screen_points, curve_width)
                
                # 在曲线起点和终点添加标记点
                if show_dots and len(screen_points) >= 2:
                    start_point = screen_points[0]
                    end_point = screen_points[-1]
                    pygame.draw.circle(screen, curve_color, (int(start_point[0]), int(start_point[1])), dot_size)
                    pygame.draw.circle(screen, curve_color, (int(end_point[0]), int(end_point[1])), dot_size)
    
    def _draw_rounded_rect(self, surface, color, rect, radius):
        """绘制圆角矩形"""
        x, y, width, height = rect
        
        # 如果圆角半径太大，调整到合适大小
        radius = min(radius, min(width, height) // 2)
        
        # 绘制圆角矩形的主体
        pygame.draw.rect(surface, color, (x + radius, y, width - 2*radius, height))
        pygame.draw.rect(surface, color, (x, y + radius, width, height - 2*radius))
        
        # 绘制四个角
        pygame.draw.circle(surface, color, (x + radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + width - radius, y + radius), radius)
        pygame.draw.circle(surface, color, (x + radius, y + height - radius), radius)
        pygame.draw.circle(surface, color, (x + width - radius, y + height - radius), radius)

class GUI:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("UST Visualizer - UST 可视化 by x-KOI-x (bilibili)")
        self.root.geometry("1000x700")  # 调整为更宽的窗口
        
        # 默认配置
        self.default_config = {
            'width': 1920,
            'height': 1080,
            'fps': 30,
            'note_color': (255, 0, 0),
            'active_note_color': (0, 255, 0),
            'lyric_color': (255, 255, 255),
            'background_color': (0, 0, 0),
            'judgment_line_color': (255, 255, 0),
            'judgment_line_position': 0.2,
            'scroll_speed': 500,
            'font_path': "",
            'font_size': 24,
            'fallback_font': "simsun",
            'note_height': 20,
            'note_corner_radius': 5,
            'note_shadow': True,
            'transparent_background': False,
            'lyric_offset': 15,
            'fade_duration': 1.0,
            # 音高曲线配置
            'show_pitch_curve': True,
            'pitch_curve_color': (0, 255, 255),
            'pitch_curve_width': 3,
            'pitch_curve_shadow': True,
            'pitch_curve_dots': True,  # 是否显示曲线端点
            'pitch_curve_dot_size': 5,  # 曲线端点大小
            'pitch_curve_smoothness': 50,  # 曲线平滑度
            # 纵向位置调整
            'vertical_offset': 0  # 纵向偏移量（像素）
        }
        
        # 当前配置
        self.config = self.default_config.copy()
        
        self.ust_file = ""
        self.output_folder = ""
        self.font_file = ""
        
        # 初始化所有UI变量
        self._init_ui_variables()
        
        self.setup_ui()
    
    def _init_ui_variables(self):
        """初始化所有UI变量，防止属性错误"""
        # 基本参数
        self.width_var = tk.StringVar(value=str(self.config['width']))
        self.height_var = tk.StringVar(value=str(self.config['height']))
        self.fps_var = tk.StringVar(value=str(self.config['fps']))
        self.font_size_var = tk.StringVar(value=str(self.config['font_size']))
        
        # 动画参数
        self.speed_var = tk.DoubleVar(value=self.config['scroll_speed'])
        self.judgment_var = tk.DoubleVar(value=self.config['judgment_line_position'])
        self.fade_duration_var = tk.DoubleVar(value=self.config['fade_duration'])
        
        # 样式参数
        self.note_height_var = tk.IntVar(value=self.config['note_height'])
        self.corner_radius_var = tk.IntVar(value=self.config['note_corner_radius'])
        self.shadow_var = tk.BooleanVar(value=self.config['note_shadow'])
        self.transparent_var = tk.BooleanVar(value=self.config['transparent_background'])
        self.lyric_offset_var = tk.IntVar(value=self.config['lyric_offset'])
        
        # 音高曲线参数
        self.show_pitch_curve_var = tk.BooleanVar(value=self.config['show_pitch_curve'])
        self.pitch_curve_width_var = tk.IntVar(value=self.config['pitch_curve_width'])
        self.pitch_curve_shadow_var = tk.BooleanVar(value=self.config['pitch_curve_shadow'])
        self.pitch_curve_dots_var = tk.BooleanVar(value=self.config['pitch_curve_dots'])
        self.pitch_curve_dot_size_var = tk.IntVar(value=self.config['pitch_curve_dot_size'])
        self.pitch_curve_smoothness_var = tk.IntVar(value=self.config['pitch_curve_smoothness'])
        
        # 纵向位置调整参数
        self.vertical_offset_var = tk.IntVar(value=self.config['vertical_offset'])
    
    def setup_ui(self):
        """设置用户界面 - 左侧文件选择，右侧参数设置"""
        # 创建主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # 创建左右分栏 - 左侧窄，右侧宽
        left_frame = ttk.Frame(main_frame, width=250)
        left_frame.pack(side="left", fill="y", padx=(0, 10))
        left_frame.pack_propagate(False)  # 固定宽度
        
        right_frame = ttk.Frame(main_frame)
        right_frame.pack(side="right", fill="both", expand=True)
        
        # 左侧面板 - 文件设置
        self.setup_left_panel(left_frame)
        
        # 右侧面板 - 使用Notebook组织参数设置
        self.setup_right_panel(right_frame)
        
        # 底部控制区域
        self.setup_bottom_panel()
    
    def setup_left_panel(self, parent):
        """设置左侧文件选择面板"""
        # 文件设置区域
        file_frame = ttk.LabelFrame(parent, text="文件设置", padding=10)
        file_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Button(file_frame, text="选择UST文件", 
                  command=self.select_ust_file).pack(fill="x", pady=5)
        self.ust_label = ttk.Label(file_frame, text="未选择UST文件", wraplength=230)
        self.ust_label.pack(fill="x", pady=5)
        
        ttk.Button(file_frame, text="选择输出文件夹", 
                  command=self.select_output_folder).pack(fill="x", pady=5)
        self.output_label = ttk.Label(file_frame, text="未选择文件夹", wraplength=230)
        self.output_label.pack(fill="x", pady=5)
        
        ttk.Button(file_frame, text="选择字体文件", 
                  command=self.select_font_file).pack(fill="x", pady=5)
        self.font_label = ttk.Label(file_frame, text="未选择字体", wraplength=230)
        self.font_label.pack(fill="x", pady=5)
    
    def setup_right_panel(self, parent):
        """设置右侧参数面板 - 使用Notebook组织"""
        # 创建Notebook（选项卡）
        notebook = ttk.Notebook(parent)
        notebook.pack(fill="both", expand=True)
        
        # 基本设置标签页
        basic_tab = ttk.Frame(notebook, padding=10)
        notebook.add(basic_tab, text="基本设置")
        self.setup_basic_tab(basic_tab)
        
        # 动画设置标签页
        anim_tab = ttk.Frame(notebook, padding=10)
        notebook.add(anim_tab, text="动画设置")
        self.setup_animation_tab(anim_tab)
        
        # 样式设置标签页
        style_tab = ttk.Frame(notebook, padding=10)
        notebook.add(style_tab, text="样式设置")
        self.setup_style_tab(style_tab)
        
        # 颜色设置标签页
        color_tab = ttk.Frame(notebook, padding=10)
        notebook.add(color_tab, text="颜色设置")
        self.setup_color_tab(color_tab)
    
    def setup_basic_tab(self, parent):
        """设置基本设置标签页"""
        # 分辨率设置
        res_frame = ttk.LabelFrame(parent, text="分辨率设置", padding=10)
        res_frame.pack(fill="x", pady=(0, 10))
        
        width_frame = ttk.Frame(res_frame)
        width_frame.pack(fill="x", pady=5)
        ttk.Label(width_frame, text="宽度:").pack(side="left")
        ttk.Entry(width_frame, textvariable=self.width_var, width=8).pack(side="right", padx=(10, 0))
        
        height_frame = ttk.Frame(res_frame)
        height_frame.pack(fill="x", pady=5)
        ttk.Label(height_frame, text="高度:").pack(side="left")
        ttk.Entry(height_frame, textvariable=self.height_var, width=8).pack(side="right", padx=(10, 0))
        
        # 帧率和字体设置
        settings_frame = ttk.LabelFrame(parent, text="其他设置", padding=10)
        settings_frame.pack(fill="x", pady=(0, 10))
        
        fps_frame = ttk.Frame(settings_frame)
        fps_frame.pack(fill="x", pady=5)
        ttk.Label(fps_frame, text="帧率:").pack(side="left")
        ttk.Entry(fps_frame, textvariable=self.fps_var, width=8).pack(side="right", padx=(10, 0))
        
        font_size_frame = ttk.Frame(settings_frame)
        font_size_frame.pack(fill="x", pady=5)
        ttk.Label(font_size_frame, text="字体大小:").pack(side="left")
        ttk.Entry(font_size_frame, textvariable=self.font_size_var, width=8).pack(side="right", padx=(10, 0))
        
        # 背景设置
        bg_frame = ttk.LabelFrame(parent, text="背景设置", padding=10)
        bg_frame.pack(fill="x")
        
        ttk.Checkbutton(bg_frame, text="透明背景", 
                       variable=self.transparent_var).pack(anchor="w", pady=5)
    
    def setup_animation_tab(self, parent):
        """设置动画设置标签页"""
        # 滚动速度
        speed_frame = ttk.LabelFrame(parent, text="滚动速度", padding=10)
        speed_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Scale(speed_frame, from_=100, to=2000, variable=self.speed_var,
                 orient="horizontal").pack(fill="x", pady=5)
        speed_value_frame = ttk.Frame(speed_frame)
        speed_value_frame.pack(fill="x")
        ttk.Label(speed_value_frame, text="速度值:").pack(side="left")
        ttk.Label(speed_value_frame, textvariable=self.speed_var, width=6).pack(side="right")
        
        # 判定线位置
        judgment_frame = ttk.LabelFrame(parent, text="判定线位置", padding=10)
        judgment_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Scale(judgment_frame, from_=0.1, to=0.5, variable=self.judgment_var, 
                 orient="horizontal").pack(fill="x", pady=5)
        judgment_value_frame = ttk.Frame(judgment_frame)
        judgment_value_frame.pack(fill="x")
        ttk.Label(judgment_value_frame, text="位置:").pack(side="left")
        ttk.Label(judgment_value_frame, textvariable=self.judgment_var, width=6).pack(side="right")
        
        # 淡入淡出时长
        fade_frame = ttk.LabelFrame(parent, text="淡入淡出效果", padding=10)
        fade_frame.pack(fill="x", pady=(0, 10))
        
        ttk.Scale(fade_frame, from_=0, to=5, variable=self.fade_duration_var,
                 orient="horizontal").pack(fill="x", pady=5)
        fade_value_frame = ttk.Frame(fade_frame)
        fade_value_frame.pack(fill="x")
        ttk.Label(fade_value_frame, text="时长:").pack(side="left")
        ttk.Label(fade_value_frame, textvariable=self.fade_duration_var, width=4).pack(side="left")
        ttk.Label(fade_value_frame, text="秒").pack(side="left")
        
        # 纵向位置调整
        vertical_frame = ttk.LabelFrame(parent, text="纵向位置调整", padding=10)
        vertical_frame.pack(fill="x")
        
        ttk.Scale(vertical_frame, from_=-200, to=200, variable=self.vertical_offset_var,
                 orient="horizontal").pack(fill="x", pady=5)
        vertical_value_frame = ttk.Frame(vertical_frame)
        vertical_value_frame.pack(fill="x")
        ttk.Label(vertical_value_frame, text="偏移量:").pack(side="left")
        ttk.Label(vertical_value_frame, textvariable=self.vertical_offset_var, width=4).pack(side="left")
        ttk.Label(vertical_value_frame, text="像素").pack(side="left")
        ttk.Label(vertical_value_frame, text="(负值上移，正值下移)").pack(side="right")
    
    def setup_style_tab(self, parent):
        """设置样式设置标签页"""
        # 音符样式
        note_style_frame = ttk.LabelFrame(parent, text="音符样式", padding=10)
        note_style_frame.pack(fill="x", pady=(0, 10))
        
        # 音符高度
        height_frame = ttk.Frame(note_style_frame)
        height_frame.pack(fill="x", pady=5)
        ttk.Label(height_frame, text="音符高度:").pack(side="left")
        ttk.Scale(height_frame, from_=5, to=50, variable=self.note_height_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(height_frame, textvariable=self.note_height_var, width=2).pack(side="right")
        
        # 圆角半径
        radius_frame = ttk.Frame(note_style_frame)
        radius_frame.pack(fill="x", pady=5)
        ttk.Label(radius_frame, text="圆角半径:").pack(side="left")
        ttk.Scale(radius_frame, from_=0, to=20, variable=self.corner_radius_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(radius_frame, textvariable=self.corner_radius_var, width=2).pack(side="right")
        
        # 其他样式选项
        options_frame = ttk.Frame(note_style_frame)
        options_frame.pack(fill="x", pady=5)
        ttk.Checkbutton(options_frame, text="音符阴影", variable=self.shadow_var).pack(side="left")
        
        # 歌词位置
        lyric_frame = ttk.LabelFrame(parent, text="歌词位置", padding=10)
        lyric_frame.pack(fill="x", pady=(0, 10))
        
        lyric_offset_frame = ttk.Frame(lyric_frame)
        lyric_offset_frame.pack(fill="x", pady=5)
        ttk.Label(lyric_offset_frame, text="垂直偏移:").pack(side="left")
        ttk.Scale(lyric_offset_frame, from_=5, to=50, variable=self.lyric_offset_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(lyric_offset_frame, textvariable=self.lyric_offset_var, width=2).pack(side="right")
        
        # 音高曲线样式
        pitch_curve_frame = ttk.LabelFrame(parent, text="音高曲线样式", padding=10)
        pitch_curve_frame.pack(fill="x")
        
        # 音高曲线开关
        ttk.Checkbutton(pitch_curve_frame, text="显示音高曲线", 
                       variable=self.show_pitch_curve_var).pack(anchor="w", pady=5)
        
        # 曲线宽度
        curve_width_frame = ttk.Frame(pitch_curve_frame)
        curve_width_frame.pack(fill="x", pady=5)
        ttk.Label(curve_width_frame, text="曲线宽度:").pack(side="left")
        ttk.Scale(curve_width_frame, from_=1, to=10, variable=self.pitch_curve_width_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(curve_width_frame, textvariable=self.pitch_curve_width_var, width=2).pack(side="right")
        
        # 曲线阴影
        ttk.Checkbutton(pitch_curve_frame, text="曲线阴影", 
                       variable=self.pitch_curve_shadow_var).pack(anchor="w", pady=5)
        
        # 曲线端点
        ttk.Checkbutton(pitch_curve_frame, text="显示曲线端点", 
                       variable=self.pitch_curve_dots_var).pack(anchor="w", pady=5)
        
        # 端点大小
        dot_size_frame = ttk.Frame(pitch_curve_frame)
        dot_size_frame.pack(fill="x", pady=5)
        ttk.Label(dot_size_frame, text="端点大小:").pack(side="left")
        ttk.Scale(dot_size_frame, from_=1, to=15, variable=self.pitch_curve_dot_size_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(dot_size_frame, textvariable=self.pitch_curve_dot_size_var, width=2).pack(side="right")
        
        # 曲线平滑度
        smoothness_frame = ttk.Frame(pitch_curve_frame)
        smoothness_frame.pack(fill="x", pady=5)
        ttk.Label(smoothness_frame, text="曲线平滑度:").pack(side="left")
        ttk.Scale(smoothness_frame, from_=10, to=200, variable=self.pitch_curve_smoothness_var,
                 orient="horizontal").pack(side="right", fill="x", expand=True, padx=(10, 0))
        ttk.Label(smoothness_frame, textvariable=self.pitch_curve_smoothness_var, width=3).pack(side="right")
    
    def setup_color_tab(self, parent):
        """设置颜色设置标签页"""
        colors = [
            ("音符颜色:", "note_color"),
            ("激活音符颜色:", "active_note_color"), 
            ("歌词颜色:", "lyric_color"),
            ("背景颜色:", "background_color"),
            ("判定线颜色:", "judgment_line_color"),
            ("音高曲线颜色:", "pitch_curve_color")
        ]
        
        for label_text, color_key in colors:
            frame = ttk.Frame(parent)
            frame.pack(fill="x", pady=5)
            
            ttk.Label(frame, text=label_text, width=15).pack(side="left")
            
            color_btn = ttk.Button(frame, text="选择颜色", 
                                  command=lambda k=color_key: self.choose_color(k))
            color_btn.pack(side="left", padx=5)
            
            # 创建颜色预览
            preview = tk.Canvas(frame, width=60, height=25)
            preview.pack(side="left", padx=5)
            self.draw_color_preview(preview, self.config[color_key])
            setattr(self, f"{color_key}_preview", preview)
    
    def setup_bottom_panel(self):
        """设置底部控制面板"""
        # 底部控制区域
        bottom_frame = ttk.Frame(self.root)
        bottom_frame.pack(fill="x", padx=10, pady=10)
        
        # 控制按钮
        button_frame = ttk.Frame(bottom_frame)
        button_frame.pack(fill="x", pady=5)
        
        ttk.Button(button_frame, text="生成序列帧", 
                  command=self.start_generation).pack(side="left", padx=5)
        
        ttk.Button(button_frame, text="保存配置", 
                  command=self.save_config).pack(side="left", padx=5)
        
        ttk.Button(button_frame, text="加载配置", 
                  command=self.load_config).pack(side="left", padx=5)
        
        # 进度条
        self.progress = ttk.Progressbar(bottom_frame, mode='indeterminate')
        self.progress.pack(fill="x", pady=5)
        
        # 日志区域
        log_frame = ttk.LabelFrame(bottom_frame, text="日志", padding=5)
        log_frame.pack(fill="both", expand=True)
        
        self.log_text = tk.Text(log_frame, height=6)
        scrollbar_log = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        self.log_text.config(yscrollcommand=scrollbar_log.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar_log.pack(side="right", fill="y")
    
    def draw_color_preview(self, canvas, color):
        """在画布上绘制颜色预览"""
        canvas.delete("all")
        canvas.create_rectangle(0, 0, 60, 25, fill=self.rgb_to_hex(color), outline="black")
    
    def rgb_to_hex(self, rgb):
        """RGB元组转十六进制颜色"""
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'
    
    def hex_to_rgb(self, hex_color):
        """十六进制颜色转RGB元组"""
        hex_color = hex_color.lstrip('#')
        return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
    
    def choose_color(self, color_key):
        """选择颜色"""
        from tkinter import colorchooser
        color = colorchooser.askcolor(initialcolor=self.rgb_to_hex(self.config[color_key]))
        if color[0]:
            self.config[color_key] = tuple(map(int, color[0]))
            preview = getattr(self, f"{color_key}_preview")
            self.draw_color_preview(preview, self.config[color_key])
    
    def select_ust_file(self):
        """选择UST文件"""
        filename = filedialog.askopenfilename(
            title="选择UST文件",
            filetypes=[("UST files", "*.ust"), ("Text files", "*.txt"), ("All files", "*.*")]
        )
        if filename:
            self.ust_file = filename
            self.ust_label.config(text=os.path.basename(filename))
            self.log(f"已选择UST文件: {os.path.basename(filename)}")
    
    def select_output_folder(self):
        """选择输出文件夹"""
        folder = filedialog.askdirectory(title="选择输出文件夹")
        if folder:
            self.output_folder = folder
            self.output_label.config(text=folder)
    
    def select_font_file(self):
        """选择字体文件"""
        filename = filedialog.askopenfilename(
            title="选择字体文件",
            filetypes=[("字体文件", "*.ttf *.otf *.ttc"), ("所有文件", "*.*")]
        )
        if filename:
            self.font_file = filename
            self.config['font_path'] = filename
            self.font_label.config(text=os.path.basename(filename))
            self.log(f"已选择字体: {os.path.basename(filename)}")
    
    def update_config_from_ui(self):
        """从UI更新配置"""
        try:
            self.config.update({
                'width': int(self.width_var.get()),
                'height': int(self.height_var.get()),
                'fps': int(self.fps_var.get()),
                'judgment_line_position': self.judgment_var.get(),
                'scroll_speed': self.speed_var.get(),
                'font_size': int(self.font_size_var.get()),
                'font_path': self.font_file,
                'note_height': self.note_height_var.get(),
                'note_corner_radius': self.corner_radius_var.get(),
                'note_shadow': self.shadow_var.get(),
                'transparent_background': self.transparent_var.get(),
                'lyric_offset': self.lyric_offset_var.get(),
                'fade_duration': self.fade_duration_var.get(),
                # 音高曲线配置
                'show_pitch_curve': self.show_pitch_curve_var.get(),
                'pitch_curve_color': self.config.get('pitch_curve_color', (0, 255, 255)),
                'pitch_curve_width': self.pitch_curve_width_var.get(),
                'pitch_curve_shadow': self.pitch_curve_shadow_var.get(),
                'pitch_curve_dots': self.pitch_curve_dots_var.get(),
                'pitch_curve_dot_size': self.pitch_curve_dot_size_var.get(),
                'pitch_curve_smoothness': self.pitch_curve_smoothness_var.get(),
                # 纵向位置调整
                'vertical_offset': self.vertical_offset_var.get()
            })
            return True
        except ValueError as e:
            messagebox.showerror("错误", f"参数格式错误: {e}")
            return False
    
    def start_generation(self):
        """开始生成序列帧"""
        if not self.ust_file:
            messagebox.showerror("错误", "请先选择UST文件")
            return
        
        if not self.output_folder:
            messagebox.showerror("错误", "请先选择输出文件夹")
            return
        
        if not self.update_config_from_ui():
            return
        
        # 检查字体
        if not self.config['font_path']:
            result = messagebox.askyesno("字体警告", 
                                       "未选择自定义字体，将使用系统默认字体。\n"
                                       "如果显示乱码，请选择支持中文的字体文件。\n"
                                       "是否继续？")
            if not result:
                return
        
        # 在新线程中生成序列帧
        self.progress.start()
        thread = threading.Thread(target=self._generate_thread)
        thread.daemon = True
        thread.start()
    
    def _generate_thread(self):
        """生成线程"""
        try:
            generator = SequenceGenerator()
            success = generator.generate_frames(
                self.ust_file, 
                self.output_folder, 
                self.config
            )
            
            self.root.after(0, self._generation_complete, success)
            
        except Exception as e:
            self.root.after(0, self._generation_error, str(e))
    
    def _generation_complete(self, success):
        """生成完成回调"""
        self.progress.stop()
        if success:
            messagebox.showinfo("完成", "序列帧生成完成！")
            self.log("序列帧生成完成")
        else:
            messagebox.showerror("错误", "序列帧生成失败")
    
    def _generation_error(self, error_msg):
        """生成错误回调"""
        self.progress.stop()
        messagebox.showerror("错误", f"生成过程中发生错误:\n{error_msg}")
        self.log(f"错误: {error_msg}")
    
    def log(self, message):
        """添加日志"""
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
    
    def save_config(self):
        """保存配置到文件"""
        # 先更新配置
        if not self.update_config_from_ui():
            return
            
        filename = filedialog.asksaveasfilename(
            title="保存配置",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")]
        )
        if filename:
            try:
                # 将颜色转换为十六进制保存
                config_to_save = self.config.copy()
                for key in config_to_save:
                    if isinstance(config_to_save[key], tuple) and len(config_to_save[key]) == 3:
                        config_to_save[key] = self.rgb_to_hex(config_to_save[key])
                
                with open(filename, 'w', encoding='utf-8') as f:
                    json.dump(config_to_save, f, indent=2, ensure_ascii=False)
                messagebox.showinfo("成功", "配置保存成功")
                self.log(f"配置已保存到: {filename}")
            except Exception as e:
                messagebox.showerror("错误", f"保存配置失败: {e}")
    
    def load_config(self):
        """从文件加载配置"""
        filename = filedialog.askopenfilename(
            title="加载配置",
            filetypes=[("JSON files", "*.json")]
        )
        if filename:
            try:
                with open(filename, 'r', encoding='utf-8') as f:
                    loaded_config = json.load(f)
                
                # 将十六进制颜色转换回RGB元组
                for key in loaded_config:
                    if isinstance(loaded_config[key], str) and loaded_config[key].startswith('#'):
                        loaded_config[key] = self.hex_to_rgb(loaded_config[key])
                
                # 更新当前配置
                self.config.update(loaded_config)
                
                # 更新文件路径
                if 'font_path' in loaded_config:
                    self.font_file = loaded_config['font_path']
                
                # 更新UI变量
                self._update_ui_from_config()
                
                messagebox.showinfo("成功", "配置加载成功")
                self.log(f"配置已从 {filename} 加载")
            except Exception as e:
                messagebox.showerror("错误", f"加载配置失败: {e}")
    
    def _update_ui_from_config(self):
        """从配置更新UI"""
        # 基本参数
        self.width_var.set(str(self.config['width']))
        self.height_var.set(str(self.config['height']))
        self.fps_var.set(str(self.config['fps']))
        self.font_size_var.set(str(self.config['font_size']))
        
        # 动画参数
        self.judgment_var.set(self.config['judgment_line_position'])
        self.speed_var.set(self.config['scroll_speed'])
        self.fade_duration_var.set(self.config['fade_duration'])
        
        # 样式参数
        self.note_height_var.set(self.config['note_height'])
        self.corner_radius_var.set(self.config['note_corner_radius'])
        self.shadow_var.set(self.config['note_shadow'])
        self.transparent_var.set(self.config['transparent_background'])
        self.lyric_offset_var.set(self.config['lyric_offset'])
        
        # 音高曲线参数
        self.show_pitch_curve_var.set(self.config.get('show_pitch_curve', True))
        self.pitch_curve_width_var.set(self.config.get('pitch_curve_width', 3))
        self.pitch_curve_shadow_var.set(self.config.get('pitch_curve_shadow', True))
        self.pitch_curve_dots_var.set(self.config.get('pitch_curve_dots', True))
        self.pitch_curve_dot_size_var.set(self.config.get('pitch_curve_dot_size', 5))
        self.pitch_curve_smoothness_var.set(self.config.get('pitch_curve_smoothness', 50))
        
        # 纵向位置参数
        self.vertical_offset_var.set(self.config.get('vertical_offset', 0))
        
        # 更新文件显示
        if self.config['font_path']:
            self.font_label.config(text=os.path.basename(self.config['font_path']))
        else:
            self.font_label.config(text="未选择字体 (将使用系统默认字体)")
        
        # 更新颜色预览
        for color_key in ['note_color', 'active_note_color', 'lyric_color', 
                         'background_color', 'judgment_line_color', 'pitch_curve_color']:
            if color_key in self.config:
                preview = getattr(self, f"{color_key}_preview", None)
                if preview:
                    self.draw_color_preview(preview, self.config[color_key])
    
    def run(self):
        """运行GUI"""
        self.root.mainloop()

if __name__ == "__main__":
    app = GUI()
    app.run()
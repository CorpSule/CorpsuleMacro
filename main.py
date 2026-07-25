import customtkinter as ctk
import threading
import keyboard
import pyautogui
import json
import os
import sys
import time
import ctypes
import cv2
import webbrowser
import stat
import urllib.request
import urllib.parse
import subprocess
from tkinter import filedialog
from PIL import Image

from utils.vision import Vision
from utils.actions import Actions
from utils.webhook import DiscordWebhook

CURRENT_VERSION = "1.06"
# Public GitHub Repository Raw Version URL
UPDATE_CHECK_URL = "https://raw.githubusercontent.com/CorpSule/CorpsuleMacro/main/version.json"

ctk.set_appearance_mode("Dark")

user32 = ctypes.windll.user32
SW_RESTORE = 9

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False

if not is_admin():
    print("[SYSTEM] 🔐 Elevating to Administrator privileges...")
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(sys.argv), None, 1)
    sys.exit()

def get_app_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.abspath(".")

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = get_app_dir()
    return os.path.join(base_path, relative_path)

def get_map_preview_path():
    return os.path.join(get_app_dir(), "assets", "anime_expeditions", "map_preview.png")

def get_safe_config_path():
    app_dir = get_app_dir()
    local_cfg = os.path.join(app_dir, "config.json")
    
    if os.path.exists(local_cfg):
        try:
            os.chmod(local_cfg, stat.S_IWRITE | stat.S_IREAD)
        except Exception:
            pass
        return local_cfg

    appdata_dir = os.path.join(os.environ.get("APPDATA", "."), "CorpsuleMacro")
    try:
        os.makedirs(appdata_dir, exist_ok=True)
        return os.path.join(appdata_dir, "config.json")
    except Exception:
        return local_cfg

def snap_roblox_side_by_side(macro_x, macro_y):
    roblox_hwnd = Actions.get_roblox_hwnd()
    if roblox_hwnd:
        user32.ShowWindow(roblox_hwnd, SW_RESTORE)
        roblox_w = 800
        roblox_h = 600
        roblox_x = max(0, macro_x - roblox_w - 10)
        roblox_y = max(0, macro_y)
        user32.MoveWindow(roblox_hwnd, roblox_x, roblox_y, roblox_w, roblox_h, True)

THEMES = {
    "Cyber Violet": {"bg": "#0B0514", "card": "#160A29", "accent": "#8B5CF6", "hover": "#7C3AED", "text": "#E9D5FF", "border": "#3B1866"},
    "Emerald Neon": {"bg": "#03140D", "card": "#0A261B", "accent": "#10B981", "hover": "#059669", "text": "#A7F3D0", "border": "#065F46"},
    "Ocean Cyan": {"bg": "#040F1A", "card": "#0B1D33", "accent": "#06B6D4", "hover": "#0891B2", "text": "#CFFAFE", "border": "#164E63"},
    "Crimson Velvet": {"bg": "#140407", "card": "#260A12", "accent": "#F43F5E", "hover": "#E11D48", "text": "#FECDD3", "border": "#881337"}
}

class PrintRedirector:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, str_val):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", str_val)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def flush(self):
        pass


class CorpsuleApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(f"🔮 Corpsule Anime Expeditions v{CURRENT_VERSION}")
        self.geometry("430x750")
        self.resizable(False, False)

        if os.path.exists(resource_path("icon.ico")):
            try:
                self.iconbitmap(resource_path("icon.ico"))
            except Exception:
                pass

        self.is_running = False

        self.config_data = self.load_full_config()
        self.theme_name = self.config_data.get("theme", "Emerald Neon")
        self.theme = THEMES.get(self.theme_name, THEMES["Emerald Neon"])
        
        self.key_start = self.config_data.get("key_start", "f1")
        self.key_stop = self.config_data.get("key_stop", "f8")
        self.key_setpos = self.config_data.get("key_setpos", "f7")
        self.webhook_url = self.config_data.get("webhook_url", "")

        self.vision = Vision()
        self.selected_map = "School Grounds"
        self.selected_diff = "Difficulty 3"

        self.start_time = None
        self.total_runs = 0
        self.total_wins = 0

        self.build_corpsule_layout()

        sys.stdout = PrintRedirector(self.console_box)
        self.bind("<Configure>", self.on_window_move)

        self.register_hotkeys()
        self.after(500, self.snap_roblox)

    def load_full_config(self):
        cfg_path = get_safe_config_path()
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    data = json.load(f)
                    if "unit_positions" in data and len(data["unit_positions"]) > 0:
                        return data
            except Exception:
                pass

        default_config = {
            "theme": "Emerald Neon",
            "key_start": "f1",
            "key_stop": "f8",
            "key_setpos": "f7",
            "webhook_url": "",
            "unit_positions": [
                {"slot": 1, "x": 400, "y": 300, "upgrades": 0},
                {"slot": 2, "x": 450, "y": 320, "upgrades": 0},
                {"slot": 3, "x": 380, "y": 280, "upgrades": 0},
                {"slot": 4, "x": 420, "y": 350, "upgrades": 0}
            ]
        }
        try:
            with open(cfg_path, "w") as f:
                json.dump(default_config, f, indent=4)
        except Exception:
            pass
        return default_config

    def save_full_config(self, key, val):
        self.config_data[key] = val
        cfg_path = get_safe_config_path()
        try:
            if os.path.exists(cfg_path):
                try:
                    os.chmod(cfg_path, stat.S_IWRITE | stat.S_IREAD)
                except Exception:
                    pass
            with open(cfg_path, "w") as f:
                json.dump(self.config_data, f, indent=4)
        except Exception as e:
            print(f"[CONFIG ERROR] {e}")

    def register_hotkeys(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass

        keyboard.add_hotkey(self.key_start, self.toggle_macro)
        keyboard.add_hotkey(self.key_stop, self.emergency_stop)
        keyboard.add_hotkey("f5", self.calibrate_and_capture_map)
        print(f"[CORPSULE] ⌨️ Hotkeys Active: Start [{self.key_start.upper()}], Emergency [{self.key_stop.upper()}], Set Pos [{self.key_setpos.upper()}], Calibrate [F5]")

    def calibrate_and_capture_map(self):
        def _async_calibrate():
            print("\n[CORPSULE] 📸 Executing Camera Calibration & Auto-Capturing Map Preview...")
            
            Actions.reposition_camera_clean()
            time.sleep(0.5)

            full_screen = self.vision.get_screenshot()
            win_x, win_y, win_w, win_h = Actions.get_roblox_rect()
            h_screen, w_screen, _ = full_screen.shape

            x1 = max(0, min(win_x, w_screen))
            y1 = max(0, min(win_y, h_screen))
            x2 = max(x1, min(win_x + win_w, w_screen))
            y2 = max(y1, min(win_y + win_h, h_screen))

            roblox_crop = full_screen[y1:y2, x1:x2]

            if roblox_crop.shape[0] > 0 and roblox_crop.shape[1] > 0:
                target_path = get_map_preview_path()
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                cv2.imwrite(target_path, roblox_crop)
                print(f"[CORPSULE] 🖼️ Saved map preview! Click 'Set Pos' to view overlay.")
            else:
                print("[CORPSULE ERROR] ❌ Could not crop Roblox window for preview!")

        threading.Thread(target=_async_calibrate, daemon=True).start()

    def on_window_move(self, event):
        try:
            snap_roblox_side_by_side(self.winfo_x(), self.winfo_y())
        except Exception:
            pass

    def snap_roblox(self):
        snap_roblox_side_by_side(self.winfo_x(), self.winfo_y())

    def build_corpsule_layout(self):
        self.configure(fg_color=self.theme["bg"])

        self.main_frame = ctk.CTkFrame(self, fg_color=self.theme["card"], border_color=self.theme["border"], border_width=2)
        self.main_frame.pack(padx=12, pady=12, fill="both", expand=True)

        header_box = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        header_box.pack(fill="x", pady=(10, 2), padx=15)

        self.title_lbl = ctk.CTkLabel(header_box, text=f"🔮 CORPSULE v{CURRENT_VERSION}", font=ctk.CTkFont(size=20, weight="bold"), text_color=self.theme["text"])
        self.title_lbl.pack(side="left")

        self.status_badge = ctk.CTkLabel(
            header_box, text=" IDLE ", font=ctk.CTkFont(size=11, weight="bold"),
            fg_color="#3F3F46", corner_radius=6, text_color="#FFFFFF"
        )
        self.status_badge.pack(side="right")

        self.lbl_s = ctk.CTkLabel(self.main_frame, text="Stage Statistics:", font=ctk.CTkFont(size=15, weight="bold"), text_color=self.theme["text"])
        self.lbl_s.pack(pady=(8, 2), padx=15, anchor="w")

        self.lbl_runtime = ctk.CTkLabel(self.main_frame, text="Runtime: 00:00:00", font=ctk.CTkFont(size=13, weight="bold"))
        self.lbl_runtime.pack(anchor="w", padx=20, pady=1)

        self.lbl_wins = ctk.CTkLabel(self.main_frame, text="Wins: 0", font=ctk.CTkFont(size=13))
        self.lbl_wins.pack(anchor="w", padx=20, pady=1)

        self.lbl_runs = ctk.CTkLabel(self.main_frame, text="Total Runs: 0", font=ctk.CTkFont(size=13))
        self.lbl_runs.pack(anchor="w", padx=20, pady=1)

        self.lbl_winrate = ctk.CTkLabel(self.main_frame, text="Win Rate: 0%", font=ctk.CTkFont(size=13))
        self.lbl_winrate.pack(anchor="w", padx=20, pady=1)

        self.sep1 = ctk.CTkFrame(self.main_frame, height=2, fg_color=self.theme["border"])
        self.sep1.pack(pady=8, fill="x", padx=15)

        self.lbl_info = ctk.CTkLabel(self.main_frame, text="Current Stage Info:", font=ctk.CTkFont(size=14, weight="bold"), text_color=self.theme["text"])
        self.lbl_info.pack(anchor="w", padx=15, pady=2)

        self.lbl_mode_status = ctk.CTkLabel(
            self.main_frame, text=f"Mode: {self.selected_map} ({self.selected_diff})", font=ctk.CTkFont(size=12, weight="bold"), text_color="gray"
        )
        self.lbl_mode_status.pack(anchor="w", padx=20, pady=2)

        btn_frame1 = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_frame1.pack(pady=6, padx=15, fill="x")

        self.btn_units = ctk.CTkButton(
            btn_frame1, text="Unit Placements", fg_color=self.theme["accent"], hover_color=self.theme["hover"],
            font=ctk.CTkFont(weight="bold"), width=175, command=self.open_unit_config
        )
        self.btn_units.pack(side="left", padx=3)

        self.btn_select_mode = ctk.CTkButton(
            btn_frame1, text="Select Mode", fg_color=self.theme["accent"], hover_color=self.theme["hover"],
            font=ctk.CTkFont(weight="bold"), width=175, command=self.open_mode_selector
        )
        self.btn_select_mode.pack(side="right", padx=3)

        btn_import = ctk.CTkButton(
            self.main_frame, text="📥 Import Config (.txt / .json)", fg_color=self.theme["accent"], hover_color=self.theme["hover"],
            font=ctk.CTkFont(weight="bold"), command=self.import_config_file
        )
        btn_import.pack(pady=3, padx=18, fill="x")

        btn_snap = ctk.CTkButton(
            self.main_frame, text="📌 Snap Roblox to Left", fg_color="#3B82F6", hover_color="#1D4ED8",
            font=ctk.CTkFont(weight="bold"), command=self.snap_roblox
        )
        btn_snap.pack(pady=3, padx=18, fill="x")

        self.sep2 = ctk.CTkFrame(self.main_frame, height=2, fg_color=self.theme["border"])
        self.sep2.pack(pady=8, fill="x", padx=15)

        kb_lbl = ctk.CTkLabel(self.main_frame, text="Keybinds:", font=ctk.CTkFont(size=13, weight="bold"), text_color="gray")
        kb_lbl.pack(anchor="w", padx=15, pady=1)

        self.lbl_kb_start = ctk.CTkLabel(self.main_frame, text=f"{self.key_start.upper()} - Start / Stop Macro", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.theme["text"])
        self.lbl_kb_start.pack(anchor="w", padx=20, pady=1)

        self.lbl_kb_stop = ctk.CTkLabel(self.main_frame, text=f"{self.key_stop.upper()} - Emergency Stop", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.theme["text"])
        self.lbl_kb_stop.pack(anchor="w", padx=20, pady=1)

        self.lbl_kb_set = ctk.CTkLabel(self.main_frame, text=f"{self.key_setpos.upper()} - Set Hover Coordinates", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.theme["text"])
        self.lbl_kb_set.pack(anchor="w", padx=20, pady=1)

        self.lbl_kb_calib = ctk.CTkLabel(self.main_frame, text="F5 - Calibrate Camera & Capture Map", font=ctk.CTkFont(size=11, weight="bold"), text_color=self.theme["text"])
        self.lbl_kb_calib.pack(anchor="w", padx=20, pady=1)

        bottom_panel = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        bottom_panel.pack(pady=8, padx=15, fill="both", expand=True)

        self.p_lbl = ctk.CTkLabel(bottom_panel, text="Process Log:", font=ctk.CTkFont(size=12, weight="bold"), text_color=self.theme["accent"])
        self.p_lbl.pack(anchor="w", pady=(2, 0))

        self.console_box = ctk.CTkTextbox(bottom_panel, height=65, font=ctk.CTkFont(family="Consolas", size=10), fg_color="#000000", text_color="#C084FC")
        self.console_box.pack(pady=2, fill="both", expand=True)
        self.console_box.configure(state="disabled")

        btn_bar = ctk.CTkFrame(bottom_panel, fg_color="transparent")
        btn_bar.pack(pady=4, fill="x")

        self.btn_settings = ctk.CTkButton(
            btn_bar, text="Settings & Keybinds", fg_color=self.theme["accent"], hover_color=self.theme["hover"],
            font=ctk.CTkFont(size=11, weight="bold"), width=120, height=32, command=self.open_settings_popup
        )
        self.btn_settings.pack(side="left", padx=2)

        self.btn_update = ctk.CTkButton(
            btn_bar, text="✨ Check Updates", fg_color="#8B5CF6", hover_color="#7C3AED",
            font=ctk.CTkFont(size=11, weight="bold"), width=120, height=32, command=self.check_for_updates
        )
        self.btn_update.pack(side="left", padx=2)

        btn_discord = ctk.CTkButton(
            btn_bar, text="💬 Discord", fg_color="#5865F2", hover_color="#4752C4",
            font=ctk.CTkFont(size=11, weight="bold"), width=110, height=32, command=lambda: webbrowser.open("https://discord.gg")
        )
        btn_discord.pack(side="right", padx=2)

    def check_for_updates(self):
        def _async_update_check():
            print(f"\n[UPDATER] 🔍 Checking for updates... (Current Version: v{CURRENT_VERSION})")
            try:
                cache_bypass_url = f"{UPDATE_CHECK_URL}?t={int(time.time())}"
                req = urllib.request.Request(
                    cache_bypass_url, 
                    headers={'User-Agent': 'Mozilla/5.0', 'Cache-Control': 'no-cache', 'Pragma': 'no-cache'}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    data = json.loads(resp.read().decode('utf-8'))
                    latest_v = data.get("version", CURRENT_VERSION)
                    dl_url = data.get("download_url", "")
                    exe_url = data.get("exe_url", dl_url)
                    changelog = data.get("changelog", "Performance fixes and improvements.")

                    if latest_v != CURRENT_VERSION:
                        print(f"[UPDATER] 🎉 NEW UPDATE AVAILABLE: v{latest_v}!")
                        self.after(0, lambda: self.prompt_update_dialog(latest_v, dl_url, exe_url, changelog))
                    else:
                        print(f"[UPDATER] ✅ You are using the latest version (v{CURRENT_VERSION})!")
            except Exception as e:
                print(f"[UPDATER ERROR] Could not reach update server: {e}")

        threading.Thread(target=_async_update_check, daemon=True).start()

    def prompt_update_dialog(self, latest_v, dl_url, exe_url, changelog):
        win = ctk.CTkToplevel(self)
        win.title("Update Available!")
        win.geometry("380x280")
        win.attributes("-topmost", True)

        ctk.CTkLabel(win, text=f"🎉 Update v{latest_v} Available!", font=ctk.CTkFont(size=16, weight="bold"), text_color="#10B981").pack(pady=(15, 5))
        ctk.CTkLabel(win, text=f"Changelog:\n{changelog}", font=ctk.CTkFont(size=12), wraplength=340).pack(pady=10)

        def start_update():
            win.destroy()
            target_url = exe_url if getattr(sys, 'frozen', False) else dl_url
            print(f"[UPDATER] 🚀 Downloading update v{latest_v}...")
            self.perform_auto_update(target_url)

        ctk.CTkButton(win, text="🚀 Update Now", fg_color="#10B981", hover_color="#059669", command=start_update).pack(pady=15)

    def perform_auto_update(self, target_url):
        def _async_download():
            try:
                app_dir = get_app_dir()
                if getattr(sys, 'frozen', False):
                    # Executable update handler
                    target_exe = sys.executable
                    new_exe = target_exe + ".new"
                    
                    urllib.request.urlretrieve(target_url, new_exe)

                    bat_path = os.path.join(app_dir, "update.bat")
                    with open(bat_path, "w") as f:
                        f.write(
                            '@echo off\n'
                            'timeout /t 4 /nobreak > nul\n'  # 4s delay guarantees PyInstaller DLL temp locks release completely!
                            f'move /y "{new_exe}" "{target_exe}"\n'
                            f'start "" "{target_exe}"\n'
                            'del "%~f0"\n'
                        )

                    subprocess.Popen([bat_path], shell=True)
                    self.after(0, self.quit_app)
                else:
                    # Python script update handler
                    target_py = os.path.abspath(__file__)
                    new_py = target_py + ".new"
                    urllib.request.urlretrieve(target_url, new_py)

                    os.replace(new_py, target_py)
                    print("[UPDATER] ✅ Macro updated successfully! Relaunching...")
                    
                    subprocess.Popen([sys.executable, target_py])
                    self.after(0, self.quit_app)
            except Exception as e:
                print(f"[UPDATER ERROR] Could not complete update: {e}")

        threading.Thread(target=_async_download, daemon=True).start()

    def quit_app(self):
        try:
            keyboard.unhook_all_hotkeys()
        except Exception:
            pass
        self.destroy()
        os._exit(0)

    def import_config_file(self):
        file_path = filedialog.askopenfilename(
            title="Select Unit Placement Config File",
            filetypes=[("Config Files", "*.txt *.json"), ("All Files", "*.*")]
        )
        if file_path:
            try:
                with open(file_path, "r") as f:
                    content = f.read().strip()

                positions = []
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and "unit_positions" in data:
                        positions = data["unit_positions"]
                    elif isinstance(data, list):
                        positions = data
                except Exception:
                    lines = content.splitlines()
                    for line in lines:
                        parts = [p.strip() for p in line.split(",") if p.strip()]
                        if len(parts) >= 3:
                            s = int(parts[0])
                            x = int(parts[1])
                            y = int(parts[2])
                            u = int(parts[3]) if len(parts) >= 4 else 0
                            positions.append({"slot": s, "x": x, "y": y, "upgrades": u})

                if len(positions) > 0:
                    self.save_full_config("unit_positions", positions)
                    print(f"[CONFIG] 📥 Successfully imported {len(positions)} unit placements!")
                else:
                    print("[CONFIG ERROR] ⚠️ Unrecognized file structure!")
            except Exception as e:
                print(f"[CONFIG ERROR] Could not import config: {e}")

    def apply_theme_colors(self, theme_name):
        self.theme_name = theme_name
        self.theme = THEMES[theme_name]
        self.save_full_config("theme", theme_name)

        self.configure(fg_color=self.theme["bg"])
        self.main_frame.configure(fg_color=self.theme["card"], border_color=self.theme["border"])
        self.title_lbl.configure(text_color=self.theme["text"])
        self.lbl_s.configure(text_color=self.theme["text"])
        self.lbl_info.configure(text_color=self.theme["text"])
        self.sep1.configure(fg_color=self.theme["border"])
        self.sep2.configure(fg_color=self.theme["border"])

        self.lbl_kb_start.configure(text_color=self.theme["text"])
        self.lbl_kb_stop.configure(text_color=self.theme["text"])
        self.lbl_kb_set.configure(text_color=self.theme["text"])
        self.lbl_kb_calib.configure(text_color=self.theme["text"])
        self.p_lbl.configure(text_color=self.theme["accent"])

        self.btn_units.configure(fg_color=self.theme["accent"], hover_color=self.theme["hover"])
        self.btn_select_mode.configure(fg_color=self.theme["accent"], hover_color=self.theme["hover"])
        self.btn_settings.configure(fg_color=self.theme["accent"], hover_color=self.theme["hover"])
        print(f"[CORPSULE] 🎨 Dynamic Theme Applied: '{theme_name}'")

    def open_mode_selector(self):
        win = ctk.CTkToplevel(self)
        win.title("Select Game Mode & Map")
        win.geometry("380x280")
        win.attributes("-topmost", True)

        lbl = ctk.CTkLabel(win, text="Select Map & Difficulty:", font=ctk.CTkFont(size=15, weight="bold"))
        lbl.pack(pady=15)

        m_drop = ctk.CTkOptionMenu(win, values=["School Grounds", "Flower Forest", "Rose Kingdom"], width=220)
        m_drop.set(self.selected_map)
        m_drop.pack(pady=8)

        d_drop = ctk.CTkOptionMenu(win, values=["Difficulty 3", "Difficulty 2", "Difficulty 1"], width=220)
        d_drop.set(self.selected_diff)
        d_drop.pack(pady=8)

        def save_mode():
            self.selected_map = m_drop.get()
            self.selected_diff = d_drop.get()
            self.lbl_mode_status.configure(text=f"Mode: {self.selected_map} ({self.selected_diff})")
            print(f"[CONFIG] Updated Mode: {self.selected_map} - {self.selected_diff}")
            win.destroy()

        btn_save = ctk.CTkButton(win, text="Save Mode", fg_color="#10B981", command=save_mode)
        btn_save.pack(pady=15)

    def open_settings_popup(self):
        win = ctk.CTkToplevel(self)
        win.title("Corpsule Settings & Keybinds")
        win.geometry("440x440")
        win.attributes("-topmost", True)

        lbl_t = ctk.CTkLabel(win, text="🎨 UI Color Theme:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_t.pack(pady=(12, 2))

        theme_drop = ctk.CTkOptionMenu(win, values=list(THEMES.keys()), command=self.apply_theme_colors)
        theme_drop.set(self.theme_name)
        theme_drop.pack(pady=4)

        lbl_k = ctk.CTkLabel(win, text="⌨️ Custom Keybinds:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_k.pack(pady=(12, 2))

        k_frame = ctk.CTkFrame(win, fg_color="transparent")
        k_frame.pack(pady=4)

        ctk.CTkLabel(k_frame, text="Start/Stop:").grid(row=0, column=0, padx=5, pady=3, sticky="e")
        e_start = ctk.CTkEntry(k_frame, width=80)
        e_start.insert(0, self.key_start)
        e_start.grid(row=0, column=1, padx=5, pady=3)

        ctk.CTkLabel(k_frame, text="Emergency Stop:").grid(row=1, column=0, padx=5, pady=3, sticky="e")
        e_stop = ctk.CTkEntry(k_frame, width=80)
        e_stop.insert(0, self.key_stop)
        e_stop.grid(row=1, column=1, padx=5, pady=3)

        ctk.CTkLabel(k_frame, text="Set Pos Hotkey:").grid(row=2, column=0, padx=5, pady=3, sticky="e")
        e_set = ctk.CTkEntry(k_frame, width=80)
        e_set.insert(0, self.key_setpos)
        e_set.grid(row=2, column=1, padx=5, pady=3)

        lbl_wh = ctk.CTkLabel(win, text="📢 Discord Webhook URL:", font=ctk.CTkFont(size=13, weight="bold"))
        lbl_wh.pack(pady=(12, 2))

        wh_entry = ctk.CTkEntry(win, width=360, placeholder_text="Paste Discord Webhook URL...")
        wh_entry.insert(0, self.webhook_url)
        wh_entry.pack(pady=4)

        def save_all_settings():
            self.key_start = e_start.get().strip().lower()
            self.key_stop = e_stop.get().strip().lower()
            self.key_setpos = e_set.get().strip().lower()
            self.webhook_url = wh_entry.get().strip()

            self.save_full_config("key_start", self.key_start)
            self.save_full_config("key_stop", self.key_stop)
            self.save_full_config("key_setpos", self.key_setpos)
            self.save_full_config("webhook_url", self.webhook_url)

            self.register_hotkeys()

            self.lbl_kb_start.configure(text=f"{self.key_start.upper()} - Start / Stop Macro")
            self.lbl_kb_stop.configure(text=f"{self.key_stop.upper()} - Emergency Stop")
            self.lbl_kb_set.configure(text=f"{self.key_setpos.upper()} - Set Hover Coordinates")

            win.destroy()

        btn_save = ctk.CTkButton(win, text="💾 Save All Settings", fg_color="#10B981", command=save_all_settings)
        btn_save.pack(pady=15)

    def open_unit_config(self):
        PlacementConfigWindow(self)

    def increment_runs(self):
        self.total_runs += 1
        self.update_stats()

    def increment_wins(self):
        self.total_wins += 1
        self.total_runs = max(self.total_runs, self.total_wins)
        self.update_stats()
        if self.webhook_url:
            runtime_str = self.lbl_runtime.cget("text").replace("Runtime: ", "")
            wr = (self.total_wins / self.total_runs * 100) if self.total_runs > 0 else 100.0
            DiscordWebhook.send_victory_notification(
                self.webhook_url, self.selected_map, self.total_wins, self.total_runs, min(100.0, wr), runtime_str
            )

    def update_stats(self):
        self.lbl_runs.configure(text=f"Total Runs: {self.total_runs}")
        self.lbl_wins.configure(text=f"Wins: {self.total_wins}")
        wr = (self.total_wins / self.total_runs * 100) if self.total_runs > 0 else 0
        self.lbl_winrate.configure(text=f"Win Rate: {min(100.0, wr):.1f}%")

    def update_timer(self):
        if self.is_running and self.start_time:
            elapsed = int(time.time() - self.start_time)
            hrs, mins, secs = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.lbl_runtime.configure(text=f"Runtime: {hrs:02d}:{mins:02d}:{secs:02d}")
            self.after(1000, self.update_timer)

    def emergency_stop(self):
        if self.is_running:
            print("\n[CORPSULE] 🚨 EMERGENCY STOP TRIGGERED! 🚨")
            self.stop_macro()

    def toggle_macro(self):
        if not self.is_running:
            self.start_macro()
        else:
            self.stop_macro()

    def start_macro(self):
        self.is_running = True
        self.start_time = time.time()
        self.status_badge.configure(text=" RUNNING ", fg_color="#10B981")
        self.update_timer()
        self.snap_roblox()
        threading.Thread(target=self.macro_loop, daemon=True).start()

    def stop_macro(self):
        self.is_running = False
        self.status_badge.configure(text=" IDLE ", fg_color="#3F3F46")
        print("[CORPSULE] Macro Stopped.")

    def macro_loop(self):
        from games.anime_expeditions import AnimeExpeditions
        print("[CORPSULE] Macro Active!")
        
        settings = {
            "auto_replay": True,
            "auto_place": True,
            "selected_map": self.selected_map,
            "selected_difficulty": self.selected_diff
        }
        
        game_engine = AnimeExpeditions(settings, app_ref=self)
        
        while self.is_running:
            game_engine.update_settings({
                "auto_replay": True,
                "auto_place": True,
                "selected_map": self.selected_map,
                "selected_difficulty": self.selected_diff
            })
            game_engine.run_cycle()
            time.sleep(1.0)


class MapPreviewGuide(ctk.CTkToplevel):
    def __init__(self, parent, row_index, on_capture_callback, set_pos_key="f7"):
        super().__init__(parent)
        self.row_index = row_index
        self.on_capture_callback = on_capture_callback
        self.set_pos_key = set_pos_key.lower().strip()
        self.hotkey_handle = None

        roblox_hwnd = Actions.get_roblox_hwnd()
        if roblox_hwnd:
            rect = ctypes.wintypes.RECT()
            user32.GetWindowRect(roblox_hwnd, ctypes.byref(rect))
            win_x = rect.left
            win_y = rect.top
            win_w = rect.right - rect.left
            win_h = rect.bottom - rect.top
        else:
            win_x, win_y, win_w, win_h = 0, 0, 800, 600

        self.geometry(f"{win_w}x{win_h}+{win_x}+{win_y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.update_idletasks()
        self.overrideredirect(True)

        overlay_frame = ctk.CTkFrame(self, fg_color="#000000", corner_radius=0, width=win_w, height=win_h)
        overlay_frame.pack(fill="both", expand=True)

        map_img_path = get_map_preview_path()
        if os.path.exists(map_img_path):
            try:
                img_pil = Image.open(map_img_path)
                ctk_img = ctk.CTkImage(light_image=img_pil, dark_image=img_pil, size=(win_w, win_h))
                img_lbl = ctk.CTkLabel(overlay_frame, image=ctk_img, text="", corner_radius=0)
                img_lbl.place(x=0, y=0, relwidth=1, relheight=1)
            except Exception as e:
                print(f"[IMAGE ERROR] {e}")

        txt_badge = ctk.CTkLabel(
            overlay_frame, 
            text=f" 📍 SET POSITION #{row_index + 1} — Hover over Roblox & press [{self.set_pos_key.upper()}] ",
            font=ctk.CTkFont(size=13, weight="bold"),
            fg_color="#160A29",
            text_color="#C084FC",
            corner_radius=8
        )
        txt_badge.place(x=15, y=15)

        try:
            self.hotkey_handle = keyboard.add_hotkey(self.set_pos_key, self.trigger_capture, suppress=False)
        except Exception:
            self.hotkey_handle = keyboard.add_hotkey("f7", self.trigger_capture, suppress=False)

        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def trigger_capture(self):
        self.cleanup_hotkey()
        self.on_capture_callback(self.row_index)
        self.destroy()

    def on_close(self):
        self.cleanup_hotkey()
        self.destroy()

    def cleanup_hotkey(self):
        try:
            if self.hotkey_handle is not None:
                keyboard.remove_hotkey(self.hotkey_handle)
                self.hotkey_handle = None
        except Exception:
            pass


class PlacementConfigWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_app = parent
        self.title("Corpsule Unit Placement Config")

        parent_x = parent.winfo_x()
        parent_y = parent.winfo_y()

        self.geometry(f"430x710+{parent_x}+{parent_y}")
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.rows_data = []

        header_frame = ctk.CTkFrame(self)
        header_frame.pack(pady=10, padx=12, fill="x")

        labels = ["#", "Slot", "Rel X", "Rel Y", "Set Pos", "Upgrades", "+/-"]
        widths = [20, 35, 45, 45, 65, 60, 55]
        for i, (text, w) in enumerate(zip(labels, widths)):
            lbl = ctk.CTkLabel(header_frame, text=text, font=ctk.CTkFont(size=10, weight="bold"), width=w)
            lbl.grid(row=0, column=i, padx=1, pady=3)

        self.scroll_frame = ctk.CTkScrollableFrame(self, height=520)
        self.scroll_frame.pack(pady=4, padx=12, fill="both", expand=True)

        saved_rows = self.load_config()
        if saved_rows:
            for row in saved_rows:
                self.add_row(row["slot"], row["x"], row["y"], row.get("upgrades", 0))

        btn_box = ctk.CTkFrame(self, fg_color="transparent")
        btn_box.pack(pady=10, padx=12, fill="x")

        save_btn = ctk.CTkButton(
            btn_box, text="💾 Save Sequence", fg_color="#10B981", hover_color="#059669",
            font=ctk.CTkFont(size=12, weight="bold"), width=195, command=self.save_config
        )
        save_btn.pack(side="left", padx=2)

        export_btn = ctk.CTkButton(
            btn_box, text="📤 Export Config (.txt)", fg_color="#3B82F6", hover_color="#1D4ED8",
            font=ctk.CTkFont(size=12, weight="bold"), width=195, command=self.export_config_txt
        )
        export_btn.pack(side="right", padx=2)

    def add_row(self, slot=1, x=0, y=0, upgrades=0):
        row_idx = len(self.rows_data) + 1
        lbl_num = ctk.CTkLabel(self.scroll_frame, text=str(row_idx), width=20, font=ctk.CTkFont(weight="bold"))
        entry_slot = ctk.CTkEntry(self.scroll_frame, width=35)
        entry_slot.insert(0, str(slot))

        entry_x = ctk.CTkEntry(self.scroll_frame, width=45)
        entry_x.insert(0, str(x))

        entry_y = ctk.CTkEntry(self.scroll_frame, width=45)
        entry_y.insert(0, str(y))

        btn_set_pos = ctk.CTkButton(
            self.scroll_frame, text="Set Pos", width=65, fg_color="#3B82F6", hover_color="#1D4ED8",
            command=lambda r=row_idx-1: self.open_map_guide(r)
        )

        combo_upgrade = ctk.CTkOptionMenu(self.scroll_frame, values=[str(i) for i in range(11)], width=60)
        combo_upgrade.set(str(upgrades))

        btn_add = ctk.CTkButton(self.scroll_frame, text="+", width=25, fg_color="#10B981", command=self.add_row)
        btn_del = ctk.CTkButton(self.scroll_frame, text="-", width=25, fg_color="#EF4444", command=lambda r=row_idx-1: self.delete_row(r))

        lbl_num.grid(row=row_idx, column=0, padx=1, pady=3)
        entry_slot.grid(row=row_idx, column=1, padx=1, pady=3)
        entry_x.grid(row=row_idx, column=2, padx=1, pady=3)
        entry_y.grid(row=row_idx, column=3, padx=1, pady=3)
        btn_set_pos.grid(row=row_idx, column=4, padx=1, pady=3)
        combo_upgrade.grid(row=row_idx, column=5, padx=1, pady=3)
        btn_add.grid(row=row_idx, column=6, padx=1, pady=3)
        btn_del.grid(row=row_idx, column=7, padx=1, pady=3)

        self.rows_data.append({
            "num": lbl_num, "slot": entry_slot, "x": entry_x, "y": entry_y,
            "set_btn": btn_set_pos, "upgrade": combo_upgrade, "add_btn": btn_add, "del_btn": btn_del
        })

    def open_map_guide(self, row_index):
        set_key = getattr(self.parent_app, "key_setpos", "f7")
        MapPreviewGuide(self, row_index, self.capture_position_data, set_pos_key=set_key)

    def capture_position_data(self, row_index):
        win_x, win_y, _, _ = Actions.get_roblox_rect()
        global_x, global_y = pyautogui.position()

        rel_x = max(0, min(global_x - win_x, 800))
        rel_y = max(0, min(global_y - win_y, 600))

        try:
            if row_index < len(self.rows_data):
                row = self.rows_data[row_index]
                if row["x"].winfo_exists():
                    row["x"].delete(0, 'end')
                    row["x"].insert(0, str(rel_x))

                if row["y"].winfo_exists():
                    row["y"].delete(0, 'end')
                    row["y"].insert(0, str(rel_y))

                print(f"[CORPSULE] 📍 Recorded Position for Row #{row_index + 1}: Relative ({rel_x}, {rel_y})")
        except Exception as e:
            print(f"[CORPSULE WARNING] Could not update row widget: {e}")

    def delete_row(self, row_index):
        if len(self.rows_data) <= 1:
            return
        for widget in self.rows_data[row_index].values():
            widget.destroy()
        self.rows_data.pop(row_index)

    def export_config_txt(self):
        file_path = filedialog.asksaveasfilename(
            title="Export Unit Placement Config",
            defaultextension=".txt",
            filetypes=[("Text File", "*.txt"), ("JSON File", "*.json")]
        )
        if file_path:
            config_list = []
            for row in self.rows_data:
                try:
                    config_list.append({
                        "slot": int(row["slot"].get()),
                        "x": int(row["x"].get()),
                        "y": int(row["y"].get()),
                        "upgrades": int(row["upgrade"].get())
                    })
                except ValueError:
                    continue
            try:
                with open(file_path, "w") as f:
                    json.dump({"unit_positions": config_list}, f, indent=4)
                print(f"[CONFIG] 📤 Exported placement config!")
            except Exception as e:
                print(f"[CONFIG ERROR] Could not export config: {e}")

    def load_config(self):
        cfg_path = get_safe_config_path()
        if os.path.exists(cfg_path):
            try:
                with open(cfg_path, "r") as f:
                    return json.load(f).get("unit_positions", [
                        {"slot": 1, "x": 400, "y": 300, "upgrades": 0},
                        {"slot": 2, "x": 450, "y": 320, "upgrades": 0},
                        {"slot": 3, "x": 380, "y": 280, "upgrades": 0},
                        {"slot": 4, "x": 420, "y": 350, "upgrades": 0}
                    ])
            except Exception:
                pass
        return [
            {"slot": 1, "x": 400, "y": 300, "upgrades": 0},
            {"slot": 2, "x": 450, "y": 320, "upgrades": 0},
            {"slot": 3, "x": 380, "y": 280, "upgrades": 0},
            {"slot": 4, "x": 420, "y": 350, "upgrades": 0}
        ]

    def save_config(self):
        config_list = []
        for row in self.rows_data:
            try:
                config_list.append({
                    "slot": int(row["slot"].get()),
                    "x": int(row["x"].get()),
                    "y": int(row["y"].get()),
                    "upgrades": int(row["upgrade"].get())
                })
            except ValueError:
                continue
        
        self.parent_app.save_full_config("unit_positions", config_list)
        print("[CORPSULE] ✅ Saved relative placement sequence permanently!")
        self.destroy()


if __name__ == "__main__":
    app = CorpsuleApp()
    app.mainloop()

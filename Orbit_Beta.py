from ursina import *
from ursina import Audio 
from datetime import datetime, timezone, timedelta
import math
import time
import cv2
from PIL import Image
import numpy as np
import random
import os
import traceback

from languages import _, languages, set_language, current_language
from facts import get_country_data, format_number
from accounts import accounts, DEFAULT_AVATAR

import socket
import threading

import requests  
import subprocess  

import random

print("DEBUG: _ type =", type(_))

loading_active = True
load_start_time = 0
load_duration = 7.0
current_progress = 0.0
skip_requested = False
tip_index = 0
last_tip_change = 0
tip_interval = 3
menu_ui_elements = []

local_offset_sec = -time.timezone if time.localtime().tm_isdst == 0 else -time.altzone
current_utc_offset = local_offset_sec // 3600
print(_("msg_time_detection").format(current_utc_offset))

app = Ursina()
window.color = color.black
window.cog_menu.enabled = False
window.fps_counter.enabled = False

main_ambient = Audio('main_ambient.mp3', loop=True, autoplay=False)
pause_menu_audio = Audio('pause_menu.mp3', loop=True, autoplay=False)
zoom_audio = Audio('zoom.mp3', loop=True, autoplay=False)
fade_audio = Audio('fade_in.mp3', loop=False, autoplay=False)

afk_timer = 0
AFK_THRESHOLD = 600

settings_file = 'orbit_settings.txt'
settings = {}

DEFAULT_SETTINGS = {
    'sound_enabled': True,
    'auto_rotate_enabled': False,
    'default_texture_is_earth': True,
    'loading_tips_enabled': True,
}

def save_settings():
    try:
        with open(settings_file, 'w') as f:
            for key, val in settings.items():
                f.write(f"{key}={val}\n")
        print(_("settings_saved"))
    except Exception as e:
        print(_("settings_save_error").format(e))

def generate_room_code():
    return random.randint(1000, 999999999)

def load_settings():
    global settings
    try:
        with open(settings_file, 'r') as f:
            for line in f:
                line = line.strip()
                if '=' in line:
                    key, val = line.split('=', 1)
                    if val.lower() == 'true':
                        settings[key] = True
                    elif val.lower() == 'false':
                        settings[key] = False
                    else:
                        settings[key] = val
        print(_("settings_loaded"))
    except FileNotFoundError:
        print(_("settings_no_file"))
        settings = DEFAULT_SETTINGS.copy()
        save_settings()
    except Exception as e:
        print(_("settings_loading_error").format(e))
        settings = DEFAULT_SETTINGS.copy()

load_settings()

loading_screen = Entity(parent=camera.ui, enabled=False)

loading_bg = Entity(parent=loading_screen, model='quad',
                    scale=(camera.aspect_ratio * 2, 2),
                    color=color.black, z=10)

loading_logo = Entity(parent=loading_screen, model='quad',
                      texture='orbit_logo.jpg',
                      scale=(0.4, 0.4), y=0.2)

progress_bg = Entity(parent=loading_screen, model='quad',
                     color=color.gray,
                     scale=(0.6, 0.03), y=-0.1, z=-1)

progress_fill = Entity(parent=progress_bg, model='quad',
                       color=color.white,
                       scale=(0, 1, 1),
                       x=-0.5, origin=(-0.5, 0),
                       z=-0.5)

skip_button = Button(parent=loading_screen, text=_("skip_intro"),
                     color=color.black,
                     text_color=color.white,
                     scale=(0.15, 0.06),
                     y=-0.2, z=-2,
                     enabled=False, visible=False)

loading_tips = Text(parent=loading_screen, text='',
                    y=-0.35, scale=0.9,
                    color=color.light_gray,
                    origin=(0.5, 0.5))
tips = [
    _("tip_0"),
    _("tip_1"),
    _("tip_2"),
    _("tip_3")
]

loading_text = Text(parent=loading_screen, text=_("loading"),
                    y=0.05, scale=1.2,
                    color=color.white,
                    origin=(0.5, 0.5))

earth = Entity(model='sphere', texture='earth_texture.jpg', scale=3)
camera.position = (0, 0, -10)

loading_screen.enabled = True
earth.enabled = False
load_start_time = time.time()

fade_overlay = Entity(
    model='quad',
    color=color.black,
    scale=(camera.aspect_ratio * 2, 2),
    parent=camera.ui,
    z=-999,
    alpha=0,
    eternal=True
)

def fade_in(duration=0.4):
    fade_overlay.enabled = True
    fade_overlay.visible = True
    fade_overlay.alpha = 0
    fade_overlay.animate('alpha', 1.0, duration=duration, curve=curve.linear)
    if not fade_audio.playing:
        fade_audio.play()
    print(_("fade_in").format(duration))

def fade_out(duration=0.4):
    fade_overlay.alpha = 1
    fade_overlay.animate('alpha', 0.0, duration=duration, curve=curve.linear)
    if not fade_audio.playing:
        fade_audio.play()
    invoke(lambda: setattr(fade_overlay, 'enabled', False), delay=duration+0.1)
    print(_("fade_out").format(duration))

def dummy_click():
    pass

def teleport_to_country(country_name):
    dot = None
    ray_dir = None
    for d in dots:
        if d.name == country_name:
            dot = d
            break
    for name, rd in ray_directions:
        if name == country_name:
            ray_dir = rd
            break
    
    if dot and ray_dir:
        surface_point = dot.world_position
        distance = 10
        cam_target = surface_point + ray_dir * distance
        camera.position = cam_target
        camera.look_at(surface_point)
        camera.rotation_z = 0
        print(_("msg_teleported").format(country_name))

def skip_loading():
    global skip_requested
    skip_requested = True
    skip_button.enabled = False
    skip_button.color = color.gray

skip_button.on_click = skip_loading

def finish_loading():
    global loading_active
    loading_active = False
    
    loading_logo.animate_scale(0.6, duration=0.6, curve=curve.out_expo)
    loading_logo.animate('alpha', 0, duration=0.6)
    progress_bg.animate_scale_x(0, duration=0.5)
    progress_bg.animate('alpha', 0, duration=0.5)
    loading_tips.animate('alpha', 0, duration=0.5)
    loading_text.animate('alpha', 0, duration=0.5)
    if skip_button.enabled:
        skip_button.animate('alpha', 0, duration=0.4)
    
    invoke(switch_to_main, delay=0.9)

def trigger_1983_jumpscare():
    print(_("easter_1983_trigger"))
    
    global typing_active, search_field, suggestions_panel, suggestions
    typing_active = False
    if search_field:
        search_field.text = ''
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()
    
    for child in list(camera.ui.children):
        child.enabled = False
    earth.enabled = False
    
    black_bg = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black,
        scale=(camera.aspect_ratio * 2, 2),
        z=50
    )
    
    try:
        gf = Entity(
            parent=camera.ui,
            model='quad',
            texture='gf_jumpscare.jpg',
            scale=(camera.aspect_ratio * 2, 2),
            z=60
        )
        print("✅ Golden Freddy image loaded")
    except Exception as e:
        print(f"❌ Could not load image: {e}")
        Text(
            parent=camera.ui,
            text=_("easter_1983_fallback"),
            position=(0, 0),
            scale=15,
            color=color.red,
            z=60
        )
    
    try:
        scream = Audio('gf_jumpscare.mp3', autoplay=True, volume=2.0)
        print(_("audio_scream"))
    except Exception as e:
        print(f"❌ Could not play audio: {e}")
    
    camera.shake(duration=1.0, magnitude=0.7)
    
    def flicker():
        black_bg.color = color.red
        invoke(lambda: setattr(black_bg, 'color', color.black), delay=0.05)
        invoke(flicker, delay=0.1)
    
    invoke(flicker, delay=0.3)
    
    print(_("crash_message"))
    invoke(application.quit, delay=1.8)

def trigger_sans_easter_egg():
    print(_("easter_sans_trigger"))
    
    global typing_active, search_field, suggestions_panel, suggestions
    typing_active = False
    if search_field:
        search_field.text = ''
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()
    
    original_color = earth.color
    earth.color = color.blue
    earth.animate_color(color.azure, duration=1.0)
    
    print(_("easter_sans_message_console"))
    
    message = Text(
        parent=camera.ui,
        text=_("easter_sans_message"),
        position=(0, 0),
        scale=3,
        color=color.white,
        background=True,
        background_color=Color(0,0,0,0.66),
        z=50
    )
    message.animate_scale(3.5, duration=0.3, curve=curve.out_back)
    destroy(message, delay=3.0)
    
    try:
        Audio('sans_sound.mp3', autoplay=True)
    except:
        try:
            Audio('zoom.mp3', pitch=0.5, autoplay=True)
        except:
            pass
    
    invoke(lambda: setattr(earth, 'color', original_color), delay=5.0)
    invoke(lambda: earth.animate_color(color.white, duration=1.0), delay=5.0)

def trigger_1961_gagarin_egg():
    print(_("easter_1961_trigger"))
    
    global typing_active, search_field, suggestions_panel, suggestions
    typing_active = False
    if search_field:
        search_field.text = ''
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()
    
    original_color = earth.color
    original_camera_z = camera.z
    
    earth.color = color.brown.tint(0.3)
    
    try:
        gagarin_audio = Audio('gagarin_poehali.mp3', autoplay=True, volume=1.5)
        print(_("audio_gagarin"))
    except:
        try:
            Audio('rocket_launch.mp3', autoplay=True, volume=1.5)
            print(_("audio_rocket"))
        except:
            pass
    
    panel = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0,0,0,0.66),
        scale=(0.7, 0.5),
        position=(0, 0),
        z=50
    )
    
    Text(parent=panel, text=_("easter_1961_title"),
         position=(0, 0.15), scale=2.5, color=color.gold)
    
    Text(parent=panel, 
         text=_("easter_1961_text"),
         position=(0, -0.05), scale=1.2, color=color.white)
    
    star = Entity(parent=panel, model='circle',
                  color=color.red, scale=(0.1, 0.1),
                  position=(0, 0.3), rotation=(0, 0, 45))
    
    camera.animate_z(-25, duration=13.0, curve=curve.out_expo)
    
    def create_particles():
        for i in range(5):
            particle = Entity(
                parent=earth,
                model='sphere',
                color=color.orange,
                scale=0.02,
                position=(0, -0.5, 0),
                unlit=True
            )
            particle.animate_position(
                (random.uniform(-0.5, 0.5), random.uniform(3, 6), random.uniform(-0.5, 0.5)),
                duration=random.uniform(2.0, 4.0),
                curve=curve.linear
            )
            destroy(particle, delay=4.0)
    
    for t in range(0, 8):
        invoke(create_particles, delay=1.0 + t*0.3)
    
    invoke(lambda: destroy(panel), delay=14.0)
    invoke(lambda: destroy(star), delay=14.0)
    invoke(lambda: setattr(earth, 'color', original_color), delay=14.0)
    invoke(lambda: camera.animate_z(original_camera_z, duration=3.0), delay=14.0)
    
    print(_("easter_1961_duration"))

def trigger_orbit_secret_egg():
    print(_("easter_orbit_trigger"))
    
    global typing_active, search_field, suggestions_panel, suggestions
    typing_active = False
    if search_field:
        search_field.text = ''
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()
    
    original_color = earth.color
    earth.color = color.blue.tint(-0.4)
    
    try:
        space_audio = Audio('space_ambient.mp3', autoplay=True, loop=True, volume=0.7)
        print("🔊 Playing space ambient")
    except:
        try:
            Audio('main_ambient.mp3', pitch=0.6, autoplay=True, volume=0.5)
        except:
            pass
    
    leo_ring = Entity(
        parent=earth,
        model='circle',
        color=color.cyan,
        scale=1.5,
        double_sided=True,
        alpha=0.3,
        thickness=2
    )
    leo_ring.rotation_x = 45
    
    geo_ring = Entity(
        parent=earth,
        model='circle',
        color=color.green,
        scale=3.2,
        double_sided=True,
        alpha=0.2,
        thickness=2
    )
    
    satellites = []
    satellite_colors = [color.white, color.yellow, color.orange, color.red]
    
    for i in range(6):
        sat = Entity(
            parent=earth,
            model='cube',
            color=random.choice(satellite_colors),
            scale=0.04,
            position=(
                random.uniform(-1.2, 1.2),
                random.uniform(-0.8, 0.8),
                random.uniform(-1.2, 1.2)
            ),
            unlit=True
        )
        satellites.append(sat)
    
    panel = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0,0,0,0.66),
        scale=(0.8, 0.6),
        position=(0, 0),
        z=50
    )
    
    Text(
        parent=panel,
        text=_("easter_orbit_title"),
        position=(0, 0.22),
        scale=2.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    Text(
        parent=panel,
        text=_("easter_orbit_text"),
        position=(0, -0.02),
        scale=0.9,
        color=color.white,
        origin=(0.5, 0.5)
    )
    
    Text(
        parent=panel,
        text=_("easter_orbit_signature"),
        position=(0, -0.25),
        scale=1.2,
        color=color.gold,
        origin=(0.5, 0.5)
    )
    
    earth.animate_rotation((0, 180, 0), duration=30.0, curve=curve.linear)
    leo_ring.animate_rotation((0, 0, 360), duration=40.0, curve=curve.linear)
    geo_ring.animate_rotation((360, 0, 0), duration=50.0, curve=curve.linear)
    
    for i, sat in enumerate(satellites):
        sat.animate_rotation(
            (random.uniform(100, 360), random.uniform(100, 360), random.uniform(100, 360)),
            duration=15.0 + i*3,
            curve=curve.linear
        )
    
    camera.animate_position((8, 4, -12), duration=25.0)
    invoke(lambda: camera.look_at((0, 0, 0)), delay=0.5)
    
    def cleanup_orbit_egg():
        print(_("easter_orbit_cleanup"))
        destroy(leo_ring)
        destroy(geo_ring)
        for sat in satellites:
            destroy(sat)
        destroy(panel)
        earth.color = original_color
        earth.rotation = (0, 0, 0)
        camera.animate_position((0, 0, -10), duration=3.0)
        camera.animate_rotation((0, 0, 0), duration=3.0)
        if 'space_audio' in locals():
            space_audio.stop()
        print("✅ Orbit secret complete")
    
    invoke(cleanup_orbit_egg, delay=25.0)

def show_country_facts(country_name):
    from facts import get_country_data, format_number
    
    data = get_country_data(country_name)
    if not data:
        return
    
    title = Text(
        parent=camera.ui,
        text=f"📍 {country_name}",
        position=(0.5, 0.3),
        scale=2,
        color=color.white,
        origin=(0.5, 0.5),
        z=40
    )
    
    y = 0.25
    facts = [
        f"Capital: {data['capital']}",
        f"Population: {format_number(data['population'])}",
        f"Area: {format_number(data['area'])} km²",
        f"Languages: {', '.join(data['languages'][:2])}",
        f"Timezone: {data['timezones'][0]}",
        f"Currency: {', '.join(data['currencies'])}",
        f"Region: {data['region']}",
        f"Borders: {len(data['borders'])} countries",
    ]
    
    text_objects = [title]
    
    for fact in facts:
        txt = Text(
            parent=camera.ui,
            text=fact,
            position=(0.5, y),
            scale=1,
            color=color.light_gray,
            origin=(0.5, 0.5),
            z=40
        )
        text_objects.append(txt)
        y -= 0.06
    
    for obj in text_objects:
        destroy(obj, delay=15.0)

def copy_to_clipboard(text):
    import subprocess
    try:
        subprocess.run('clip', input=text.strip().encode('utf-16'), check=True)
        show_message("✅ Copied to clipboard!", color.green)
    except:
        try:
            import pyperclip
            pyperclip.copy(text)
            show_message("✅ Copied!", color.green)
        except:
            show_message("❌ Copy failed", color.red)

def show_controls_panel():
    print(_("controls_panel_open"))
    
    panel = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0,0,0,0.66),
        scale=(0.7, 0.8),
        position=(0, 0),
        z=30
    )
    
    Text(
        parent=panel,
        text=_("controls_title"),
        position=(0, 0.35),
        scale=2.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    controls = [
        _("controls_section_mouse"),
        _("controls_drag"),
        _("controls_m"),
        _("controls_c"),
        _("controls_esc"),
        "",
        _("controls_section_nav"),
        _("controls_arrows"),
        _("controls_type"),
        _("controls_enter"),
        "",
        _("controls_section_features"),
        _("controls_s"),
        _("controls_t"),
        _("controls_h"),
        _("controls_j"),
        "",
        _("controls_section_eggs"),
        _("controls_egg_text")
    ]
    
    for i, line in enumerate(controls):
        y_pos = 0.25 - i * 0.045
        color_val = color.white
        if ':' in line:
            color_val = color.yellow
            y_pos += 0.02
        
        Text(
            parent=panel,
            text=line,
            position=(-0.32, y_pos),
            scale=0.9,
            color=color_val,
            origin=(0, 0.5)
        )
    
    Button(
        parent=panel,
        text=_("close"),
        position=(0, -0.4),
        scale=(0.3, 0.1),
        color=color.dark_gray,
        text_color=color.white,
        highlight_color=color.cyan,
        on_click=lambda: destroy(panel)
    )

def show_language_menu():
    from languages import languages, current_language, set_language
    
    panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black,
        scale=(0.4, 0.6),
        position=(0.2, 0),
        z=30
    )
    
    Text(
        parent=panel,
        text="Select Language",
        position=(0, 0.25),
        scale=1.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    for i, (code, name, _) in enumerate(languages):
        Button(
            parent=panel,
            text=name,
            position=(0, 0.15 - i * 0.08),
            scale=(0.35, 0.06),
            color=color.blue if i == current_language else color.dark_gray,
            text_color=color.white,
            on_click=Func(lambda i=i: set_language(i) or destroy(panel))
        )
    
    Button(
        parent=panel,
        text="Close",
        position=(0.35, 0.28),
        scale=(0.2, 0.06),
        color=color.red,
        text_color=color.white,
        on_click=lambda: destroy(panel)
    )

def close_language_menu(panel, overlay):
    destroy(panel)
    destroy(overlay)

def show_account_menu():
    global current_account_overlay, current_account_panel
    from accounts import accounts, DEFAULT_AVATAR
    
    if current_account_overlay:
        destroy(current_account_overlay)
        current_account_overlay = None
    if current_account_panel:
        destroy(current_account_panel)
        current_account_panel = None
    
    current_account_overlay = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0, 0, 0, 0.66),
        scale=(camera.aspect_ratio * 2, 2),
        z=20
    )
    
    current_account_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black,
        scale=(0.4, 0.6),
        position=(0.3, 0),
        z=30
    )
    
    Text(
        parent=current_account_panel,
        text="Account",
        position=(0, 0.25),
        scale=1.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    if accounts.current_user:
        user_data = accounts.get_current_user_data()
        
        Entity(
            parent=current_account_panel,
            model='quad',
            texture=user_data['avatar'] if user_data else DEFAULT_AVATAR,
            scale=(0.2, 0.2),
            position=(0, 0.1),
            z=-1
        )
        
        Text(
            parent=current_account_panel,
            text=accounts.current_user,
            position=(0, -0.05),
            scale=1.2,
            color=color.white,
            origin=(0.5, 0.5)
        )
        
        if user_data:
            created = user_data['created'].split()[0]
            Text(
                parent=current_account_panel,
                text=f"Joined: {created}",
                position=(0, -0.15),
                scale=0.8,
                color=color.light_gray,
                origin=(0.5, 0.5)
            )
        
        Button(
            parent=current_account_panel,
            text="Log Out",
            position=(0, -0.25),
            scale=(0.25, 0.06),
            color=color.orange,
            text_color=color.white,
            on_click=lambda: logout_and_close()
        )
        
        Button(
            parent=current_account_panel,
            text="Delete",
            position=(0, -0.33),
            scale=(0.25, 0.06),
            color=color.red,
            text_color=color.white,
            on_click=lambda: delete_account()
        )
        
    else:
        Text(
            parent=current_account_panel,
            text="Not logged in",
            position=(0, 0.1),
            scale=1.2,
            color=color.white,
            origin=(0.5, 0.5)
        )
        
        Button(
            parent=current_account_panel,
            text="Login",
            position=(0, -0.05),
            scale=(0.25, 0.06),
            color=color.green,
            text_color=color.white,
            on_click=show_login_ui
        )
        
        Button(
            parent=current_account_panel,
            text="Sign Up",
            position=(0, -0.13),
            scale=(0.25, 0.06),
            color=color.blue,
            text_color=color.white,
            on_click=show_signup_ui
        )
    
    Button(
        parent=current_account_panel,
        text="✕",
        position=(0.35, 0.28),
        scale=(0.04, 0.04),
        color=color.red,
        text_color=color.white,
        on_click=close_account_menu
    )

def close_account_menu():
    global current_account_overlay, current_account_panel
    if current_account_overlay:
        destroy(current_account_overlay)
        current_account_overlay = None
    if current_account_panel:
        destroy(current_account_panel)
        current_account_panel = None

def show_login_ui():
    global current_account_panel
    if current_account_panel:
        destroy(current_account_panel)
        current_account_panel = None
    
    current_account_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black,
        scale=(0.4, 0.4),
        position=(0.3, 0),
        z=30
    )
    
    Text(
        parent=current_account_panel,
        text="Login",
        position=(0, 0.15),
        scale=1.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    username = InputField(
        parent=current_account_panel,
        position=(0, 0.05),
        scale=(0.3, 0.06),
        placeholder="Username"
    )
    
    password = InputField(
        parent=current_account_panel,
        position=(0, -0.03),
        scale=(0.3, 0.06),
        placeholder="Password"
    )
    
    Button(
        parent=current_account_panel,
        text="Login",
        position=(0, -0.12),
        scale=(0.2, 0.06),
        color=color.green,
        on_click=lambda: login(username.text, password.text)
    )
    
    Button(
        parent=current_account_panel,
        text="Back",
        position=(0, -0.2),
        scale=(0.15, 0.05),
        color=color.gray,
        on_click=show_account_menu
    )

def back_to_account_menu(overlay, panel):
    destroy(panel)
    show_account_menu() 

def show_signup_ui():
    global current_account_panel
    if current_account_panel:
        destroy(current_account_panel)
        current_account_panel = None
    
    current_account_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black,
        scale=(0.4, 0.4),
        position=(0.3, 0),
        z=30
    )
    
    Text(
        parent=current_account_panel,
        text="Sign Up",
        position=(0, 0.15),
        scale=1.5,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    username = InputField(
        parent=current_account_panel,
        position=(0, 0.05),
        scale=(0.3, 0.06),
        placeholder="Username"
    )
    
    password = InputField(
        parent=current_account_panel,
        position=(0, -0.03),
        scale=(0.3, 0.06),
        placeholder="Password"
    )
    
    Button(
        parent=current_account_panel,
        text="Create",
        position=(0, -0.12),
        scale=(0.2, 0.06),
        color=color.blue,
        on_click=lambda: signup(username.text, password.text)
    )
    
    Button(
        parent=current_account_panel,
        text="Back",
        position=(0, -0.2),
        scale=(0.15, 0.05),
        color=color.gray,
        on_click=show_account_menu
    )

def login(username, password):
    global current_account_overlay, current_account_panel
    from accounts import accounts
    if not username or not password:
        show_message("Please fill all fields", color.red)
        return
    success, msg = accounts.login(username, password)
    show_message(msg, color.green if success else color.red)
    if success:
        if current_account_overlay:
            destroy(current_account_overlay)
            current_account_overlay = None
        if current_account_panel:
            destroy(current_account_panel)
            current_account_panel = None
        create_main_menu()

def signup(username, password):
    global current_account_overlay, current_account_panel
    from accounts import accounts
    if not username or not password:
        show_message("Please fill all fields", color.red)
        return
    success, msg = accounts.create_account(username, password)
    show_message(msg, color.green if success else color.red)
    if success:
        accounts.login(username, password)
        if current_account_overlay:
            destroy(current_account_overlay)
            current_account_overlay = None
        if current_account_panel:
            destroy(current_account_panel)
            current_account_panel = None
        create_main_menu()
        
def logout_and_close():
    global current_account_overlay, current_account_panel
    from accounts import accounts
    accounts.logout()
    if current_account_overlay:
        destroy(current_account_overlay)
        current_account_overlay = None
    if current_account_panel:
        destroy(current_account_panel)
        current_account_panel = None
    create_main_menu()

def delete_account():
    global current_account_overlay, current_account_panel
    from accounts import accounts
    if accounts.current_user:
        success, msg = accounts.delete_account(accounts.current_user)
        show_message(msg, color.green if success else color.red)
        if success:
            if current_account_overlay:
                destroy(current_account_overlay)
                current_account_overlay = None
            if current_account_panel:
                destroy(current_account_panel)
                current_account_panel = None
            create_main_menu()

def show_message(msg, color=color.white):
    popup = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0, 0, 0, 0.66),
        scale=(0.4, 0.1),
        position=(0, 0),
        z=70 
    )
    Text(
        parent=popup,
        text=msg,
        position=(0, 0),
        scale=1,
        color=color,
        origin=(0.5, 0.5)
    )
    destroy(popup, delay=2.0)

def create_main_menu():
    global current_menu, menu_ui_elements
    
    if current_menu:
        destroy(current_menu)
        current_menu = None
    
    print(_("menu_creating"))
    menu_ui_elements.clear()

    for child in list(camera.ui.children):
        if child != loading_screen:
            child.enabled = False
            menu_ui_elements.append(child)
    
    current_menu = Entity(parent=camera.ui)
    
    title_text = Text(
        parent=current_menu,
        text=_("app_title"),
        position=(-0.15, 0.45),
        scale=4,
        color=color.white,
    )

    start_btn = Button(
        parent=current_menu,
        text=_("start_orbit"),
        position=(0, 0.2),
        scale=(0.4, 0.12),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.gray,
        text_scale=1.2,
        on_click=start_game
    )
    
    coming_soon_btn = Button(
        parent=current_menu,
        text=_("coming_soon"),
        position=(0, 0.0),
        scale=(0.35, 0.1),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.gray,
        on_click=show_coming_soon
    )

    multiplayer_btn = Button(
        parent=current_menu,
        text="🎮 MP",
        position=(0.7, -0.45), 
        scale=(0.1, 0.08),
        color=color.clear,
        text_color=color.cyan,
        highlight_color=color.blue,
        on_click=show_multiplayer_menu
    )
    menu_ui_elements.append(multiplayer_btn)
    
    quit_btn = Button(
        parent=current_menu,
        text=_("quit"),
        position=(0, -0.2),
        scale=(0.3, 0.1),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.gray,
        on_click=application.quit
    )
    
    from accounts import accounts
    account_status = f"Logged in as: {accounts.current_user}" if accounts.current_user else "Not logged in"
    
    account_text = Text(
        parent=current_menu,
        text=account_status,
        position=(0, -0.35),
        scale=0.8,
        color=color.light_gray,
        origin=(0.5, 0.5)
    )
    
    account_btn = Button(
        parent=current_menu,
        text="Account",
        position=(0, -0.4),
        scale=(0.3, 0.08),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.cyan,
        on_click=show_account_menu
    )

    lang_btn = Button(
        parent=current_menu,
        text=_("language"),
        position=(0, -0.3),
        scale=(0.3, 0.1),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.cyan,
        on_click=show_language_menu
    )

    control_btn = Button(
        parent=current_menu,
        text=_("controls"),
        position=(0, -0.1),
        scale=(0.3, 0.1),
        color=color.clear,
        text_color=color.white,
        highlight_color=color.gray,
        on_click=show_controls_panel
    )
    
    global menu_music
    try:
        menu_music = Audio('main_menu.mp3', loop=True, autoplay=True)
        print(_("audio_music_on"))
    except:
        print(_("audio_music_off"))
        menu_music = None
    
    print("🎮 Main Menu ready")

def create_skip_intro_button():
    global skip_intro_button
    skip_intro_button = Button(
        parent=camera.ui,
        text=_("skip_intro"),
        position=(0.75, 0.45), 
        scale=(0.15, 0.06),
        color=color.black66,
        text_color=color.white,
        highlight_color=color.orange,
        visible=True,   
        enabled=True,
        on_click=skip_intro
    )
    print("⏭️ Skip Intro button created")

def skip_intro():
    global skip_intro_button, video_quad
    print(_("skip_intro_message"))
    
    if video_quad:
        video_quad.enabled = False
    
    global video_playing
    video_playing = False

    if skip_intro_button:
        skip_intro_button.animate_scale((0.01, 0.01), duration=0.3, curve=curve.in_back)
        skip_intro_button.animate('alpha', 0, duration=0.2)
        destroy(skip_intro_button, delay=0.31)
        skip_intro_button = None
    
    show_menu_after_video()

def start_game():
    print(_("game_starting"))
    
    if 'menu_music' in globals() and menu_music:
        menu_music.stop()
    
    for child in list(camera.ui.children):
        if child.enabled and hasattr(child, 'animate_y'):
            try:
                child.animate_y(child.y - 1.5, duration=0.5, curve=curve.in_back)
                if hasattr(child, 'color') and child.color is not None:
                    child.animate('alpha', 0, duration=0.5)
            except:
                pass
       
    fade_in(0.6)
    invoke(show_globe, delay=0.8)

def show_globe():
    try:
        print("🌍 SHOW GLOBE STARTED")
        global app_active, current_menu
        
        if current_menu:
            destroy(current_menu)
            current_menu = None
        
        app_active = True

        for child in list(camera.ui.children):
            child.enabled = False
        
        earth.enabled = True
        if clock_text:
            clock_text.enabled = True

        support_button.enabled = True
        support_button.visible = True

        create_planets_button()

        if settings.get('default_texture_is_earth', True):
            earth.texture = 'earth_texture.jpg'
        else:
            earth.texture = 'map.png'
            if game_mode != "multiplayer":
                activate_map_mode()
        
        if settings.get('sound_enabled', True):
            sound_toggle.text = _("sound_toggle_on")
        else:
            sound_toggle.text = _("sound_toggle_off")
        if settings.get('auto_rotate_enabled', False):
            auto_rotate_toggle.text = _("auto_rotate_toggle_on")
        else:
            auto_rotate_toggle.text = _("auto_rotate_toggle_off")
        if settings.get('default_texture_is_earth', True):
            default_texture_toggle.text = _("default_texture_toggle_earth")
        else:
            default_texture_toggle.text = _("default_texture_toggle_map")
        if settings.get('loading_tips_enabled', True):
            loading_tips_toggle.text = _("loading_tips_toggle_on")
        else:
            loading_tips_toggle.text = _("loading_tips_toggle_off")
        
        if game_mode == "multiplayer":
            print("🎮 Multiplayer mode detected, ensuring UI is visible")
            if mp_room_text:
                mp_room_text.enabled = True
                mp_room_text.visible = True
            if mp_code_text:
                mp_code_text.enabled = True
                mp_code_text.visible = True
            if mp_player_count:
                mp_player_count.enabled = True
                mp_player_count.visible = True
            if mp_chat_panel:
                mp_chat_panel.enabled = True
                mp_chat_panel.visible = True
        
        fade_out(0.6)
        print("🌍 Globe should be visible now")
        
    except Exception as e:
        print(f"🔥 CRASH IN SHOW_GLOBE: {e}")
        import traceback
        traceback.print_exc()

def toggle_planet_ui():
    global planet_ui_panel
    if planet_ui_panel:
        planet_ui_panel.animate_scale((0,0), duration=0.2, curve=curve.out_back)
        destroy(planet_ui_panel, delay=0.21)
        planet_ui_panel = None
    else:
        create_planet_selection_ui()

def create_planet_selection_ui():
    global planet_ui_panel
    planet_ui_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=Color(0,0,0,0.7),
        scale=(0.25, 0.7),
        position=(0.65, 0),
        z=20,
        alpha=0
    )
    planet_ui_panel.animate('alpha', 1, duration=0.2)
    planet_ui_panel.animate_scale((0.25, 0.7), duration=0.3, curve=curve.out_back)
    
    Text(parent=planet_ui_panel, text="🌌 PLANETS", 
         position=(0, 0.3), scale=1.2, color=color.white, origin=(0.5,0.5))
    
    planets = [
        ("☀️ SUN", "sun"),
        ("☿ MERCURY", "mercury"),
        ("♀️ VENUS", "venus"),
        ("🌍 EARTH", "earth"),
        ("♂️ MARS", "mars"),
        ("♃ JUPITER", "jupiter"),
        ("♄ SATURN", "saturn"),
        ("♅ URANUS", "uranus"),
        ("♆ NEPTUNE", "neptune")
    ]
    
    for i, (display_name, planet_key) in enumerate(planets):
        y_pos = 0.2 - i * 0.07
        Button(
            parent=planet_ui_panel,
            text=display_name,
            position=(0, y_pos),
            scale=(0.2, 0.05),
            color=color.black,
            text_color=color.white,
            highlight_color=color.dark_gray,
            on_click=Func(switch_to_planet, planet_key)
        )
    
    Button(
        parent=planet_ui_panel,
        text="← BACK",
        position=(-0.1, -0.5), 
        scale=(0.15, 0.05),
        color=color.dark_gray,
        text_color=color.white,
        on_click=toggle_planet_ui
    )

def switch_to_planet(planet_key):
    global current_planet, solar_system_active, sun_watch_timer, sun_warning_active
    toggle_planet_ui()
    fade_in(0.4)
    
    if not solar_system_active and planet_key != "earth":
        enter_solar_system_mode()
    elif planet_key == "earth" and solar_system_active:
        exit_solar_system_mode()
    
    try:
        earth.texture = f"{planet_key}_texture.jpg"
        current_planet = planet_key
        print(f"Switched to {planet_key}")
    except:
        print(f"Could not load {planet_key}_texture.jpg")

    if planet_key != "earth":
        for dot in dots:
            dot.visible = False
    else:
        for dot in dots:
            dot.visible = True

    
    sun_watch_timer = 0
    sun_warning_active = False
    handle_planet_effects(planet_key)
    invoke(fade_out, 0.4, delay=0.5)

def enter_solar_system_mode():
    global solar_system_active, ss_back_button, sun_light 
    solar_system_active = True
    
    if support_button:
        support_button.enabled = False
        support_button.visible = False
    if clock_text:
        clock_text.enabled = False
    if planet_button:
        planet_button.enabled = False
        planet_button.visible = False
    
    ss_back_button = Button(
        parent=camera.ui,
        text="← BACK TO EARTH",
        position=(0.7, 0.4),
        scale=(0.2, 0.06),
        color=color.black,
        text_color=color.white,
        on_click=exit_solar_system_mode
    )

def exit_solar_system_mode():
    global solar_system_active, ss_back_button, saturn_rings, sun_light 
    solar_system_active = False
    fade_in(0.4)
    
    if support_button:
        support_button.enabled = True
        support_button.visible = True
    if clock_text:
        clock_text.enabled = True
    if planet_button:
        planet_button.enabled = True
        planet_button.visible = True

    if sun_light:
        destroy(sun_light)
        sun_light = None
    
    if ss_back_button:
        destroy(ss_back_button)
        ss_back_button = None
    
    if saturn_rings:
        destroy(saturn_rings)
        saturn_rings = None
    
    earth.texture = "earth_texture.jpg"
    current_planet = "earth"
    invoke(fade_out, 0.4, delay=0.5)

def handle_planet_effects(planet_key):
    global saturn_rings
    
    if saturn_rings:
        destroy(saturn_rings)
        saturn_rings = None

    if planet_key == "sun":
        global sun_light
        sun_light = PointLight(parent=earth, color=color.yellow, position=(0,0,0), range=10, intensity=2)
    
    if planet_key == "saturn":
        saturn_rings = Entity(
            parent=earth,
            model='circle',
            color=color.rgba(255,255,200,100),
            scale=1.8,
            thickness=3,
            double_sided=True
        )
        saturn_rings.rotation_x = 45

def create_planets_button():
    global planet_button
    planet_button = Button(
        parent=camera.ui,
        text="🌌 PLANETS",
        position=(0.7, 0.4),
        scale=(0.15, 0.06),
        color=color.black,
        text_color=color.white,
        highlight_color=color.dark_gray,
        on_click=toggle_planet_ui
    )

def show_menu_after_video():
    print(_("video_ended"))
    global video_quad
    if video_quad:
        destroy(video_quad)
        video_quad = None

    create_main_menu()

def play_video_intro():
    print(_("video_loading"))
    
    cap = cv2.VideoCapture('intro.mp4')
    if not cap.isOpened():
        print(_("video_error"))
        show_menu_after_video()
        return
    
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    if fps <= 0:
        fps = 30
    frame_delay = 1 / (fps * 1.4)

    global video_quad
    video_quad = Entity(
        model='quad',
        scale=(camera.aspect_ratio * 2, 2),
        parent=camera.ui,
        z=10,
        texture_scale=(1, 1),
        texture_offset=(0, 0)
    )
    
    last_frame = None

    global video_playing
    video_playing = True
    
    def update_frame():
        nonlocal last_frame
        if not video_playing:
            return
        ret, frame = cap.read()
        if ret:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)
            video_quad.texture = Texture(img)
            last_frame = frame_rgb
            invoke(update_frame, delay=frame_delay)
        else:
            cap.release()
            if last_frame is not None:
                img = Image.fromarray(last_frame)
                video_quad.texture = Texture(img)
            video_quad.z = 5
            show_menu_after_video()
    
    update_frame()

def switch_to_main():
    loading_screen.enabled = False
    earth.enabled = False
    camera.ui.enabled = True

    if not skip_intro_button:
        create_skip_intro_button()
    
    try:
        play_video_intro()
    except Exception as e:
        print(f"⚠️ Video failed: {e}")
        create_main_menu()

def update_loading():
    global current_progress, skip_requested
    global tip_index, last_tip_change
    
    elapsed = time.time() - load_start_time
    
    if skip_requested:
        progress = 1.0
    else:
        progress = min(1.0, elapsed / load_duration)
    
    current_progress = progress
    progress_fill.scale_x = progress
    
    if progress >= 0.7 and not skip_button.enabled:
        skip_button.enabled = True
        skip_button.visible = True
        skip_button.animate_color(color.white, duration=0.3)
    
    if elapsed - last_tip_change > tip_interval:
        tip_index = random.randint(0, len(tips)-1) 
        loading_tips.text = _(f"tip_{tip_index}")
    last_tip_change = elapsed
    if loading_tips.text == '':
        loading_tips.text = tips[0]
    
    if progress >= 1.0:
        finish_loading()

    if loading_tips_enabled:
        if elapsed - last_tip_change > tip_interval:
            tip_index = (tip_index + 1) % len(tips)
            loading_tips.text = tips[tip_index]
            last_tip_change = elapsed
        if loading_tips.text == '':
            loading_tips.text = tips[0]
    else:
        loading_tips.text = '' 

map_active = False
dots = []
ray_directions = []
typing_active = False

time_explorer_panel = None
clock_text = None
current_utc_offset = 0
time_countries = []
selected_time_index = 0
time_panel_visible = False
scroll_position = 0

history_mode_active = False
timeline_panel = None
timeline_cube = None
timeline_visible = False
timeline_era_positions = []
confirmation_panel = None
current_era_index = 0

compare_mode_active = False
second_globe = None
divider = None
original_camera_z = -10

search_field = None
suggestions_panel = None
suggestions = []

skip_intro_button = None
video_quad = None
video_playing = False

app_active = False 

journey_active = False
journey_sequence = []     
journey_step = 0          
journey_landmarks_by_era = {
    0: [
        (3000, 1600, "Giza Pyramids", 200, 13),
    ],
    1: [
        (3424, 1246, "Rome", +158, 15),      
    ],
    2: [
        (5200, 1400, "Karakorum", -19, 10),
    ],
    3: [
        (3274, 1208, "Paris", +212, +16),       
    ],
    4: [
        (4872, 852, "Moscow", +55, -5),         
    ]
}

def switch_language(index):
    """Switch language, update UI colors, show restart message"""
    set_language(index)
    
    if 'language_buttons' in globals():
        for i, btn in enumerate(language_buttons):
            if i == index:
                btn.color = color.blue
            else:
                btn.color = color.black33

    restart_msg = Text(
        text=_("language_changed_message"),
        position=(0, 0.2),
        scale=2,
        color=color.cyan,
        background=True,
        background_color=color.black66,
        origin=(0.5, 0.5)
    )
    destroy(restart_msg, delay=3.0)
    
    print(f"🌐 Language changed to {languages[index][1]}")

landmark_stories = {
    "Giza Pyramids": "Built as eternal tombs for pharaohs 4,500 years ago.\nThe only surviving Wonder of the Ancient World!\nConstruction: 20 years, 2.3 million stone blocks.",
    "Rome": "Capital of the Roman Empire at its peak under Trajan.\nPopulation: 1+ million people.\nCenter of law, engineering, and culture across 3 continents.",
    "Karakorum": "Capital of the Mongol Empire under Genghis Khan.\nFrom here, horsemen conquered the largest land empire in history!\nStrategic center of the Silk Road.",
    "Paris": "1700s Paris: Heart of the Enlightenment era.\nCenter of philosophy, fashion, and science.\nPopulation: 600,000 before the French Revolution.",
    "Moscow": "1945 Moscow: Capital of the victorious Soviet Union.\nHeavily damaged in WWII (200+ air raids).\nNow emerging as a Cold War superpower."
}

journey_ui_text = None
journey_paused = False 

escape_panel_visible = False

current_menu = None  

current_account_overlay = None
current_account_panel = None

multiplayer_server = None
multiplayer_client = None
multiplayer_thread = None
multiplayer_active = False
multiplayer_id = -1
multiplayer_players = {}         
multiplayer_names = {}            
multiplayer_is_host = False
multiplayer_host_thread = None
multiplayer_server_port = 5555
multiplayer_server_ip = 'localhost'
multiplayer_clients = []         
multiplayer_room_name = "Orbit Room"
multiplayer_room_code = 0
multiplayer_max_players = 8
multiplayer_is_public = False
multiplayer_connected_players = 1
multiplayer_ping_cooldown = 0
PING_COOLDOWN = 2.0
game_mode = "normal"

mp_room_text = None
mp_code_text = None
mp_ip_text = None
mp_player_count = None
mp_chat_panel = None
mp_chat_input = None
mp_chat_messages = []
mp_chat_history = []
mp_pings = []

solar_system_active = False
current_planet = "earth"
planet_button = None
planet_ui_panel = None
sun_watch_timer = 0
sun_warning_active = False
saturn_rings = None
ss_back_button = None
SUN_WARNING_TIME = 10
sun_light = None

def generate_room_code():
    return random.randint(1000, 9999)

def copy_to_clipboard(text):
    try:
        import subprocess
        subprocess.run('clip', input=text.strip().encode('utf-16'), check=True)
        show_message("✅ Copied!", color.green)
    except:
        try:
            import pyperclip
            pyperclip.copy(text)
            show_message("✅ Copied!", color.green)
        except:
            show_message("❌ Copy failed", color.red)

def show_message(msg, color=color.white):
    popup = Entity(parent=camera.ui, model='quad', color=Color(0,0,0,0.66),
                   scale=(0.4,0.1), position=(0,0), z=70)
    Text(parent=popup, text=msg, position=(0,0), scale=1, color=color, origin=(0.5,0.5))
    destroy(popup, delay=2.0)

def show_host_setup():
    overlay = Entity(parent=camera.ui, model='quad', color=Color(0,0,0,0.66),
                     scale=(camera.aspect_ratio*2, 2), z=20)
    
    panel = Entity(parent=camera.ui, model='quad', color=color.black,
                   scale=(0.5, 0.6), position=(-0.3,0), z=30)
    
    Text(parent=panel, text="🖥️ HOST GAME", position=(0,0.25),
         scale=2, color=color.cyan, origin=(0.5,0.5))
    
    Text(parent=panel, text="Room Name:", position=(-0.2,0.15), scale=1, color=color.white)
    room_input = InputField(parent=panel, position=(0.1,0.15), scale=(0.3,0.06), placeholder="My Orbit")

    Text(parent=panel, text="Max Players:", position=(-0.2,0.05), scale=1, color=color.white)
    max_input = InputField(parent=panel, position=(0.1,0.05), scale=(0.3,0.06), placeholder="8")

    Text(parent=panel, text="Current Players:", position=(-0.2, -0.1), scale=1, color=color.white)
    current_players_text = Text(parent=panel, text="1", position=(0.1, -0.1), scale=1, color=color.green)
    
    is_public = False
    def toggle_privacy():
        nonlocal is_public
        is_public = not is_public
        privacy_btn.text = "🌍 PUBLIC" if is_public else "🔒 PRIVATE"
        privacy_btn.color = color.green if is_public else color.red
    
    privacy_btn = Button(parent=panel, text="🔒 PRIVATE", position=(0,-0.05),
                         scale=(0.3,0.06), color=color.red, on_click=toggle_privacy)

    def start_host():
        nonlocal overlay, panel, current_players_text
        name = room_input.text if room_input.text and room_input.text.strip() != "" else "Orbit Room"
        print(f"📝 Room name from input: '{name}'") 
        max_players = int(max_input.text) if max_input.text and max_input.text.isdigit() else 8
        
        current_players_text.text = "1"
        
        destroy(overlay)
        destroy(panel)
        
        start_host_server(name, max_players, is_public)
    
    Button(parent=panel, text="🚀 START HOSTING", position=(0,-0.15),
           scale=(0.4,0.08), color=color.green, on_click=start_host)
    
    def go_back():
        destroy(overlay)
        destroy(panel)
        show_multiplayer_menu()
    
    Button(parent=panel, text="← BACK", position=(-0.2,-0.25),
           scale=(0.2,0.06), color=color.gray, on_click=go_back)

def start_host_server(room_name, max_players, is_public):
    print("🔥🔥🔥 START HOST SERVER IS DEFINITELY CALLED 🔥🔥🔥")
    print(f"Room: {room_name}, Max: {max_players}, Public: {is_public}")


    global multiplayer_is_host, multiplayer_server, multiplayer_host_thread
    global multiplayer_room_name, multiplayer_max_players, multiplayer_is_public
    global multiplayer_room_code, multiplayer_connected_players, game_mode
    global multiplayer_clients, multiplayer_server_port
    
    multiplayer_room_name = room_name
    multiplayer_max_players = max_players
    multiplayer_is_public = is_public
    multiplayer_room_code = generate_room_code()
    multiplayer_connected_players = 1
    game_mode = "multiplayer"
    multiplayer_is_host = True
    multiplayer_clients = []
    
    try:
        multiplayer_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        multiplayer_server.bind(('0.0.0.0', multiplayer_server_port))
        multiplayer_server.listen(5)
        print(f"✅ HOST: Server started on port {multiplayer_server_port}")
        print(f"✅ HOST: Room code = {multiplayer_room_code}")
        
        multiplayer_host_thread = threading.Thread(target=host_server_loop, daemon=True)
        multiplayer_host_thread.start()
        
        connect_as_host_client()

        print("✅ Host server started, now calling start_game()")
        start_game()
        print("✅ start_game() called")

        create_multiplayer_ui()
        
        fade_in(0.5)
        invoke(fade_out, 0.5, delay=0.6)
        
    except Exception as e:
        print(f"❌ HOST ERROR: {e}")
        show_message(f"Failed to host: {e}", color.red)
        multiplayer_is_host = False

def host_server_loop():
    global multiplayer_server, multiplayer_clients, multiplayer_active, multiplayer_connected_players
    
    while multiplayer_is_host:
        try:
            conn, addr = multiplayer_server.accept()
            print(f"🔌 New connection from {addr}")
            
            player_id = len(multiplayer_clients) + 1 
            
            if player_id >= multiplayer_max_players:
                conn.send(b"FULL")
                conn.close()
                continue
            
            conn.send(f"ID:{player_id}".encode())
            
            for pid, name in multiplayer_names.items():
                if pid != player_id:  
                    try:
                        conn.send(f"JOIN:{pid}:{name}".encode())
                    except:
                        pass
            
            multiplayer_clients.append(conn)
            multiplayer_connected_players = len(multiplayer_clients) + 1
            
            broadcast(f"COUNT:{multiplayer_connected_players}")
            
            thread = threading.Thread(target=handle_host_client, args=(conn, player_id), daemon=True)
            thread.start()
            
            broadcast(f"CHAT:Server:👤 Player {player_id} joined")
            
        except Exception as e:
            if multiplayer_is_host:
                print(f"❌ HOST LOOP ERROR: {e}")
            break

def handle_host_client(conn, player_id):
    global multiplayer_clients, multiplayer_names, multiplayer_connected_players
    
    while multiplayer_is_host:
        try:
            data = conn.recv(1024).decode()
            if not data:
                break
            
            print(f"📨 Received from {player_id}: {data[:50]}") 
            
            if data.startswith("POS:"):
                for client in multiplayer_clients:
                    if client != conn:
                        try:
                            client.send(data.encode())
                        except:
                            pass
                            
            elif data.startswith("NAME:"):
                name = data[5:]
                multiplayer_names[player_id] = name
                broadcast(f"NAME:{player_id}:{name}")
                
            elif data.startswith("CHAT:"):
                msg = data[5:]
                broadcast(f"CHAT:{player_id}:{msg}")
                
            elif data.startswith("PING:"):
                coords = data[5:]
                broadcast(f"PING:{player_id}:{coords}")
                
        except ConnectionResetError:
            print(f"❌ Client {player_id} connection reset")
            break
        except Exception as e:
            print(f"❌ Client {player_id} error: {e}")
            break
    
    print(f"❌ Player {player_id} disconnected")
    if conn in multiplayer_clients:
        multiplayer_clients.remove(conn)
    multiplayer_connected_players = len(multiplayer_clients) + 1
    
    broadcast(f"COUNT:{multiplayer_connected_players}")
    
    if player_id in multiplayer_names:
        name = multiplayer_names[player_id]
        del multiplayer_names[player_id]
        broadcast(f"LEFT:{player_id}")
        broadcast(f"CHAT:Server:👋 {name} left")
    
    try:
        conn.close()
    except:
        pass

def broadcast(message):
    """Send message to all connected clients"""
    disconnected = []
    
    for client in multiplayer_clients:
        try:
            client.send(message.encode())
        except:
            disconnected.append(client)
    
    for client in disconnected:
        if client in multiplayer_clients:
            multiplayer_clients.remove(client)

def connect_as_host_client():
    """Host connects to own server as client"""
    global multiplayer_client, multiplayer_thread, multiplayer_active
    global multiplayer_id, multiplayer_names
    
    try:
        multiplayer_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        multiplayer_client.connect(('127.0.0.1', multiplayer_server_port))
        multiplayer_active = True
        multiplayer_id = 0
        multiplayer_names[0] = accounts.current_user if accounts.current_user else "Host"
        
        multiplayer_client.send(f"NAME:{multiplayer_names[0]}".encode())
        
        multiplayer_thread = threading.Thread(target=client_receive_loop, daemon=True)
        multiplayer_thread.start()
        
        print("✅ Host connected as client")
        
    except Exception as e:
        print(f"❌ Host client connection failed: {e}")
        multiplayer_active = False

def join_server(ip, port, room_code=None):
    """Join a multiplayer server"""
    global multiplayer_client, multiplayer_thread, multiplayer_active
    global multiplayer_server_ip, multiplayer_server_port, game_mode
    global multiplayer_id, multiplayer_names
    
    multiplayer_server_ip = ip
    multiplayer_server_port = port
    
    try:
        multiplayer_client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        multiplayer_client.connect((ip, port))
        
        data = multiplayer_client.recv(1024).decode()
        if data == "FULL":
            show_message("❌ Room is full", color.red)
            return False
        
        if data.startswith("ID:"):
            multiplayer_id = int(data.split(":")[1])
        
        multiplayer_active = True
        game_mode = "multiplayer"
        
        name = accounts.current_user if accounts.current_user else f"Player{multiplayer_id}"
        multiplayer_names[multiplayer_id] = name
        multiplayer_client.send(f"NAME:{name}".encode())
        
        multiplayer_thread = threading.Thread(target=client_receive_loop, daemon=True)
        multiplayer_thread.start()
        
        create_multiplayer_ui()
        
        fade_in(0.5)
        invoke(fade_out, 0.5, delay=0.6)
        
        show_message(f"✅ Joined as {name}", color.green)
        return True
        
    except Exception as e:
        print(f"❌ JOIN ERROR: {e}")
        show_message(f"Connection failed: {e}", color.red)
        return False

def client_receive_loop():
    """Receive data from server"""
    global multiplayer_players, multiplayer_names, mp_chat_messages, multiplayer_active
    
    while multiplayer_active:
        try:
            data = multiplayer_client.recv(1024).decode()
            if not data:
                break
            
            print(f"📩 Client received: {data[:50]}")  
            
            if data.startswith("POS:"):
                parts = data[4:].split(",")
                pid = int(parts[0])
                x, y, z, rx, ry, rz = map(float, parts[1:7])
                
                if pid == multiplayer_id:
                    continue
                
                if pid in multiplayer_players:
                    multiplayer_players[pid].position = (x, y, z)
                    multiplayer_players[pid].rotation = (rx, ry, rz)
                else:
                    create_player_orb(pid, (x, y, z), (rx, ry, rz))
                    
            elif data.startswith("NAME:"):
                parts = data[5:].split(":", 1)
                pid = int(parts[0])
                name = parts[1]
                multiplayer_names[pid] = name
                
                if pid in multiplayer_players:
                    for child in multiplayer_players[pid].children:
                        if hasattr(child, 'text'):
                            child.text = name
                            break
                
            elif data.startswith("CHAT:"):
                parts = data[5:].split(":", 1)
                sender = parts[0]
                msg = parts[1]
                
                if sender == "Server":
                    add_chat_message(f"🖥️ {msg}")
                else:
                    try:
                        pid = int(sender)
                        name = multiplayer_names.get(pid, f"Player{pid}")
                        add_chat_message(f"{name}: {msg}")
                    except ValueError:
                        add_chat_message(f"{sender}: {msg}")
                
            elif data.startswith("PING:"):
                parts = data[5:].split(":", 1)
                pid = int(parts[0])
                coords = parts[1].split(",")
                x, y, z = map(float, coords)
                create_ping(pid, (x, y, z))
                
            elif data.startswith("JOIN:"):
                parts = data[5:].split(":", 1)
                pid = int(parts[0])
                name = parts[1]
                multiplayer_names[pid] = name
                add_chat_message(f"👤 {name} joined")
                
            elif data.startswith("LEFT:"):
                pid = int(data[5:])
                name = multiplayer_names.get(pid, f"Player{pid}")
                if pid in multiplayer_players:
                    destroy(multiplayer_players[pid])
                    del multiplayer_players[pid]
                if pid in multiplayer_names:
                    del multiplayer_names[pid]
                add_chat_message(f"👋 {name} left")
                
            elif data.startswith("COUNT:"):
                count = int(data[6:])
                if mp_player_count:
                    mp_player_count.text = f"👥 {count}/{multiplayer_max_players}"
                
        except Exception as e:
            print(f"❌ RECEIVE ERROR: {e}")
            import traceback
            traceback.print_exc()
            break
    
    if multiplayer_active:
        stop_multiplayer()

def create_player_orb(pid, pos, rot):
    """Create a visual representation for another player"""
    group = Entity()
    group.position = pos
    group.rotation = rot
    
    color_list = [color.blue, color.green, color.yellow, color.orange,
                  color.pink, color.cyan, color.magenta, color.lime]
    orb_color = color_list[pid % len(color_list)]
    
    orb = Entity(parent=group, model='sphere', color=orb_color, scale=0.15)
    
    name = multiplayer_names.get(pid, f"Player{pid}")
    name_text = Text(parent=group, text=name, position=(0,0.3,0),
                     scale=0.02, color=color.white, origin=(0.5,0.5))
    
    multiplayer_players[pid] = group

def create_ping(pid, pos):
    """Create a temporary ping marker"""
    ping = Entity(parent=earth, model='sphere', color=color.red,
                  scale=0.1, position=pos, unlit=True)
    
    ping.animate_scale(0.2, duration=0.3, curve=curve.out_back)
    ping.animate_scale(0.05, duration=0.3, delay=0.3)
    
    destroy(ping, delay=1.0)
    mp_pings.append(ping)

def stop_multiplayer():
    """Clean shutdown of multiplayer"""
    global multiplayer_active, multiplayer_is_host, game_mode
    global multiplayer_client, multiplayer_server, multiplayer_clients
    global multiplayer_players, multiplayer_names, mp_chat_messages
    global mp_room_text, mp_code_text, mp_ip_text, mp_player_count, mp_chat_panel, mp_chat_input
    
    multiplayer_active = False
    game_mode = "normal"
    
    if multiplayer_client:
        try:
            multiplayer_client.close()
        except:
            pass
        multiplayer_client = None
    
    if multiplayer_is_host:
        multiplayer_is_host = False
        for client in multiplayer_clients:
            try:
                client.close()
            except:
                pass
        multiplayer_clients.clear()
        
        if multiplayer_server:
            try:
                multiplayer_server.close()
            except:
                pass
            multiplayer_server = None
    
    for pid, entity in multiplayer_players.items():
        destroy(entity)
    multiplayer_players.clear()
    multiplayer_names.clear()
    mp_chat_messages.clear()
    
    if mp_room_text:
        destroy(mp_room_text)
        mp_room_text = None
    if mp_code_text:
        destroy(mp_code_text)
        mp_code_text = None
    if mp_ip_text:
        destroy(mp_ip_text)
        mp_ip_text = None
    if mp_player_count:
        destroy(mp_player_count)
        mp_player_count = None
    if mp_chat_panel:
        destroy(mp_chat_panel)
        mp_chat_panel = None
    
    camera.position = (0, 0, -10)
    camera.rotation = (0, 0, 0)
    
    print("🛑 Multiplayer stopped")

def show_multiplayer_menu():
    overlay = Entity(parent=camera.ui, model='quad', color=Color(0,0,0,0.66),
                     scale=(camera.aspect_ratio*2, 2), z=20)
    
    panel = Entity(parent=camera.ui, model='quad', color=color.black,
                    scale=(0.4, 0.5), position=(-0.3,0), z=30) 
    
    Text(parent=panel, text="🎮 MULTIPLAYER", position=(0,0.2),
         scale=2, color=color.cyan, origin=(0.5,0.5))
    
    Button(parent=panel, text="🖥️ HOST GAME", position=(0,0.05),
           scale=(0.3,0.08), color=color.green, on_click=lambda: [destroy(overlay), destroy(panel), show_host_setup()])
    
    Button(parent=panel, text="🔌 JOIN GAME", position=(0,-0.05),
           scale=(0.3,0.08), color=color.blue, on_click=lambda: [destroy(overlay), destroy(panel), show_join_menu()])
    
    Button(parent=panel, text="← BACK", position=(-0.15,-0.2),
           scale=(0.15,0.06), color=color.gray, on_click=lambda: [destroy(overlay), destroy(panel)])


def show_join_menu():
    overlay = Entity(parent=camera.ui, model='quad', color=Color(0,0,0,0.66),
                    scale=(camera.aspect_ratio*2, 2), z=20)
                    
    panel = Entity(parent=camera.ui, model='quad', color=color.black,
                   scale=(0.5, 0.6), position=(-0.3,0), z=30)
    
    Text(parent=panel, text="🔌 JOIN GAME", position=(0,0.25),
         scale=2, color=color.cyan, origin=(0.5,0.5))
    
    Text(parent=panel, text="- OR -", position=(0,-0.12), scale=1, color=color.gray)
    
    Text(parent=panel, text="Room Code:", position=(-0.2,-0.18), scale=1, color=color.white)
    code_input = InputField(parent=panel, position=(0.1,-0.18), scale=(0.3,0.06), 
                           placeholder="Enter code", active=True)
    
    Button(parent=panel, text="🔑 JOIN BY CODE", position=(0,-0.25),
           scale=(0.3,0.07), color=color.orange,
           on_click=lambda: join_by_code(code_input.text))
    
    Button(parent=panel, text="← BACK", position=(-0.2,-0.35),
           scale=(0.15,0.06), color=color.gray, on_click=lambda: [destroy(overlay), destroy(panel), show_multiplayer_menu()])

def join_by_code(code):
    """Join a room using its code"""
    try:
        code = code.strip()
        if not code:
            show_message("❌ Enter a room code", color.red)
            return
            
        room_code = int(code)
        
        show_message(f"🔍 Looking for room {room_code}...", color.yellow)

        success = join_server('127.0.0.1', 5555)
        
        if success:
            show_message(f"✅ Joined room {room_code}", color.green)
        else:
            show_message("❌ Room not found", color.red)
            
    except ValueError:
        show_message("❌ Invalid code - use numbers only", color.red)
    except Exception as e:
        print(f"❌ JOIN ERROR: {e}")
        show_message("❌ Connection failed", color.red)

def create_multiplayer_ui():
    """Create in-game multiplayer UI"""
    global mp_room_text, mp_code_text, mp_player_count, mp_chat_panel, mp_chat_input
    
    mp_room_text = Text(parent=camera.ui, text=f"🏠 {multiplayer_room_name}",
                        position=(-0.7,0.45), scale=1, color=color.gold,
                        background=True, background_color=Color(0,0,0,0.5), z=10)
    
    mp_code_text = Text(parent=camera.ui, text=f"🔑 Code: {multiplayer_room_code}",
                        position=(-0.7,0.35), scale=0.8, color=color.yellow,
                        background=True, background_color=Color(0,0,0,0.5), z=10)
    
    mp_player_count = Text(parent=camera.ui, text=f"👥 {multiplayer_connected_players}/{multiplayer_max_players}",
                           position=(0.7,0.45), scale=1, color=color.cyan,
                           background=True, background_color=Color(0,0,0,0.5), z=10)
    
    create_chat_ui()

def create_chat_ui():
    global mp_chat_panel, mp_chat_input
    
    mp_chat_panel = Entity(parent=camera.ui, model='quad', color=Color(0,0,0,0.66),
                           scale=(0.4,0.25), position=(-0.7,-0.35), origin=(0,0), z=10)
    
    mp_chat_messages.clear()
    
    mp_chat_input = InputField(parent=mp_chat_panel, position=(0.05,0.05), scale=(0.3,0.06),
                               placeholder="Type here...", active=False)
    
    Button(parent=mp_chat_panel, text="📤", position=(0.35,0.05), scale=(0.05,0.06),
           color=color.blue, on_click=send_chat_message)
    
    chat_visible = True
    def toggle_chat():
        nonlocal chat_visible
        chat_visible = not chat_visible
        mp_chat_panel.visible = chat_visible
    
    Button(parent=camera.ui, text="Chat", position=(-0.7,-0.45), scale=(0.05,0.04),
           color=color.blue, on_click=toggle_chat)

def send_chat_message():
    if mp_chat_input and mp_chat_input.text:
        msg = mp_chat_input.text
        mp_chat_input.text = ""
        
        if multiplayer_active and multiplayer_client:
            try:
                multiplayer_client.send(f"CHAT:{msg}".encode())
                add_chat_message(f"You: {msg}")
            except:
                pass

def add_chat_message(text):
    """Add message to chat display"""
    y_pos = 0.2 - len(mp_chat_messages) * 0.05
    
    msg_text = Text(parent=mp_chat_panel, text=text, position=(0.05, y_pos),
                    scale=1.2, color=color.white, origin=(0,0.5)) 
    
    mp_chat_messages.append(msg_text)
    
    if len(mp_chat_messages) > 5:
        old = mp_chat_messages.pop(0)
        destroy(old)
    
    for i, msg in enumerate(mp_chat_messages):
        msg.y = 0.2 - i * 0.05

def update_multiplayer():
    """Call this from main update() when game_mode == 'multiplayer'"""
    global multiplayer_ping_cooldown
    
    if not multiplayer_active:
        return

    speed = 0.1
    if held_keys['w']: camera.y += speed
    if held_keys['s']: camera.y -= speed
    if held_keys['a']: camera.x -= speed
    if held_keys['d']: camera.x += speed
    if held_keys['q']: camera.z += speed
    if held_keys['e']: camera.z -= speed
    
    if held_keys['left mouse']:
        earth.rotation_y += mouse.velocity[0] * 40
        earth.rotation_x -= mouse.velocity[1] * 40
    
    if multiplayer_client:
        pos = camera.position
        rot = camera.rotation
        try:
            multiplayer_client.send(f"POS:{multiplayer_id},{pos.x},{pos.y},{pos.z},{rot.x},{rot.y},{rot.z}".encode())
        except:
            stop_multiplayer()

    if held_keys['right mouse'] and time.time() - multiplayer_ping_cooldown > PING_COOLDOWN:
        multiplayer_ping_cooldown = time.time()
        
        hit_info = raycast(camera.position, camera.forward, distance=30, ignore=[camera])
        if hit_info.hit and hit_info.entity == earth:
            pos = hit_info.world_point
            try:
                multiplayer_client.send(f"PING:{pos.x},{pos.y},{pos.z}".encode())
                create_ping(multiplayer_id, pos)
            except:
                pass
    
    if mp_player_count:
        mp_player_count.text = f"👥 {multiplayer_connected_players}/{multiplayer_max_players}"

country_data = [
("RUSSIA", (4872, 852), 0, 0, color.red, "Moscow", 3),
("USA", (1474, 1394), 25, 0, color.blue, "Washington D.C.", -5),
("BRAZIL", (2348, 2278), -70, 0, color.green, "Brasília", -3),
("CANADA", (1324, 983), 35, -7, color.yellow, "Ottawa", -5),
("CHINA", (5013, 1458), -15, 0, color.orange, "Beijing", 8),
("JAPAN", (5821, 1397), -97, 0, color.pink, "Tokyo", 9),
("ITALY", (3424, 1246), 163, -4, color.violet, "Rome", 1),
("GERMANY", (3403, 1105), 166, -6, color.cyan, "Berlin", 1),
("UNITED KINGDOM", (3197, 1066), 190, -5, color.magenta, "London", 0),
("FRANCE", (3274, 1208), 181, -3, color.turquoise, "Paris", 1),
("ARGENTINA", (2081, 2783), -45, 7, color.lime, "Buenos Aires", -3),
("MEXICO", (1390, 1702), 27, 1, color.brown, "Mexico City", -6),
("AUSTRALIA", (5634, 2596), -80, 5, color.gold, "Canberra", 10),
("EGYPT", (3762, 1632), 125, 0, color.gold, "Cairo", 2),  
("NIGERIA", (3365, 1965), 173, 2, color.brown, "Abuja", 1), 
("GREENLAND", (2502, 481), -90, -2, color.azure, "Nuuk", -3),
("INDONESIA", (4640, 1747), -10, -15, color.violet, "Jakarta", 7),
("COLOMBIA", (1913, 2044), -27, 1, color.magenta, "Bogotá", -5),
("HONDURAS", (1716, 1801), -8, 3, color.gray, "Tegucigalpa", -6),
("NORTH KOREA", (5596, 1413), -72, 2, color.salmon, "Pyongyang", 9),
("MONGOLIA", (5111, 1191), -21, 0, color.smoke, "Ulaanbaatar", 8),
("ROMANIA", (3673, 1257), 135, -1, color.cyan, "Bucharest", 2),
("KYRGYZSTAN", (4577, 1314), 35, -3, color.gold, "Bishkek", 6),
("UZBEKISTAN", (4362, 1320), 60, -3, color.lime, "Tashkent", 5),
("PORTUGAL", (2987, 1347), 205, -4, color.orange, "Lisbon", 0),
("IRAN", (4198, 1470), 75, -2, color.violet, "Tehran", 3.5),
("INDIA", (4640, 1747), 30, 10, color.orange, "New Delhi", 5.5),
("CUBA", (1760, 1709), -12, 2, color.green, "Havana", -5),
("THAILAND", (5054, 1829), -18, 1, color.pink, "Bangkok", 7),
("CHAD", (3570, 1834), 148, 1, color.brown, "N'Djamena", 1),
("VIETNAM", (5236, 1847), -33, -2, color.green, "Hanoi", 7),
("SUDAN", (3759, 1849), 128, 4, color.brown, "Khartoum", 2),
("EL SALVADOR", (1531, 1887), 10, 3, color.gold, "San Salvador", -6),
("COSTA RICA", (1639, 1957), -5, 2, color.green, "San José", -6),
("SRI LANKA", (4726, 2008), 20, 2, color.gold, "Sri Jayawardenepura Kotte", 5.5),
("SINGAPORE", (5142, 2091), -25, 2, color.red, "Singapore", 8),
("ZAMBIA", (3696, 2367), 128, 5, color.green, "Lusaka", 2),
("MOZAMBIQUE", (3913, 2444), 113, 4, color.orange, "Maputo", 2),
("SOUTH AFRICA", (3663, 2702), 135, 7, color.gold, "Pretoria", 2),
("CHILE", (1887, 2687), -30, 5, color.red, "Santiago", -4),
("NEW ZEALAND", (6202, 2833), -150, 3, color.green, "Wellington", 12),
("ETHIOPIA", (3941, 1970), 105, 2, color.orange, "Addis Ababa", 3),
("VENEZUELA", (2037, 1946), -40, 2, color.yellow, "Caracas", -4),
("BELIZE", (1650, 1801), 2, 0, color.green, "Belmopan", -6),
("AFGHANISTAN", (4415, 1466), 55, -2, color.brown, "Kabul", 4.5),
("TURKIYE", (3858, 1367), 110, -3, color.red, "Ankara", 3),
("UKRAINE", (3650, 1100), 130, -5, color.blue, "Kyiv", 2),
("NETHERLANDS", (3277, 1046), 175, -6, color.orange, "Amsterdam", 1),
("ICELAND", (2906, 746), 222, -2, color.cyan, "Reykjavik", 0),
("NORWAY", (3353, 754), 170, -5, color.red, "Oslo", 1),
]

history_eras = [
    {
        "name": "Ancient Wonders (300 BCE)",
        "year": -300,
        "map_file": "300_BCE.jpg",
        "description": "Hellenistic kingdoms, Persian Empire, Seven Wonders stand.",
        "key_events": ["Library of Alexandria built", "Mauryan Empire in India"]
    },
    {
        "name": "Roman Empire Peak (117 CE)",
        "year": 117,
        "map_file": "117_CE.jpg",
        "description": "Roman Empire at greatest extent under Trajan.",
        "key_events": ["Silk Road active", "Han Dynasty in China"]
    },
    {
        "name": "Mongol Empire Rise (1200 CE)",
        "year": 1200,
        "map_file": "1200_CE.jpg",
        "description": "Genghis Khan unites Mongols, beginning of largest land empire.",
        "key_events": ["Silk Road under Mongol control", "Spread of technologies"]
    },
    {
        "name": "Colonial Peak (1700 CE)",
        "year": 1700,
        "map_file": "1700_CE.jpg",
        "description": "European colonial empires at their height before revolutions.",
        "key_events": ["British East India Company", "Atlantic slave trade"]
    },
    {
        "name": "Post‑World War II (1945)",
        "year": 1945,
        "map_file": "1945.jpg",
        "description": "Post‑war borders, emerging Cold War, decolonization begins.",
        "key_events": ["UN founded", "Nuremberg Trials", "Start of Cold War"]
    }
]

history_eras_sorted = sorted(history_eras, key=lambda e: e['year'])

historical_facts = [
    {
        "eras": ["Ancient Wonders (300 BCE)", "Roman Empire Peak (117 CE)"],
        "lat": 41.9,
        "lon": 12.5,
        "title": "Rome",
        "description": "Capital of Roman Empire",
        "type": "capital"
    },
    {
        "eras": ["Ancient Wonders (300 BCE)"],
        "lat": 31.2,
        "lon": 29.9,
        "title": "Lighthouse of Alexandria",
        "description": "One of Seven Wonders",
        "type": "wonder"
    },
    {
        "eras": ["Roman Empire Peak (117 CE)"],
        "lat": 39.9,
        "lon": 116.4,
        "title": "Han Dynasty Capital",
        "description": "Luoyang — eastern capital of Han China",
        "type": "capital"
    },
    {
        "eras": ["Mongol Empire Rise (1200 CE)"],
        "lat": 47.9,
        "lon": 106.9,
        "title": "Karakorum",
        "description": "Capital of Mongol Empire under Genghis Khan",
        "type": "capital"
    },
    {
        "eras": ["Colonial Peak (1700 CE)"],
        "lat": 51.5,
        "lon": -0.1,
        "title": "London",
        "description": "Center of British Empire",
        "type": "capital"
    },
    {
        "eras": ["Post‑World War II (1945)"],
        "lat": 38.9,
        "lon": -77.0,
        "title": "Washington D.C.",
        "description": "United Nations founding conference held here",
        "type": "capital"
    },
]

region_evolution = [
    {
        "name": "Egypt",
        "eras": [0, 1, 4],  
        "lat": 26.0,
        "lon": 30.0,
        "color": color.gold
    },
    {
        "name": "Roman Empire",
        "eras": [0, 1],  
        "lat": 41.9,
        "lon": 12.5,
        "color": color.red
    },
    {
        "name": "Mongol Empire",
        "eras": [2], 
        "lat": 46.0,
        "lon": 105.0,
        "color": color.green
    },
    {
        "name": "United Kingdom",
        "eras": [3, 4],  
        "lat": 51.5,
        "lon": -0.1,
        "color": color.blue
    }
]

def select_country(country_name):
    global typing_active

    if country_name == "1983":
        trigger_1983_jumpscare()
        return
    
    if country_name.upper() == "SANS":
        trigger_sans_easter_egg()
        return

    if country_name == "1961":
        trigger_1961_gagarin_egg()
        return

    if country_name.upper() == "ORBIT":
        trigger_orbit_secret_egg()
        return

    typing_active = False
    print(f"🔍 Selected: {country_name}")
    
    fade_in(0.4)
    invoke(teleport_to_country, country_name, delay=0.4)
    invoke(fade_out, 0.4, delay=0.8)

    invoke(show_country_facts, country_name, delay=1.0)
    
    global search_field, suggestions_panel, suggestions
    if search_field:
        search_field.text = ''
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()

def update_suggestions():
    global suggestions_panel, suggestions
    
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions.clear()
    
    if not search_field or not search_field.text:
        return
    
    query = search_field.text.strip().lower()
    if not query:
        return
    
    matches = []
    for name, _, _, _, _, _, _ in country_data:
        if query in name.lower():
            matches.append(name)
    
    if matches:
        suggestions_panel = Entity(
            parent=camera.ui,
            model='quad',
            color=color.black,
            scale=(0.3, 0.05 * len(matches)),
            position=(-0.65, 0.30),
            origin=(0, 0),
            z=-1
        )
        
        for i, match in enumerate(matches):
            btn = Button(
                parent=suggestions_panel,
                text=match,
                color=color.black33,
                scale=(1, 0.9 / len(matches)),
                position=(0, 0.5 - (i + 0.5) / len(matches)),
                text_color=color.white,
                text_scale=0.8,
                on_click=Func(select_country, match)
            )
            suggestions.append(btn)

def start_search():
    close_all_ui() 
    global search_field, typing_active
    typing_active = True
    if not search_field:
        search_field = InputField(
            position=(-0.65, 0.35),
            scale=(0.3, 0.05),
            active=True,
            visible=True,
            text='',
            color=color.black,
            text_color=color.white,
            placeholder=_("search_placeholder"),
            placeholder_color=color.gray,
            font='unifont-13.0.06.ttf' 
        )
    else:
        search_field.active = True
        search_field.visible = True
    update_suggestions()

def pixel_to_globe_surface(pixel_x, pixel_y, lon_offset=0, lat_offset=0):
    map_width, map_height = 6460, 3403
    u = pixel_x / map_width
    v = pixel_y / map_height
    
    longitude = (u - 0.5) * (2 * math.pi) + math.radians(-95) + math.radians(lon_offset)
    latitude = (0.5 - v) * math.pi + math.radians(lat_offset)
    
    x_math = 3 * math.cos(latitude) * math.sin(longitude)
    y_math = 3 * math.sin(latitude)
    z_math = 3 * math.cos(latitude) * math.cos(longitude)
    
    scale_factor = 0.6 / 3.0
    x_visual = x_math * scale_factor
    y_visual = y_math * scale_factor
    z_visual = z_math * scale_factor
    
    return (x_visual, y_visual, z_visual)

def lat_lon_to_position(lat, lon):
    lat_rad = math.radians(lat)
    lon_rad = math.radians(lon)
    
    x = math.cos(lat_rad) * math.sin(lon_rad) * 3
    y = math.sin(lat_rad) * 3
    z = math.cos(lat_rad) * math.cos(lon_rad) * 3
    
    return Vec3(x * 0.6/3, y * 0.6/3, z * 0.6/3)

def update_clock():
    global clock_text, current_utc_offset
    
    if clock_text is None:
        return
    
    from datetime import datetime, timezone, timedelta
    
    if current_utc_offset == 0:
        import time
        local_offset_sec = -time.timezone if time.localtime().tm_isdst == 0 else -time.altzone
        current_utc_offset = local_offset_sec // 3600
    
    utc_now = datetime.now(timezone.utc)
    local_time = utc_now + timedelta(hours=current_utc_offset)
    time_str = local_time.strftime("%H:%M:%S")
    
    clock_text.text = _("clock_prefix") + f" {time_str}"
    
    invoke(update_clock, delay=1)

def animate_digital_roll(old_offset, new_offset, country_name):
    global current_utc_offset
    
    steps = 10
    total_duration = 0.5
    
    for i in range(1, steps + 1):
        inter_offset = old_offset + (new_offset - old_offset) * i / steps
        invoke(show_intermediate_time, inter_offset, delay=i * (total_duration / steps))
    
    invoke(lambda: set_final_time(new_offset, country_name), delay=total_duration + 0.1)

def show_intermediate_time(offset):
    from datetime import datetime, timezone, timedelta
    utc_now = datetime.now(timezone.utc)
    temp_time = utc_now + timedelta(hours=offset)
    time_str = temp_time.strftime("%H:%M:%S")
    if clock_text:
        clock_text.text = _("clock_prefix") + f" {time_str}"

def set_final_time(offset, country_name):
    global current_utc_offset
    current_utc_offset = offset
    print(_("msg_time_switched").format(country_name))

def create_clock_ui():
    global clock_text
    
    clock_text = Text(
        text=_("clock_prefix") + " --:--:--",
        position=(0.75, -0.45),
        origin=(0.5, 0.5),
        scale=1.2,
        color=color.white,
        background=True,
        background_color=color.black66
    )
    update_clock()

def toggle_time_explorer():
    global time_explorer_panel, time_content, time_countries, selected_time_index, time_panel_visible
    
    if time_explorer_panel is None:
        time_explorer_panel = Entity(
            parent=camera.ui,
            model='quad',
            color=color.black66,
            scale=(0.3, 0.5),
            position=(1.5, 0.0),
            origin=(0, 0),
            z=-5,
            visible=False
        )
        
        time_content = Entity(
            parent=time_explorer_panel,
            model='quad',
            color=color.clear,
            scale=(0.95, 0.7),
            position=(0, 0),
            origin=(0, 0)
        )

        scroll_position = 0 
        
        time_countries.clear()
        for i, (name, _, _, _, _, capital, utc) in enumerate(country_data):
            btn = Button(
                parent=time_content,
                text=str(_(f"country_{name}")) + f" ({capital})",
                color=color.black33,
                scale=(0.95, 0.08),
                position=(0, 0.35 - i * 0.1),
                origin=(0.5, 0.5),
                text_color=color.white,
                text_scale=0.65,
                on_click=Func(switch_to_country_time, name, utc)
            )
            time_countries.append(btn)
        
        selected_time_index = 0
        update_time_selection()
    
    global time_panel_visible
    if time_panel_visible:
        time_explorer_panel.animate_x(1.5, duration=0.3)
        invoke(lambda: setattr(time_explorer_panel, 'visible', False), delay=0.31)
        for btn in time_countries:
            btn.visible = False
        time_panel_visible = False
        print(_("ui_time_closed"))
    else:
        time_explorer_panel.x = 1.5
        time_explorer_panel.visible = True
        time_explorer_panel.animate_x(0.75, duration=0.3)
        for btn in time_countries:
            btn.visible = True
        time_panel_visible = True
        print(_("ui_time_open"))

def update_time_selection():
    for i, btn in enumerate(time_countries):
        if i == selected_time_index:
            btn.color = color.blue
            btn.text_color = color.white
        else:
            btn.color = color.black33
            btn.text_color = color.white

def switch_to_country_time(country_name, utc_offset):
    global current_utc_offset
    
    if country_name == "UNITED KINGDOM" and current_utc_offset == 0:
        utc_offset = -3
        print(_("london_time_note"))
    
    animate_digital_roll(current_utc_offset, utc_offset, country_name)
    
    global time_panel_visible
    if time_explorer_panel and time_panel_visible:
        time_explorer_panel.visible = False
        time_panel_visible = False
        for btn in time_countries:
            btn.visible = False
    
    print(_("msg_time_switched_full").format(country_name, current_utc_offset))

def move_time_selection(direction):
    global selected_time_index, scroll_position
    
    if not time_panel_visible or not time_content:
        return
    
    old_index = selected_time_index
    selected_time_index = (selected_time_index + direction) % len(time_countries)
    
    update_time_selection()
    
    if direction == 1:
        target_scroll = scroll_position - 0.14
    else:
        target_scroll = scroll_position + 0.14
    
    max_scroll_up = 2.0
    max_scroll_down = -1.5
    target_scroll = max(max_scroll_down, min(max_scroll_up, target_scroll))

    if abs(target_scroll - scroll_position) > 0.01:
        time_content.animate_y(target_scroll, duration=0.15)
        scroll_position = target_scroll

def select_highlighted_time():
    if time_panel_visible and 0 <= selected_time_index < len(country_data):
        name, _, _, _, _, capital, utc = country_data[selected_time_index]
        switch_to_country_time(name, utc)

def create_timeline_ui():
    global timeline_panel, timeline_cube, timeline_era_positions
    
    timeline_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.8, 0.18),
        position=(0, 0.3),
        z=-5,
        visible=False
    )
    
    timeline_line = Entity(
        parent=timeline_panel,
        model='quad',
        color=color.gray,
        scale=(0.75, 0.01),
        position=(0, 0)
    )
    
    timeline_era_positions.clear()
    marker_width = 0.15
    start_x = -0.3
    
    for i, era in enumerate(history_eras):
        pos_x = start_x + i * marker_width
        timeline_era_positions.append(pos_x)
        
        Entity(
            parent=timeline_panel,
            model='circle',
            color=color.gold,
            scale=(0.02, 0.02),
            position=(pos_x, 0)
        )
        
        year = era['year']
        suffix = 'BCE' if year < 0 else 'CE'
        display_year = abs(year)
        
        btn = Button(
            parent=timeline_panel,
            text=str(display_year),
            color=color.clear,
            scale=(0.12, 0.08),
            position=(pos_x, -0.12),
            text_scale=1.5,
            text_color=color.white,
            highlight_color=color.clear,
            pressed_color=color.clear,
            on_click=dummy_click
        )
        btn.collider = None
    
    timeline_cube = Draggable(
        parent=timeline_panel,
        model='cube',
        color=color.gold,
        scale=(0.05, 0.05, 0.05),
        position=(timeline_era_positions[0], 0, -0.1),
        lock_y=True,
        lock_z=True,
        z=-0.2,
        unlit=True
    )
    
    print(_("timeline_created"))

def show_timeline():
    global timeline_visible
    
    if timeline_panel is None:
        create_timeline_ui()
    
    timeline_panel.visible = True
    timeline_cube.visible = True
    timeline_visible = True
    
    timeline_panel.y = -0.5
    timeline_panel.animate_y(0.3, duration=0.4)
    
    print(_("ui_timeline_open"))

def hide_timeline():
    global timeline_visible
    
    if timeline_panel:
        timeline_panel.animate_y(-0.5, duration=0.3)
        invoke(lambda: setattr(timeline_panel, 'visible', False), delay=0.31)
        timeline_cube.visible = False
    timeline_visible = False
    print(_("ui_timeline_closed"))

def update_timeline():
    global current_era_index
    
    if not timeline_visible:
        return
    
    cube_x = timeline_cube.x
    nearest_dist = 999
    nearest_index = 0
    
    for i, pos_x in enumerate(timeline_era_positions):
        dist = abs(cube_x - pos_x)
        if dist < nearest_dist:
            nearest_dist = dist
            nearest_index = i
    
    if nearest_dist < 0.02 and nearest_index != current_era_index:
        timeline_cube.x = timeline_era_positions[nearest_index]
        show_confirmation(nearest_index)

def enter_history_mode():
    global history_mode_active
    
    for dot in dots:
        dot.visible = False
    
    history_mode_active = True
    print(_("msg_history_active"))

def exit_history_mode():
    global history_mode_active
    
    if earth.texture.name == 'map.png':
        for dot in dots:
            dot.visible = True
    
    history_mode_active = False
    print(_("msg_history_disabled"))

def show_confirmation(era_index):
    global confirmation_panel, current_era_index
    
    current_era_index = era_index
    era = history_eras[era_index]
    
    if confirmation_panel:
        destroy(confirmation_panel)
    
    confirmation_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.6, 0.3),
        position=(0, 0),
        z=-10,
        unlit=True
    )
    
    title_btn = Button(
        parent=confirmation_panel,
        text=_("travel_question").format(era['name']),
        color=color.clear,
        scale=(0.5, 0.15),
        position=(0, 0.08),
        text_scale=1.8,
        text_color=color.white,
        highlight_color=color.clear,
        pressed_color=color.clear,
        on_click=dummy_click
    )
    title_btn.collider = None
    
    year = era['year']
    suffix = 'BCE' if year < 0 else 'CE'
    display_year = abs(year)
    
    year_btn = Button(
        parent=confirmation_panel,
        text=str(display_year) + " " + _(f"era_suffix_{suffix}"),
        color=color.clear,
        scale=(0.3, 0.08),
        position=(0, -0.02),
        text_scale=1.3,
        text_color=color.gold,
        highlight_color=color.clear,
        pressed_color=color.clear,
        on_click=dummy_click
    )
    year_btn.collider = None
    
    yes_btn = Button(
        parent=confirmation_panel,
        text=_("travel_yes"),
        color=color.green,
        scale=(0.25, 0.12),
        position=(-0.15, -0.15),
        text_scale=1.5,
        on_click=Func(confirm_era_travel, era_index)
    )
    
    no_btn = Button(
        parent=confirmation_panel,
        text=_("travel_no"),
        color=color.red,
        scale=(0.25, 0.12),
        position=(0.15, -0.15),
        text_scale=1.5,
        on_click=Func(cancel_confirmation)
    )

def confirm_era_travel(era_index):
    global confirmation_panel, history_mode_active
    
    if confirmation_panel:
        destroy(confirmation_panel)
        confirmation_panel = None
    
    era = history_eras[era_index]
    print(_("travel_start").format(era['name']))
    
    hide_timeline()
    
    camera.animate_z(camera.z - 3, duration=0.5, curve=curve.out_expo)
    fade_in(0.5)
    
    invoke(lambda: setattr(earth, 'texture', era['map_file']), delay=0.5)
    invoke(enter_history_mode, delay=0.5)
    
    invoke(lambda: camera.animate_z(camera.z + 3, duration=0.5, curve=curve.in_expo), delay=0.5)
    invoke(lambda: fade_overlay.animate_color(color.cyan.tint(0.2), duration=0.3), delay=0.5)
    invoke(fade_out, 0.5, delay=1.0)
    
    print(_("travel_complete").format(era['name']))

def cancel_confirmation():
    global confirmation_panel
    if confirmation_panel:
        destroy(confirmation_panel)
        confirmation_panel = None
    print(_("travel_cancelled"))

def toggle_compare_mode():
    global compare_mode_active, second_globe, divider
    
    if not history_mode_active:
        print(_("msg_compare_warning"))
        return
    
    if compare_mode_active:
        camera.animate_position((0, 0, -10), duration=0.4, curve=curve.in_expo)
        camera.animate_rotation((0, 0, 0), duration=0.4)
        
        earth.animate_x(0, duration=0.4)
        
        if second_globe:
            destroy(second_globe)
            second_globe = None
        if divider:
            destroy(divider)
            divider = None
        
        compare_mode_active = False
        print(_("compare_mode_off"))
        
    else:
        earth.animate_x(-5, duration=0.4)
        
        second_globe = Entity(
            model='sphere',
            texture='map.png',
            scale=3,
            position=(5, 0, 0),
            rotation=earth.rotation,
            unlit=True
        )
        
        camera.animate_position((0, 0, -20), duration=0.4, curve=curve.out_expo)
        camera.animate_rotation((0, 0, 0), duration=0.4)
        
        divider = Entity(
            parent=camera.ui,
            model='quad',
            color=color.white,
            scale=(0.005, 1.2),
            position=(0, 0),
            z=-5,
            unlit=True
        )
        divider.scale_x = 0.001
        divider.animate_scale_x(0.005, duration=0.3)
        
        compare_mode_active = True
        print(_("compare_mode_on"))

def toggle_journey():
    global journey_active, journey_sequence, journey_step, journey_ui_text, journey_paused
    
    if not history_mode_active:
        print(_("msg_journey_disabled"))
        return
    
    if journey_active or journey_paused:
        journey_active = False
        journey_paused = False
        journey_step = 0
        journey_sequence = []
        
        if journey_ui_text:
            destroy(journey_ui_text)
            journey_ui_text = None
        
        print(_("msg_journey_stopped"))
        return
    
    journey_active = True
    journey_paused = False
    journey_step = 0  
    
    current_year = history_eras[current_era_index]['year']
    sorted_eras = sorted(history_eras, key=lambda e: e['year'])
    current_pos = next(i for i, e in enumerate(sorted_eras) if e['year'] == current_year)
    
    if current_pos >= len(sorted_eras) // 2:
        journey_sequence = sorted_eras[current_pos::-1]
        print(_("msg_journey_backward"))
    else:
        journey_sequence = sorted_eras[current_pos:]
        print(_("msg_journey_forward"))

    next_journey_step()

def next_journey_step():
    global journey_step, journey_ui_text, journey_paused
    
    if not journey_active:
        return
    
    if journey_step >= len(journey_sequence):
        toggle_journey()
        return
    
    era = journey_sequence[journey_step]
    era_index = history_eras.index(era)
    
    fade_in(0.5)
    invoke(lambda: setattr(earth, 'texture', era['map_file']), delay=0.5)
    invoke(fade_out, 0.5, delay=1.0)
    
    landmarks = journey_landmarks_by_era.get(era_index)
    if not landmarks:
        landmarks = [(0, 0, "Unknown", 0, 0)]
    
    landmark_index = min(journey_step, len(landmarks)-1)
    landmark = landmarks[landmark_index]
    
    if len(landmark) == 5:
        px, py, name, lon_off, lat_off = landmark
    else:
        px, py, name = landmark
        lon_off, lat_off = 0, 0
    
    target_pos = Vec3(pixel_to_globe_surface(px, py, lon_off, lat_off))
    
    if journey_ui_text:
        destroy(journey_ui_text)
        journey_ui_text = None
    
    story = landmark_stories.get(name, "Explore this historical period.")
    
    year = era['year']
    suffix = 'BCE' if year < 0 else 'CE'
    display_year = abs(year)
    
    journey_ui_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.8, 0.4),
        position=(0, 0.2),
        z=-10
    )
    
    title_text = Text(
        parent=journey_ui_panel,
        text=_(f"era_name_{era_index}") + "\n📍 " + _(f"landmark_{name}"),
        position=(0.3, 0.12),
        scale=(1.8, 2.2), 
        color=color.gold,
        origin=(0.5, 0.5)
    )

    year_text = Text(
        parent=journey_ui_panel,
        text=str(display_year) + " " + _(f"era_suffix_{suffix}"),
        position=(0, 0.01),
        scale=(2.2, 2.6),  
        color=color.orange,
        origin=(0.5, 0.5)
    )  
    
    story_text = Text(
        parent=journey_ui_panel,
        text=_(f"story_{name.replace(' ', '_')}"),
        position=(0.3, -0.12),
        scale=(0.9, 1.1),
        color=color.white,
        origin=(0.5, 0.5)
    )
    
    button_y = -0.3
    
    stop_btn = Button(
        parent=camera.ui,
        text=_("journey_stop"),
        position=(-0.2, button_y),
        scale=(0.15, 0.07),
        color=color.orange,
        text_color=color.white,
        on_click=lambda: stop_journey_at_step(journey_ui_panel, stop_btn, skip_btn, continue_btn)
    )
    
    skip_btn = Button(
        parent=camera.ui,
        text=_("journey_skip"),
        position=(0, button_y),
        scale=(0.15, 0.07),
        color=color.red,
        text_color=color.white,
        on_click=lambda: skip_to_final_era(journey_ui_panel, stop_btn, skip_btn, continue_btn)
    )
    
    continue_btn = Button(
        parent=camera.ui,
        text=_("journey_continue"),
        position=(0.2, button_y),
        scale=(0.2, 0.07),
        color=color.green,
        text_color=color.white,
        visible=False,
        enabled=False,
        on_click=lambda: continue_journey(journey_ui_panel, stop_btn, skip_btn, continue_btn)
    )
    
    continue_btn.visible = True
    continue_btn.enabled = True
    
    invoke(lambda: auto_continue_journey(journey_ui_panel, stop_btn, skip_btn, continue_btn), delay=8.0)
    
    journey_ui_text = journey_ui_panel  
    
    camera_target_pos = target_pos + Vec3(0, 0, -8)
    camera.animate_position(camera_target_pos, duration=2.0)
    camera.animate_rotation((0, 0, 0), duration=2.0)
    invoke(lambda: camera.look_at(target_pos), delay=2.0)
    
    dot = Entity(
        parent=earth,
        model='sphere',
        color=color.cyan,
        scale=0.08,
        position=target_pos,
        unlit=True,
        alpha=1.0
    )
    destroy(dot, delay=7.9)  
    
    print(_("msg_journey_step").format(journey_step+1, len(journey_sequence), era['name'], name))
    
    journey_current_step_data = {
        'panel': journey_ui_panel,
        'stop_btn': stop_btn,
        'skip_btn': skip_btn,
        'continue_btn': continue_btn,
        'step': journey_step,
        'era': era
    }


def stop_journey_at_step(panel, stop_btn, skip_btn, continue_btn):
    """Pause journey at current step, show CONTINUE button"""
    global journey_paused
    
    print(_("journey_paused"))
    journey_paused = True
    
    stop_btn.visible = False
    stop_btn.enabled = False
    skip_btn.visible = False
    skip_btn.enabled = False
    
    continue_btn.visible = True
    continue_btn.enabled = True
    continue_btn.text = _("journey_continue")
    continue_btn.color = color.green

def skip_to_final_era(panel, stop_btn, skip_btn, continue_btn):
    """Skip entire journey to final era (1945)"""
    global journey_step, journey_active
    
    print(_("journey_skipped"))
    
    if panel:
        destroy(panel)
    destroy(stop_btn)
    destroy(skip_btn)
    destroy(continue_btn)
    
    final_era = history_eras[4] 
    fade_in(0.5)
    invoke(lambda: setattr(earth, 'texture', final_era['map_file']), delay=0.5)
    invoke(fade_out, 0.5, delay=1.0)
    
    journey_active = False
    journey_step = 0
    
    completion_text = Text(
        text=_("journey_skipped_message"),
        position=(0, 0.3),
        scale=2,
        color=color.orange,
        background=True,
        background_color=color.black66
    )
    destroy(completion_text, delay=3.0)
    
    print(_("msg_journey_final"))

def continue_journey(panel, stop_btn, skip_btn, continue_btn):
    """Continue journey to next step"""
    global journey_step, journey_paused
    
    print(_("journey_continuing"))
    journey_paused = False
    
    if panel:
        destroy(panel)
    destroy(stop_btn)
    destroy(skip_btn)
    destroy(continue_btn)
    
    journey_step += 1
    
    invoke(next_journey_step, delay=0.5)

def auto_continue_journey(panel, stop_btn, skip_btn, continue_btn):
    """Auto-continue if no button pressed (after 8 seconds)"""
    global journey_paused
    
    if journey_paused:
        return 
    
    print(_("journey_auto_continue"))
    
    if panel:
        destroy(panel)
    if stop_btn:
        destroy(stop_btn)
    if skip_btn:
        destroy(skip_btn)
    if continue_btn:
        destroy(continue_btn)
    
    global journey_step
    journey_step += 1
    
    invoke(next_journey_step, delay=0.5)

def activate_map_mode():
    global map_active, dots, ray_directions
    if map_active:
        return
    
    print(_("map_activating"))
    map_active = True
    earth.texture = 'map.png'
    
    print(_("map_placing_dots"))
    
    for name, pixel, lon_off, lat_off, col, capital, utc in country_data:
        pos = pixel_to_globe_surface(pixel[0], pixel[1], lon_offset=lon_off, lat_offset=lat_off)
        
        dot = Entity(
            parent=earth,
            model='sphere',
            color=col,
            scale=0.05,
            position=pos,
            collider='sphere',
            name=name,
            unlit=True
        )
        dots.append(dot)
        
        world_pos = earth.position + dot.position
        ray_dir = world_pos.normalized()
        ray_directions.append((name, ray_dir))
    
    print(_("map_rays_stored").format(len(ray_directions)))
    
    global search_field, suggestions_panel, suggestions
    if search_field:
        search_field.active = False
        search_field.visible = False
    if suggestions_panel:
        destroy(suggestions_panel)
        suggestions_panel = None
    suggestions.clear()
    
    print(_("msg_map_ready"))

def input(key):
    global map_active, typing_active, search_field, suggestions_panel

    if typing_active:
        if key in ['t', 's', 'h', 'escape']: 
            return  

    if escape_panel_visible and key != 'escape':
        return

    if not app_active:
        if key == 'escape':
            application.quit()
        return
  
    if not map_active:
        if key != 'm' and key != 'space':
            activate_map_mode()
        return

    if map_active:
        if key == 'escape':
            toggle_escape_menu()
            return

    if map_active:
        if key == 's':
            close_all_ui()
            toggle_settings_panel()
            return
    
    if map_active:
        if key == 't':
            close_all_ui()
            toggle_time_explorer()
            return

        if key == 'h':
            if history_mode_active:
                fade_in(0.4)
                invoke(lambda: setattr(earth, 'texture', 'map.png'), delay=0.4)
                invoke(exit_history_mode, delay=0.4)
                invoke(fade_out, 0.4, delay=0.8)
                print(_("msg_history_exited"))
            elif timeline_visible:
                hide_timeline()
            else:
                if map_active:
                    close_all_ui() 
                    show_timeline()
                else:
                    print(_("map_activate_first"))
            return
        
        if key == 'enter' and confirmation_panel:
            confirm_era_travel(current_era_index)
            return
        
        if key == 'escape' and confirmation_panel:
            cancel_confirmation()
            return

        if key == 'c' and history_mode_active:
            toggle_compare_mode()
            return

        if history_mode_active and key == 't':
            print(_("msg_time_disabled"))
            return
        
        if history_mode_active and len(key) == 1 and key.isprintable() and key not in 'h j':
            print(_("msg_search_disabled"))
            return
        
        if key == 'm' and history_mode_active:
            print(_("msg_map_disabled"))
            return
        
        if time_panel_visible:
            if key == 'up arrow':
                move_time_selection(-1)
                return
            if key == 'down arrow':
                move_time_selection(1)
                return
            if key == 'enter':
                select_highlighted_time()
                return
            if key == 'escape':
                toggle_time_explorer()
                return

        if key == 'j' and history_mode_active:
            toggle_journey()
            return
        
        if typing_active:
            if key in ['enter', 'escape']:
                pass
            elif len(key) == 1 and key.isprintable() and key not in 'm px t h j':
                if not search_field or not search_field.active:
                    start_search()
                invoke(update_suggestions, delay=1/60)
                return
            else:
                return

        if key == 'escape':
            for child in camera.ui.children:
                if hasattr(child, 'children'):
                    for subchild in child.children:
                        if hasattr(subchild, 'text') and subchild.text == 'ROADMAP & IDEAS':
                            destroy(child)  
                            return

        if key == 'escape':
            for child in camera.ui.children:
                if hasattr(child, 'text') and child.text == "ORBIT CONTROLS":
                    destroy(child)
                    return
        
        if key == 'm':
            if earth.texture.name == 'map.png':
                earth.texture = 'earth_texture.jpg'
                for dot in dots:
                    dot.visible = False
                if search_field:
                    search_field.visible = False
                    search_field.active = False
                if suggestions_panel:
                    destroy(suggestions_panel)
                    suggestions_panel = None
                    suggestions.clear()
                print(_("msg_texture_earth"))
            else:
                earth.texture = 'map.png'
                for dot in dots:
                    dot.visible = True
                if search_field:
                    search_field.visible = True
                print(_("msg_texture_map"))
        
        if key == 'c':
            camera.position = (0, 0, -10)
            camera.rotation = (0, 0, 0)
            print(_("msg_camera_reset"))
        
        if key == 'space':
            camera.position = (0, 0, -10)
            camera.rotation = (0, 0, 0)
            earth.rotation = (0, 0, 0)
            print(_("msg_view_reset"))
        
        if key == 'page up':
            camera.z += 1
        if key == 'page down':
            camera.z -= 1
        
        if len(key) == 1 and key.isprintable() and key not in 'm px t h j':
            close_all_ui()  
            if not search_field or not search_field.active:
                start_search()
            invoke(update_suggestions, delay=1/60)
            return
        
        if key == 'enter' and search_field and search_field.text.strip():
            query = search_field.text.strip()
            
            if query == "1983":
                trigger_1983_jumpscare()
                return
            
            if query.upper() == "SANS":
                trigger_sans_easter_egg()
                return

            if query == "1961":
                trigger_1961_gagarin_egg()
                return

            if query.upper() == "ORBIT":
                trigger_orbit_secret_egg()
                return
            
            query_lower = query.lower()
            matches = [name for name, _, _, _, _, _, _ in country_data if query_lower in name.lower()]
            if matches:
                select_country(matches[0])
        
        if key == 'escape' and search_field:
            search_field.active = False
            search_field.visible = False
            typing_active = False
            if suggestions_panel:
                destroy(suggestions_panel)
                suggestions_panel = None
            suggestions.clear()

def update():
    global afk_timer, game_mode, sun_watch_timer, sun_warning_active, sun_light 

    if game_mode == "multiplayer" and multiplayer_active:
        update_multiplayer()
        return

    if solar_system_active and current_planet == "sun":
        sun_distance = distance(camera.position, earth.position)
        
        DANGER_DISTANCE = 8
        CRITICAL_DISTANCE = 5
        
        if sun_distance < DANGER_DISTANCE:
            danger_level = 1 - ((sun_distance - CRITICAL_DISTANCE) / (DANGER_DISTANCE - CRITICAL_DISTANCE))
            danger_level = max(0, min(1, danger_level))
            
            red_intensity = danger_level * 0.7
            
            fade_overlay.enabled = True
            fade_overlay.visible = True
            fade_overlay.z = 999
            fade_overlay.color = color.red
            fade_overlay.alpha = red_intensity
            
            if sun_distance < CRITICAL_DISTANCE and not sun_warning_active:
                sun_warning_active = True
                
                fade_overlay.color = color.red
                fade_overlay.alpha = 1
                invoke(lambda: setattr(fade_overlay, 'alpha', 0.3), delay=0.2)
                
                warning_text = Text(
                    parent=camera.ui,
                    text="☀️ TOO CLOSE! ☀️",
                    position=(0,0),
                    scale=3,
                    color=color.white,
                    background=True,
                    background_color=Color(0,0,0,0.9),
                    z=100
                )
                destroy(warning_text, delay=2)
                
                def reset_warning():
                    global sun_warning_active
                    sun_warning_active = False
                invoke(reset_warning, delay=3)
        else:
            fade_overlay.alpha = max(0, fade_overlay.alpha - time.dt * 2)
            if fade_overlay.alpha < 0.01:
                fade_overlay.alpha = 0
                fade_overlay.color = color.black
                fade_overlay.enabled = False
                sun_warning_active = False

    if loading_active:
        update_loading()
        return

    if not app_active:
        return

    if settings.get('auto_rotate_enabled', False):
        earth.rotation_y += 10 * time.dt

    if timeline_visible:
        update_timeline()
    
    if timeline_visible and timeline_cube and timeline_era_positions:
        left = timeline_era_positions[0]
        right = timeline_era_positions[-1]
        
        if timeline_cube.x < left:
            timeline_cube.x = left
            timeline_cube.animate_x(left + 0.02, duration=0.1)
            timeline_cube.animate_x(left, duration=0.1)
        
        if timeline_cube.x > right:
            timeline_cube.x = right
            timeline_cube.animate_x(right - 0.02, duration=0.1)
            timeline_cube.animate_x(right, duration=0.1)
        
        timeline_cube.y = 0
        timeline_cube.z = -0.1
      
    if held_keys['left mouse']:
        earth.rotation_y += mouse.velocity[0] * 40
        earth.rotation_x -= mouse.velocity[1] * 40

    if compare_mode_active and second_globe:
        second_globe.rotation = earth.rotation
   
    if not (time_panel_visible or timeline_visible):
        globe_center = (0, 0, 0)
        current_dist = distance(camera.position, globe_center)
        zoom_speed = time.dt * 10
        min_dist = 5
        max_dist = 35

        if held_keys['up arrow'] and current_dist > min_dist:
            camera.position += camera.forward * zoom_speed
        if held_keys['down arrow'] and current_dist < max_dist:
            camera.position -= camera.forward * zoom_speed
        
        if held_keys['up arrow'] or held_keys['down arrow']:
            if not zoom_audio.playing:
                zoom_audio.play()
        else:
            if zoom_audio.playing:
                zoom_audio.stop()

    if map_active and not escape_panel_visible:
        if held_keys['left mouse'] or held_keys['up arrow'] or held_keys['down arrow'] or typing_active:
            afk_timer = 0
            if main_ambient.playing:
                main_ambient.stop()
        else:
            afk_timer += time.dt
            if afk_timer > AFK_THRESHOLD and not main_ambient.playing:
                main_ambient.play()
    else:
        if main_ambient.playing:
            main_ambient.stop()

print("\n" + "="*60)
print(_("startup_transition"))
print("="*60)
print(_("startup_texture_info"))
print(_("startup_click_info"))
print(_("startup_countries_info"))
print("="*60 + "\n")

def show_coming_soon():
    soon_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.85, 0.85),
        position=(0, 0),
        z=-20
    )
    
    Text(parent=soon_panel, text=_("roadmap_title"),
         position=(0, 0.38), scale=2.8, color=color.cyan)
    
    Text(parent=soon_panel, text=_("planned_by_team"),
         position=(-0.38, 0.28), scale=1.5, color=color.green)
    
    team_plans = [
        _("roadmap_alpha"),
        _("roadmap_beta"),
        _("roadmap_city_zoom"),
        _("roadmap_quiz"),
        _("roadmap_climate"),
        _("roadmap_population")
    ]
    
    for i, plan in enumerate(team_plans):
        Text(parent=soon_panel, text=plan,
             position=(-0.38, 0.18 - i*0.05),
             scale=0.85, color=color.white)
    
    Text(parent=soon_panel, text='USER SUGGESTIONS:',
         position=(0.05, 0.28), scale=1.5, color=color.orange)
    
    user_suggestions = [
        "🗳️ Vote at: zakkhhar@mail.ru",
        "(Your idea could be here!)",
        "Most requested:",
        "• Weather simulation",
        "• Night/day cycle",
        "• Country comparison tool",
        "• Export map images"
    ]
    
    for i, suggestion in enumerate(user_suggestions):
        Text(parent=soon_panel, text=suggestion,
             position=(0.05, 0.18 - i*0.05),
             scale=0.85, color=color.light_gray)
    
    Text(parent=soon_panel, 
         text=_("roadmap_footer"),
         position=(0, -0.35), scale=1.0, color=color.yellow)
    
    Text(parent=soon_panel,
         text=_("roadmap_footer_small"),
         position=(0, -0.4), scale=0.9, color=color.light_gray)
    
    close_btn = Button(
        parent=soon_panel,
        text=_("back_to_menu"),
        position=(0, -0.48),
        scale=(0.35, 0.1),
        color=color.dark_gray,
        text_color=color.white,
        highlight_color=color.cyan,
        on_click=lambda: destroy(soon_panel)
    )
    
    print(_("ui_coming_soon_open"))

support_panel_visible = False
credits_clicked_this_session = False
credits_popup_open = False

support_button = Button(
    parent=camera.ui,
    text=_("support_button"),
    scale=(0.06, 0.06),
    position=(0.78, 0.10),
    color=color.black,
    text_color=color.white,
    highlight_color=color.gray,
    on_click=lambda: toggle_support_panel()
)

support_button.enabled = False
support_button.visible = False

support_panel = Entity(
    parent=camera.ui,
    model='quad',
    color=color.black66,
    scale=(0.5, 0.4),
    position=(0, -0.6),
    origin=(0.5, 0),
    z=-10,
    enabled=False,
    visible=False
)

settings_panel = Entity(
    parent=camera.ui,
    model='quad',
    color=color.gray,         
    position=(0, 0),        
    scale=(0.5, 0.5),     
    origin=(0, 0),
    z=-5,
    visible=False,
    enabled=False
)

settings_panel_visible = False

import traceback
traceback.print_stack()
print("DEBUG: _ is", type(_))
print("DEBUG: _ contents:", _)

settings_title = Text(
    parent=settings_panel,
    text=_("settings_title"),
    position=(0.2, 0.48),
    origin=(0.5, 0.5),
    scale=2,
    color=color.rgb(169, 169, 169),
    z=-1
)

print("DEBUG: before line 2685, _ type =", type(_))

auto_rotate_enabled = False

auto_rotate_toggle = Button(
    parent=settings_panel,
    text=_("auto_rotate_toggle_off"),
    position=(0.15, 0.35),
    scale=(0.6, 0.08),
    color=color.black33,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.black,
    on_click=lambda: toggle_auto_rotate()
)

def toggle_auto_rotate():
    settings['auto_rotate_enabled'] = not settings['auto_rotate_enabled']
    
    if settings['auto_rotate_enabled']:
        auto_rotate_toggle.text = _("auto_rotate_toggle_on")
        print(_("audio_rotate_on"))
    else:
        auto_rotate_toggle.text = _("auto_rotate_toggle_off")
        print(_("audio_rotate_off"))
    
    save_settings()  

music_enabled = True

sound_enabled = True

sound_toggle = Button(
    parent=settings_panel,
    text=_("sound_toggle_on"),
    position=(0.15, 0.25),
    scale=(0.6, 0.08),
    color=color.black33,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.cyan,
    on_click=lambda: toggle_sound()
)

def toggle_sound():
    settings['sound_enabled'] = not settings.get('sound_enabled', True)
    
    if settings['sound_enabled']:
        sound_toggle.text = _("sound_toggle_on")
        if 'menu_music' in globals() and menu_music:
            menu_music.resume()
        main_ambient.volume = 1.0
        zoom_audio.volume = 1.0
        fade_audio.volume = 1.0
        pause_menu_audio.volume = 1.0
        print(_("audio_sound_on"))
    else:
        sound_toggle.text = _("sound_toggle_off")
        if 'menu_music' in globals() and menu_music:
            menu_music.pause()
        main_ambient.volume = 0
        zoom_audio.volume = 0
        fade_audio.volume = 0
        pause_menu_audio.volume = 0
        print(_("audio_sound_off"))
    
    save_settings()

default_texture_is_earth = True 

default_texture_toggle = Button(
    parent=settings_panel,
    text=_("default_texture_toggle_earth"),
    position=(0.15, 0.15),
    scale=(0.6, 0.08),
    color=color.black33,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.cyan,
    on_click=lambda: toggle_default_texture()
)

def toggle_default_texture():
    settings['default_texture_is_earth'] = not settings['default_texture_is_earth']
    
    if settings['default_texture_is_earth']:
        default_texture_toggle.text = _("default_texture_toggle_earth")
        print(_("settings_default_texture_earth"))
    else:
        default_texture_toggle.text = _("default_texture_toggle_map")
        print(_("settings_default_texture_map"))
    
    save_settings()  

loading_tips_enabled = True

loading_tips_toggle = Button(
    parent=settings_panel,
    text='[X] Loading Tips',
    position=(0.15, 0.05),
    scale=(0.6, 0.08),
    color=color.black33,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.cyan,
    on_click=lambda: toggle_loading_tips()
)

def toggle_loading_tips():
    settings['loading_tips_enabled'] = not settings['loading_tips_enabled']
    
    if settings['loading_tips_enabled']:
        loading_tips_toggle.text = '[X] Loading Tips'
        print(_("audio_loading_tips_on"))
    else:
        loading_tips_toggle.text = '[ ] Loading Tips'
        print(_("audio_loading_tips_off"))
    
    save_settings()  

orbit_doctor_button = Button(
    parent=settings_panel,
    text=_("orbit_doctor"),
    position=(0.15, -0.05),
    scale=(0.6, 0.08),
    color=color.black33,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.orange,
    on_click=lambda: open_orbit_doctor()
)

def open_orbit_doctor():
    doctor_panel = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.7, 0.9),
        position=(0, 0),
        z=-20
    )
    
    Text(
        parent=doctor_panel,
        text=_("doctor_title"),
        position=(0, 0.40),
        scale=2,
        color=color.cyan,
        origin=(0.5, 0.5)
    )
    
    diagnostics = []
    
    if earth.enabled:
        diagnostics.append(_("doctor_globe_loaded") if earth.enabled else _("doctor_globe_not_loaded"))
    else:
        diagnostics.append("❌ Globe not loaded")
    
    if len(country_data) > 0:
        diagnostics.append(_("doctor_countries_loaded").format(len(country_data)))
    else:
        diagnostics.append(_("doctor_countries_empty"))
    
    if len(dots) > 0:
        diagnostics.append(_("doctor_dots_placed").format(len(dots)))
    else:
        diagnostics.append(_("doctor_dots_missing"))
    
    diagnostics.append(_("doctor_camera_pos").format(camera.position))
    diagnostics.append(_("doctor_camera_rot").format(camera.rotation))
    
    tex_name = earth.texture.name if earth.texture else "None"
    diagnostics.append(_("doctor_texture").format(tex_name))
    
    diagnostics.append(_("doctor_map_active").format(map_active))
    
    diagnostics.append(_("doctor_history_mode").format(history_mode_active))
    
    diagnostics.append(_("doctor_compare_mode").format(compare_mode_active))
    
    diagnostics.append(_("doctor_time_panel").format(time_panel_visible))
    
    diagnostics.append(_("doctor_escape_menu").format(escape_panel_visible))

    diagnostics.append(_("doctor_settings_open").format(settings_panel_visible))
    
    if 'menu_music' in globals() and menu_music:
        diagnostics.append(_("doctor_menu_music_loaded") if menu_music else _("doctor_menu_music_not_loaded"))
    
    for i, msg in enumerate(diagnostics):
        Text(
            parent=doctor_panel,
            text=msg,
            position=(-0.32, 0.25 - i * 0.045),
            scale=0.8,
            color=color.white,
            origin=(0, 0.5)
        )
    
    clear_errors_btn = Button(
        parent=doctor_panel,
        text=_("doctor_clear_errors"),
        position=(0, -0.35),
        scale=(0.35, 0.08),
        color=color.orange,
        text_color=color.white,
        highlight_color=color.gold,
        on_click=lambda: clear_errors(doctor_panel)
    )
    
    close_btn = Button(
        parent=doctor_panel,
        text=_("doctor_close"),
        position=(0, -0.45),
        scale=(0.25, 0.08),
        color=color.red,
        text_color=color.white,
        on_click=lambda: destroy(doctor_panel)
    )

def clear_errors(panel):
    fixes_applied = []
    
    if abs(camera.z) > 30 or camera.position == (0, 0, 0):
        camera.position = (0, 0, -10)
        camera.rotation = (0, 0, 0)
        fixes_applied.append(_("doctor_fix_camera"))
    
    if not earth.enabled:
        earth.enabled = True
        fixes_applied.append(_("doctor_fix_globe"))
    
    global compare_mode_active, second_globe, divider
    if compare_mode_active:
        compare_mode_active = False
        if second_globe:
            destroy(second_globe)
            second_globe = None
        if divider:
            destroy(divider)
            divider = None
        fixes_applied.append(_("doctor_fix_compare"))
    
    global time_panel_visible, timeline_visible, escape_panel_visible
    if time_panel_visible and time_explorer_panel:
        time_explorer_panel.x = 1.5
        time_explorer_panel.visible = False
        time_panel_visible = False
        fixes_applied.append(_("doctor_fix_time"))
    
    if timeline_visible and timeline_panel:
        timeline_panel.visible = False
        timeline_visible = False
        fixes_applied.append(_("doctor_fix_timeline"))
    
    if escape_panel_visible:
        escape_panel.x = 1.5
        escape_panel.visible = False
        escape_panel_visible = False
        fixes_applied.append(_("doctor_fix_escape"))
    
    if earth.texture and earth.texture.name == 'map.png':
        for dot in dots:
            dot.visible = True
        fixes_applied.append(_("doctor_fix_dots"))

    global typing_active, search_field, suggestions_panel
    if typing_active and search_field:
        search_field.active = False
        search_field.visible = False
        typing_active = False
        if suggestions_panel:
            destroy(suggestions_panel)
            suggestions_panel = None
        fixes_applied.append(_("doctor_fix_search"))
    
    global confirmation_panel
    if confirmation_panel:
        destroy(confirmation_panel)
        confirmation_panel = None
        fixes_applied.append(_("doctor_fix_confirmation"))

    if fixes_applied:
        feedback_text = _("doctor_fixed_prefix") + "\n".join(_("doctor_fixed_item").format(fix) for fix in fixes_applied)
        print("🛠️ Clear All Errors applied:", fixes_applied)
    else:
        feedback_text = _("doctor_no_errors")
        print("🛠️ No errors found")
    
    feedback = Text(
        parent=panel,
        text=feedback_text,
        position=(0, -0.25),
        scale=0.9,
        color=color.green,
        origin=(0.5, 0.5)
    )
    destroy(feedback, delay=3.0)

reset_settings_button = Button(
    parent=settings_panel,
    text=_("reset_settings"),
    position=(0.15, -0.15),
    scale=(0.6, 0.08),
    color=color.dark_gray,
    text_color=color.white,
    text_scale=0.8,
    highlight_color=color.orange,
    on_click=lambda: reset_settings()
)

def reset_settings():
    global settings
    settings = DEFAULT_SETTINGS.copy()
    save_settings()
    
    sound_toggle.text = _("sound_toggle_on")
    auto_rotate_toggle.text = _("auto_rotate_toggle_off")
    default_texture_toggle.text = _("default_texture_toggle_earth")
    loading_tips_toggle.text = _("loading_tips_toggle_on")
    
    if 'menu_music' in globals() and menu_music and settings['sound_enabled']:
        menu_music.resume()
    elif 'menu_music' in globals() and menu_music and not settings['sound_enabled']:
        menu_music.pause()
    
    print(_("settings_reset"))
    
    feedback = Text(
        parent=settings_panel,
        text=_("reset_feedback"),
        position=(0.5, -0.15),
        scale=1.0,
        color=color.orange,
        origin=(0.5, 0.5)
    )
    destroy(feedback, delay=1.5)

escape_panel = Entity(
    parent=camera.ui,
    model='quad',
    color=color.gray.tint(-0.3), 
    scale=(0.5, 0.7),             
    position=(1.5, 0.0),         
    origin=(0, 0),                
    z=-15,
    visible=False,
    enabled=False
)

escape_panel_visible = False

escape_title = Text(
    parent=escape_panel,
    text=_("paused"),
    position=(0.11, 0.45),
    origin=(0.5, 0.5),
    scale=2.5,
    color=color.white,
    z=-13  
)

resume_btn = Button(
    parent=escape_panel,
    text=_("resume"),
    position=(0, 0.2),
    scale=(0.4, 0.12),
    color=color.dark_gray,
    text_color=color.white,
    highlight_color=color.light_gray,
    on_click=lambda: toggle_escape_menu()
)

def quit_to_menu():
    print(_("quit_to_menu_message"))
    if escape_panel_visible:
        toggle_escape_menu()
    
    fade_in(0.5)
    invoke(return_to_main_menu, delay=0.5)

def return_to_main_menu():
    global app_active, current_menu
    
    app_active = False
    
    if current_menu:
        destroy(current_menu)
        current_menu = None
    
    for child in list(camera.ui.children):
        child.enabled = False
    earth.enabled = False
    
    create_main_menu()
    
    fade_out(0.5)

menu_btn = Button(
    parent=escape_panel,
    text=_("quit_to_menu"),
    position=(0, 0.0),
    scale=(0.4, 0.12),
    color=color.dark_gray,
    text_color=color.white,
    highlight_color=color.orange,
    on_click=quit_to_menu
)

desktop_btn = Button(
    parent=escape_panel,
    text=_("quit_to_desktop"),
    position=(0, -0.2),
    scale=(0.4, 0.12),
    color=color.dark_gray,
    text_color=color.white,
    highlight_color=color.red,
    on_click=application.quit
)

def toggle_support_panel():
    global support_panel_visible
    
    if support_panel_visible:
        support_panel.animate_y(-0.6, duration=0.3, curve=curve.out_sine)
        invoke(lambda: setattr(support_panel, 'visible', False), delay=0.31)
        support_panel_visible = False
        global credits_clicked_this_session
        credits_clicked_this_session = False 
        print(_("ui_support_closed"))
    else:
        support_panel.y = -0.6
        support_panel.visible = True
        support_panel.enabled = True
        support_panel.animate_y(-0.15, duration=0.3, curve=curve.out_sine)
        support_panel_visible = True
        print("🛈 Support opened")

        buttons = [report_bug_button, version_button, credits_button]
        for i, btn in enumerate(buttons):
            btn.scale_y = 0.01 
            invoke(lambda b=btn: b.animate_scale_y(0.1, duration=0.2, curve=curve.out_back), delay=i*0.08)

report_bug_button = Button(
    parent=support_panel,
    text=_("report_bug"),
    scale=(0.4, 0.1),
    position=(-0.60, 0.4),
    color=color.dark_gray,
    text_color=color.white,
    on_click=lambda: open_email()
)

version_button = Button(
    parent=support_panel,
    text=_("version"),
    scale=(0.4, 0.1),
    position=(-0.60, -0.07 ),
    color=color.black33,
    text_color=color.light_gray,
    highlight_color=color.black33,
    on_click=lambda: None
)
version_button.collider = None


credits_button = Button(
    parent=support_panel,
    text=_("credits"),
    scale=(0.4, 0.1),
    position=(-0.60, -0.21 ),
    color=color.dark_gray,
    text_color=color.white,
    on_click=lambda: show_credits()
)

import webbrowser

def open_email():
    recipient = "zakkhhar@mail.ru"
    subject = _("bug_report_subject")
    body = _("bug_report_body")
    
    url = f"https://e.mail.ru/compose/?to={recipient}&subject={subject}&body={body}"
    
    webbrowser.open_new(url)
    print("📧 Opening mail.ru compose...")

def show_credits():
    global credits_clicked_this_session, credits_popup_open
    
    if credits_popup_open:  
        return
    
    credits_clicked_this_session = True
    credits_popup_open = True
    
    credits_popup = Entity(
        parent=camera.ui,
        model='quad',
        color=color.black66,
        scale=(0.7, 0.5),
        position=(0, 0),
        z=-20
    )
    
    Text(
        parent=credits_popup,
        text=_("credits_title") + "\n\n" + _("credits_created") + "\n" + _("credits_description"),
        scale=1.5,
        color=color.white,
        origin=(-0.3, -0.2) 
    )
    
    def close_credits():
        destroy(credits_popup)
        global credits_popup_open
        credits_popup_open = False
    
    close_btn = Button(
        parent=credits_popup,
        text=_("credits_close"),
        scale=(0.2, 0.08),
        position=(0, -0.2),
        on_click=close_credits
    )
    
    print(_("ui_credits_shown"))

def toggle_escape_menu():
    global escape_panel_visible
    
    if not escape_panel_visible:
        for btn in [resume_btn, menu_btn, desktop_btn]:
            btn.enabled = True
            btn.color = color.dark_gray
        
        escape_panel.x = 1.5
        escape_panel.visible = True
        escape_panel.enabled = True
        escape_panel.animate_x(0.7, duration=0.4, curve=curve.out_back)
        escape_panel_visible = True

        if not pause_menu_audio.playing:
            pause_menu_audio.play()

        print(_("ui_escape_open"))
    else:
        escape_panel.animate_x(1.5, duration=0.3, curve=curve.in_sine)
        invoke(lambda: setattr(escape_panel, 'visible', False), delay=0.31)
        escape_panel_visible = False

        if pause_menu_audio.playing:
            pause_menu_audio.stop()

        print(_("ui_escape_closed"))

def close_all_ui():
    global typing_active, time_panel_visible, settings_panel_visible
    global escape_panel_visible, timeline_visible, support_panel_visible
    
    if typing_active:
        typing_active = False
        if search_field:
            search_field.active = False
            search_field.visible = False
        global suggestions_panel
        if suggestions_panel:
            destroy(suggestions_panel)
            suggestions_panel = None
        print(_("ui_search_closed"))
    
    if time_panel_visible:
        toggle_time_explorer()  
    
    if settings_panel_visible:
        toggle_settings_panel()
    
    if timeline_visible:
        hide_timeline()
    
    if support_panel_visible:
        toggle_support_panel()
    
    global confirmation_panel
    if confirmation_panel:
        destroy(confirmation_panel)
        confirmation_panel = None
    
    for child in list(camera.ui.children):
        if hasattr(child, 'text') and child.text == 'Orbit Doctor':
            destroy(child)
    
    print(_("ui_all_closed"))

last_settings_toggle = 0

def toggle_settings_panel():
    global settings_panel_visible, last_settings_toggle
    
    if time.time() - last_settings_toggle < 1.0:
        print(_("settings_cooldown"))
        return
    
    last_settings_toggle = time.time()
    
    if not settings_panel_visible:
        settings_panel.x = 1.5
        settings_panel.visible = True
        settings_panel.enabled = True
        settings_panel.animate_x(0.65, duration=0.3, curve=curve.out_sine)
        settings_panel_visible = True
        print(_("ui_settings_open"))
        
    else:
        settings_panel.animate_x(1.5, duration=0.3, curve=curve.out_sine)
        invoke(lambda: setattr(settings_panel, 'visible', False), delay=0.31)
        settings_panel_visible = False
        print(_("ui_settings_closed"))

create_clock_ui()
app.run()
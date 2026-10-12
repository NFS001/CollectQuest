"""
CollectQuest – Simple Version
==============================
Collect all required shapes before time runs out!
You have 5 hearts. Traps and enemies hurt you.

CONTROLS:
  W / S          : move forward / backward
  A / D          : move left / right
  Arrow LEFT/RIGHT: orbit camera
  Q / E          : rotate gun
  SPACE or LEFT CLICK : shoot
  C              : change camera (top-down, angled, first-person)
  R              : restart
"""

from OpenGL.GL import *
from OpenGL.GLUT import *
from OpenGL.GLU import *
import random
import math
import time

# ─────────────────────────────────────────────────────────────
#  WINDOW SIZE
# ─────────────────────────────────────────────────────────────
WINDOW_W = 1000
WINDOW_H = 800

# ─────────────────────────────────────────────────────────────
#  GAME NUMBERS
# ─────────────────────────────────────────────────────────────
TILE_SIZE         = 90       # size of each floor tile
BASE_RENDER_RAD   = 7        # how many tiles around player are shown
BLIND_RENDER_RAD  = 1        # render radius when blind trap is active
GAME_DURATION     = 180      # seconds to finish the game
BASE_MOVE_SPEED   = 0.12     # normal movement speed
MAX_HEALTH        = 5        # starting hearts

ITEM_PROB         = 0.08     # 8% chance a new tile has a collectible
POWERUP_PROB      = 0.15     # 15% chance a new tile has a power-up

# Trap chance increases with level
TRAP_PROB_BY_LEVEL = {1: 0.15, 2: 0.25, 3: 0.40}

# ─────────────────────────────────────────────────────────────
#  SHAPE GOALS  –  how many of each shape to collect
# ─────────────────────────────────────────────────────────────
SHAPE_QUOTA = {
    "sphere":  3,
    "cube":    2,
    "cone":    2,
    "torus":   2,
    "diamond": 3,
    "star":    3,
}
SHAPES = list(SHAPE_QUOTA.keys())

SHAPE_COLOR = {
    "sphere":  (0.90, 0.20, 0.95),
    "cube":    (0.20, 0.85, 1.00),
    "cone":    (1.00, 0.50, 0.00),
    "torus":   (0.10, 1.00, 0.55),
    "diamond": (1.00, 0.92, 0.10),
    "star":    (1.00, 0.35, 0.55),
}

# ─────────────────────────────────────────────────────────────
#  TRAP TYPES
# ─────────────────────────────────────────────────────────────
TRAP_TYPES  = ["damage", "slow", "blind", "score"]
TRAP_COLORS = {
    "damage": (0.85, 0.05, 0.05),
    "slow":   (0.95, 0.80, 0.05),
    "blind":  (0.55, 0.05, 0.85),
    "score":  (0.05, 0.45, 0.90),
}
TRAP_LABELS = {
    "damage": "DMG  -1 heart",
    "slow":   "SLOW  blocks W/S 5s",
    "blind":  "BLIND fog 4s",
    "score":  "SCORE -2 items",
}

# ─────────────────────────────────────────────────────────────
#  POWER-UP TYPES
# ─────────────────────────────────────────────────────────────
POWERUP_TYPES  = ["shield", "reveal"]
POWERUP_COLORS = {
    "shield": (0.10, 0.60, 1.00),
    "reveal": (1.00, 0.90, 0.10),
}
POWERUP_LABELS = {
    "shield": "SHIELD  trap immune 5s",
    "reveal": "REVEAL  area revealed",
}

# ─────────────────────────────────────────────────────────────
#  CAMERA
# ─────────────────────────────────────────────────────────────
CAMERA_MODES    = ["top_down", "angled", "first_person"]
camera_mode_idx = 1       # start in angled mode
camera_angle    = 45.0    # orbit angle in degrees
fovY            = 60.0
CAMERA_DIST     = 550.0
CAMERA_HEIGHT   = 480.0

# ─────────────────────────────────────────────────────────────
#  ENEMY NUMBERS
# ─────────────────────────────────────────────────────────────
ENEMY_SPAWN_PROGRESS = 0.40   # enemies appear after 40% progress
ENEMY_BASE_SPEED     = 0.008
ENEMY_FAST_SPEED     = 0.016
ENEMY_SHOOT_RANGE    = 400.0
ENEMY_SHOOT_CD       = 2.5    # enemy shoots every 2.5 seconds
BULLET_HIT_RADIUS    = 40.0
PLAYER_SHOOT_CD      = 0.6    # player can shoot every 0.6 seconds

# Gun position numbers
GUN_BASE_DIST = 18.0
GUN_LENGTH    = 42.0
GUN_HEIGHT    = 52.0
GUN_TIP_DIST  = GUN_BASE_DIST + GUN_LENGTH

# ─────────────────────────────────────────────────────────────
#  GAME STATE VARIABLES
# ─────────────────────────────────────────────────────────────
player_grid         = [0, 0]          # tile position (col, row)
player_world        = [0.0, 0.0]      # smooth world position
player_target_world = [0.0, 0.0]      # where we are moving to
player_facing       = 0.0             # rotation in degrees
player_moving       = False
move_progress       = 0.0
move_speed          = BASE_MOVE_SPEED

player_health   = MAX_HEALTH
shape_collected = {s: 0 for s in SHAPES}
tiles_collected = 0                   # total tiles collected (never goes down)

game_state    = "playing"             # "playing", "win", "lose_hp", "lose_time"
start_time    = time.time()
time_left     = float(GAME_DURATION)
current_level = 1

status_effects = []   # list of {"type": ..., "until": ...}
tile_map  = {}        # stores all generated tiles
anim_time = 0.0       # increases each frame, used for animations

flash_color = (0.0, 0.0, 0.0, 0.0)   # screen flash color (r, g, b, a)
flash_until = 0.0

event_msg       = ""      # short message shown in middle of screen
event_msg_until = 0.0

enemies   = []   # list of enemy dicts
bullets   = []   # enemy bullets
p_bullets = []   # player bullets

gun_acquired       = False
gun_relative_angle = 0.0   # extra rotation from Q/E
last_player_shot   = 0.0


# ─────────────────────────────────────────────────────────────
#  STATUS EFFECTS
# ─────────────────────────────────────────────────────────────
def has_effect(etype):
    now = time.time()
    for e in status_effects:
        if e["type"] == etype and e["until"] > now:
            return True
    return False


def add_effect(etype, duration):
    global status_effects
    now = time.time()
    # Remove old copy of this effect first
    status_effects = [e for e in status_effects if e["type"] != etype]
    status_effects.append({"type": etype, "until": now + duration})


def tick_effects():
    global status_effects, move_speed
    now = time.time()
    status_effects = [e for e in status_effects if e["until"] > now]
    move_speed = BASE_MOVE_SPEED


# ─────────────────────────────────────────────────────────────
#  LEVEL & PROGRESS
# ─────────────────────────────────────────────────────────────
def total_target():
    return sum(SHAPE_QUOTA.values())


def total_collected():
    return sum(shape_collected.values())


def progress_fraction():
    total = total_target()
    if total == 0:
        return 0.0
    return min(1.0, tiles_collected / total)


def update_level():
    global current_level
    p = progress_fraction()
    if p >= 0.70:
        current_level = 3
    elif p >= 0.40:
        current_level = 2
    else:
        current_level = 1


def trap_prob():
    return TRAP_PROB_BY_LEVEL[current_level]


# ─────────────────────────────────────────────────────────────
#  TILE HELPERS
# ─────────────────────────────────────────────────────────────
def choose_item_shape():
    # Pick a shape that the player still needs more of
    needed = []
    for shape in SHAPES:
        if shape_collected[shape] < SHAPE_QUOTA[shape]:
            needed.append(shape)
    if len(needed) > 0:
        return random.choice(needed)
    return random.choice(SHAPES)


def tile_dist(c1, r1, c2, r2):
    return math.sqrt((c1 - c2) ** 2 + (r1 - r2) ** 2)


def get_tile(col, row):
    """
    Return the tile at (col, row). If it does not exist yet, create it.
    Tiles are created randomly as: item, powerup, trap, or safe.
    """
    key = (col, row)
    if key not in tile_map:
        # Starting tile is always safe
        if col == 0 and row == 0:
            tile_map[key] = {
                "revealed": True, "visible": True, "type": "safe",
                "trap_type": None, "shape": None, "powerup": None,
            }
            return tile_map[key]

        r = random.random()

        if r < ITEM_PROB:
            tile_map[key] = {
                "revealed": False, "visible": False, "type": "item",
                "trap_type": None, "shape": choose_item_shape(), "powerup": None,
            }
        elif r < ITEM_PROB + POWERUP_PROB:
            tile_map[key] = {
                "revealed": False, "visible": False, "type": "powerup",
                "trap_type": None, "shape": None, "powerup": random.choice(POWERUP_TYPES),
            }
        elif r < ITEM_PROB + POWERUP_PROB + trap_prob():
            tile_map[key] = {
                "revealed": False, "visible": False, "type": "trap",
                "trap_type": random.choice(TRAP_TYPES), "shape": None, "powerup": None,
            }
        else:
            tile_map[key] = {
                "revealed": False, "visible": False, "type": "safe",
                "trap_type": None, "shape": None, "powerup": None,
            }

    # Ensure visible key always exists (safety for any tile missing it)
    if "visible" not in tile_map[key]:
        tile_map[key]["visible"] = tile_map[key]["revealed"]

    return tile_map[key]


def set_event(msg, duration=2.5):
    global event_msg, event_msg_until
    event_msg       = msg
    event_msg_until = time.time() + duration


def apply_trap(trap_type):
    global player_health, game_state, flash_color, flash_until

    if has_effect("shield"):
        set_event("SHIELD blocked the trap!", 2.0)
        return

    if trap_type == "damage":
        player_health -= 1
        flash_color = (0.8, 0.0, 0.0, 0.5)
        flash_until = time.time() + 0.4
        set_event("! DAMAGE  -1 heart")
        if player_health <= 0:
            game_state = "lose_hp"

    elif trap_type == "slow":
        add_effect("slow", 5.0)
        flash_color = (0.8, 0.75, 0.0, 0.35)
        flash_until = time.time() + 0.4
        set_event("~ SLOW  W/S blocked for 5s  (use A/D)")

    elif trap_type == "blind":
        add_effect("blind", 4.0)
        flash_color = (0.3, 0.0, 0.6, 0.55)
        flash_until = time.time() + 0.5
        set_event("* BLIND  fog of war 4s")

    elif trap_type == "score":
        deducted = 0
        candidates = [s for s in SHAPES if shape_collected[s] > 0]
        random.shuffle(candidates)
        for s in candidates:
            if deducted >= 2:
                break
            shape_collected[s] = max(0, shape_collected[s] - 1)
            deducted += 1
        flash_color = (0.0, 0.25, 0.75, 0.40)
        flash_until = time.time() + 0.4
        set_event(f"$ SCORE  -{deducted} item(s) lost")


def apply_powerup(ptype, col, row):
    global flash_color, flash_until
    flash_until = time.time() + 0.4

    if ptype == "shield":
        add_effect("shield", 5.0)
        flash_color = (0.0, 0.5, 1.0, 0.35)
        set_event("** SHIELD  trap immunity 5s")

    elif ptype == "reveal":
        for dc in range(-3, 4):
            for dr in range(-3, 4):
                if math.sqrt(dc * dc + dr * dr) <= 3.5:
                    # Only mark as visible (shows on floor) NOT as revealed.
                    # revealed=True would make reveal_tile() skip the tile,
                    # so traps and items would never trigger when stepped on.
                    get_tile(col + dc, row + dr)["visible"] = True
        flash_color = (1.0, 0.9, 0.0, 0.35)
        set_event(".. REVEAL  area revealed")


def reveal_tile(col, row):
    """Called when player steps onto a tile. Applies effects."""
    global game_state, tiles_collected
    tile = get_tile(col, row)
    if tile["revealed"]:
        return
    tile["revealed"] = True
    tile["visible"]  = True   # also mark visible so drawing uses the right colour
    if game_state != "playing":
        return

    if tile["type"] == "trap":
        apply_trap(tile["trap_type"])

    elif tile["type"] == "item":
        shape = tile["shape"]
        shape_collected[shape] += 1
        tiles_collected += 1
        tile["type"] = "collected"
        if all(shape_collected[s] >= SHAPE_QUOTA[s] for s in SHAPES):
            game_state = "win"

    elif tile["type"] == "powerup":
        apply_powerup(tile["powerup"], col, row)
        tile["type"] = "collected"


# ─────────────────────────────────────────────────────────────
#  ENEMY SYSTEM
# ─────────────────────────────────────────────────────────────
def enemy_move_speed():
    if current_level >= 3:
        return ENEMY_FAST_SPEED
    return ENEMY_BASE_SPEED


def maybe_spawn_enemies():
    global gun_acquired
    if progress_fraction() < ENEMY_SPAWN_PROGRESS:
        return
    max_enemies = current_level + 1
    if len(enemies) >= max_enemies:
        return

    for _ in range(50):
        angle = random.uniform(0, 2 * math.pi)
        d     = random.uniform(2, 14)
        col   = int(player_grid[0] + math.cos(angle) * d)
        row   = int(player_grid[1] + math.sin(angle) * d)
        enemies.append({
            "x": float(col * TILE_SIZE),
            "y": float(row * TILE_SIZE),
            "health": 2,
            "last_shot": time.time() - random.uniform(0, ENEMY_SHOOT_CD),
            "patrol_angle": random.uniform(0, 2 * math.pi),
        })
        if not gun_acquired:
            gun_acquired = True
            set_event("!! ENEMIES INCOMING  SPACE = shoot", 4.0)
        break


def update_enemies():
    global player_health, game_state
    now    = time.time()
    px, py = player_world
    spd    = enemy_move_speed()

    for e in enemies:
        dx   = px - e["x"]
        dy   = py - e["y"]
        dist = math.sqrt(dx * dx + dy * dy)

        if dist > 0:
            # Chase player
            chase = 0.7 if current_level >= 3 else 0.35
            e["x"] += (dx / dist) * spd * TILE_SIZE * chase
            e["y"] += (dy / dist) * spd * TILE_SIZE * chase
            # Small patrol movement added on top
            e["patrol_angle"] += 0.02
            e["x"] += math.cos(e["patrol_angle"]) * spd * TILE_SIZE * 0.3
            e["y"] += math.sin(e["patrol_angle"]) * spd * TILE_SIZE * 0.3

        # Enemy shoots if close enough and cooldown passed
        if dist < ENEMY_SHOOT_RANGE and now - e["last_shot"] > ENEMY_SHOOT_CD:
            e["last_shot"] = now
            if dist > 0:
                spd_b = 3.5 if current_level >= 3 else 2.5
                bullets.append({
                    "x": e["x"], "y": e["y"],
                    "vx": (dx / dist) * spd_b * TILE_SIZE * 0.06,
                    "vy": (dy / dist) * spd_b * TILE_SIZE * 0.06,
                })


def update_bullets():
    global player_health, game_state, flash_color, flash_until
    px, py = player_world

    # Enemy bullets – hurt player
    for b in bullets[:]:
        b["x"] += b["vx"]
        b["y"] += b["vy"]
        dx = b["x"] - px
        dy = b["y"] - py
        if math.sqrt(dx * dx + dy * dy) < BULLET_HIT_RADIUS:
            if not has_effect("shield"):
                player_health -= 1
                flash_color = (0.8, 0.0, 0.0, 0.6)
                flash_until = time.time() + 0.4
                set_event("! Enemy hit  -1 heart", 2.0)
                if player_health <= 0:
                    game_state = "lose_hp"
            if b in bullets:
                bullets.remove(b)
            continue
        if abs(b["x"] - px) > 1400 or abs(b["y"] - py) > 1400:
            if b in bullets:
                bullets.remove(b)

    # Player bullets – hurt enemies
    for b in p_bullets[:]:
        b["x"] += b["vx"]
        b["y"] += b["vy"]
        hit = False
        for e in enemies[:]:
            dx = b["x"] - e["x"]
            dy = b["y"] - e["y"]
            if math.sqrt(dx * dx + dy * dy) < BULLET_HIT_RADIUS:
                e["health"] -= 1
                if e["health"] <= 0 and e in enemies:
                    enemies.remove(e)
                    spawn_replacement_enemy()
                hit = True
                break
        if hit or abs(b["x"] - px) > 1400 or abs(b["y"] - py) > 1400:
            if b in p_bullets:
                p_bullets.remove(b)


def spawn_replacement_enemy():
    """Spawn a new enemy far from player after killing one."""
    for _ in range(60):
        angle = random.uniform(0, 2 * math.pi)
        d     = random.uniform(10, 18)
        col   = int(player_grid[0] + math.cos(angle) * d)
        row   = int(player_grid[1] + math.sin(angle) * d)
        enemies.append({
            "x": float(col * TILE_SIZE),
            "y": float(row * TILE_SIZE),
            "health": 2,
            "last_shot": time.time() + 1.5,
            "patrol_angle": random.uniform(0, 2 * math.pi),
        })
        set_event("!! New enemy spawned!", 2.0)
        break


# ─────────────────────────────────────────────────────────────
#  GUN HELPERS
# ─────────────────────────────────────────────────────────────
def player_forward_angle():
    # When player_facing = 0, forward is +Y direction = 90 degrees in math
    return (90 + player_facing) % 360


def actual_gun_angle():
    return (player_forward_angle() + gun_relative_angle) % 360


def gun_direction():
    angle = math.radians(actual_gun_angle())
    dx = math.cos(angle)
    dy = math.sin(angle)
    return dx, dy


def gun_tip_position():
    dx, dy = gun_direction()
    px, py = player_world
    tip_x = px + dx * GUN_TIP_DIST
    tip_y = py + dy * GUN_TIP_DIST
    return tip_x, tip_y


def player_shoot():
    global last_player_shot
    now = time.time()
    if not gun_acquired:
        return
    if game_state != "playing":
        return
    if now - last_player_shot < PLAYER_SHOOT_CD:
        return
    last_player_shot = now
    tip_x, tip_y = gun_tip_position()
    dx, dy = gun_direction()
    bullet_speed = 4.5 * TILE_SIZE * 0.10
    p_bullets.append({
        "x": tip_x, "y": tip_y,
        "vx": dx * bullet_speed,
        "vy": dy * bullet_speed,
    })


# ─────────────────────────────────────────────────────────────
#  RESET
# ─────────────────────────────────────────────────────────────
def reset_game():
    global player_grid, player_world, player_target_world, player_facing
    global player_moving, move_progress, move_speed
    global player_health, shape_collected, tiles_collected, game_state
    global start_time, time_left, tile_map, anim_time
    global status_effects, flash_color, flash_until, event_msg, event_msg_until
    global enemies, bullets, p_bullets, gun_acquired, last_player_shot
    global current_level, gun_relative_angle

    player_grid[:]         = [0, 0]
    player_world[:]        = [0.0, 0.0]
    player_target_world[:] = [0.0, 0.0]
    player_facing   = 0.0
    player_moving   = False
    move_progress   = 0.0
    move_speed      = BASE_MOVE_SPEED
    player_health   = MAX_HEALTH
    shape_collected = {s: 0 for s in SHAPES}
    tiles_collected = 0
    game_state      = "playing"
    start_time      = time.time()
    time_left       = float(GAME_DURATION)
    tile_map.clear()
    status_effects  = []
    flash_color     = (0.0, 0.0, 0.0, 0.0)
    flash_until     = 0.0
    event_msg       = ""
    event_msg_until = 0.0
    enemies.clear()
    bullets.clear()
    p_bullets.clear()
    gun_acquired       = False
    last_player_shot   = 0.0
    current_level      = 1
    gun_relative_angle = 0.0
    anim_time          = 0.0
    tile_map[(0, 0)] = {
        "revealed": True, "visible": True, "type": "safe",
        "trap_type": None, "shape": None, "powerup": None,
    }


# Build the starting tile
tile_map[(0, 0)] = {
    "revealed": True, "visible": True, "type": "safe",
    "trap_type": None, "shape": None, "powerup": None,
}


# ─────────────────────────────────────────────────────────────
#  TEXT HELPER  (same pattern as 3D_OpenGL_Intro)
# ─────────────────────────────────────────────────────────────
def draw_text(x, y, text, font=GLUT_BITMAP_HELVETICA_18, color=(1, 1, 1)):
    glColor3f(color[0], color[1], color[2])
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glRasterPos2f(x, y)
    for ch in text:
        glutBitmapCharacter(font, ord(ch))
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ─────────────────────────────────────────────────────────────
#  SCREEN QUAD  (for HUD bars and overlays)
# ─────────────────────────────────────────────────────────────
def draw_screen_quad(x, y, w, h, r, g, b, a=1.0):
    if w <= 0:
        return
    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    gluOrtho2D(0, WINDOW_W, 0, WINDOW_H)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glColor4f(r, g, b, a)
    glBegin(GL_QUADS)
    glVertex2f(x,     y)
    glVertex2f(x + w, y)
    glVertex2f(x + w, y + h)
    glVertex2f(x,     y + h)
    glEnd()
    glDisable(GL_BLEND)
    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)


# ─────────────────────────────────────────────────────────────
#  SHAPE DRAWING HELPERS
# ─────────────────────────────────────────────────────────────
def draw_torus_manual(R=22, r=9, nring=16, nseg=20):
    for i in range(nring):
        a0 = 2 * math.pi * i       / nring
        a1 = 2 * math.pi * (i + 1) / nring
        glBegin(GL_QUAD_STRIP)
        for j in range(nseg + 1):
            b = 2 * math.pi * j / nseg
            for a in (a0, a1):
                x = (R + r * math.cos(b)) * math.cos(a)
                y = (R + r * math.cos(b)) * math.sin(a)
                z = r * math.sin(b)
                glVertex3f(x, y, z)
        glEnd()


def draw_diamond():
    s = 18
    h = 28
    base = [(s, s, 0), (-s, s, 0), (-s, -s, 0), (s, -s, 0)]
    glBegin(GL_TRIANGLES)
    for i in range(4):
        b0 = base[i]
        b1 = base[(i + 1) % 4]
        glVertex3f(0, 0,  h)
        glVertex3f(b0[0], b0[1], b0[2])
        glVertex3f(b1[0], b1[1], b1[2])
        glVertex3f(0, 0, -h)
        glVertex3f(b1[0], b1[1], b1[2])
        glVertex3f(b0[0], b0[1], b0[2])
    glEnd()


def draw_star():
    R_out = 22
    R_in  = 10
    depth = 8
    pts   = 6
    verts = []
    for k in range(pts * 2):
        a  = math.pi / pts * k
        rr = R_out if k % 2 == 0 else R_in
        verts.append((rr * math.cos(a), rr * math.sin(a)))

    for z in (depth, -depth):
        glBegin(GL_TRIANGLE_FAN)
        glVertex3f(0, 0, z)
        for vx, vy in verts:
            glVertex3f(vx, vy, z)
        glVertex3f(verts[0][0], verts[0][1], z)
        glEnd()

    n = len(verts)
    glBegin(GL_QUADS)
    for i in range(n):
        x0, y0 = verts[i]
        x1, y1 = verts[(i + 1) % n]
        glVertex3f(x0, y0,  depth)
        glVertex3f(x1, y1,  depth)
        glVertex3f(x1, y1, -depth)
        glVertex3f(x0, y0, -depth)
    glEnd()


def draw_floating_object(shape, col, row):
    """Bobbing and spinning collectible above a tile."""
    phase = col * 1.7 + row * 1.1
    bob   = math.sin(anim_time * 2.0 + phase) * 8.0
    spin  = math.fmod(anim_time * 75, 360.0)
    r, g, b = SHAPE_COLOR[shape]
    glColor3f(r, g, b)
    glTranslatef(0.0, 0.0, 35.0 + bob)

    if shape == "sphere":
        glRotatef(spin, 0.3, 0.6, 1.0)
        gluSphere(gluNewQuadric(), 18, 22, 22)
    elif shape == "cube":
        glRotatef(spin, 1.0, 0.6, 0.4)
        glutSolidCube(32)
    elif shape == "cone":
        glRotatef(spin, 0.0, 0.0, 1.0)
        glRotatef(-90, 1, 0, 0)
        gluCylinder(gluNewQuadric(), 18, 0, 38, 20, 8)
    elif shape == "torus":
        glRotatef(spin, 0.5, 1.0, 0.2)
        draw_torus_manual()
    elif shape == "diamond":
        glRotatef(spin, 0.0, 0.0, 1.0)
        draw_diamond()
    elif shape == "star":
        glRotatef(spin, 0.0, 0.0, 1.0)
        draw_star()


# ─────────────────────────────────────────────────────────────
#  TRAP MARKER  (shown after stepping on trap)
# ─────────────────────────────────────────────────────────────
def draw_trap_marker(trap_type):
    r, g, b = TRAP_COLORS[trap_type]
    glColor3f(r, g, b)
    glLineWidth(5)

    if trap_type == "damage":
        glBegin(GL_LINES)
        glVertex3f(-28, -28, 2)
        glVertex3f( 28,  28, 2)
        glVertex3f( 28, -28, 2)
        glVertex3f(-28,  28, 2)
        glEnd()

    elif trap_type == "slow":
        glBegin(GL_LINES)
        glVertex3f( 0,  28, 2)
        glVertex3f( 0, -20, 2)
        glVertex3f( 0, -20, 2)
        glVertex3f(-18,  0, 2)
        glVertex3f( 0, -20, 2)
        glVertex3f( 18,  0, 2)
        glEnd()

    elif trap_type == "blind":
        segs = 16
        glBegin(GL_LINE_LOOP)
        for i in range(segs):
            a = 2 * math.pi * i / segs
            glVertex3f(math.cos(a) * 22, math.sin(a) * 14, 2)
        glEnd()
        glBegin(GL_LINES)
        glVertex3f(-24, -16, 2)
        glVertex3f( 24,  16, 2)
        glEnd()

    elif trap_type == "score":
        glBegin(GL_LINES)
        glVertex3f(0,  30, 2)
        glVertex3f(0, -30, 2)
        glEnd()
        segs = 10
        glBegin(GL_LINE_STRIP)
        for i in range(segs + 1):
            a = math.pi + math.pi * i / segs
            glVertex3f(math.cos(a) * 18, math.sin(a) * 12 + 10, 2)
        glEnd()
        glBegin(GL_LINE_STRIP)
        for i in range(segs + 1):
            a = math.pi * i / segs
            glVertex3f(math.cos(a) * 18, math.sin(a) * 12 - 10, 2)
        glEnd()

    glLineWidth(1)


# ─────────────────────────────────────────────────────────────
#  TILE DRAWING
# ─────────────────────────────────────────────────────────────
def draw_tile(col, row, tile):
    wx   = col * TILE_SIZE
    wy   = row * TILE_SIZE
    half = TILE_SIZE * 0.5 - 2.0
    ttype = tile["type"]

    glPushMatrix()
    glTranslatef(wx, wy, 0)

    # Floor colour
    # visible = player can see the tile (stepped on OR revealed by power-up)
    # revealed = player actually stepped on it (effects have fired)
    # Use .get() so tiles created before the visible key was added still work.
    if not tile.get("visible", tile["revealed"]):
        glColor3f(0.10, 0.10, 0.16)    # dark = not yet seen
    elif ttype in ("safe", "collected", "powerup"):
        glColor3f(0.20, 0.40, 0.20)    # green = safe floor
    elif ttype == "trap":
        tr, tg, tb = TRAP_COLORS[tile["trap_type"]]
        glColor3f(tr * 0.28, tg * 0.28, tb * 0.28)
    else:
        # item tile: slight tint from the shape colour
        ir, ig, ib = SHAPE_COLOR[tile["shape"]]
        glColor3f(ir * 0.18, ig * 0.18, ib * 0.18)

    glBegin(GL_QUADS)
    glVertex3f(-half, -half, 0)
    glVertex3f( half, -half, 0)
    glVertex3f( half,  half, 0)
    glVertex3f(-half,  half, 0)
    glEnd()

    # Grid border lines
    glColor3f(0.0, 0.0, 0.0)
    glLineWidth(1)
    glBegin(GL_LINE_LOOP)
    glVertex3f(-half, -half, 0.5)
    glVertex3f( half, -half, 0.5)
    glVertex3f( half,  half, 0.5)
    glVertex3f(-half,  half, 0.5)
    glEnd()

    # Floating collectible object above item tiles
    if ttype == "item" and tile["shape"]:
        glPushMatrix()
        draw_floating_object(tile["shape"], col, row)
        glPopMatrix()

    # Trap marker shown after stepping on it
    if tile["revealed"] and ttype == "trap":
        draw_trap_marker(tile["trap_type"])

    # Sparkle dots on collected tiles
    if tile["revealed"] and ttype == "collected":
        glColor3f(0.55, 1.0, 0.55)
        glPointSize(5)
        glBegin(GL_POINTS)
        for ddx, ddy in [(-18,-18),(18,-18),(0,22),(-22,6),(22,6),(0,-24),(10,14),(-10,14)]:
            glVertex3f(ddx, ddy, 2)
        glEnd()
        glPointSize(1)

    glPopMatrix()


def draw_grid():
    pc, pr = player_grid
    if has_effect("blind"):
        rad = BLIND_RENDER_RAD
    else:
        rad = BASE_RENDER_RAD
    for dc in range(-rad, rad + 1):
        for dr in range(-rad, rad + 1):
            draw_tile(pc + dc, pr + dr, get_tile(pc + dc, pr + dr))


# ─────────────────────────────────────────────────────────────
#  PLAYER CHARACTER
# ─────────────────────────────────────────────────────────────
def draw_player():
    px, py = player_world
    glPushMatrix()
    glTranslatef(px, py, 0)
    glRotatef(player_facing, 0, 0, 1)

    # Body colour changes with active effects
    br, bg, bb = 0.18, 0.52, 1.00
    if has_effect("slow"):   br, bg, bb = 0.90, 0.80, 0.05
    if has_effect("blind"):  br, bg, bb = 0.50, 0.05, 0.80
    if has_effect("shield"): br, bg, bb = 0.10, 0.60, 1.00

    # Legs
    leg_swing = math.sin(anim_time * 8) * 15 if player_moving else 0
    for i, side in enumerate((-7, 7)):
        glPushMatrix()
        glTranslatef(side, 0, 4)
        if i == 0:
            glRotatef(leg_swing, 1, 0, 0)
        else:
            glRotatef(-leg_swing, 1, 0, 0)
        glColor3f(0.10, 0.18, 0.65)
        gluCylinder(gluNewQuadric(), 5, 4, 20, 8, 2)
        glPopMatrix()

    # Torso
    glColor3f(br, bg, bb)
    glTranslatef(0, 0, 12)
    gluCylinder(gluNewQuadric(), 14, 11, 36, 14, 4)

    # Arms
    arm_swing = math.sin(anim_time * 8) * 20 if player_moving else 0
    for side in (-1, 1):
        glPushMatrix()
        glTranslatef(side * 17, 0, 26)
        glRotatef(arm_swing * side, 1, 0, 0)
        glColor3f(br, bg, bb)
        gluCylinder(gluNewQuadric(), 4, 3, 24, 8, 2)
        glPopMatrix()

    # Neck
    glTranslatef(0, 0, 36)
    glColor3f(0.92, 0.78, 0.65)
    gluCylinder(gluNewQuadric(), 6, 6, 6, 10, 2)

    # Head
    glTranslatef(0, 0, 6)
    gluSphere(gluNewQuadric(), 13, 16, 16)

    # Eyes
    for ex in (-5, 5):
        glPushMatrix()
        glTranslatef(ex, 11, 2)
        glColor3f(0.05, 0.05, 0.05)
        gluSphere(gluNewQuadric(), 3.5, 8, 8)
        glPopMatrix()

    # Hat
    glColor3f(0.08, 0.08, 0.55)
    glTranslatef(0, 0, 11)
    gluCylinder(gluNewQuadric(), 14, 7, 16, 14, 2)

    glPopMatrix()

    # Gun barrel (drawn when acquired)
    # gluCylinder grows along Z. We rotate 90 degrees around Y so it points along X.
    # Then rotate around Z to point in the gun angle direction.
    if gun_acquired:
        gun_angle = actual_gun_angle()

        glPushMatrix()
        glTranslatef(px, py, 0)
        glRotatef(gun_angle, 0, 0, 1)
        glTranslatef(GUN_BASE_DIST, 0, GUN_HEIGHT)
        glRotatef(90, 0, 1, 0)
        glColor3f(0.65, 0.65, 0.65)
        gluCylinder(gluNewQuadric(), 4, 3, GUN_LENGTH, 8, 2)
        glPopMatrix()

        # Glowing muzzle tip
        tip_x, tip_y = gun_tip_position()
        glPushMatrix()
        glTranslatef(tip_x, tip_y, GUN_HEIGHT)
        glColor3f(0.10, 1.00, 0.90)
        gluSphere(gluNewQuadric(), 6, 8, 8)
        glPopMatrix()


# ─────────────────────────────────────────────────────────────
#  ENEMIES
# ─────────────────────────────────────────────────────────────
def draw_enemies():
    now = time.time()
    for e in enemies:
        glPushMatrix()
        glTranslatef(e["x"], e["y"], 0)

        # Enemy body
        glColor3f(0.85, 0.10, 0.10)
        glTranslatef(0, 0, 8)
        gluCylinder(gluNewQuadric(), 13, 10, 30, 10, 3)
        glTranslatef(0, 0, 30)
        gluSphere(gluNewQuadric(), 12, 12, 12)

        # Enemy eyes (yellow)
        for ex in (-4, 4):
            glPushMatrix()
            glTranslatef(ex, 10, 2)
            glColor3f(1.0, 0.9, 0.0)
            gluSphere(gluNewQuadric(), 3, 8, 8)
            glPopMatrix()

        # Ring that glows red when about to shoot
        since = now - e["last_shot"]
        if since > ENEMY_SHOOT_CD * 0.8:
            glColor3f(1.0, 0.2, 0.0)
        else:
            glColor3f(0.3, 0.1, 0.1)
        draw_torus_manual(R=14, r=3, nring=10, nseg=8)

        glPopMatrix()


# ─────────────────────────────────────────────────────────────
#  BULLETS
# ─────────────────────────────────────────────────────────────
def draw_bullets():
    # Enemy bullets: red
    for b in bullets:
        glPushMatrix()
        glTranslatef(b["x"], b["y"], 30)
        glColor3f(1.0, 0.15, 0.15)
        gluSphere(gluNewQuadric(), 7, 8, 8)
        glPopMatrix()

    # Player bullets: cyan
    for b in p_bullets:
        glPushMatrix()
        glTranslatef(b["x"], b["y"], 30)
        glColor3f(0.10, 1.00, 0.90)
        gluSphere(gluNewQuadric(), 6, 8, 8)
        glPopMatrix()


# ─────────────────────────────────────────────────────────────
#  HUD (heads-up display – 2D info drawn on top of 3D)
# ─────────────────────────────────────────────────────────────
def draw_hud():
    now   = time.time()
    BAR_W = 200

    # ── Left panel ──────────────────────────────────────────
    draw_text(10, WINDOW_H - 28, "CollectQuest",
              GLUT_BITMAP_TIMES_ROMAN_24, (1.0, 0.85, 0.10))

    lvl_col = {1: (0.4, 1.0, 0.4), 2: (1.0, 0.7, 0.1), 3: (1.0, 0.2, 0.2)}
    draw_text(195, WINDOW_H - 28, "LVL " + str(current_level),
              GLUT_BITMAP_TIMES_ROMAN_24, lvl_col[current_level])

    # HP hearts
    for i in range(MAX_HEALTH):
        if i < player_health:
            r, g, b = 0.95, 0.15, 0.15
        else:
            r, g, b = 0.30, 0.10, 0.10
        draw_screen_quad(10 + i * 22, WINDOW_H - 56, 16, 16, r, g, b)
    draw_text(10 + MAX_HEALTH * 22 + 6, WINDOW_H - 56,
              "HP " + str(player_health) + "/" + str(MAX_HEALTH),
              GLUT_BITMAP_HELVETICA_12, (1.0, 0.6, 0.6))
    if has_effect("shield"):
        draw_text(10 + MAX_HEALTH * 22 + 68, WINDOW_H - 56,
                  "[SHIELD]", GLUT_BITMAP_HELVETICA_12, (0.30, 0.80, 1.00))

    # Timer bar
    if time_left <= 20:
        tc = (1.0, 0.20, 0.20)
    elif time_left <= 45:
        tc = (1.0, 0.70, 0.10)
    else:
        tc = (0.55, 1.00, 0.55)
    draw_screen_quad(10, WINDOW_H - 76, BAR_W, 11, 0.12, 0.12, 0.12)
    draw_screen_quad(10, WINDOW_H - 76, int(BAR_W * time_left / GAME_DURATION), 11, tc[0], tc[1], tc[2])
    draw_text(10, WINDOW_H - 92,
              "Time: " + str(int(time_left)).zfill(3) + "s",
              GLUT_BITMAP_HELVETICA_12, tc)

    # Progress bar
    prog = progress_fraction()
    draw_screen_quad(10, WINDOW_H - 108, BAR_W, 9, 0.12, 0.12, 0.12)
    draw_screen_quad(10, WINDOW_H - 108, int(BAR_W * prog), 9, 0.30, 0.85, 0.40)
    draw_text(10, WINDOW_H - 122,
              "Progress: " + str(int(prog * 100)) + "%  (" + str(tiles_collected) + "/" + str(total_target()) + " tiles)",
              GLUT_BITMAP_HELVETICA_12, (0.50, 1.00, 0.50))

    # Level threshold markers on progress bar
    for thresh in (0.40, 0.70):
        mx = 10 + int(BAR_W * thresh)
        draw_screen_quad(mx - 1, WINDOW_H - 110, 2, 13, 1.0, 0.4, 0.0)

    # Active status effects
    eff_y = WINDOW_H - 140
    for e in status_effects:
        rem = e["until"] - now
        if rem > 0:
            et = e["type"]
            ec = TRAP_COLORS.get(et, POWERUP_COLORS.get(et, (1, 1, 1)))
            blink = True
            if rem < 2:
                blink = int(rem * 4) % 2 == 0
            if blink:
                draw_text(10, eff_y,
                          "[" + et.upper() + "]  " + str(round(rem, 1)) + "s",
                          GLUT_BITMAP_HELVETICA_12, ec)
            eff_y -= 18

    # Gun info
    if gun_acquired:
        draw_text(10, 68,
                  "Gun: " + str(int(actual_gun_angle())).zfill(3) + "  Q/E rotate  SPACE/CLICK shoot",
                  GLUT_BITMAP_HELVETICA_12, (0.85, 0.85, 0.25))

    # Controls line
    ws_note = ""
    if has_effect("slow"):
        ws_note = "  [W/S BLOCKED]"
    draw_text(10, 48,
              "Camera: " + CAMERA_MODES[camera_mode_idx].replace("_", " ").upper() + "  [C]  [R] restart",
              GLUT_BITMAP_HELVETICA_12, (0.60, 0.60, 0.80))
    if has_effect("slow"):
        col = (0.95, 0.80, 0.05)
    else:
        col = (0.50, 0.50, 0.70)
    draw_text(10, 30,
              "WASD: move    Q/E: rotate gun    Arrow L/R: orbit camera" + ws_note,
              GLUT_BITMAP_HELVETICA_12, col)

    # ── Centre panel: OBJECTS TO COLLECT ───────────────────
    panel_x = 330
    panel_y = WINDOW_H - 10
    panel_w = 340
    draw_screen_quad(panel_x - 6, panel_y - 190, panel_w, 186, 0.05, 0.05, 0.10, 0.80)
    draw_text(panel_x + 80, panel_y - 22,
              "OBJECTS TO COLLECT",
              GLUT_BITMAP_HELVETICA_18, (1.0, 1.0, 0.40))

    BAR_OBJ_W = 80
    row_h     = 24
    for idx, shape in enumerate(SHAPES):
        have = shape_collected[shape]
        need = SHAPE_QUOTA[shape]
        done = have >= need
        ir, ig, ib = SHAPE_COLOR[shape]
        rx = panel_x
        ry = panel_y - 48 - idx * row_h

        # Colour swatch
        draw_screen_quad(rx, ry - 2, 12, 14, ir, ig, ib)

        # Shape name
        if done:
            name_col = (0.30, 1.00, 0.35)
        else:
            name_col = (ir, ig, ib)
        draw_text(rx + 16, ry + 8,
                  shape.upper().ljust(7),
                  GLUT_BITMAP_HELVETICA_12, name_col)

        # Progress bar for this shape
        fill = int(BAR_OBJ_W * min(have, need) / need)
        draw_screen_quad(rx + 82, ry - 1, BAR_OBJ_W, 12, 0.12, 0.12, 0.12)
        if done:
            draw_screen_quad(rx + 82, ry - 1, BAR_OBJ_W, 12, 0.10, 0.90, 0.30)
        else:
            draw_screen_quad(rx + 82, ry - 1, fill, 12, ir * 0.75, ig * 0.75, ib * 0.75)

        if done:
            draw_text(rx + 82 + BAR_OBJ_W + 6, ry + 8,
                      "DONE", GLUT_BITMAP_HELVETICA_12, (0.25, 1.0, 0.35))
        else:
            draw_text(rx + 82 + BAR_OBJ_W + 6, ry + 8,
                      str(have) + "/" + str(need), GLUT_BITMAP_HELVETICA_12, (1.0, 1.0, 1.0))

    total_done = sum(1 for s in SHAPES if shape_collected[s] >= SHAPE_QUOTA[s])
    draw_text(panel_x, panel_y - 50 - len(SHAPES) * row_h,
              "Shapes done: " + str(total_done) + "/" + str(len(SHAPES)),
              GLUT_BITMAP_HELVETICA_12, (0.90, 0.90, 0.50))

    # ── Right panel: legend ─────────────────────────────────
    lx = WINDOW_W - 218
    draw_text(lx, WINDOW_H - 28, "TRAPS (hidden)",
              GLUT_BITMAP_HELVETICA_12, (1.0, 0.40, 0.40))
    for i, tt in enumerate(TRAP_TYPES):
        tr, tg, tb = TRAP_COLORS[tt]
        draw_text(lx, WINDOW_H - 46 - i * 16,
                  TRAP_LABELS[tt], GLUT_BITMAP_HELVETICA_12, (tr, tg, tb))

    yoff = WINDOW_H - 46 - len(TRAP_TYPES) * 16 - 14
    draw_text(lx, yoff, "POWER-UPS (hidden in tiles)",
              GLUT_BITMAP_HELVETICA_12, (0.90, 0.90, 0.20))
    for i, pt in enumerate(POWERUP_TYPES):
        pr, pg, pb = POWERUP_COLORS[pt]
        draw_text(lx, yoff - 18 - i * 16,
                  POWERUP_LABELS[pt], GLUT_BITMAP_HELVETICA_12, (pr, pg, pb))

    if enemies:
        draw_text(lx, yoff - 18 - len(POWERUP_TYPES) * 16 - 16,
                  "ENEMIES ACTIVE: " + str(len(enemies)),
                  GLUT_BITMAP_HELVETICA_12, (1.0, 0.20, 0.20))

    draw_text(lx, 30, "Dark tiles = unexplored",
              GLUT_BITMAP_HELVETICA_12, (0.45, 0.45, 0.60))

    # ── Event message (centre of screen) ───────────────────
    if now < event_msg_until:
        draw_text(WINDOW_W // 2 - 160, WINDOW_H // 2 + 130,
                  event_msg, GLUT_BITMAP_HELVETICA_18, (1.0, 0.90, 0.10))

    # ── Screen flash on trap hit ────────────────────────────
    if now < flash_until:
        fr, fg, fb, fa = flash_color
        fade = max(0.0, (flash_until - now) / 0.5)
        draw_screen_quad(0, 0, WINDOW_W, WINDOW_H, fr, fg, fb, fa * fade)

    # ── End game overlays ───────────────────────────────────
    cx = WINDOW_W // 2
    cy = WINDOW_H // 2

    if game_state == "win":
        draw_screen_quad(cx - 215, cy - 72, 430, 155, 0.0, 0.14, 0.0, 0.93)
        draw_text(cx - 82,  cy + 58, "YOU  WIN!",
                  GLUT_BITMAP_TIMES_ROMAN_24, (0.15, 1.0, 0.30))
        draw_text(cx - 158, cy + 20,
                  "Collected all " + str(total_target()) + " items in " + str(int(GAME_DURATION - time_left)) + "s",
                  GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
        draw_text(cx - 118, cy - 18, "Press  R  to play again",
                  GLUT_BITMAP_HELVETICA_18, (0.80, 0.80, 0.80))

    elif game_state == "lose_hp":
        draw_screen_quad(cx - 215, cy - 72, 430, 155, 0.22, 0.0, 0.0, 0.93)
        draw_text(cx - 112, cy + 58, "YOU  DIED!",
                  GLUT_BITMAP_TIMES_ROMAN_24, (1.0, 0.18, 0.18))
        draw_text(cx - 132, cy + 20,
                  "Got " + str(total_collected()) + " / " + str(total_target()) + " items",
                  GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
        draw_text(cx - 118, cy - 18, "Press  R  to play again",
                  GLUT_BITMAP_HELVETICA_18, (0.80, 0.80, 0.80))

    elif game_state == "lose_time":
        draw_screen_quad(cx - 215, cy - 72, 430, 155, 0.18, 0.09, 0.0, 0.93)
        draw_text(cx - 98,  cy + 58, "TIME'S  UP!",
                  GLUT_BITMAP_TIMES_ROMAN_24, (1.0, 0.55, 0.05))
        draw_text(cx - 138, cy + 20,
                  "Only got " + str(total_collected()) + " / " + str(total_target()) + " items",
                  GLUT_BITMAP_HELVETICA_18, (1, 1, 1))
        draw_text(cx - 118, cy - 18, "Press  R  to play again",
                  GLUT_BITMAP_HELVETICA_18, (0.80, 0.80, 0.80))


# ─────────────────────────────────────────────────────────────
#  CAMERA  (same pattern as 3D_OpenGL_Intro's setupCamera)
# ─────────────────────────────────────────────────────────────
def setup_camera():
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    gluPerspective(fovY, WINDOW_W / WINDOW_H, 0.1, 12000)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()

    px, py = player_world
    mode   = CAMERA_MODES[camera_mode_idx]

    if mode == "top_down":
        gluLookAt(px, py, 800,
                  px, py, 0,
                  0, 1, 0)

    elif mode == "angled":
        rad = math.radians(camera_angle)
        cx  = px + CAMERA_DIST * math.sin(rad)
        cy  = py - CAMERA_DIST * math.cos(rad)
        gluLookAt(cx, cy, CAMERA_HEIGHT,
                  px, py, 40,
                  0, 0, 1)

    else:  # first_person
        rad = math.radians(player_facing + 90)
        lx  = px + math.cos(rad) * 50
        ly  = py + math.sin(rad) * 50
        gluLookAt(px, py, 65,
                  lx, ly, 55,
                  0, 0, 1)


# ─────────────────────────────────────────────────────────────
#  MOVEMENT  (grid-based, same as intro pattern)
# ─────────────────────────────────────────────────────────────
def try_move(dcol, drow):
    global player_moving, move_progress, player_facing
    if player_moving or game_state != "playing":
        return
    # Slow trap blocks W/S (drow moves)
    if has_effect("slow") and drow != 0:
        set_event("~ SLOW  W/S blocked!  Use A/D to move", 1.0)
        return

    nc = player_grid[0] + dcol
    nr = player_grid[1] + drow
    player_grid[0] = nc
    player_grid[1] = nr
    player_target_world[0] = float(nc * TILE_SIZE)
    player_target_world[1] = float(nr * TILE_SIZE)
    player_moving  = True
    move_progress  = 0.0

    if dcol == 1:
        player_facing = -90
    elif dcol == -1:
        player_facing = 90
    elif drow == 1:
        player_facing = 0
    elif drow == -1:
        player_facing = 180

    reveal_tile(nc, nr)


def update_movement():
    global player_moving, move_progress
    if not player_moving:
        return
    move_progress += move_speed
    if move_progress >= 1.0:
        move_progress = 1.0
        player_moving = False
    tx = player_target_world[0]
    ty = player_target_world[1]
    player_world[0] += (tx - player_world[0]) * move_speed * 4
    player_world[1] += (ty - player_world[1]) * move_speed * 4
    if not player_moving:
        player_world[0] = tx
        player_world[1] = ty


# ─────────────────────────────────────────────────────────────
#  INPUT  (same structure as 3D_OpenGL_Intro)
# ─────────────────────────────────────────────────────────────
def keyboard_listener(key, x, y):
    global camera_mode_idx, gun_relative_angle

    if key in (b'w', b'W'):
        try_move(0, 1)
    elif key in (b's', b'S'):
        try_move(0, -1)
    elif key in (b'a', b'A'):
        try_move(-1, 0)
    elif key in (b'd', b'D'):
        try_move(1, 0)
    elif key in (b'q', b'Q'):
        if gun_acquired and game_state == "playing":
            gun_relative_angle += 6
    elif key in (b'e', b'E'):
        if gun_acquired and game_state == "playing":
            gun_relative_angle -= 6
    elif key in (b'c', b'C'):
        camera_mode_idx = (camera_mode_idx + 1) % len(CAMERA_MODES)
    elif key in (b'r', b'R'):
        reset_game()
    elif key == b' ':
        player_shoot()


def special_key_listener(key, x, y):
    global camera_angle

    if key == GLUT_KEY_UP:
        try_move(0, 1)
    elif key == GLUT_KEY_DOWN:
        try_move(0, -1)
    elif key == GLUT_KEY_LEFT:
        camera_angle -= 6
    elif key == GLUT_KEY_RIGHT:
        camera_angle += 6


def mouse_listener(button, state, x, y):
    if button == GLUT_LEFT_BUTTON and state == GLUT_DOWN:
        player_shoot()


# ─────────────────────────────────────────────────────────────
#  DISPLAY & IDLE  (same structure as 3D_OpenGL_Intro)
# ─────────────────────────────────────────────────────────────
def show_screen():
    global anim_time, time_left, game_state

    anim_time += 0.016
    tick_effects()
    update_level()

    if game_state == "playing":
        time_left = max(0.0, GAME_DURATION - (time.time() - start_time))
        if time_left <= 0:
            game_state = "lose_time"
        maybe_spawn_enemies()
        update_enemies()
        update_bullets()

    update_movement()

    glClearColor(0.04, 0.04, 0.09, 1)
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    glLoadIdentity()
    glViewport(0, 0, WINDOW_W, WINDOW_H)

    setup_camera()
    glEnable(GL_DEPTH_TEST)

    draw_grid()

    if CAMERA_MODES[camera_mode_idx] != "first_person":
        draw_player()
        draw_enemies()
        draw_bullets()

    glDisable(GL_DEPTH_TEST)
    draw_hud()

    glutSwapBuffers()


def idle():
    glutPostRedisplay()


# ─────────────────────────────────────────────────────────────
#  MAIN  (same structure as 3D_OpenGL_Intro)
# ─────────────────────────────────────────────────────────────
def main():
    glutInit()
    glutInitDisplayMode(GLUT_DOUBLE | GLUT_RGB | GLUT_DEPTH)
    glutInitWindowSize(WINDOW_W, WINDOW_H)
    glutInitWindowPosition(80, 40)
    glutCreateWindow(b"CollectQuest")

    glutDisplayFunc(show_screen)
    glutKeyboardFunc(keyboard_listener)
    glutSpecialFunc(special_key_listener)
    glutMouseFunc(mouse_listener)
    glutIdleFunc(idle)

    glutMainLoop()


if __name__ == "__main__":
    main()
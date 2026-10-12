# CollectQuest

CollectQuest is a 3D grid-based collection game built with Python, PyOpenGL, and GLUT. Explore procedurally generated tiles, collect the required shapes, and avoid traps and enemies before time runs out.

## Features

- Six collectible shapes, each with a collection quota
- Procedurally generated item, trap, power-up, and safe tiles
- Three camera modes: top-down, angled, and first-person
- Health and timer limits, status effects, and multiple difficulty levels
- Enemies and shooting combat that unlock as you make progress

## Requirements

- Python 3
- PyOpenGL
- A GLUT implementation, such as FreeGLUT

Install the Python packages:

```powershell
py -m pip install PyOpenGL PyOpenGL_accelerate
```

Install FreeGLUT separately if it is not already available on your system. PyOpenGL's GLUT bindings require the native GLUT library at runtime.

## Run

From the project directory:

```powershell
py CollectQuest.py
```

## Controls

| Key / input | Action |
| --- | --- |
| W / S | Move forward / backward |
| A / D | Move left / right |
| Up / Down arrows | Move forward / backward |
| Left / Right arrows | Orbit the camera |
| C | Cycle camera mode |
| Q / E | Rotate the gun after it is acquired |
| Space / left mouse button | Shoot after the gun is acquired |
| R | Restart the game |

Collect every required shape before the three-minute timer expires. Traps and enemy hits reduce health; losing all five hearts or running out of time ends the game.

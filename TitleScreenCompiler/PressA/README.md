# Newer DS "Press A" Graphics Creator Script

(by RoadrunnerWMC)

This creates the "Press (A)!" animation frames for the title screen PNGs that can be found one directory up from here.

The script was written for Linux, and is unlikely to work on Windows without some adjustment since it references Linux's `/tmp` folder.

## Inputs

- Press-A.png
- Anim-BG.png
- bottoms.png
    
## Outputs

- ts-1.png through ts-8.png: graphics files you can use as inputs for the script in the parent directory
- anim.png: the animation frames by themselves
- anim.gif: a gif preview of the animation, so you can more easily see how it turned out

## Setup and Usage

- Install dependencies listed in the parent directory's readme.
- Additionally, install imageio with pip.
- Edit input images however you want.
- python3 press-a-graphics.py

## License

GNU GPL v3 -- see LICENSE file in parent directory for details.

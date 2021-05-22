# Newer DS Level Preview Graphics Compiler

(by RoadrunnerWMC)

This creates all the graphics files for the preview screens that appear while levels are loading.

The script was written for Linux, but ought to run on Windows, too.

## Note

Since there are a lot of shared palettes among the in-game image files, you can't just import individual preview files into the ROM manually without probably breaking stuff. This is why the script generates and imports all the images at the same time, instead of letting you choose which ones to import (which would make it run faster, if it was possible).

## Inputs

- `Newer Super Mario Bros. DS Orig.nds`
- "previews" folder: level preview images (155x112)
- config.json: level names, background colors, etc
- "bottoms", "characters", "static" folders: self-explanatory
    
## Outputs

- `Newer Super Mario Bros. DS.nds`
- Additional output folders for debugging:
    - "out-png": the full-quality images the script puts together
    - "out-enpg": the (lower quality) enpg files they're converted to
    - "out-enpg-png": PNG renders of the enpgs, so you can see how the enpg-ification affected the image quality
    - "out-enpg-lz": the enpg file agains, but lz-compressed (this is what is ultimately inserted into the rom)

## Setup and Usage

- Install Pillow, PyQt5, libimagequant and ndspy with pip.
- Install ImageMagick.
    - If you get errors about "command 'convert' not found" or similar, that means it can't find ImageMagick.
        - Windows has a built-in "convert.exe" in system32 that can conflict with ImageMagick's "convert" command, which can result in weird issues. If that happens, either ensure it's using the correct "convert" command, or try running on a different OS instead (Linux).
- Install the font "New Super Mario Font (Mario Party 9)", which can be found online
- Put "Newer Super Mario Bros. DS Orig.nds" (exact filename) in the main directory.
    - The script will automatically inject all the files into it and save the output as "Newer Super Mario Bros. DS.nds".
- Edit input stuff (images, config) however you want.
- Optional: clear out the "out-png", "out-enpg", "out-enpg-png", and "out-enpg-lz" folders
    - Don't delete them, though! These folders *must* exist when you run the script!
- python3 graphics-compiler.py
    - (or, on Windows) py -3 graphics-compiler.py
    - This will probably take a while to finish (maybe 10-15 minutes or so)

## License

GNU GPL v3 -- see LICENSE file for details.

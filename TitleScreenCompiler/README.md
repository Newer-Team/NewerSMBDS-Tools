# Newer DS Title Screen Graphics Compiler

(by RoadrunnerWMC)

This converts and inserts the graphics files for the title screen. This is re-run every time a new release is made, since the version number is baked into the title screen graphics and this script adds that.

The script was written for Linux, but ought to run on Windows, too.

There's also another script which was used to help make the PNG images here (with their embedded animation frames), which can be found in the "PressA" subdirectory.

## Note

Since there are a lot of shared palettes among the in-game image files, you can't just import individual preview files into the ROM manually without probably breaking stuff. This is why the script generates and imports all the images at the same time.

## Inputs

- The version number string is defined as a "VERSION" constant at the top of compile-ts-graphics.py
- `Newer Super Mario Bros. DS.nds`
- ts-0.png through ts-8.png: graphics files to be converted.
    - The version number will be automatically added to ts-0.png.
    
## Outputs

- `Newer Super Mario Bros. DS.nds` (yes, the script overwrites the input file)
- Additional output folders for debugging:
    - "out-enpg": the (lower quality) enpg files the input pngs were converted to
    - "out-enpg-png": PNG renders of the enpgs, so you can see how the enpg-ification affected the image quality
    - "out-enpg-lz": the enpg file agains, but lz-compressed (this is what is ultimately inserted into the rom)

## Setup and Usage

- Install Pillow, PyQt5, libimagequant and ndspy with pip.
- Install ImageMagick.
    - If you get errors about "command 'convert' not found" or similar, that means it can't find ImageMagick.
        - Windows has a built-in "convert.exe" in system32 that can conflict with ImageMagick's "convert" command, which can result in weird issues. If that happens, either ensure it's using the correct "convert" command, or try running on a different OS instead (Linux).
- Install the font "New Super Mario Font (Mario Party 9)", which can be found online
- Put "Newer Super Mario Bros. DS.nds" (exact filename) in the main directory.
    - The script will automatically inject all the files into it and save the output back to the same file, overwriting it.
- Edit input stuff (images, version number) however you want.
- Optional: clear out the "out-enpg", "out-enpg-png", and "out-enpg-lz" folders
    - Don't delete them, though! These folders *must* exist when you run the script!
- python3 compile-ts-graphics.py
    - (or, on Windows) py -3 compile-ts-graphics.py

## License

GNU GPL v3 -- see LICENSE file for details.

# ATIS - automatic terminal information service, or something along those lines

This is essentially a janky TTS program. See releases for the recommended audio archive.
IF YOU'RE READING THIS SO EARLY THAT THERE ARE NO RELEASES YET, THEN HOLD ON 

## Usage

1. Make a txt file, this will be your prompt. 
2. Inside the file, put what you want to be turned into audio. For example, with my recommended mapping file:

```
THISIS LGHE INFO D AUTOMATIC TIME 1630Z.
SURFACEWINDS 360 DEGREES AT 4 KNOTS CAVOK TEMPERATURE 15 DEGREES DEWPOINT 5 DEGREES QNH 1014.
RWYINUSE 30.
TRANSITIONLEVEL FL70.
ACKNOWLEDGE D ADVISEACFTTYPE AND STAND ONFIRSTCONTACT WITH LGHE.
```

All words will be collapsed to lowercase, and all numbers will be parsed separately.  Obviously, this is not a standard ATIS format, so some reformatting may need to happen, but you can map words as you like - for example in the standard mapping, `SURFACEWINDS` gets mapped to the surface_wind.wav. **See the audio folder in the latest release for all recordings available.**

3. Open up the ATIS generator, select your prompt and the audio folder, then look through the tokens (audio files to be combined) that are listed. For each one, if the text is red, that means that no file is associated with that token, and so you'll probably need to manage the audio, which can be done by double clicking that row. If you leave it red, then the token will be skipped when compiling the final recording. See more in the following sections.

4. Enter the name of the file you want to generate, remembering to add the .wav suffix to show it's a WAV file, then press "generate". All done!

### Recording

In the manage audio window, to the right, there is a column for recording new audio. Input your file name, remembering to include the .wav suffix, then press the record button (any leading/trailing silence gets cutoff when compiling). Then, press stop recording, then press the bottom submit recording button to save. This file is now added to your audio folder, and is mapped to that token.

### Mapping

In the manage audio window, to the left, you can select a file in the audio folder for each token. 

## Installation

You will need ffmpeg installed on your system.

### Binaries
Just get them from the releases section

### Source
Now the real deal. Clone this repository then run `pip install -r requirements.txt` to quickly get all the packages. Then, run `python main.py`. Simples





_Overall this was a pretty badly slapped together project. If there are any issues (which there are several of) then please contact me (develop331) and I'll fix them, or open an issue on GitHub_

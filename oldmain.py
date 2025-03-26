import os
import sys
import re
import wave
import simpleaudio as sa
from pydub import AudioSegment
from pydub.silence import detect_nonsilent

import sounddevice as sd
import numpy as np
import queue

GAP_DURATION_MS = 100  # 100ms silent gap between words

def load_prompt(prompt_path):
    """
    Read the prompt from a .txt file and split into tokens.
    If an empty line is encountered, insert a special token "DELAY_1S".
    Non-empty lines are tokenized into letters and individual digits.
    """
    with open(prompt_path, "r") as f:
        lines = f.read().splitlines()

    tokens = []
    for line in lines:
        if line.strip() == "":
            tokens.append("DELAY_1S")
        else:
            # Extract letter sequences and single digits
            line_tokens = re.findall(r'[A-Za-z]+|\d', line)
            tokens.extend(line_tokens)
    return tokens

def load_mapping(folder_path):
    """Load the TSV mapping file from the folder."""
    mapping_file = os.path.join(folder_path, "mapping.tsv")
    mapping = {}
    if os.path.isfile(mapping_file):
        with open(mapping_file, "r") as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    key = parts[0].lower()
                    mapping[key] = parts[1]
    else:
        print("Mapping file 'mapping.tsv' not found. A new one will be created if needed.")
    return mapping

def update_mapping_file(mapping, folder_path):
    """Write the mapping dictionary back to mapping.tsv in the folder."""
    mapping_file = os.path.join(folder_path, "mapping.tsv")
    with open(mapping_file, "w") as f:
        for word, filename in mapping.items():
            f.write(f"{word}\t{filename}\n")
    print(f"Mapping file updated at {mapping_file}")

def record_audio(filename, folder_path, sample_rate=44100, channels=1, dtype='int16'):
    """
    Record audio using sounddevice until the user presses Enter to stop.
    The recording is saved as a WAV file with the given filename in the folder.
    """
    print("Press Enter to start recording.")
    input()
    print("Recording... Press Enter to stop.")
    
    q = queue.Queue()

    def callback(indata, frames, time_info, status):
        if status:
            print(status, file=sys.stderr)
        q.put(indata.copy())

    stream = sd.InputStream(samplerate=sample_rate, channels=channels, dtype=dtype, callback=callback)
    stream.start()
    
    input()  # Wait for Enter to stop recording
    stream.stop()
    stream.close()
    
    frames = []
    while not q.empty():
        frames.append(q.get())
    if not frames:
        print("No audio was recorded.")
        sys.exit(1)
    
    audio_data = np.concatenate(frames, axis=0)
    raw_data = audio_data.tobytes()
    
    seg = AudioSegment(
        data=raw_data,
        sample_width=audio_data.dtype.itemsize,
        frame_rate=sample_rate,
        channels=channels
    )
    
    file_path = os.path.join(folder_path, filename)
    seg.export(file_path, format="wav")
    print(f"Recorded audio saved as {file_path}")
    return file_path

def get_wav_file_for_token(token, mapping, folder_path):
    """
    Return the .wav file path for a given token.
    If the token is not in mapping, ask the user for the file name.
    If the user enters a value starting with 'record ', record audio.
    If user enters 'N/A', return None.
    """
    token_lower = token.lower()
    if token_lower in mapping:
        wav_filename = mapping[token_lower]
        if wav_filename.upper() == "N/A":
            return None
    else:
        wav_filename = input(f"Enter the .wav file name for '{token}' (or type N/A if none, or 'record X.wav' to record): ").strip()
        if wav_filename.upper() == "N/A":
            mapping[token_lower] = "N/A"
            return None
        if wav_filename.lower().startswith("record "):
            # Expect format: record X.wav
            parts = wav_filename.split(maxsplit=1)
            if len(parts) != 2:
                print("Invalid record command format. Exiting.")
                sys.exit(1)
            record_filename = parts[1]
            full_path = record_audio(record_filename, folder_path)
            mapping[token_lower] = record_filename
            return full_path
        else:
            full_path = os.path.join(folder_path, wav_filename)
            if not os.path.isfile(full_path):
                print(f"File {wav_filename} does not exist. Exiting.")
                sys.exit(1)
            mapping[token_lower] = wav_filename

    full_path = os.path.join(folder_path, mapping[token_lower])
    if not os.path.isfile(full_path):
        print(f"File {mapping[token_lower]} not found.")
        sys.exit(1)
    return full_path

def trim_silence(audio, silence_threshold=-40, min_silence_length=50):
    """Remove leading and trailing silence from an audio segment."""
    non_silent_ranges = detect_nonsilent(audio, min_silence_length, silence_threshold)
    if not non_silent_ranges:
        return AudioSegment.silent(duration=0)
    start_trim, end_trim = non_silent_ranges[0][0], non_silent_ranges[-1][1]
    return audio[start_trim:end_trim]

def compile_wav_files(wav_items, output_file):
    """
    Concatenate multiple WAV files and silence markers into one.
    For items equal to "SILENCE_1000", a one-second silence is inserted.
    For other items, files are loaded, trimmed, converted to a common format,
    and concatenated with a small gap between.
    """
    if not wav_items:
        print("No wav items provided to compile.")
        sys.exit(1)
    
    # Determine reference parameters from the first actual file.
    reference_audio = None
    for item in wav_items:
        if item != "SILENCE_1000":
            reference_audio = AudioSegment.from_wav(item)
            break
    if reference_audio is None:
        print("No valid audio files to compile.")
        sys.exit(1)
    
    common_frame_rate = reference_audio.frame_rate
    common_sample_width = reference_audio.sample_width
    common_channels = reference_audio.channels
    
    final_audio = AudioSegment.empty()
    silence_gap = AudioSegment.silent(duration=GAP_DURATION_MS)
    
    for item in wav_items:
        if item == "SILENCE_1000":
            # Insert one second of silence.
            final_audio += AudioSegment.silent(duration=500)
        else:
            seg = AudioSegment.from_wav(item)
            seg = trim_silence(seg)
            if seg.frame_rate != common_frame_rate:
                seg = seg.set_frame_rate(common_frame_rate)
            if seg.sample_width != common_sample_width:
                seg = seg.set_sample_width(common_sample_width)
            if seg.channels != common_channels:
                seg = seg.set_channels(common_channels)
            final_audio += seg + silence_gap
    final_audio.export(output_file, format="wav")
    print(f"Compiled wav file saved as {output_file}")

def play_wav_file(wav_file):
    """Play a WAV file using simpleaudio."""
    try:
        wave_obj = sa.WaveObject.from_wave_file(wav_file)
        play_obj = wave_obj.play()
        play_obj.wait_done()
    except Exception as e:
        print(f"Error playing {wav_file}: {e}")

def main():
    if len(sys.argv) != 3:
        print("Usage: python script.py <prompt.txt> <folder_path>")
        sys.exit(1)
    
    prompt_path = sys.argv[1]
    folder_path = sys.argv[2]
    
    if not os.path.isfile(prompt_path):
        print(f"Prompt file {prompt_path} not found.")
        sys.exit(1)
    if not os.path.isdir(folder_path):
        print(f"Folder {folder_path} not found.")
        sys.exit(1)
    
    tokens = load_prompt(prompt_path)
    print("Tokens extracted from prompt:", tokens)
    
    mapping = load_mapping(folder_path)
    
    wav_items_to_compile = []
    for token in tokens:
        if token == "DELAY_1S":
            # Add a marker for one-second silence.
            wav_items_to_compile.append("SILENCE_1000")
        else:
            wav_path = get_wav_file_for_token(token, mapping, folder_path)
            if wav_path:
                wav_items_to_compile.append(wav_path)
            else:
                print(f"Skipping token '{token}' as no file is associated.")
    
    update_mapping_file(mapping, folder_path)
    
    # Save compiled.wav in the current working directory.
    output_wav = os.path.join(os.getcwd(), "compiled.wav")
    compile_wav_files(wav_items_to_compile, output_wav)
    
    play_wav_file(output_wav)

if __name__ == "__main__":
    main()

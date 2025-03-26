import os
import re
import tkinter as tk
from tkinter import filedialog, ttk
import simpleaudio as sa
from pydub import AudioSegment
import sounddevice as sd
import numpy as np
import queue
from pydub.silence import detect_nonsilent

GAP_DURATION_MS = 100  # 100ms silent gap between words

def load_prompt(prompt_path):
    with open(prompt_path, "r") as f:
        lines = f.read().splitlines()
    tokens = []
    for line in lines:
        if line.strip() == "":
            tokens.append(("DELAY_1S", ""))
        else:
            line_tokens = re.findall(r'[A-Za-z]+|\d', line)
            tokens.extend([(token, "") for token in line_tokens])
    return tokens

def load_mapping(folder_path):
    mapping_file = os.path.join(folder_path, "mapping.tsv")
    mapping = {}
    if os.path.isfile(mapping_file):
        with open(mapping_file, "r") as f:
            for line in f:
                parts = line.strip().split('\t')
                if len(parts) >= 2:
                    mapping[parts[0].lower()] = parts[1]
    return mapping

def update_mapping_file(mapping, folder_path):
    mapping_file = os.path.join(folder_path, "mapping.tsv")
    with open(mapping_file, "w") as f:
        for word, filename in mapping.items():
            f.write(f"{word}\t{filename}\n")

def record_audio(token):
    def start_recording():
        nonlocal stream, audio_data, recording
        if not recording:
            recording = True
            record_button.config(text="End Recording")
            audio_data = []
            stream = sd.InputStream(samplerate=44100, channels=1, dtype='int16', callback=callback)
            stream.start()
        else:
            stream.stop()
            stream.close()
            recording = False
            record_button.config(text="Submit Recording")
    
    def submit_recording():
        file_name = file_name_entry.get()
        if file_name:
            file_path = os.path.join(folder_entry.get(), f"{file_name}.wav")
            AudioSegment(
                data=np.concatenate(audio_data, axis=0).tobytes(),
                sample_width=2,
                frame_rate=44100,
                channels=1
            ).export(file_path, format="wav")
            mapping[token.lower()] = f"{file_name}.wav"
            update_mapping_file(mapping, folder_entry.get())
            update_table()
            record_window.destroy()
    
    def callback(indata, frames, time_info, status):
        audio_data.append(indata.copy())
    
    record_window = tk.Toplevel(root)
    record_window.title(f"Manage Audio for {token}")
    record_window.geometry("300x150")
    
    record_frame = tk.Frame(record_window)
    record_frame.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")

    tk.Label(record_frame, text="File Name:").pack()
    file_name_entry = tk.Entry(record_frame)
    file_name_entry.pack()

    record_button = tk.Button(record_frame, text="Start Recording", command=start_recording)
    record_button.pack()

    submit_button = tk.Button(record_frame, text="Submit Recording", command=submit_recording)
    submit_button.pack()

    map_button = tk.Button(record_window, text="Map Audio", command=lambda: map_audio_file(token))
    map_button.grid(row=0, column=0, padx=10, pady=10)

    stream = None
    recording = False
    audio_data = []

def map_audio_file(token):
    # Open a file dialog to select a file from the audio directory
    file_path = filedialog.askopenfilename(title="Select Audio File", filetypes=[("WAV Files", "*.wav")])
    if file_path:
        mapped_file_name = os.path.basename(file_path)
        mapping[token.lower()] = mapped_file_name
        update_mapping_file(mapping, folder_entry.get())
        update_table()

def update_table():
    for row in table.get_children():
        table.delete(row)
    for token, _ in tokens:
        assigned_audio = mapping.get(token.lower(), "N/A")
        if assigned_audio == "N/A":
            font_style = ('Helvetica', 10, 'bold')
            color = 'red'
        else:
            font_style = ('Helvetica', 10)
            color = 'black'
        table.insert("", "end", values=(token, assigned_audio, "Manage"),
                     tags=(assigned_audio,))
        table.tag_configure(assigned_audio, foreground=color, font=font_style)

def select_prompt():
    global tokens
    file_path = filedialog.askopenfilename(title="Select Prompt File", filetypes=[("Text Files", "*.txt")])
    if file_path:
        prompt_entry.delete(0, tk.END)
        prompt_entry.insert(0, file_path)
        tokens = load_prompt(file_path)
        update_table()

def select_folder():
    global mapping
    folder = filedialog.askdirectory(title="Select Audio Folder")
    if folder:
        folder_entry.delete(0, tk.END)
        folder_entry.insert(0, folder)
        mapping = load_mapping(folder)
        update_table()

def on_manage_click(event):
    selected_item = table.selection()
    if selected_item:
        token = table.item(selected_item, "values")[0]
        record_audio(token)

def trim_silence(audio, silence_threshold=-40, min_silence_length=50):
    """Remove leading and trailing silence from an audio segment."""
    non_silent_ranges = detect_nonsilent(audio, min_silence_length, silence_threshold)
    if not non_silent_ranges:
        return AudioSegment.silent(duration=0)
    start_trim, end_trim = non_silent_ranges[0][0], non_silent_ranges[-1][1]
    return audio[start_trim:end_trim]

def compile_wav_files(wav_items, output_file):
    if not wav_items:
        print("No wav items provided to compile.")
        return
    reference_audio = None
    for item in wav_items:
        if item != "SILENCE_1000":
            reference_audio = AudioSegment.from_wav(item)
            break
    if reference_audio is None:
        print("No valid audio files to compile.")
        return

    common_frame_rate = reference_audio.frame_rate
    common_sample_width = reference_audio.sample_width
    common_channels = reference_audio.channels

    final_audio = AudioSegment.empty()
    silence_gap = AudioSegment.silent(duration=GAP_DURATION_MS)

    for item in wav_items:
        if item == "SILENCE_1000":
            final_audio += AudioSegment.silent(duration=500)  # 500ms gap between words
        else:
            seg = AudioSegment.from_wav(item)
            seg = trim_silence(seg)  # Trim leading/trailing silence
            seg = seg.set_frame_rate(common_frame_rate)
            seg = seg.set_sample_width(common_sample_width)
            seg = seg.set_channels(common_channels)
            final_audio += seg + silence_gap  # Add gap only between words, not before or after

    final_audio.export(output_file, format="wav")
    print(f"Compiled wav file saved as {output_file}")

def generate_audio():
    wav_items_to_compile = []
    for token, _ in tokens:
        if token == "DELAY_1S":
            wav_items_to_compile.append("SILENCE_1000")
        else:
            wav_path = mapping.get(token.lower(), None)
            if wav_path:
                wav_items_to_compile.append(os.path.join(folder_entry.get(), wav_path))

    output_file = generate_filename_entry.get().strip()
    if not output_file:
        print("Please provide a filename.")
        return
    output_path = os.path.join(os.getcwd(), output_file)  # Save in the current directory
    compile_wav_files(wav_items_to_compile, output_path)

root = tk.Tk()
root.title("ATIS Audio Editor")
root.geometry("600x400")

prompt_label = tk.Label(root, text="Prompt File:")
prompt_label.pack()
prompt_entry = tk.Entry(root, width=50)
prompt_entry.pack()
prompt_button = tk.Button(root, text="Browse", command=select_prompt)
prompt_button.pack()

folder_label = tk.Label(root, text="Audio Folder:")
folder_label.pack()
folder_entry = tk.Entry(root, width=50)
folder_entry.pack()
folder_button = tk.Button(root, text="Browse", command=select_folder)
folder_button.pack()

table_frame = tk.Frame(root)
table_frame.pack(expand=True, fill=tk.BOTH)

table = ttk.Treeview(table_frame, columns=("Token", "Audio File", "Action"), show="headings")
table.heading("Token", text="Token")
table.heading("Audio File", text="Audio File")
table.heading("Action", text="Action")
table.bind("<Double-1>", on_manage_click)
table.pack(expand=True, fill=tk.BOTH)

generate_audio_frame = tk.Frame(root)
generate_audio_frame.pack(fill=tk.X)

generate_filename_label = tk.Label(generate_audio_frame, text="Generate Audio Filename:")
generate_filename_label.pack(side=tk.LEFT, padx=5)

generate_filename_entry = tk.Entry(generate_audio_frame, width=20)
generate_filename_entry.pack(side=tk.LEFT)

generate_audio_button = tk.Button(generate_audio_frame, text="Generate Audio", command=generate_audio)
generate_audio_button.pack(side=tk.LEFT, padx=5)

tokens = []
mapping = {}

root.mainloop()

import tkinter as tk
from tkinter import ttk
import sounddevice as sd
import numpy as np
import speech_recognition as sr
from scipy.io.wavfile import write
from googletrans import Translator, LANGUAGES
from gtts import gTTS
import pygame  # New import for pygame
import tempfile
import os
import threading
import queue
import asyncio

# Initialize pygame mixer
pygame.mixer.init()

# Initialize the translator
translator = Translator()

# Create a reverse mapping from language names to their codes
language_code_mapping = {name.lower(): code for code, name in LANGUAGES.items()}

# Queue to store audio chunks for processing
audio_queue = queue.Queue()

# Increase chunk size to 1 second for better audio capture
chunk_size = 5  # Record 1 second of audio at a time
sample_rate = 16000   # Sample rate (8kHz)

# Function to capture audio in a non-blocking way
def capture_audio():
    global stop_recording
    recognizer = sr.Recognizer()

    while not stop_recording:
        input_text.set("Listening...")
        # Capture real-time audio in small chunks
        recording = sd.rec(int(chunk_size * sample_rate), samplerate=sample_rate, channels=1, dtype=np.int16)
        sd.wait()

        # Detect silence and stop recording if silence is detected
        if detect_silence(recording):
            input_text.set("Silence detected. Stopping...")
            continue

        # Save the chunk and queue it for processing
        filename = tempfile.mktemp(suffix='.wav')
        write(filename, sample_rate, recording)
        audio_queue.put(filename)

# Detect silence based on average energy levels
def detect_silence(audio_chunk, silence_threshold=0.01):
    energy = np.abs(audio_chunk).mean()
    return energy < silence_threshold

# Function to process audio from the queue continuously
async def process_audio_queue():
    while not stop_recording:
        if not audio_queue.empty():
            filename = audio_queue.get()
            await handle_audio(filename)

# Function to recognize and translate speech from audio with retry logic
async def handle_audio(filename):
    try:
        recognizer = sr.Recognizer()
        with sr.AudioFile(filename) as source:
            # Adjust for background noise for a longer duration
            recognizer.adjust_for_ambient_noise(source, duration=1)
            audio = recognizer.record(source)
            lang_code = language_code_mapping[source_language.get().lower()]
            text = recognize_with_retry(recognizer, audio, lang_code)
            input_text.set(f"Recognized: {text}")
            print(f"Recognized: {text}")
            await translate_text(text)
    except sr.UnknownValueError:
        input_text.set("Could not understand audio.")
        print("Could not understand audio.")
    except sr.RequestError as e:
        input_text.set(f"Error with recognition service: {e}")
        print(f"Error with recognition service: {e}")
    except KeyError:
        input_text.set("Selected source language not supported.")
        print("Selected source language not supported.")
    except Exception as e:
        input_text.set(f"Error: {str(e)}")
        print(f"Error: {str(e)}")

# Function to recognize speech with retries
def recognize_with_retry(recognizer, audio, lang_code, retries=3):
    for attempt in range(retries):
        try:
            return recognizer.recognize_google(audio, language=lang_code)
        except sr.RequestError as e:
            print(f"Attempt {attempt + 1} failed: {e}")
            if attempt == retries - 1:
                raise e

# Function to translate text asynchronously
async def translate_text(source_text):
    if source_text:
        try:
            selected_target_language = target_language.get().lower()
            translated_lang_code = language_code_mapping[selected_target_language]
            translated = translator.translate(source_text, src=language_code_mapping[source_language.get().lower()], dest=translated_lang_code)
            output_text.set(f"Translated: {translated.text}")
            print(f"Translated: {translated.text}")
            await speak_translated_text(translated.text)
        except Exception as e:
            output_text.set(f"Translation Error: {str(e)}")
            print(f"Translation Error: {str(e)}")
    else:
        output_text.set("No input text to translate.")
        print("No input text to translate.")

# Function to convert text to speech asynchronously using pygame
async def speak_translated_text(text_to_speak):
    if text_to_speak:
        try:
            # Create a temporary MP3 file using gTTS
            temp_mp3_file = tempfile.mktemp(suffix='.mp3')
            tts = gTTS(text=text_to_speak, lang=language_code_mapping[target_language.get().lower()])
            tts.save(temp_mp3_file)

            # Play the audio using pygame mixer
            pygame.mixer.music.load(temp_mp3_file)
            pygame.mixer.music.play()

            # Wait for the audio to finish playing
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)

            # Clean up temporary file after a short delay
            await asyncio.sleep(0.1)  # Ensure the file is not in use before deleting
            os.remove(temp_mp3_file)
        except Exception as e:
            print(f"Error in speech synthesis: {str(e)}")

# Function to draw a capsule button with a 3D effect
def create_3d_capsule_button(parent, text, command, width, height=30, radius=20, relief="raised", **kwargs):
    canvas = tk.Canvas(parent, width=width, height=height, highlightthickness=0, bg=parent['bg'])
    canvas.pack(pady=5)

    # Create a capsule shape for the button background
    canvas.create_arc((0, 0, 2*radius, 2*radius), start=90, extent=180, fill="#3498DB", outline="")
    canvas.create_arc((width-2*radius, 0, width, 2*radius), start=270, extent=180, fill="#3498DB", outline="")
    canvas.create_rectangle((radius, 0, width-radius, height), fill="#3498DB", outline="")
    
    # Configure the button for a 3D look
    button = tk.Button(parent, text=text, command=command, relief=relief, borderwidth=4, **kwargs)
    button.configure(bg="#3498DB", fg="#FFFFFF", font=("Arial", 14), activebackground="#2980B9", activeforeground="#FFFFFF")
    canvas.create_window(width/2, height/2, window=button)
    return button

# Function to start recording and translation
def start_process():
    global stop_recording
    stop_recording = False
    # Start capturing audio in a thread
    threading.Thread(target=capture_audio).start()
    # Start processing the audio queue in the main thread with asyncio
    threading.Thread(target=lambda: asyncio.run(process_audio_queue())).start()

# Function to stop the recording process
def stop_process():
    global stop_recording
    stop_recording = True

# Populate languages with complete names
languages = LANGUAGES

# Create the GUI using tkinter with modern styling
root = tk.Tk()
root.title("BaatChit")
root.geometry("600x400")
root.configure(bg="#2998EC")

# Styling variables
button_style = {"bg": "#2980B9", "fg": "#FFFFFF", "font": ("Helvetica", 14), "relief": tk.RAISED, "bd": 3}
label_style = {"bg": "#2998EC", "fg": "#ECF0F1", "font": ("Helvetica", 12)}
entry_style = {"bg": "#ECF0F1", "fg": "#2998EC", "font": ("Helvetica", 12), "bd": 2}

# Input text field (recognized speech)
input_text = tk.StringVar()
tk.Label(root, text="Input (Speech to Text):", **label_style).pack(pady=(10, 0))
tk.Entry(root, textvariable=input_text, width=50, **entry_style).pack(pady=5)

# Source Language Selection (default to Hindi)
tk.Label(root, text="Source Language:", **label_style).pack()
source_language = tk.StringVar(value="Hindi")
source_language_dropdown = ttk.Combobox(root, textvariable=source_language, values=list(LANGUAGES.values()), state="readonly")
source_language_dropdown.pack(pady=5)

# Target Language Selection (default to English)
tk.Label(root, text="Target Language:", **label_style).pack()
target_language = tk.StringVar(value="English")
target_language_dropdown = ttk.Combobox(root, textvariable=target_language, values=list(LANGUAGES.values()), state="readonly")
target_language_dropdown.pack(pady=5)

# Output text field (translated text)
output_text = tk.StringVar()
tk.Label(root, text="Translated Text:", **label_style).pack(pady=(10, 0))
tk.Entry(root, textvariable=output_text, width=50, **entry_style).pack(pady=5)

# Start and Stop buttons with rounded edges
create_3d_capsule_button(root, "Start", start_process, 200, 50, relief="raised")
create_3d_capsule_button(root, "Stop", stop_process, 200, 50, relief="raised", bg="#E74C3C")

# Variable to control the recording loop
stop_recording = False

# Run the tkinter loop
root.mainloop()
from flask import Flask, request, jsonify
from fun import (
    transcribe_audio,
    get_wav_duration,
    analyze_audio,
    compare_lines,
    count_duplicate_lines,
    count_skipped_lines,
    count_words
)
import requests
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
from difflib import SequenceMatcher

app = Flask(__name__)

recognizer = sr.Recognizer()
def transcribe_audio_with_ffmpeg(audio_file_url, recognizer, language="nl-NL"):
    temp_file_path = "file.wav"  # Set the desired filename

    try:
        # Download the audio file directly from the URL
        response = requests.get(audio_file_url)
        if response.status_code != 200:
            raise Exception(f"Failed to download audio from the provided URL. Status code: {response.status_code}")

        # Save audio data to a temporary file with the desired filename
        with open(temp_file_path, "wb") as temp_file:
            temp_file.write(response.content)

        # Provide the path to ffmpeg and ffprobe
        AudioSegment.converter = "/usr/bin/ffmpeg"
        AudioSegment.ffmpeg = "/usr/bin/ffmpeg"
        AudioSegment.ffprobe = "/usr/bin/ffprobe"

        # Convert audio to WAV format using pydub
        try:
            audio = AudioSegment.from_file(temp_file_path)
            audio.export('temp.wav', format="wav")
        except CouldntDecodeError:
            raise Exception("Failed to decode audio file. Check if the file is in a supported format.")

        # Use the recognizer directly without using pydub
        with sr.AudioFile('temp.wav') as source:
            recognizer.adjust_for_ambient_noise(source)

            audio = recognizer.record(source)
            response = recognizer.recognize_google(audio, language=language, show_all=True)

            if 'alternative' in response:
                # Extract the first alternative transcription
                alternative = response['alternative'][0]
                text = alternative.get('transcript', '')
                confidence = alternative.get('confidence', None)

                # Insert a line break when there's a pause in speech
                pauses = recognizer.pause_threshold
                text_with_line_breaks = ""
                for i, phrase in enumerate(text.split('\n')):
                    if i > 0:
                        text_with_line_breaks += '\n'

                    text_with_line_breaks += phrase

                    # Check if there is a pause between phrases
                    if i < len(text.split('\n')) - 1:
                        duration = recognizer.get_duration(audio)
                        if duration > pauses:
                            text_with_line_breaks += '\n'

                return text_with_line_breaks, confidence

            else:
                return "No transcription found in the response", None

    except sr.UnknownValueError:
        return "Could not understand audio", None

    except sr.RequestError as e:
        return f"Could not request results; {str(e)}", None

    finally:
        # No need to remove the temporary file since it's now "file.wav"
        pass

@app.route('/process_audio', methods=['POST'])
def process_audio():
    try:
        # Get data from the request
        data = request.get_json()
        audio_url = data.get('audio_url')
        original_text = data.get('original_text')

        # Download audio (you may need to install another library for this)
        # You can replace this with your own method to handle audio files
        # For example, using requests to download the file
        # import requests
        # audio_content = requests.get(audio_url).content

        # Call the functions
        transcribed_text, confidence = transcribe_audio_with_ffmpeg(audio_url, recognizer, language="nl-NL")
        # transcribed_text = transcribe_audio(audio_url)
        print(transcribe_audio)
        duration = get_wav_duration('temp.wav')
        analysis_result = analyze_audio('temp.wav')
        deleted_words, inserted_words, substituted_words, repeated_words = compare_lines(original_text, transcribed_text)
        dup = count_duplicate_lines(transcribed_text)
        skip = count_skipped_lines(transcribed_text)
        word_count = count_words(transcribed_text)

        # Prepare JSON response
        response = {
            'transcribed_text': transcribed_text,
            'duration': duration,
            'analysis_result': analysis_result,
            'deleted_words': deleted_words,
            'inserted_words': inserted_words,
            'substituted_words': substituted_words,
            'repeated_words': repeated_words,
            'duplicate_lines': dup,
            'skipped_lines': skip,
            'word_count': word_count
        }

        return jsonify(response)

    except Exception as e:
        # Handle exceptions and return an error response
        return jsonify({'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)

from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
import json
from flask_cors import CORS
import time

from fun import analyze_audio, compare_lines, count_duplicate_lines, count_skipped_lines, count_words, calculate_word_count_ratio, get_wav_duration
app = Flask(__name__)
recognizer = sr.Recognizer()
CORS(app, origins="*")
def calculate_error_metrics(original_text, transcribed_text, delete, insert, sub, manual_text):
    words_original = original_text.split()
    words_transcribed = transcribed_text.split()

    if manual_text:
        words_manual_text = manual_text.split()
        wt_maual = len(words_manual_text)
    else:
        words_manual_text = []
        wt_maual = 0

    wr = len(words_transcribed)
    wt_original = len(words_original)
    wc = wt_original - (delete + insert + sub)

    acc = wc * 100 / wt_original
    wc = max(0, wc)
    acc = max(0, acc)
    oriVsTran = 100 * min(wt_original / wr, wr / wt_original)
    manualVsTrans = 100 * min(wt_maual / wr, wr / wt_maual) if wt_maual > 0 else 0
    manualVsorginal = 100 * min(wt_maual / wt_original, wt_original / wt_maual) if wt_maual > 0 else 0

    error_metrics = {
        'WR': wr,
        'WC': wc,
        'Words Correct per Minute': calculate_words_per_minute(wc, transcribed_text),
        'Acc': acc,
        'oriVsTran': oriVsTran,
        'manualVsTrans': manualVsTrans,
        'manualVsorginal': manualVsorginal
    }

    return error_metrics
def calculate_words_per_minute(words_correct, transcribed_text):
    audio_duration = get_wav_duration('temp.wav')
    words_per_minute = (words_correct / audio_duration) * 60
    # Round the words_per_minute to the nearest whole number
    words_per_minute = round(words_per_minute)
    return words_per_minute
def calculate_pause_metrics(transcribed_text):
    # Implement your logic to calculate pause metrics
    # ...
    # Placeholder values, replace with actual calculations
    pauses_1_3_seconds = 5
    hesitations_3_seconds = 2
    pause_metrics = {
        'Pauses (1-3 seconds)': pauses_1_3_seconds,
        'Hesitations (3+ seconds)': hesitations_3_seconds,
        # Add other pause metrics as needed
    }
    return pause_metrics
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

def format_word_list(word_list):
    return [{'ID': entry['ID'], 'Word': entry['Word']} for entry in word_list]
bufferData=[]
@app.route('/process_audio', methods=['POST'])
def process_audio():
    try:
        # Get data from the request
        data = request.get_json()
        audio_url = data.get('audio_url')
        original_text = data.get('original_text')
       
        manual_text= data.get('manual_text')
        # Call the functions
        transcrib = ''
        id = data.get('id')
        if id and audio_url:
            transcribed_text, confidence = transcribe_audio_with_ffmpeg(audio_url, recognizer, language="nl-NL")
            newData = {}
            newData["id"] = id
            newData["Text"] = transcribed_text
            bufferData.append(newData)
            print(bufferData)
            response = {
            'staus': 'done with audio at google'
        }
            return jsonify(response)
        else:  
            print("okok")
            print("Searching for ID:", id)

            start_time = time.time()
            timeout_duration = 90  # 90 seconds = 1.5 minutes
            id_found = False

            while not id_found and time.time() - start_time < timeout_duration:
                elapsed_time = time.time() - start_time
                print(f"Elapsed time: {elapsed_time:.2f} seconds")

                for item in bufferData:
                    if 'id' in item and item['id'] == id:
                        transcrib = item['Text']
                        print("Data of this:", transcrib)
                        id_found = True  # Set the flag to True when ID is found
                        break   
        # Additional analysis
            analysis_result = analyze_audio('temp.wav')
            substituted_words,delete_words,insert_words,merged= compare_lines(original_text, transcrib)
            duplicate_lines = count_duplicate_lines(transcrib)
            skipped_lines = count_skipped_lines(transcrib)
            word_count = count_words(transcrib)
            # Calculate accuracy, audio duration, and transcription confidence score
            correct_words = word_count - len(insert_words)  # Exclude inserted words from the correct count
            accuracy = (correct_words / word_count) * 100 if word_count != 0 else 0
            audio_duration = get_wav_duration('temp.wav')
            # transcription_confidence = confidence if confidence is not None else 0
            original_vs_audio = calculate_word_count_ratio(transcrib, original_text)
            
        
            delete, insert, sub = len(delete_words), len(insert_words), len(substituted_words)
            print(delete,insert,sub)
            error_metrics = calculate_error_metrics(original_text, transcrib, delete, insert, sub, manual_text)


            formatted_deleted_words = format_word_list(delete_words)
            formatted_inserted_words = format_word_list(insert_words)
            formatted_substituted_words = format_word_list(substituted_words)
            # merded_formeted = format_word_list(merged)

        
            accuracy=error_metrics['Acc']

            original_vs_audio = calculate_word_count_ratio(transcrib, original_text)
            # Prepare JSON response with additional outcomes
            response = {
        'transcribed_text': transcrib,
        'analysis_result': analysis_result,
        'deleted_words': formatted_deleted_words,
        'inserted_words':  formatted_inserted_words,
        'merged':merged,
        'substituted_words': formatted_substituted_words,
        'duplicate_lines': count_duplicate_lines(transcrib),
        'skipped_lines': count_skipped_lines(transcrib),
        # 'word_count': word_count,
        'error_metrics': error_metrics,
        # 'pause_metrics': pause_metrics,
        'original_vs_audio': error_metrics['oriVsTran'],
        'manualVsTrans':error_metrics['manualVsTrans'],
        'manualVsorginal':error_metrics['manualVsorginal'],
        'accuracy': accuracy,
        'audio_duration': audio_duration,
        
    }
            return jsonify(response)
    except Exception as e:
        
        return jsonify({'error': str(e)})
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

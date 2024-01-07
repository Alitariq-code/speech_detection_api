
import speech_recognition as sr
from pydub import AudioSegment
from pydub.silence import split_on_silence
from difflib import SequenceMatcher

import re
import pandas as pd

from fuzzywuzzy import fuzz

def remove_newlines(text):
    cleaned_text = text.replace('\n', ' ')
    return cleaned_text
def remove_punctuation(text):
    # Remove commas and periods
    cleaned_text = text.replace(',', '').replace('.', ' ')
    cleaned_text = cleaned_text.replace('“', '').replace('”', ' ')
    return cleaned_text
def track_deleted_words(original_lines, spoken_lines):
    print(original_lines,spoken_lines)
    original_lines = original_lines.split()
    spoken_lines = spoken_lines.split()
    print('inside deleted',type(original_lines),type(spoken_lines))
    # Initialize lists to store deleted words and their positions
    deleted_words = []
    deleted_positions = []
    

    # Iterate through each word in the original text
    for index, word in enumerate(original_lines):
        # print(word)
        # Check if the word is missing in the spoken text
        word = word.strip()  
        if word not in spoken_lines:
            # print("worddddddsssssssssssssss-----------------------",word)
            deleted_words.append(word)
            deleted_positions.append(index)
            
    # print(deleted_positions)
    # print("issue",deleted_positions,deleted_words)
    return deleted_words, deleted_positions


def track_inserted_words(original_lines, spoken_lines):

    original_words = original_lines.split()
    spoken_words = spoken_lines.split()
    # print("okok",spoken_words)
    # print("okoksss",original_words)
    # Initialize lists to store inserted words and their positions
    
    inserted_words = []
    inserted_positions = []
    # print("insertion------")
    # print(spoken_words)
    # print(original_words)


    # Iterate through each word in the spoken text
    for index, word in enumerate(spoken_words):
        # print("orgi",original_words)

        # Check if the word is not in the original text
        if word not in original_words:
            inserted_words.append(word)
            inserted_positions.append(index)
    print("posi",inserted_words)
    return inserted_words, inserted_positions


def find_most_similar(word, word_list):
    similarities = [(w, SequenceMatcher(None, word, w).ratio()) for w in word_list]
    similarities.sort(key=lambda x: x[1], reverse=True)
    return similarities[0]

def transcribe_audio(audio_file_path, language="nl-NL"):
    """
    Transcribes audio from a given file path using Google Speech Recognition.

    Parameters:
    - audio_file_path (str): Path to thprint("okok",spoken_words)
    # print("okoksss",original_words)e audio file.
    - language (str): Language code for transcription (default is "nl-NL").

    Returns:
    - str: Transcribed text.
    """
    recognizer = sr.Recognizer()

    # Provide the path to ffmpeg and ffprobe
    AudioSegment.converter = "/usr/bin/ffmpeg"
    AudioSegment.ffmpeg = "/usr/bin/ffmpeg"
    AudioSegment.ffprobe = "/usr/bin/ffprobe"

    audio = AudioSegment.from_file(audio_file_path)
    audio.export("temp.wav", format="wav")

    with sr.AudioFile("temp.wav") as source:
        recognizer.adjust_for_ambient_noise(source)

        try:
            audio = recognizer.record(source)
            text = recognizer.recognize_google(audio, language=language)

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

            return text_with_line_breaks

        except sr.UnknownValueError:
            return "Could not understand audio"

        except sr.RequestError as e:
            return f"Could not request results; {str(e)}"

def get_wav_duration(file_path):
    """
    Get the duration of a WAV file.

    Parameters:
    - file_path (str): Path to the WAV file.

    Returns:
    - float: Duration in seconds.
    """
    audio = AudioSegment.from_file(file_path)
    duration_in_seconds = len(audio) / 1000.0
    return duration_in_seconds

def analyze_audio(file_path):
    """
    Analyze audio for word repetitions, short pauses, and long pauses.

    Parameters:
    - file_path (str): Path to the audio file.

    Returns:
    - dict: Analysis results.
    """
    audio = AudioSegment.from_file(file_path, format="wav")
    
    # Set thresholds for pause durations
    short_pause_threshold = 3000  # 3 seconds
    long_pause_threshold = 3000   # 3 seconds
    
    # Initialize variables for counting repetitions and pauses
    word_repetitions = 0
    short_pauses = 0
    long_pauses = 0
    
    # Split audio on silence
    segments = split_on_silence(audio, silence_thresh=-40)  # Adjust the threshold based on your audio
    
    # Iterate through the segments
    for i in range(len(segments)):
        segment_duration = len(segments[i])
        
        # Check if the segment duration falls within the pause thresholds
        if segment_duration >= short_pause_threshold and segment_duration <= long_pause_threshold:
            short_pauses += 1
        elif segment_duration > long_pause_threshold:
            long_pauses += 1
        
        # Check for repeated words within a 3-second window
        window_start = max(0, i - 1)
        window_end = min(len(segments), i + 1)
        window = segments[window_start:window_end]
        
        if len(window) > 1 and compare_segments(segments[i], sum(window)):
            word_repetitions += 1
    
    return {
        "word_repetitions": word_repetitions,
        "short_pauses": short_pauses,
        "long_pauses": long_pauses
    }


def compare_lines(original_text, spoken_text):
    def preprocess_text(text):
        return re.sub(r'[\r\n]+', ' ', re.sub(r'[^\w\s]', ' ', text)).lower()
    def align_texts(original, spoken):
        sequence_matcher = SequenceMatcher(None, original, spoken)
        operations = []
        for opcode in sequence_matcher.get_opcodes():
            tag, i1, i2, j1, j2 = opcode
            if tag == 'delete':
                operations.append(['Deletion', ' '.join(original[i1:i2]), i1, i2-1, '', '', '', '', '', 0])
            elif tag == 'insert':
                before_context = ' '.join(spoken[max(0, j1-1):j1])
                after_context = ' '.join(spoken[j2:min(len(spoken), j2+1)])
                operations.append(['Insertion', '', '', '', ' '.join(spoken[j1:j2]), j1, j2-1, before_context, after_context, 0])
            elif tag == 'replace':
                original_segment = ' '.join(original[i1:i2])
                spoken_segment = ' '.join(spoken[j1:j2])
                similarity = fuzz.ratio(original_segment, spoken_segment)
                operations.append(['Substitution', original_segment, i1, i2-1, spoken_segment, j1, j2-1, '', '', similarity])
        return operations
    def process_substitutions(df):
        new_rows = []
        for index, row in df.iterrows():
            if row['Operation'] == 'Substitution' and row['Similarity'] < 40:
                # Splitting the row into two parts: Insertion and Deletion
                insertion_row = row.copy()
                insertion_row['Operation'] = 'Insertion'
                deletion_row = row.copy()
                deletion_row['Operation'] = 'Deletion'
                new_rows.extend([insertion_row, deletion_row])
            else:
                new_rows.append(row)
        return pd.DataFrame(new_rows)
    # Preprocessing texts
    preprocessed_original_text = preprocess_text(original_text).split()
    preprocessed_spoken_text = preprocess_text(spoken_text).split()
    # Aligning and getting differences
    differences = align_texts(preprocessed_original_text, preprocessed_spoken_text)
    # Creating DataFrame
    df = pd.DataFrame(differences, columns=['Operation', 'Original Segment', 'Original Start', 'Original End', 'Spoken Segment', 'Spoken Start', 'Spoken End', 'Before Context', 'After Context', 'Similarity'])
    # Process substitutions
    processed_df = process_substitutions(df)
    # Function to select columns based on the operation
    def select_columns(row):
        if row['Operation'] in ['Insertion', 'Substitution']:
            return pd.Series([row['Operation'], row['Spoken Segment'], row['Spoken Start'], row['Spoken End']])
        elif row['Operation'] == 'Deletion':
            return pd.Series([row['Operation'], row['Original Segment'], row['Original Start'], row['Original End']])
    # Define a function to determine the class based on the color
    def determine_class(color):
        if color == 'Red':
            return 'Deletion'
        elif color == 'Yellow':
            return 'Substitution'
        elif color == 'Pink':
            return 'Insertion'
        elif color == 'Green':
            return 'Correct'
        else:
            return 'Unknown'

    # Function to generate ID and word pairs
    def generate_id_word_pairs(row):
        start = row['Start/Spoken Start']
        end = row['End/Spoken End']
        segment = row['Segment/Original Segment']
        # Split the segment into words
        words = segment.split()
        # Generate ID and word pairs
        id_word_pairs = [(start + i, word) for i, word in enumerate(words)]
        return id_word_pairs
    try:
        # Applying the function to each row and reformating DataFrame
        reformatted_df = processed_df.apply(select_columns, axis=1)
        reformatted_df.columns = ['Operation', 'Segment/Original Segment', 'Start/Spoken Start', 'End/Spoken End']
        reformatted_df=reformatted_df.reset_index(drop=True)
        insert=reformatted_df[reformatted_df['Operation']=='Insertion']
        delete=reformatted_df[reformatted_df['Operation']=='Deletion']
        subt=reformatted_df[reformatted_df['Operation']=='Substitution']
        # Apply the function to each row and flatten the list
        try:
            id_word_pairs_list = insert.apply(generate_id_word_pairs, axis=1).explode()
            # Create a new dataframe with ID and word columns
            insert_df = pd.DataFrame(id_word_pairs_list.tolist(), columns=['ID', 'word'])
        except:
            insert_df = pd.DataFrame(columns=['ID', 'word'])
        try:
            # Apply the function to each row and flatten the list
            id_word_pairs_list = delete.apply(generate_id_word_pairs, axis=1).explode()
            # Create a new dataframe with ID and word columns
            delete_df = pd.DataFrame(id_word_pairs_list.tolist(), columns=['ID', 'word'])
        except:
            delete_df= pd.DataFrame(columns=['ID', 'word'])
        try:
            id_word_pairs_list = subt.apply(generate_id_word_pairs, axis=1).explode()
            # Create a new dataframe with ID and word columns
            subt_df = pd.DataFrame(id_word_pairs_list.tolist(), columns=['ID', 'word'])
        except:
            subt_df= pd.DataFrame(columns=['ID', 'word'])
        # Iterate over each row in the Substitution DataFrame
        substituted_words = []
        delete_words = []
        insert_words = []
        for index, row in subt_df.iterrows():
            substituted_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            substituted_words.append(substituted_word)
        for index, row in delete_df.iterrows():
            delete_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            delete_words.append(delete_word)
        for index, row in insert_df.iterrows():
            insert_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            insert_words.append(insert_word)
    # ...
        print("subWOrds",substituted_words)
        print("deleted",delete_words)
        print("insert",insert_words)
    except:
        delete_df= pd.DataFrame(columns=['ID', 'word'])
        subt_df= pd.DataFrame(columns=['ID', 'word'])
        insert_df= pd.DataFrame(columns=['ID', 'word'])
        substituted_words = []
        delete_words = []
        insert_words = []
        for index, row in subt_df.iterrows():
            substituted_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            substituted_words.append(substituted_word)
        for index, row in delete_df.iterrows():
            delete_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            delete_words.append(delete_word)
        for index, row in insert_df.iterrows():
            insert_word = {
            'ID': row['ID'],
            'Word': row['word'],
        }
            insert_words.append(insert_word)
    # ...
        print("subWOrds",substituted_words)
        print("deleted",delete_words)
        print("insert",insert_words)
    spoken_df = pd.DataFrame({'ID': range(len(preprocessed_spoken_text)), 'word': preprocessed_spoken_text})
    spoken_df['Color']='Green'
    merged_df = pd.merge(spoken_df, subt_df, on='ID', how='left', suffixes=('_spoken', '_subt'))
    merged_df['Color'] = merged_df['Color'].where(merged_df['word_subt'].isnull(), 'Yellow')
    merged_df=merged_df[['ID','word_spoken','Color']]
    merged_df = pd.merge(merged_df, insert_df, on='ID', how='left', suffixes=('', '_insr'))
    merged_df['Color'] = merged_df['Color'].where(merged_df['word'].isnull(), 'Pink')
    merged_df=merged_df[['ID','word_spoken','Color']]
    delete_df['Color']='Red'
    delete_df.columns=merged_df.columns
    merged_df=pd.concat([merged_df,delete_df])
    merged_df=merged_df.sort_values("ID")
    merged_df=merged_df.reset_index().reset_index()
    merged_df=merged_df[['level_0','word_spoken','Color']]
    merged_df.columns=delete_df.columns
    # Create a new column 'Class' based on the 'Color' column
    merged_df['Class'] = merged_df['Color'].apply(determine_class)
    merged = [] 
    for index, row in merged_df.iterrows():
            insert_word = {
            'ID': row['ID'],
            'Word': row['word_spoken'],
            'Color': row['Color'],
            'Class': row['Class'],
        }
            merged.append(insert_word)
    return substituted_words,delete_words,insert_words,merged


def count_duplicate_lines(text_data):
    """
    Count the number of duplicate lines in the given text data.

    Parameters:
    - text_data (str): Text data.

    Returns:
    - int: Number of duplicate lines.
    """
    seen_lines = set()
    duplicate_count = 0

    lines = text_data.split('\n')  # Split the input text into lines

    for line in lines:
        line = line.strip()  # Remove leading and trailing whitespaces
        if not line:
            continue  # Skip empty lines

        if line in seen_lines:
            duplicate_count += 1
        else:
            seen_lines.add(line)

    return duplicate_count
def count_words(text):
    words = text.split()
    return len(words)

# word_count = count_words(original_text)

def count_skipped_lines(text_data):
    """
    Count the number of skipped lines in the given text data.

    Parameters:
    - text_data (str): Text data.

    Returns:
    - int: Number of skipped lines.
    """
    lines = text_data.split('\n')  # Split the input text into lines
    skipped_count = 0

    for i in range(1, len(lines) - 1):
        current_line = lines[i].strip()
        next_line = lines[i + 1].strip()

        if not next_line:
            skipped_count += 1

    return skipped_count

def count_words(text):
    """
    Count the number of words in the given text.

    Parameters:
    - text (str): Text.

    Returns:
    - int: Number of words.
    """
    words = text.split()
    return len(words)

def remove_duplicates(word_list):
    """
    Remove duplicates from a list while maintaining the order.

    Parameters:
    - word_list (list): List of words.

    Returns:
    - list: List with duplicates removed.
    """
    unique_words = []
    seen_words = set()

    for word in word_list:
        if word not in seen_words:
            unique_words.append(word)
            seen_words.add(word)

    return unique_words

# def remove_newlines(text):
#     """
#     Remove newline characters from the given text.

#     Parameters:
#     - text (str): Text.

#     Returns:
#     - str: Text with newlines removed.
#     """
#     return text.replace('\n', '')


def compare_segments(segment1, segment2):
    """
    Compare two audio segments based on their root mean square (RMS) values.

    Parameters:
    - segment1 (AudioSegment): First audio segment.
    - segment2 (AudioSegment): Second audio segment.

    Returns:
    - bool: True if the RMS of segment1 is greater than 80% of the RMS of segment2, else False.
    """
    return segment1.set_frame_rate(44100).set_channels(1).rms > segment2.set_frame_rate(44100).set_channels(1).rms * 0.8


def find_repeated_words(text):
    words = text.split()
    repeated_words = []
    for i in range(len(words) - 1):
        if words[i] == words[i + 1]:
            repeated_words.append(words[i])
    return repeated_words



def calculate_word_count_ratio(transcribed_text, original_text, max_ratio=100):
    word_count_org = count_words(original_text)
    word_count_transcribed = count_words(transcribed_text)

    ratio = min(100*word_count_org / word_count_transcribed , word_count_transcribed* 100/word_count_org)
    return ratio


# Example usage:
# transcribed_text = transcribe_audio("/home/alicode/Desktop/stock/AVI 4.wav")
# duration = get_wav_duration('temp.wav')
# analysis_result = analyze_audio('temp.wav')
# deleted_words, inserted_words, substituted_words, repeated_words = compare_lines(org, transcribed_text)
# dup = count_duplicate_lines(transcribed_text)
# skip = count_skipped_lines(transcribed_text)
# word_count = count_words(transcribed_text)
# ...

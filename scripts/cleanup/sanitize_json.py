#!/usr/bin/env python3
"""
Sanitizes master.json to extract specific fields into sanitized.json
"""

import json


def sanitize_master_json(input_file='master.json', output_file='sanitized.json'):
    """
    Extract specific fields from master.json and save to sanitized.json
    
    Extracted fields:
    1. uploader
    2. description  
    3. view_count
    4. like_count
    5. comment_count
    6. subtitle_transcription
    7. upload_date
    """
    
    # Read the master.json file
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Extract only the specified fields for videos with subtitle_transcription > 40 characters
    sanitized_data = []
    
    for video in data:
        subtitle_transcription = video.get('subtitle_transcription', '')
        
        # Only include videos with subtitle_transcription longer than 40 characters
        if len(subtitle_transcription) > 40:
            sanitized_video = {
                'uploader': video.get('uploader', ''),
                'description': video.get('description', ''),
                'view_count': video.get('view_count', 0),
                'like_count': video.get('like_count', 0),
                'comment_count': video.get('comment_count', 0),
                'subtitle_transcription': subtitle_transcription,
                'upload_date': video.get('upload_date', '')
            }
            sanitized_data.append(sanitized_video)
    
    # Write sanitized data to output file
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(sanitized_data, f, indent=2, ensure_ascii=False)
    
    print(f"Sanitized {len(sanitized_data)} videos from {input_file} to {output_file}")


if __name__ == '__main__':
    sanitize_master_json()
import requests, json, time, os, subprocess, ffmpeg
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from requests_oauthlib import OAuth1
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Twitter credentials (replace with clips channel when api access granted)
api_key = os.getenv('api_key')
api_secret_key = os.getenv('api_secret_key')
access_token = os.getenv('access_token')
access_token_secret = os.getenv('access_token_secret')

# Twitch credentials
client_id = os.getenv('client_id')
client_secret = os.getenv('client_secret')
channel_id = os.getenv('channel_id')

# Email credentials
host_email = os.getenv('host_email')
recipt_email = os.getenv('recipt_email')
host_email_password = os.getenv('host_email_password')

# Other config variables
ffmpeg_path = "E:\\ffmpeg-6.1-essentials_build\\bin\\ffmpeg.exe"
smtp_email_server = 'smtp.gmail.com'

def convert_video_for_twitter(input_path, output_path):
    # The command line arguments to use 'ffmpeg' for conversion

    ffmpeg_command = [
        ffmpeg_path, # Change this to be wherever FFMpeg is located
        '-i', input_path,    # Input file
        '-c:v', 'libx264',  # Video codec to use
        '-preset', 'fast',  # Preset for encoding speed/quality tradeoff
        '-c:a', 'aac',      # Audio codec to use
        '-strict', 'experimental', # Allow experimental codecs (required for some versions of 'ffmpeg' for AAC)
        '-b:a', '128k',     # Audio bitrate
        output_path         # Output file
    ]

    # Run the command
    try:
        # Start the conversion process and capture the output
        with subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, bufsize=1, universal_newlines=True) as process:
            for line in process.stdout:  # This loop will print the output in real-time
                print(line, end='')  # Print FFmpeg progress on the same line
            process.wait()  # Wait for the FFmpeg process to finish
        print("Conversion completed successfully.")
        if input_path != output_path and os.path.exists(input_path):
                os.remove(input_path)
                print(f"Deleted the original file: {input_path}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Conversion failed with error: {e.stderr}")
        return False
    except Exception as e:
        print(f"An error occurred: {e}")
        return False
    
def send_error_email(subject, message):
    msg = MIMEMultipart()
    msg['From'] = host_email
    msg['To'] = recipt_email
    msg['Subject'] = subject

    body = MIMEText(message, 'plain')
    msg.attach(body)

    try:
        server = smtplib.SMTP(smtp_email_server, 587)
        server.starttls()
        server.login(host_email, host_email_password)
        text = msg.as_string()
        server.sendmail(host_email, recipt_email, text)
        server.quit()
        print("Email sent successfully")
    except Exception as e:
        print(f"Failed to send email: {e}")

def append_unique_clips(new_clips, file_path='clipsToBePosted.json', posted_file_path='postedClips.json'):
    # Read the existing content of the file or initialize it if the file doesn't exist
    try:
        with open(file_path, 'r') as file:
            existing_clips = json.load(file)
    except FileNotFoundError:
        existing_clips = []

    try:
        with open(posted_file_path, 'r') as file:
            posted_clips = json.load(file)
    except FileNotFoundError:
        posted_clips = []

    # Extract existing clip IDs
    existing_ids = {clip['id'] for clip in existing_clips}
    existing_ids.update(clip['id'] for clip in posted_clips)

    new_clips_number = 0
    
    # Append new clips that are not already present in the existing clips
    # Currently set to client's specifications, would need to be updated per client or standardized if deployed publicly
    for clip in new_clips:
        if clip['id'] not in existing_ids and "!clip" not in clip['title'] and "!noclips" not in clip['title']:

            clip_url = clip['thumbnail_url'].replace('-preview-480x272.jpg', '.mp4')

            # Download the clip
            clip_response = requests.get(clip_url)
            # Check response status and save the file if successful
            if clip_response.status_code == 200:
                with open(clip['id'] + ".mp4", 'wb') as file:
                    file.write(clip_response.content)

            result = convert_video_for_twitter(clip['id'] + ".mp4", clip['id'] + "-converted.mp4")
            print(result)

            existing_clips.append(clip)
            new_clips_number = new_clips_number + 1
    
    # Sort the combined list by 'created_at' in descending order
    # The newest clips will be at the top
    existing_clips.sort(key=lambda x: datetime.strptime(x['created_at'], '%Y-%m-%dT%H:%M:%SZ'), reverse=True)

    # Write the updated clips back to the file
    with open(file_path, 'w') as file:
        json.dump(existing_clips, file, indent=4)

    return new_clips_number


def post_oldest_clip():
    # Load the current clips to be posted
    with open('clipsToBePosted.json', 'r') as file:
        clips_to_be_posted = json.load(file)
    
    # Take the oldest clip (last in the list)
    oldest_clip = clips_to_be_posted.pop(-1) if clips_to_be_posted else None

    if oldest_clip:
        response = post_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, oldest_clip)

    
        if (response is False):
                response = {"error": True, "status_code": 9000, "message": "Twitter API Authentication Invalid"}
                return response, False

        if (response.status_code == 201):

            # Extract main tweet id
            response_dict = response.json()
            tweet_id = response_dict['data']['id']
            print(tweet_id)

            replyResponse = reply_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, tweet_id, oldest_clip)

            if (replyResponse is False):
                response = {"error": True, "status_code": 9000, "message": "Twitch API Authentication Failure. Check Twitch auth."}
                deleted = delete_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, tweet_id)
                return response, False

            elif (replyResponse.status_code == 201):

                os.remove(oldest_clip['id'] + '-converted.mp4')
                print(f"Deleted the original file: {oldest_clip['id'] + '-converted.mp4'}")

                # Write the updated list back to the file without the oldest clip
                with open('clipsToBePosted.json', 'w') as file:
                    json.dump(clips_to_be_posted, file, indent=4)
                
                # Load the current posted clips
                try:
                    with open('postedClips.json', 'r') as file:
                        posted_clips = json.load(file)
                except FileNotFoundError:
                    # If the file does not exist, start a new list
                    posted_clips = []

                # Append the oldest clip to the posted clips
                posted_clips.append(oldest_clip)

                # Write the updated posted clips back to the file
                with open('postedClips.json', 'w') as file:
                    json.dump(posted_clips, file, indent=4)
                
                # Return the oldest clip
                return oldest_clip, True
            
            else:
                # Handle the Twitter post error (non-201 response)
                try:
                    deleted = delete_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, tweet_id)

                    if (deleted):
                        return response, True
                    else:
                        send_error_email("Error Notification", "Something besides api authentication is broken.")
                        return response, False
                except Exception as e:
                    send_error_email("Error Notification", str(e) + "\nError at post_oldest_clip > Handle twitter non-201, non-authentication error.")
                    return response, False
        
        else:
            # Handle the Twitter post error (non-201 response and non-authentication error)
            return response, True
    else:
        # If there was no oldest clip, set a custom error response
        response = {"error": False, "status_code": 69, "message": "No Clip Found"}
        return response, True  # Return the custom error response as a tuple

def get_twitch_game(client_id, client_secret, game_id):
    # Fetch an OAuth token
    try:
        auth_response = requests.post(f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials')
        access_token = auth_response.json()['access_token']
    except Exception as e:
        send_error_email("Error Notification", str(e) + "\nError in get_twitch_game")
        return auth_response

    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }

    # Get game
    game_response = requests.get(f'https://api.twitch.tv/helix/games?id={game_id}', headers=headers)
    print(game_response.text)
    

    return game_response
    
# Get Twitch clips
def get_twitch_clips(client_id, client_secret, channel_id):
    # Fetch an OAuth token
    try:
        auth_response = requests.post(f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials')
        access_token = auth_response.json()['access_token']
    except Exception as e:
        send_error_email("Error Notification", str(e) + "\nError in get_twitch_clips")
        return auth_response, 0

    # Set time and date for clip scraping window to one week
    # To avoid timezone conflicts of accessing clips, set window to start 24 hours in the future of client timezone.
    now = datetime.now()
    now = now + timedelta(days=1)
    one_week_prior = now - timedelta(days=8)
    formatted_time_start = one_week_prior.isoformat("T") + "Z"
    formatted_time_end = now.isoformat("T") + "Z"
    #print(formatted_time_end)

    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }

    # Get clips from the past 24 hours
    clips_response = requests.get(f'https://api.twitch.tv/helix/clips?broadcaster_id={channel_id}&started_at={formatted_time_start}&ended_at={formatted_time_end}&first=100', headers=headers)

    # Insert new clips into clipsTobePosted.json
    number = append_unique_clips(clips_response.json()['data'])
    return clips_response.json()['data'], number

def post_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, oldest_clip):
    url = "https://api.twitter.com/2/tweets"

    # Set up OAuth1 authentication
    auth = OAuth1(api_key, api_secret_key, access_token, access_token_secret)

    headers = {'Content-Type': 'application/json'}

    file_path = oldest_clip['id'] + "-converted.mp4"

    # Check if the file exists before trying to upload
    if os.path.exists(file_path):
        print("File exists.")
        media_key = upload_video_chunked(api_key, api_secret_key, access_token, access_token_secret, file_path)
    else:
        print("File does not exist. Check the path.")

    if not media_key:
        print("Failed to get media key. Cannot post tweet.")
        return False  # Exit if media key is not received

    # Convert the data dictionary to a JSON string
    data_json = json.dumps({
        'text': oldest_clip['title'], 
        'media': {
            'media_ids': [media_key]
        }
    })
    print("Posting Tweet:", data_json, "\n\n")

    response = requests.post(url, data=data_json, headers=headers, auth=auth)
    print(response.text)


    return response

def reply_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, tweet_id, oldest_clip):
    url = "https://api.twitter.com/2/tweets"

    # Set up OAuth1 authentication
    auth = OAuth1(api_key, api_secret_key, access_token, access_token_secret)

    headers = {'Content-Type': 'application/json'}

    # Convert to datetime object
    timestamp_dt = datetime.strptime(oldest_clip['created_at'], "%Y-%m-%dT%H:%M:%SZ")

    # Format datetime in the new format
    formatted_date = timestamp_dt.strftime("%B %d, %Y")

    game_response = get_twitch_game(client_id, client_secret, oldest_clip['game_id'])

    try:
        game_data = game_response.json()['data']
        game_name = game_data[0]['name']
    except Exception as e:
        return False
    
    reply_payload = {
        "text": oldest_clip['url'] + "\nTitle: " + oldest_clip['title'] + "\nGame: " + game_name + "\nClipped by: " + oldest_clip['creator_name'] + "\nClipped on: " + formatted_date,
        "reply": {
            "in_reply_to_tweet_id": tweet_id
        }
    }
    

    # Convert the reply data dictionary to a JSON string
    reply_data_json = json.dumps(reply_payload)

    # Make the POST request to the Twitter API
    reply_response = requests.post(url, data=reply_data_json, headers=headers, auth=auth)
    print(reply_response.text)

    return reply_response

def delete_directly_to_twitter(api_key, api_secret_key, access_token, access_token_secret, tweet_id):
    url = f"https://api.twitter.com/2/tweets/{tweet_id}"

    # Set up OAuth1 authentication
    auth = OAuth1(api_key, api_secret_key, access_token, access_token_secret)

    # Make the DELETE request
    response = requests.delete(url, auth=auth)

    # Check if the request was successful
    if response.status_code == 200:
        print(f"Tweet with ID {tweet_id} was successfully deleted.")
        return True
    else:
        print(f"Failed to delete tweet. Status code: {response.status_code}, Response: {response.text}")
        return False




def upload_video_chunked(api_key, api_secret_key, access_token, access_token_secret, file_path):
    # Step 1: INIT
    media_id_ready_to_use = None
    init_url = 'https://upload.twitter.com/1.1/media/upload.json'
    auth = OAuth1(api_key, api_secret_key, access_token, access_token_secret)
    file_size = os.path.getsize(file_path)
    print(file_path)
    
    init_data = {
        'command': 'INIT',
        'total_bytes': file_size,
        'media_type': 'video/mp4',
        'media_category': 'tweet_video'  # Use 'amplify_video' for Ads API
    }
    init_resp = requests.post(init_url, data=init_data, auth=auth)
    media_id = init_resp.json().get('media_id_string')  # Use media_id_string for compatibility
    print(init_resp.text)


    # Step 2: APPEND
    append_url = 'https://upload.twitter.com/1.1/media/upload.json'
    segment_id = 0
    bytes_sent = 0
    with open(file_path, 'rb') as f:
        while bytes_sent < file_size:
            chunk = f.read(4*1024*1024)  # Read a chunk of the file
            append_data = {
                'command': 'APPEND',
                'media_id': media_id,
                'segment_index': segment_id
            }
            files = {
                'media': chunk
            }
            requests.post(append_url, data=append_data, files=files, auth=auth)
            segment_id += 1
            bytes_sent = f.tell()

    # Step 3: FINALIZE
    finalize_data = {
        'command': 'FINALIZE',
        'media_id': media_id
    }
    finalize_resp = requests.post(init_url, data=finalize_data, auth=auth)

    processing_info = finalize_resp.json().get('processing_info', None)
    while processing_info and processing_info.get('state') != 'succeeded':
        # If processing has not succeeded yet, enter the checking loop.
        check_after_secs = processing_info['check_after_secs'] if 'check_after_secs' in processing_info else None

        while processing_info and processing_info.get('state') != 'succeeded':
            if 'check_after_secs' in processing_info:
                time.sleep(check_after_secs)  # Wait before polling
            else:
                time.sleep(5)  # If no specific check time provided, wait for 5 seconds before retrying.

            status_resp = requests.get(init_url, params={'command': 'STATUS', 'media_id': media_id}, auth=auth)
            print(status_resp)
            processing_info = status_resp.json().get('processing_info', None)
            print(processing_info)
            check_after_secs = processing_info.get('check_after_secs') if processing_info and 'check_after_secs' in processing_info else None

    # If there's no processing_info in the response or the state is 'succeeded'
    # you can safely assume the media is ready to use.
    media_id_ready_to_use = media_id
    
    return media_id_ready_to_use  # This media_id can now be used to attach the media to a Tweet.


control = True
try:
    print("Attempting to gather clips.")
    clips, number = get_twitch_clips(client_id, client_secret, channel_id)
    print("Gathered " + str(number) + " new clips")
except Exception as e:
    now = datetime.now()
    print("[" + str(now) + "] Fatal Error:")
    print(e)
while(control):
    now = datetime.now()

    try:
        if now.hour == 0 and now.minute == 0:
            print("[" + str(now) + "] Attempting to gather clips.")
            clips, number = get_twitch_clips(client_id, client_secret, channel_id)  # Call your function
            print("Gathered " + str(number) + " new clips")
            time.sleep(60)

        elif now.minute == 0 and now.hour in [10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22]:
            print("[" + str(now) + "] Attempting to post clip.")
            oldest_clip, control = post_oldest_clip()
            print("\n")
            print(oldest_clip)
            time.sleep(60)

    except Exception as e:
        print("[" + str(now) + "] Fatal Error:")
        print(e)
        send_error_email("Error Notification", str(e) + "\nBroke in main loop of try-catch while at: " + "[" + str(now) + "]")

    print("[" + str(now) + "]" + " Waiting...")
    time.sleep(60 - now.second - (now.microsecond / 1000000.0))


# NOT USED
# def get_twitch_vod(client_id, client_secret, vod_id):
#     # Fetch an OAuth token
#     auth_response = requests.post(f'https://id.twitch.tv/oauth2/token?client_id={client_id}&client_secret={client_secret}&grant_type=client_credentials')
#     access_token = auth_response.json()['access_token']

#     headers = {
#         'Client-ID': client_id,
#         'Authorization': f'Bearer {access_token}'
#     }

#     # Get vod
#     vod_response = requests.get(f'https://api.twitch.tv/helix/videos?id={vod_id}', headers=headers)
#     print(vod_response.text)

#     # Insert new clips into clipsTobePosted.json
#     vod_data = vod_response.json()['data']
#     vod_name = vod_data[0]['title']

#     return vod_name

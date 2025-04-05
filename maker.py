import os
import re
import requests
import spotipy
import textwrap
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.parse import urlparse
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from io import BytesIO
from dotenv import load_dotenv

load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")

ALBUM_LINK = "https://open.spotify.com/album/67Evm6gPc9wFSUf1aXOrKO?si=VUOuL-qnQcymRxggAdtgdw"
OUTPUT_BASE_DIR = "images"
FONT_PATH = "C:/Users/wormy/Downloads/Roboto/Roboto-Regular.ttf"
BLUR_RADIUS = 25
TEXT_COLOR = (255, 255, 255, 220)
TEXT_PADDING = 10

try:
    client_id = SPOTIFY_CLIENT_ID
    client_secret = SPOTIFY_CLIENT_SECRET

    if not client_id or not client_secret:
        raise ValueError("SPOTIPY_CLIENT_ID or SPOTIPY_CLIENT_SECRET environment variables not set.")

    auth_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(auth_manager=auth_manager)
    print("Successfully authenticated with Spotify.")

except Exception as e:
    print(f"Error setting up Spotify authentication: {e}")
    print("Please ensure SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET environment variables are set correctly.")
    exit(1)

def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = re.sub(r'\s+', '_', name)
    name = name.strip('_ ')
    return name if name else "untitled"

def extract_album_id_from_url(url):
    try:
        parsed_url = urlparse(url)
        if parsed_url.netloc == 'open.spotify.com' and parsed_url.path.startswith('/album/'):
            album_id = parsed_url.path.split('/')[2]
            if album_id:
                return f"spotify:album:{album_id}"
    except Exception as e:
        print(f"Error parsing URL '{url}': {e}")
        return None
    print(f"Could not extract album ID from URL: {url}")
    return None

def get_best_fitting_text_and_font(draw, text, font_path, max_width, max_height, initial_font_size=120, min_font_size=10):
    font_size = initial_font_size

    # iterate downwards from initial font size
    while font_size >= min_font_size:
        try:
            # try loading the font
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            raise

        # check if single line fits
        bbox_single = draw.textbbox((0, 0), text, font=font)
        width_single = bbox_single[2] - bbox_single[0]
        height_single = bbox_single[3] - bbox_single[1]

        if width_single <= max_width and height_single <= max_height:
            return text, font # return if single line fits

        # prepare for wrapping if single line didn't fit
        char_width_bbox = draw.textbbox((0,0), "W", font=font)
        avg_char_width = char_width_bbox[2] - char_width_bbox[0]
        if avg_char_width <= 0: avg_char_width = font_size * 0.6
        wrap_width_chars = max(1, int(max_width / avg_char_width))

        # wrap text
        wrapper = textwrap.TextWrapper(
            width=wrap_width_chars,
            break_long_words=False,
            replace_whitespace=True,
            drop_whitespace=True
        )
        wrapped_lines = wrapper.wrap(text)
        wrapped_text = '\n'.join(wrapped_lines)

        # if wrapping didn't create multiple lines but was needed, skip to smaller font
        if len(wrapped_lines) <= 1 and width_single > max_width:
             font_size -= 2
             continue

        # check if wrapped text fits
        bbox_multi = draw.multiline_textbbox((0, 0), wrapped_text, font=font, align='center')
        width_multi = bbox_multi[2] - bbox_multi[0]
        height_multi = bbox_multi[3] - bbox_multi[1]

        if width_multi <= max_width and height_multi <= max_height:
            return wrapped_text, font # return wrapped text if it fits

        # if nothing fits, decrease font size and retry
        font_size -= 2

    # fallback: minimum size didn't fit, use minimum size
    print(f"Warning: Text '{text[:30]}...' might be too large. Using minimum size {min_font_size}.")
    try:
        font = ImageFont.truetype(font_path, min_font_size)
    except IOError:
        raise

    # check if single line fits at minimum size
    bbox_single = draw.textbbox((0, 0), text, font=font)
    width_single = bbox_single[2] - bbox_single[0]
    height_single = bbox_single[3] - bbox_single[1]

    if width_single <= max_width and height_single <= max_height:
         return text, font

    # wrap at minimum size as last resort
    char_width_bbox = draw.textbbox((0,0), "W", font=font)
    avg_char_width = char_width_bbox[2] - char_width_bbox[0]
    if avg_char_width <= 0: avg_char_width = min_font_size * 0.6
    wrap_width_chars = max(1, int(max_width / avg_char_width))
    wrapper = textwrap.TextWrapper(width=wrap_width_chars, break_long_words=False, replace_whitespace=True, drop_whitespace=True)
    wrapped_lines = wrapper.wrap(text)
    wrapped_text = '\n'.join(wrapped_lines)
    return wrapped_text, font

if __name__ == "__main__":
    print(f"Processing album link: {ALBUM_LINK}")

    album_uri = extract_album_id_from_url(ALBUM_LINK)

    if not album_uri:
        print("Failed to get valid Spotify album URI from the provided link.")
        exit(1)

    print(f"Extracted Album URI: {album_uri}")

    try:
        album_info = sp.album(album_uri)

        if not album_info:
            print(f"Could not retrieve album info for: {album_uri}")
            exit(1)

        album_name = album_info.get('name', 'Unknown Album')
        print(f"Found album: {album_name}")

        cover_url = None
        if album_info.get('images'):
            cover_url = album_info['images'][0]['url']

        if not cover_url:
            print(f"Could not find cover art for album: {album_name}")
            exit(1)

        tracks = []
        results = album_info['tracks']
        tracks.extend(results['items'])
        while results['next']:
            try:
                results = sp.next(results)
                if results:
                    tracks.extend(results['items'])
                else:
                    print("Warning: Reached end of track pagination or encountered an issue.")
                    break
            except Exception as page_e:
                print(f"Warning: Could not fetch next page of tracks: {page_e}")
                break

        if not tracks:
            print(f"No tracks found for album: {album_name}")
            exit(1)

        print(f"Found {len(tracks)} tracks.")

        sanitized_album_name = sanitize_filename(album_name)
        album_output_dir = os.path.join(OUTPUT_BASE_DIR, sanitized_album_name)

        try:
            os.makedirs(album_output_dir, exist_ok=True)
            print(f"Output directory: {album_output_dir}")
        except OSError as e:
            print(f"Error creating directory {album_output_dir}: {e}")
            exit(1)

        try:
            print(f"Downloading cover art from: {cover_url}")
            response = requests.get(cover_url, timeout=30)
            response.raise_for_status()
            cover_image_bytes = BytesIO(response.content)
            base_cover = Image.open(cover_image_bytes).convert("RGBA")
            print("Cover art downloaded successfully.")
        except requests.exceptions.RequestException as e:
            print(f"Error downloading cover art: {e}")
            exit(1)
        except Exception as e:
            print(f"Error opening cover image: {e}")
            exit(1)

        for i, track in enumerate(tracks):
            track_num = i + 1
            track_name = track.get('name', f'Track {track_num}')
            sanitized_track_name = sanitize_filename(track_name)
            output_filename = f"{track_num:02d}_{sanitized_track_name}.png"
            output_path = os.path.join(album_output_dir, output_filename)

            print(f"  Processing Track {track_num}: {track_name}")

            try:
                blurred_cover = base_cover.copy()
                blurred_cover = blurred_cover.filter(ImageFilter.GaussianBlur(radius=BLUR_RADIUS))

                draw = ImageDraw.Draw(blurred_cover)
                img_width, img_height = blurred_cover.size
                max_text_width = img_width - (2 * TEXT_PADDING)
                max_text_height = img_height - (2 * TEXT_PADDING)

                try:
                    final_text, font = get_best_fitting_text_and_font(
                        draw,
                        track_name,
                        FONT_PATH,
                        max_text_width,
                        max_text_height,
                        initial_font_size=300
                    )
                except IOError:
                     print(f"Error: Font file not found at '{FONT_PATH}'. Please check the path.")
                     print("Stopping script.")
                     exit(1)

                center_x = img_width / 2
                center_y = img_height / 2

                draw.multiline_text(
                    (center_x, center_y),
                    final_text,
                    font=font,
                    fill=TEXT_COLOR,
                    align='center',
                    anchor='mm'
                )

                blurred_cover.save(output_path, "PNG")

            except Exception as e:
                print(f"    Error processing track {track_num} ({track_name}): {e}")

    except spotipy.exceptions.SpotifyException as e:
        print(f"Spotify API error: {e}")
        if e.http_status == 401:
            print("Authentication error. Please check your Spotify credentials (SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET).")
        elif e.http_status == 404:
            print(f"Album not found. Please check the album link/URI: {album_uri}")
        else:
            print("An unexpected Spotify API error occurred.")
        exit(1)
    except requests.exceptions.RequestException as e:
        print(f"Network error communicating with Spotify: {e}")
        exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        exit(1)

    print("\nProcessing complete.")
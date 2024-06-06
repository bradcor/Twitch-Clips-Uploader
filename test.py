import cv2
import numpy as np

# Open the source video, edit by hand for now
cap = cv2.VideoCapture('PolishedObeseAxeNerfRedBlaster-p7rQDPX7gM96DAfE-converted.mp4')
fps = cap.get(cv2.CAP_PROP_FPS)
frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

# Calculate new dimensions
output_height = 1920
output_width = 1080

# Prepare the writer
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
out = cv2.VideoWriter('ZZZZZZZZZZZZZZZZZZ3.mp4', fourcc, fps, (output_width, output_height))

# Calculate the minimum number of frames for a 30-second duration
min_frames_for_scroll = 30 * fps

# Use the larger of the actual frame count or the 30-second minimum to calculate the scroll rate
total_frames_for_scroll = max(frame_count, min_frames_for_scroll)

# Calculate the scroll amount per frame
total_scroll_width = output_width // 2  # Maximum scroll distance
scroll_amount_per_frame = total_scroll_width / total_frames_for_scroll

# Function to apply blur
def apply_blur(quadrant):
    downscaled = cv2.pyrDown(cv2.pyrDown(cv2.pyrDown(quadrant)))
    blurred = cv2.GaussianBlur(downscaled, (21, 21), 0)
    upscaled = cv2.pyrUp(cv2.pyrUp(cv2.pyrUp(blurred)))
    final_blur = cv2.GaussianBlur(upscaled, (31, 31), 0)
    return final_blur

current_frame = 0

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    # Calculate the new size keeping the aspect ratio
    aspect_ratio = 16 / 9
    new_height = int(output_width / aspect_ratio)

    # Resize the frame to new height, maintaining aspect ratio
    resized_frame = cv2.resize(frame, (output_width, new_height), interpolation=cv2.INTER_AREA)

    # Define quadrant sizes based on the resized frame
    quadrant_width = resized_frame.shape[1] // 2
    quadrant_height = resized_frame.shape[0] // 2

    # Create a black background
    background = np.zeros((output_height, output_width, 3), dtype=np.uint8)

    # Calculate the position for the resized frame on the background (centered)
    y_offset = (output_height - new_height) // 2

    # Calculate the current scroll position for top and bottom bars
    scroll_pos_top = int(current_frame * scroll_amount_per_frame)
    scroll_pos_bottom = int(current_frame * scroll_amount_per_frame)

    # Crop the sections for the top and bottom bars with the current scroll position
    scroll_pos_top = min(scroll_pos_top, quadrant_width)
    scroll_pos_bottom = min(scroll_pos_bottom, quadrant_width)

    top_bar_section = resized_frame[0:quadrant_height, quadrant_width-scroll_pos_top:2*quadrant_width-scroll_pos_top]
    bottom_bar_section = resized_frame[quadrant_height:2*quadrant_height, scroll_pos_bottom:quadrant_width+scroll_pos_bottom]

    # Apply blur to both sections
    blurred_top_bar = apply_blur(top_bar_section)
    blurred_bottom_bar = apply_blur(bottom_bar_section)

    # Stretch the blurred sections to fill the bar areas
    blurred_top_bar_stretched = cv2.resize(blurred_top_bar, (output_width, y_offset), interpolation=cv2.INTER_AREA)
    blurred_bottom_bar_stretched = cv2.resize(blurred_bottom_bar, (output_width, y_offset), interpolation=cv2.INTER_AREA)

    # Overlay the blurred and stretched sections onto the top and bottom bar areas in the background
    background[0:y_offset, :] = blurred_top_bar_stretched
    background[output_height - y_offset:output_height, :] = blurred_bottom_bar_stretched

    # Place the resized frame in the center of the background frame
    background[y_offset:y_offset + new_height, :] = resized_frame

    # Write the frame
    out.write(background)

    # Increment the current frame
    current_frame += 1

# Release everything
cap.release()
out.release()
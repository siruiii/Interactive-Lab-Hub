import cv2
import json
import time
from escpos.printer import Usb

# --- Configuration ---
# Replace with your printer's actual VID/PID
USB_VENDOR_ID = 0x0416  # Example: 0x04b8 (Epson)
USB_PRODUCT_ID = 0x5011 # Example: 0x0202 (Epson)
JSON_FILE = 'qr_m.json'
CAMERA_INDEX = 0  # 0 usually refers to the default webcam

# NOTE: Cooldown is removed since the code will only print ONCE per unique QR code data.
# COOLDOWN_TIME = 5

def load_messages(file_path):
    """Loads the QR code -> message mapping from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"--- ERROR: JSON file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"--- ERROR: Invalid JSON format in {file_path}")
        return None

def print_message(message):
    """Initializes the printer and prints the specified message."""
    # Using plain ASCII log to prevent UnicodeEncodeError
    print(f"[PRINTER] Attempting to connect and print...")
    try:
        # 1. Connect to the USB Printer
        p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID) 

        # 2. Initialize the Printer
        p.set(align='left', font='b', height=0, width=1)
        
        # 3. Print Content
        p.text(message + "\n")
        
        # 4. Perform Partial Cut
        p.cut()
        
        print("[PRINTER] SUCCESS: Message successfully sent to the printer.")
        return True

    except Exception as e:
        # Ensure the error message 'e' is also handled safely if it contains non-ASCII characters
        error_msg = str(e).encode('ascii', 'replace').decode('ascii')
        print(f"[PRINTER] FAILURE: An error occurred during printing: {error_msg}")
        return False

def qr_code_detection_loop(messages_map):
    """
    Main loop to capture video, detect QR codes, and trigger printing.
    """
    if not messages_map:
        return

    # Use a set to store codes that have already been printed once
    printed_codes = set()

    # Initialize video capture
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print(f"--- ERROR: Could not open video stream or file at index {CAMERA_INDEX}")
        return

    # Initialize the QR code detector
    qr_detector = cv2.QRCodeDetector()
    
    # Use plain ASCII log
    print("--- STARTUP: Starting camera feed. Press 'q' to quit. ---")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("--- ERROR: Failed to grab frame.")
            break

        # Detect the QR code and decode its data
        data, bbox, rectified_image = qr_detector.detectAndDecode(frame)

        if data:
            # QR code was detected
            
            if data in messages_map:
                
                if data not in printed_codes:
                    # This is a NEW, UNPRINTED, and KNOWN QR code
                    
                    message_to_print = messages_map[data]
                    # Use plain ASCII log
                    print(f"[READ] SUCCESS: Detected new QR Code Data: {data}. Matching message found.")

                    if print_message(message_to_print):
                        # Add the code to the set only if printing was successful
                        printed_codes.add(data)
                        
                else:
                    # Code is known and was already printed
                    print(f"[READ] DETECTED: QR code '{data}' detected, but message has already been printed once.")
            
            else:
                # Code detected, but no message match in the JSON
                print(f"[READ] DETECTED: QR code '{data}' detected, but NO matching message found in JSON.")

            # Optional: Draw a bounding box around the QR code
            if bbox is not None:
                int_points = bbox[0].astype(int)
                cv2.polylines(frame, [int_points], True, (0, 255, 0), 2)
        
        else:
            # No QR code was detected in the frame
            # Log this only occasionally to prevent overwhelming the console
            # pass 

            # Optional: Log if nothing is detected
            # print("[READ] Scanning... No QR code detected in this frame.")
            pass


        # Display the resulting frame
        cv2.imshow('QR Code Detector', frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # When everything done, release the capture and destroy windows
    cap.release()
    cv2.destroyAllWindows()
    print("--- SHUTDOWN: Application closed. ---")

# --- Main execution ---
if __name__ == "__main__":
    messages_map = load_messages(JSON_FILE)
    if messages_map:
        qr_code_detection_loop(messages_map)
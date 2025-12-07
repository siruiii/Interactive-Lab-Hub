import cv2
import json
import time
from escpos.printer import Usb

# --- Configuration ---
# Replace with your printer's actual VID/PID
USB_VENDOR_ID = 0x0416  # Example: 0x04b8 (Epson)
USB_PRODUCT_ID = 0x5011 # Example: 0x0202 (Epson)
JSON_FILE = 'qr_messages.json'
CAMERA_INDEX = 0  # 0 usually refers to the default webcam

# Set a cooldown period (in seconds) to prevent immediate re-printing
COOLDOWN_TIME = 5

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
    print(f"[PRINTER] Attempting to connect and print...")
    try:
        # 1. Connect to the USB Printer
        p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID) 

        # 2. Initialize the Printer
        p.set(align='left', font='b', height=1, width=1)
        
        # 3. Print Content
        p.text("--- QR Code Message ---\n")
        p.text(message + "\n")
        p.text("-----------------------\n")
        p.text("\n\n\n\n") # Extra lines for spacing
        
        # 4. Perform Partial Cut
        p.cut()
        
        print("[PRINTER] SUCCESS: Message successfully sent to the printer.")
        return True

    except Exception as e:
        print(f"[PRINTER] FAILURE: An error occurred during printing: {e}")
        return False

def qr_code_detection_loop(messages_map):
    """
    Main loop to capture video, detect QR codes, and trigger printing.
    """
    if not messages_map:
        return

    # Initialize video capture
    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print(f"--- ERROR: Could not open video stream or file at index {CAMERA_INDEX}")
        return

    # Initialize the QR code detector
    qr_detector = cv2.QRCodeDetector()
    
    # Store the last successfully printed code and the time to enforce a cooldown
    last_printed_code = None
    last_print_time = 0
    print_cooldown_active = False

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
            current_time = time.time()
            
            # Check if the code is known and if the cooldown has passed
            if data in messages_map:
                print_cooldown_active = (current_time - last_print_time <= COOLDOWN_TIME)
                
                if data != last_printed_code or not print_cooldown_active:
                    
                    message_to_print = messages_map[data]
                    print(f"[READ] SUCCESS: Detected QR Code Data: {data}. Matching message found.")

                    if print_message(message_to_print):
                        # Update tracking only on successful print
                        last_printed_code = data
                        last_print_time = current_time
                    
                else:
                    # In cooldown period
                    print(f"[READ] DETECTED: Code '{data}' detected again, but still in cooldown period ({COOLDOWN_TIME}s).")
            
            else:
                # Code detected, but no message match in the JSON
                print(f"[READ] DETECTED: QR code '{data}' detected, but NO matching message found in JSON.")

            # Optional: Draw a bounding box around the QR code
            if bbox is not None:
                int_points = bbox[0].astype(int)
                cv2.polylines(frame, [int_points], True, (0, 255, 0), 2)
        
        else:
            # No QR code was detected in the frame
            print("[READ] Scanning... No QR code detected in this frame.")

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
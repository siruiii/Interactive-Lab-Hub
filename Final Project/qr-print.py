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
# of the same code after a successful print.
COOLDOWN_TIME = 5

def load_messages(file_path):
    """Loads the QR code -> message mapping from a JSON file."""
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"🛑 Error: JSON file not found at {file_path}")
        return None
    except json.JSONDecodeError:
        print(f"🛑 Error: Invalid JSON format in {file_path}")
        return None

def print_message(message):
    """Initializes the printer and prints the specified message."""
    print(f"🖨️ Attempting to print: '{message}'")
    try:
        # 1. Connect to the USB Printer
        p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID) 

        # 2. Initialize the Printer
        # Set alignment to left for better readability of long messages
        p.set(align='left', font='b', height=1, width=1)
        
        # 3. Print Content
        p.text("--- QR Code Message ---\n")
        p.text(message + "\n")
        p.text("-----------------------\n")
        p.text("\n\n\n\n") # Extra lines for spacing
        
        # 4. Perform Partial Cut
        p.cut()
        
        print("✅ Successfully printed receipt.")
        return True

    except Exception as e:
        print(f"❌ Printing Error: An error occurred: {e}")
        # Could not connect or print (e.g., printer offline, wrong IDs, permission issue)
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
        print(f"🛑 Error: Could not open video stream or file at index {CAMERA_INDEX}")
        return

    # Initialize the QR code detector
    qr_detector = cv2.QRCodeDetector()
    
    # Store the last successfully printed code and the time to enforce a cooldown
    last_printed_code = None
    last_print_time = 0

    print("🎥 Starting camera feed. Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("Failed to grab frame.")
            break

        # Detect the QR code and decode its data
        data, bbox, rectified_image = qr_detector.detectAndDecode(frame)

        if data:
            # A QR code was detected
            current_time = time.time()
            
            # Check if this code has a corresponding message
            if data in messages_map:
                # Check if this is a new code OR if the cooldown time has passed
                if data != last_printed_code or (current_time - last_print_time > COOLDOWN_TIME):
                    
                    message_to_print = messages_map[data]
                    print(f"🔍 Detected QR Code Data: {data}")

                    if print_message(message_to_print):
                        # Update tracking only on successful print
                        last_printed_code = data
                        last_print_time = current_time
                    
                else:
                    # In cooldown period
                    print(f"⏳ Detected code '{data}', but currently in cooldown period.")
            else:
                print(f"⚠️ Detected QR code '{data}', but no matching message found in JSON.")

            # Optionally draw a bounding box around the QR code
            if bbox is not None:
                # bbox is a numpy array of shape (1, 4, 2)
                int_points = bbox[0].astype(int)
                cv2.polylines(frame, [int_points], True, (0, 255, 0), 2)
                
        
        # Display the resulting frame
        cv2.imshow('QR Code Detector', frame)

        # Break the loop on 'q' key press
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # When everything done, release the capture and destroy windows
    cap.release()
    cv2.destroyAllWindows()
    print("Application closed.")

# --- Main execution ---
if __name__ == "__main__":
    messages_map = load_messages(JSON_FILE)
    if messages_map:
        qr_code_detection_loop(messages_map)